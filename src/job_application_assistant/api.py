from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from job_application_assistant.applications.dashboard import (
    count_sent_in_past_days,
    count_sent_today,
    filter_application_records,
    paginate_application_records,
    render_application_dashboard,
    sort_application_records,
)
from job_application_assistant.applications.store import ApplicationStore, ApplicationStoreValidationError, normalize_source_url
from job_application_assistant.codex_provider import CodexProvider, CodexProviderError
from job_application_assistant.config import AppPaths
from job_application_assistant.context.indexer import build_context, ensure_context
from job_application_assistant.drafts.pipeline import run_draft_pipeline
from job_application_assistant.drafts.job_store import DraftJobStore
from job_application_assistant.drafts.jobs import DraftJobRunner, build_job_status
from job_application_assistant.models import (
    DraftJobCreated,
    DraftJobStatus,
    DraftLookupResponse,
    DraftRequest,
    DraftResponse,
    ApplicationLookupResponse,
    ApplicationLogRequest,
    ApplicationRecord,
    ApplicationSummaryResponse,
    PdfExportResponse,
    ReindexResponse,
    RevealPdfResponse,
    StoredDraft,
)
from job_application_assistant.drafts.pdf_export import (
    PdfExportError,
    archive_cover_letter_pdf,
    export_cover_letter_pdf,
    reveal_pdf,
)
from job_application_assistant.drafts.storage import DraftStore, DraftStoreValidationError
from job_application_assistant.drafts.view import render_draft_view


def create_app() -> FastAPI:
    paths = AppPaths()
    paths.ensure_runtime()
    store = DraftStore(paths.db_path)
    store.init()
    job_store = DraftJobStore(paths.db_path)
    job_store.init()
    application_store = ApplicationStore(paths.db_path)
    application_store.init()
    job_store.fail_active("Server restarted before this draft job completed.")
    context = ensure_context(paths.portfolio_root, paths.context_dir, paths.resume_pdf_path)
    codex = CodexProvider(paths)
    runner = DraftJobRunner(
        context=context,
        codex=codex,
        draft_store=store,
        job_store=job_store,
        max_workers=paths.max_workers,
    )

    app = FastAPI(title="Job Application Assistant", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("shutdown")
    def shutdown() -> None:
        runner.shutdown()

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "project_count": len(context.projects),
            "max_workers": paths.max_workers,
        }

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard")

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(
        q: str = "",
        source: str = "",
        sent: str = "",
        limit: int = Query(500, ge=1, le=1000),
        page: int = Query(1, ge=1),
        sort: str = "applied",
        direction: str = "desc",
    ) -> HTMLResponse:
        try:
            all_records = application_store.list(limit=0)
            draft_ids_by_source_url = _draft_ids_by_source_url(store)
        except ApplicationStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DraftStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        filtered_records = filter_application_records(all_records, query=q, source=source, sent=sent)
        sorted_records = sort_application_records(filtered_records, sort=sort, direction=direction)
        paginated_records = paginate_application_records(sorted_records, page=page, page_size=limit)
        return HTMLResponse(
            render_application_dashboard(
                records=paginated_records.records,
                all_records=all_records,
                query=q,
                source=source,
                sent=sent,
                limit=limit,
                page=paginated_records.page,
                total_pages=paginated_records.total_pages,
                filtered_total=paginated_records.total_records,
                today_total=count_sent_today(all_records),
                sort=sort,
                direction=direction,
                draft_ids_by_source_url=draft_ids_by_source_url,
            )
        )

    @app.post("/context/reindex")
    def reindex() -> ReindexResponse:
        refreshed = build_context(paths.portfolio_root, paths.context_dir, paths.resume_pdf_path)
        context.profile = refreshed.profile
        context.resume = refreshed.resume
        context.offers = refreshed.offers
        context.projects = refreshed.projects
        return ReindexResponse(project_count=len(context.projects), context_dir=str(paths.context_dir))

    @app.post("/draft")
    def draft(request: DraftRequest) -> DraftResponse:
        try:
            result = run_draft_pipeline(request=request, context=context, codex=codex, store=store)
        except CodexProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        response = store.get_response(result.stored.id)
        if response is None:
            raise HTTPException(status_code=500, detail="Draft was not stored")
        return response

    @app.post("/draft-jobs", status_code=202)
    def create_draft_job(request: DraftRequest) -> DraftJobCreated:
        return runner.enqueue(request)

    @app.post("/applications")
    def log_application(request: ApplicationLogRequest) -> ApplicationRecord:
        try:
            record = application_store.log(request)
            _archive_cover_letter_for_application(record, store, paths)
            return record
        except ApplicationStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DraftStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/applications/lookup")
    def lookup_application(source_url: str = Query(..., min_length=1)) -> ApplicationLookupResponse:
        try:
            application = application_store.get_by_source_url(source_url)
        except ApplicationStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApplicationLookupResponse(matched=application is not None, application=application)

    @app.get("/applications")
    def list_applications(
        limit: int = Query(100, ge=1, le=1000),
        source: str | None = None,
    ) -> list[ApplicationRecord]:
        try:
            return application_store.list(limit=limit, source=source)
        except ApplicationStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/applications/summary")
    def application_summary(days: int = Query(1, ge=1, le=3650)) -> ApplicationSummaryResponse:
        try:
            records = application_store.list(limit=0)
        except ApplicationStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        end_date = datetime.now().astimezone().date()
        start_date = end_date - timedelta(days=days - 1)
        return ApplicationSummaryResponse(
            days=days,
            count=count_sent_in_past_days(records, days=days, today=end_date),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

    @app.get("/draft-jobs/{job_id}")
    def get_draft_job(job_id: str) -> DraftJobStatus:
        record = job_store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Draft job not found")
        try:
            return build_job_status(record, store)
        except DraftStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/drafts/lookup")
    def lookup_draft(source_url: str = Query(..., min_length=1)) -> DraftLookupResponse:
        try:
            draft = _latest_draft_response_by_source_url(store, source_url)
        except DraftStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return DraftLookupResponse(matched=draft is not None, draft=draft)

    @app.get("/drafts/{draft_id}", response_model=None)
    def get_draft(draft_id: str, request: Request, format: str = "") -> DraftResponse | HTMLResponse:
        try:
            response = store.get_response(draft_id)
        except DraftStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if response is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        if format != "json" and _prefers_html(request):
            return HTMLResponse(render_draft_view(response))
        return response

    @app.post("/drafts/{draft_id}/pdf")
    def create_pdf(draft_id: str) -> PdfExportResponse:
        try:
            stored = store.get_stored_draft(draft_id)
        except DraftStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if stored is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        try:
            return export_cover_letter_pdf(stored, paths.pdf_output_dir, paths.resume_pdf_path)
        except PdfExportError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/drafts/{draft_id}/pdf")
    def get_pdf(draft_id: str) -> FileResponse:
        try:
            stored = store.get_stored_draft(draft_id)
        except DraftStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if stored is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        try:
            exported = export_cover_letter_pdf(stored, paths.pdf_output_dir, paths.resume_pdf_path)
        except PdfExportError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return FileResponse(
            exported.pdf_path,
            media_type="application/pdf",
            filename=exported.filename,
        )

    @app.post("/drafts/{draft_id}/pdf/reveal")
    def reveal_pdf_file(draft_id: str) -> RevealPdfResponse:
        try:
            stored = store.get_stored_draft(draft_id)
        except DraftStoreValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if stored is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        try:
            exported = export_cover_letter_pdf(stored, paths.pdf_output_dir, paths.resume_pdf_path)
            opened = reveal_pdf(paths.pdf_output_dir / exported.filename, paths.pdf_output_dir)
        except PdfExportError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RevealPdfResponse(draft_id=draft_id, pdf_path=exported.pdf_path, opened=opened)

    return app


def _draft_ids_by_source_url(store: DraftStore) -> dict[str, str]:
    draft_ids = {}
    for draft in store.list_stored_drafts(skip_invalid=True):
        normalized = normalize_source_url(draft.request.opportunity_snapshot().source_url)
        if normalized and normalized not in draft_ids:
            draft_ids[normalized] = draft.id
    return draft_ids


def _archive_cover_letter_for_application(record: ApplicationRecord, store: DraftStore, paths: AppPaths) -> None:
    stored = _stored_draft_for_application(record, store)
    if stored is None:
        return
    archive_cover_letter_pdf(stored, paths.pdf_output_dir, paths.pdf_archive_dir)


def _stored_draft_for_application(record: ApplicationRecord, store: DraftStore) -> StoredDraft | None:
    if record.draft_id:
        return store.get_stored_draft(record.draft_id)

    normalized_source_url = normalize_source_url(record.source_url)
    if not normalized_source_url:
        return None

    for draft in store.list_stored_drafts(skip_invalid=True):
        draft_source_url = normalize_source_url(draft.request.opportunity_snapshot().source_url)
        if draft_source_url == normalized_source_url:
            return draft
    return None


def _latest_draft_response_by_source_url(store: DraftStore, source_url: str) -> DraftResponse | None:
    normalized_source_url = normalize_source_url(source_url)
    if not normalized_source_url:
        return None
    for draft in store.list_stored_drafts(skip_invalid=True):
        draft_source_url = normalize_source_url(draft.request.opportunity_snapshot().source_url)
        if draft_source_url == normalized_source_url:
            response = store.get_response(draft.id)
            if response is not None:
                return response
    return None


def _prefers_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept

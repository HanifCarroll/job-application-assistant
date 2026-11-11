from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import logging

from job_application_assistant.codex_provider import CodexProvider
from job_application_assistant.drafts.pipeline import run_draft_pipeline
from job_application_assistant.drafts.job_store import DraftJobRecord, DraftJobStore
from job_application_assistant.models import (
    CodexRunTiming,
    ContextBundle,
    DraftJobCreated,
    DraftJobStage,
    DraftJobStatus,
    DraftRequest,
    StageTiming,
)
from job_application_assistant.drafts.storage import DraftStore


logger = logging.getLogger(__name__)


class DraftJobRunner:
    def __init__(
        self,
        context: ContextBundle,
        codex: CodexProvider,
        draft_store: DraftStore,
        job_store: DraftJobStore,
        max_workers: int,
    ) -> None:
        self.context = context
        self.codex = codex
        self.draft_store = draft_store
        self.job_store = job_store
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job-application-draft")

    def enqueue(self, request: DraftRequest) -> DraftJobCreated:
        job = self.job_store.create(request)
        self._executor.submit(self._run, job.id, request)
        return job

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job_id: str, request: DraftRequest) -> None:
        try:
            result = run_draft_pipeline(
                request=request,
                context=self.context,
                codex=self.codex,
                store=self.draft_store,
                on_stage=lambda stage: self._record_stage(job_id, stage),
                on_stage_timing=lambda stage, timing: self._record_stage_timing(job_id, stage, timing),
                on_codex_timing=lambda timing: self._record_codex_timing(job_id, timing),
            )
            self.job_store.complete(job_id, result.stored.id)
        except Exception as exc:
            logger.exception("Draft job failed: %s", job_id)
            self.job_store.fail(job_id, str(exc) or exc.__class__.__name__)

    def _record_stage(self, job_id: str, stage: DraftJobStage) -> None:
        self.job_store.update_stage(job_id, stage)

    def _record_stage_timing(self, job_id: str, stage: DraftJobStage, timing: StageTiming) -> None:
        self.job_store.record_stage_timing(job_id, stage, timing)

    def _record_codex_timing(self, job_id: str, timing: CodexRunTiming) -> None:
        self.job_store.record_codex_timing(job_id, timing)


def build_job_status(record: DraftJobRecord, draft_store: DraftStore) -> DraftJobStatus:
    result = draft_store.get_response(record.result_draft_id) if record.result_draft_id is not None else None
    selected_angle = result.selected_angle.label if result is not None else ""
    selected_projects = result.selected_projects if result is not None else []
    return DraftJobStatus(
        id=record.id,
        status=record.status,
        stage=record.stage,
        elapsed_seconds=_elapsed_seconds(record.created_at),
        selected_angle=selected_angle,
        selected_projects=selected_projects,
        result=result,
        error=record.error,
        timings=record.timings,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _elapsed_seconds(created_at: str) -> float:
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return 0.0
    return max(0.0, (datetime.now(UTC) - created).total_seconds())

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import cast
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from pydantic import ValidationError

from job_application_assistant.models import (
    ApplicationDetectedBy,
    ApplicationLogRequest,
    ApplicationRecord,
    ApplicationStatus,
    OpportunitySnapshot,
)


EXPECTED_APPLICATION_COLUMNS = {
    "id",
    "status",
    "applied_at",
    "source",
    "source_url",
    "normalized_source_url",
    "title",
    "company",
    "location",
    "draft_id",
    "draft_job_id",
    "opportunity_json",
    "detected_by",
    "warnings_json",
    "created_at",
    "updated_at",
}


class ApplicationStoreValidationError(Exception):
    pass


class ApplicationStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            columns = self._table_columns(conn, "applications")
            if columns and columns != EXPECTED_APPLICATION_COLUMNS:
                raise ApplicationStoreValidationError(
                    "Existing applications table does not match the current schema. Export it before migrating."
                )
            conn.execute(
                """
                create table if not exists applications (
                    id text primary key,
                    status text not null,
                    applied_at text not null,
                    source text not null,
                    source_url text not null,
                    normalized_source_url text unique,
                    title text not null,
                    company text not null,
                    location text not null,
                    draft_id text not null,
                    draft_job_id text not null,
                    opportunity_json text not null,
                    detected_by text not null,
                    warnings_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute("create index if not exists idx_applications_applied_at on applications (applied_at)")
            conn.execute("create index if not exists idx_applications_source on applications (source)")

    def log(self, request: ApplicationLogRequest) -> ApplicationRecord:
        now = utc_now_iso()
        normalized_source_url = normalize_source_url(request.opportunity.source_url)
        with self._connect() as conn:
            existing = None
            if normalized_source_url:
                existing = conn.execute(
                    "select * from applications where normalized_source_url = ?",
                    (normalized_source_url,),
                ).fetchone()

            if existing is None:
                application_id = uuid4().hex
                conn.execute(
                    """
                    insert into applications (
                        id,
                        status,
                        applied_at,
                        source,
                        source_url,
                        normalized_source_url,
                        title,
                        company,
                        location,
                        draft_id,
                        draft_job_id,
                        opportunity_json,
                        detected_by,
                        warnings_json,
                        created_at,
                        updated_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        application_id,
                        request.status,
                        request.applied_at,
                        request.opportunity.source,
                        request.opportunity.source_url,
                        normalized_source_url or None,
                        request.opportunity.title,
                        request.opportunity.company,
                        request.opportunity.location,
                        request.draft_id,
                        request.draft_job_id,
                        request.opportunity.model_dump_json(),
                        request.detected_by,
                        json.dumps(request.warnings),
                        now,
                        now,
                    ),
                )
                row = conn.execute("select * from applications where id = ?", (application_id,)).fetchone()
            else:
                updated = _merge_application(existing, request, normalized_source_url, now)
                conn.execute(
                    """
                    update applications
                    set status = ?,
                        applied_at = ?,
                        source = ?,
                        source_url = ?,
                        normalized_source_url = ?,
                        title = ?,
                        company = ?,
                        location = ?,
                        draft_id = ?,
                        draft_job_id = ?,
                        opportunity_json = ?,
                        detected_by = ?,
                        warnings_json = ?,
                        updated_at = ?
                    where id = ?
                    """,
                    (
                        updated.status,
                        updated.applied_at,
                        updated.source,
                        updated.source_url,
                        updated.normalized_source_url or None,
                        updated.title,
                        updated.company,
                        updated.location,
                        updated.draft_id,
                        updated.draft_job_id,
                        updated.opportunity.model_dump_json(),
                        updated.detected_by,
                        json.dumps(updated.warnings),
                        updated.updated_at,
                        updated.id,
                    ),
                )
                row = conn.execute("select * from applications where id = ?", (updated.id,)).fetchone()
        if row is None:
            raise ApplicationStoreValidationError("Application row was not stored")
        return self._record_from_row(row)

    def list(self, *, limit: int = 100, source: str | None = None) -> list[ApplicationRecord]:
        params: list[object] = []
        where = ""
        if source:
            where = "where source = ?"
            params.append(source)
        limit_clause = ""
        if limit > 0:
            limit_clause = "limit ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select * from applications
                {where}
                order by applied_at desc, created_at desc, title asc
                {limit_clause}
                """,
                params,
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def get_by_source_url(self, source_url: str) -> ApplicationRecord | None:
        normalized_source_url = normalize_source_url(source_url)
        if not normalized_source_url:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "select * from applications where normalized_source_url = ?",
                (normalized_source_url,),
            ).fetchone()
        return self._record_from_row(row) if row is not None else None

    def _record_from_row(self, row: sqlite3.Row) -> ApplicationRecord:
        try:
            opportunity = OpportunitySnapshot.model_validate_json(str(row["opportunity_json"]))
        except ValidationError as exc:
            raise ApplicationStoreValidationError(f"Stored application {row['id']} has invalid opportunity JSON") from exc
        try:
            warnings = json.loads(str(row["warnings_json"]))
        except json.JSONDecodeError as exc:
            raise ApplicationStoreValidationError(f"Stored application {row['id']} has invalid warnings JSON") from exc
        if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
            raise ApplicationStoreValidationError(f"Stored application {row['id']} has invalid warnings JSON")
        return ApplicationRecord(
            id=str(row["id"]),
            status=cast(ApplicationStatus, str(row["status"])),
            applied_at=str(row["applied_at"]),
            source=str(row["source"]),
            source_url=str(row["source_url"]),
            normalized_source_url=str(row["normalized_source_url"] or ""),
            title=str(row["title"]),
            company=str(row["company"]),
            location=str(row["location"]),
            draft_id=str(row["draft_id"]),
            draft_job_id=str(row["draft_job_id"]),
            opportunity=opportunity,
            detected_by=cast(ApplicationDetectedBy, str(row["detected_by"])),
            warnings=warnings,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"pragma table_info({table})").fetchall()
        return {str(row["name"]) for row in rows}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def normalize_source_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw.split("#", 1)[0].rstrip("/")
    if not parsed.scheme or not parsed.netloc:
        return raw.split("#", 1)[0].rstrip("/")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _merge_application(
    existing: sqlite3.Row,
    request: ApplicationLogRequest,
    normalized_source_url: str,
    updated_at: str,
) -> ApplicationRecord:
    opportunity = request.opportunity
    return ApplicationRecord(
        id=str(existing["id"]),
        status=request.status,
        applied_at=str(existing["applied_at"]) or request.applied_at,
        source=_prefer(opportunity.source, str(existing["source"])),
        source_url=_prefer(opportunity.source_url, str(existing["source_url"])),
        normalized_source_url=normalized_source_url,
        title=_prefer(opportunity.title, str(existing["title"])),
        company=_prefer(opportunity.company, str(existing["company"])),
        location=_prefer(opportunity.location, str(existing["location"])),
        draft_id=_prefer(request.draft_id, str(existing["draft_id"])),
        draft_job_id=_prefer(request.draft_job_id, str(existing["draft_job_id"])),
        opportunity=opportunity,
        detected_by=request.detected_by,
        warnings=request.warnings,
        created_at=str(existing["created_at"]),
        updated_at=updated_at,
    )


def _prefer(next_value: str, existing_value: str) -> str:
    return next_value if next_value else existing_value

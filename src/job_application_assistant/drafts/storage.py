from __future__ import annotations

from pathlib import Path
import sqlite3

from pydantic import ValidationError

from job_application_assistant.models import DraftRequest, DraftResponse, DraftResult, StoredDraft


EXPECTED_DRAFT_COLUMNS = {"id", "created_at", "request_json", "draft_json"}


class DraftStoreValidationError(Exception):
    pass


class DraftStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if self._table_columns(conn, "drafts") not in (set(), EXPECTED_DRAFT_COLUMNS):
                conn.execute("drop table drafts")
            conn.execute(
                """
                create table if not exists drafts (
                    id text primary key,
                    created_at text not null,
                    request_json text not null,
                    draft_json text not null
                )
                """
            )

    def insert(self, draft: StoredDraft) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into drafts (id, created_at, request_json, draft_json)
                values (?, ?, ?, ?)
                """,
                (
                    draft.id,
                    draft.created_at,
                    draft.request.model_dump_json(),
                    draft.draft.model_dump_json(),
                ),
            )

    def get_response(self, draft_id: str) -> DraftResponse | None:
        with self._connect() as conn:
            row = conn.execute(
                "select id, created_at, draft_json from drafts where id = ?",
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            draft = DraftResult.model_validate_json(str(row["draft_json"]))
        except ValidationError as exc:
            raise DraftStoreValidationError(_invalid_draft_message(str(row["id"]))) from exc
        return DraftResponse(
            **draft.model_dump(),
            id=str(row["id"]),
            created_at=str(row["created_at"]),
        )

    def get_stored_draft(self, draft_id: str) -> StoredDraft | None:
        with self._connect() as conn:
            row = conn.execute(
                "select id, created_at, request_json, draft_json from drafts where id = ?",
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            return StoredDraft(
                id=str(row["id"]),
                created_at=str(row["created_at"]),
                request=DraftRequest.model_validate_json(str(row["request_json"])),
                draft=DraftResult.model_validate_json(str(row["draft_json"])),
            )
        except ValidationError as exc:
            raise DraftStoreValidationError(_invalid_draft_message(str(row["id"]))) from exc

    def list_stored_drafts(self, *, skip_invalid: bool = False) -> list[StoredDraft]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select id, created_at, request_json, draft_json
                from drafts
                order by created_at desc
                """
            ).fetchall()
        drafts = []
        for row in rows:
            try:
                drafts.append(
                    StoredDraft(
                        id=str(row["id"]),
                        created_at=str(row["created_at"]),
                        request=DraftRequest.model_validate_json(str(row["request_json"])),
                        draft=DraftResult.model_validate_json(str(row["draft_json"])),
                    )
                )
            except ValidationError as exc:
                if skip_invalid:
                    continue
                raise DraftStoreValidationError(_invalid_draft_message(str(row["id"]))) from exc
        return drafts

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"pragma table_info({table})").fetchall()
        return {str(row["name"]) for row in rows}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def make_stored_draft(
    request: DraftRequest,
    draft: dict[str, object],
) -> StoredDraft:
    return StoredDraft(request=request, draft=DraftResult.model_validate(draft))


def _invalid_draft_message(draft_id: str) -> str:
    return f"Stored draft {draft_id} no longer matches the current draft schema. Regenerate the draft before exporting it."

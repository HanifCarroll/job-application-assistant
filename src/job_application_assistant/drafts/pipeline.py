from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Iterator

from job_application_assistant.codex_provider import CodexProvider
from job_application_assistant.models import (
    CodexRunTiming,
    ContextBundle,
    DraftJobStage,
    DraftRequest,
    StageTiming,
    StoredDraft,
)
from job_application_assistant.drafts.prompts import build_draft_prompt
from job_application_assistant.drafts.storage import DraftStore, make_stored_draft


StageCallback = Callable[[DraftJobStage], None]
StageTimingCallback = Callable[[DraftJobStage, StageTiming], None]
CodexTimingCallback = Callable[[CodexRunTiming], None]


@dataclass(frozen=True)
class DraftPipelineResult:
    stored: StoredDraft


def run_draft_pipeline(
    request: DraftRequest,
    context: ContextBundle,
    codex: CodexProvider,
    store: DraftStore,
    on_stage: StageCallback | None = None,
    on_stage_timing: StageTimingCallback | None = None,
    on_codex_timing: CodexTimingCallback | None = None,
) -> DraftPipelineResult:
    with _timed_stage("codex_draft", on_stage, on_stage_timing):
        draft = codex.generate(
            build_draft_prompt(request, context),
            phase="draft",
            on_timing=on_codex_timing,
        )

    with _timed_stage("saving", on_stage, on_stage_timing):
        stored = make_stored_draft(request, draft)
        store.insert(stored)
    return DraftPipelineResult(stored=stored)


def _notify(callback: StageCallback | None, stage: DraftJobStage) -> None:
    if callback is not None:
        callback(stage)


@contextmanager
def _timed_stage(
    stage: DraftJobStage,
    on_stage: StageCallback | None,
    on_stage_timing: StageTimingCallback | None,
) -> Iterator[None]:
    _notify(on_stage, stage)
    started_at = _utc_now_iso()
    started = perf_counter()
    try:
        yield
    finally:
        if on_stage_timing is not None:
            on_stage_timing(
                stage,
                StageTiming(
                    started_at=started_at,
                    finished_at=_utc_now_iso(),
                    duration_ms=round((perf_counter() - started) * 1000),
                ),
            )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()

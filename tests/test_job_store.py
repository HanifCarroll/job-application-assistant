from __future__ import annotations

from pathlib import Path

from job_application_assistant.drafts.job_store import DraftJobStore
from job_application_assistant.drafts.jobs import build_job_status
from job_application_assistant.models import CodexRunTiming, DraftRequest, StageTiming, UpworkProject
from job_application_assistant.drafts.storage import DraftStore, make_stored_draft


def test_job_store_tracks_completion_and_draft_audit(tmp_path: Path) -> None:
    db_path = tmp_path / "drafts.db"
    draft_store = DraftStore(db_path)
    draft_store.init()
    job_store = DraftJobStore(db_path)
    job_store.init()
    request = DraftRequest(project=UpworkProject(title="Build a SaaS workflow"))
    final: dict[str, object] = {
        "draft_text": "I would stabilize the riskiest workflow first.",
        "draft_type": "cover_letter",
        "subject_line": "",
        "selected_angle": {
            "key": "saas",
            "label": "SaaS",
            "promise": "Stabilize SaaS",
            "caused_by": ["offer.saas"],
        },
        "role_classification": "SaaS workflow stabilization",
        "application_strategy": "Lead with production stabilization proof.",
        "selected_projects": ["genrupt"],
        "rejected_projects": [],
        "decisions": [],
        "claims": [],
        "warnings": [],
    }

    job = job_store.create(request)
    job_store.update_stage(job.id, "codex_draft")
    job_store.record_stage_timing(
        job.id,
        "codex_draft",
        StageTiming(
            started_at="2026-01-01T00:00:00.100000+00:00",
            finished_at="2026-01-01T00:00:01.600000+00:00",
            duration_ms=1500,
        ),
    )
    job_store.record_codex_timing(
        job.id,
        CodexRunTiming(
            phase="draft",
            started_at="2026-01-01T00:00:00.100000+00:00",
            finished_at="2026-01-01T00:00:01.600000+00:00",
            duration_ms=1500,
            return_code=0,
            prompt_chars=1200,
            stdout_bytes=50,
            stderr_bytes=10,
            output_bytes=600,
            parse_duration_ms=2,
        ),
    )
    draft = make_stored_draft(request, final)
    draft_store.insert(draft)
    job_store.complete(job.id, draft.id)

    record = job_store.get(job.id)

    assert record is not None
    status = build_job_status(record, draft_store)
    assert status.status == "succeeded"
    assert status.stage == "done"
    assert status.selected_angle == "SaaS"
    assert status.selected_projects == ["genrupt"]
    assert status.result is not None
    assert status.result.draft_text == "I would stabilize the riskiest workflow first."
    assert status.timings.stages["codex_draft"].duration_ms == 1500
    assert status.timings.queue_ms == 0
    assert status.timings.codex_runs[0].phase == "draft"
    assert status.timings.codex_runs[0].duration_ms == 1500


def test_fail_active_marks_stale_jobs_failed(tmp_path: Path) -> None:
    job_store = DraftJobStore(tmp_path / "drafts.db")
    job_store.init()
    job = job_store.create(DraftRequest(project=UpworkProject(title="Job")))
    job_store.update_stage(job.id, "codex_draft")

    job_store.fail_active("Server restarted.")
    record = job_store.get(job.id)

    assert record is not None
    assert record.status == "failed"
    assert record.stage == "failed"
    assert record.error == "Server restarted."

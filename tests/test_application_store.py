from __future__ import annotations

from pathlib import Path

from job_application_assistant.applications.store import ApplicationStore, normalize_source_url
from job_application_assistant.models import ApplicationLogRequest, OpportunitySnapshot


def test_normalize_source_url_removes_fragment_and_trailing_slash() -> None:
    assert normalize_source_url("https://Example.com/jobs/123/#details") == "https://example.com/jobs/123"


def test_application_store_upserts_by_normalized_source_url(tmp_path: Path) -> None:
    store = ApplicationStore(tmp_path / "drafts.db")
    store.init()
    first = store.log(
        ApplicationLogRequest(
            opportunity=OpportunitySnapshot(
                source="indeed",
                source_url="https://www.indeed.com/jobs/123/#start",
                title="Software Engineer",
                company="Acme",
            ),
            applied_at="2026-06-17T00:00:00+00:00",
            detected_by="csv_import",
        )
    )

    second = store.log(
        ApplicationLogRequest(
            opportunity=OpportunitySnapshot(
                source="indeed",
                source_url="https://www.indeed.com/jobs/123/",
                title="Senior Software Engineer",
                company="Acme Inc",
                location="Remote",
            ),
            draft_id="draft-1",
            draft_job_id="job-1",
            detected_by="manual",
        )
    )

    records = store.list(limit=10)
    assert len(records) == 1
    assert second.id == first.id
    assert second.applied_at == "2026-06-17T00:00:00+00:00"
    assert second.title == "Senior Software Engineer"
    assert second.company == "Acme Inc"
    assert second.location == "Remote"
    assert second.draft_id == "draft-1"
    assert second.draft_job_id == "job-1"
    assert records[0].id == first.id


def test_application_store_gets_record_by_normalized_source_url(tmp_path: Path) -> None:
    store = ApplicationStore(tmp_path / "drafts.db")
    store.init()
    stored = store.log(
        ApplicationLogRequest(
            opportunity=OpportunitySnapshot(
                source="dice",
                source_url="https://www.dice.com/job-detail/abc123?x=1#apply",
                title="Software Engineer",
                company="Acme",
            ),
            detected_by="platform_confirmation",
        )
    )

    matched = store.get_by_source_url("https://www.dice.com/job-detail/abc123?x=1")

    assert matched is not None
    assert matched.id == stored.id
    assert matched.detected_by == "platform_confirmation"
    assert store.get_by_source_url("") is None

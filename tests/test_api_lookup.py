from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from pathlib import Path
from typing import Self

import pytest
from fastapi.testclient import TestClient

import job_application_assistant.api as api
from job_application_assistant.config import AppPaths


def test_lookup_misses_return_200_with_unmatched_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = AppPaths(
        context_dir=tmp_path / "context",
        runtime_dir=tmp_path / "runtime",
        db_path=tmp_path / "drafts.db",
        codex_runs_dir=tmp_path / "codex-runs",
        pdf_output_dir=tmp_path / "cover-letters",
        pdf_archive_dir=tmp_path / "cover-letters" / "archive",
    )
    monkeypatch.setattr(api, "AppPaths", lambda: paths)
    client = TestClient(api.create_app())

    application = client.get(
        "/applications/lookup",
        params={"source_url": "https://www.dice.com/job-detail/missing"},
    )
    draft = client.get(
        "/drafts/lookup",
        params={"source_url": "https://www.dice.com/job-detail/missing"},
    )

    assert application.status_code == 200
    assert application.json() == {"matched": False, "application": None}
    assert draft.status_code == 200
    assert draft.json() == {"matched": False, "draft": None}


def test_application_summary_counts_recent_local_day_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            value = cls(2026, 6, 26, 12, 0, tzinfo=UTC)
            if tz is None:
                return value
            return cls.fromtimestamp(value.timestamp(), tz)

    paths = AppPaths(
        context_dir=tmp_path / "context",
        runtime_dir=tmp_path / "runtime",
        db_path=tmp_path / "drafts.db",
        codex_runs_dir=tmp_path / "codex-runs",
        pdf_output_dir=tmp_path / "cover-letters",
        pdf_archive_dir=tmp_path / "cover-letters" / "archive",
    )
    monkeypatch.setattr(api, "AppPaths", lambda: paths)
    monkeypatch.setattr(api, "datetime", FixedDateTime)
    client = TestClient(api.create_app())

    for source_url, applied_at in [
        ("https://www.dice.com/job-detail/today", "2026-06-26T15:00:00+00:00"),
        ("https://www.dice.com/job-detail/recent", "2026-06-24T15:00:00+00:00"),
        ("https://www.dice.com/job-detail/old", "2026-06-23T15:00:00+00:00"),
    ]:
        response = client.post(
            "/applications",
            json={
                "opportunity": {
                    "source": "dice",
                    "source_url": source_url,
                    "title": "Software Engineer",
                    "company": "Acme",
                },
                "applied_at": applied_at,
                "detected_by": "manual",
            },
        )
        assert response.status_code == 200

    today = client.get("/applications/summary")
    recent = client.get("/applications/summary", params={"days": 3})

    assert today.status_code == 200
    assert today.json() == {
        "days": 1,
        "count": 1,
        "start_date": "2026-06-26",
        "end_date": "2026-06-26",
    }
    assert recent.status_code == 200
    assert recent.json() == {
        "days": 3,
        "count": 2,
        "start_date": "2026-06-24",
        "end_date": "2026-06-26",
    }

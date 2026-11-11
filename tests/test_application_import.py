from __future__ import annotations

from pathlib import Path

from job_application_assistant.applications.importer import import_applications_csv, read_application_csv
from job_application_assistant.applications.store import ApplicationStore


def test_read_application_csv_maps_numbers_export(tmp_path: Path) -> None:
    csv_path = tmp_path / "Job Search.csv"
    csv_path.write_text(
        "\ufeffRole;Company;Link;Date Sent\n"
        "AI Product Engineer;Employ;https://www.linkedin.com/jobs/view/4424614012;17/06/2026\n",
        encoding="utf-8",
    )

    [request] = read_application_csv(csv_path)

    assert request.opportunity.title == "AI Product Engineer"
    assert request.opportunity.company == "Employ"
    assert request.opportunity.source == "linkedin"
    assert request.opportunity.source_url == "https://www.linkedin.com/jobs/view/4424614012"
    assert request.applied_at == "2026-06-17T00:00:00+00:00"
    assert request.detected_by == "csv_import"


def test_import_applications_csv_persists_unique_applications(tmp_path: Path) -> None:
    csv_path = tmp_path / "Job Search.csv"
    csv_path.write_text(
        "Role;Company;Link;Date Sent\n"
        "Software Engineer;Acme;https://example.com/jobs/1;17/06/2026\n"
        "Software Engineer;Acme;https://example.com/jobs/1#details;17/06/2026\n",
        encoding="utf-8",
    )
    store = ApplicationStore(tmp_path / "drafts.db")
    store.init()

    result = import_applications_csv(csv_path, store)

    assert result.row_count == 2
    assert result.application_count == 1
    assert len(store.list(limit=10)) == 1

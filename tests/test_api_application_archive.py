from __future__ import annotations

from pathlib import Path

from job_application_assistant.api import _archive_cover_letter_for_application
from job_application_assistant.applications.store import ApplicationStore
from job_application_assistant.config import AppPaths
from job_application_assistant.drafts.pdf_export import cover_letter_pdf_path
from job_application_assistant.drafts.storage import DraftStore, make_stored_draft
from job_application_assistant.models import ApplicationLogRequest, DraftRequest, OpportunitySnapshot


def test_archive_cover_letter_for_application_moves_pdf_for_record_draft(tmp_path: Path) -> None:
    db_path = tmp_path / "drafts.db"
    draft_store = DraftStore(db_path)
    draft_store.init()
    application_store = ApplicationStore(db_path)
    application_store.init()
    output_dir = tmp_path / "cover-letters"
    archive_dir = output_dir / "archive"
    stored = make_stored_draft(
        DraftRequest(
            opportunity=OpportunitySnapshot(
                source="dice",
                source_url="https://www.dice.com/job-detail/abc123",
                title="Software Engineer",
                company="Acme Systems",
            )
        ),
        _draft_payload("Draft body."),
    )
    draft_store.insert(stored)
    output_dir.mkdir()
    active_path = cover_letter_pdf_path(stored, output_dir)
    active_path.write_bytes(b"%PDF-1.4\n")
    record = application_store.log(
        ApplicationLogRequest(
            opportunity=stored.request.opportunity_snapshot(),
            draft_id=stored.id,
            detected_by="platform_confirmation",
        )
    )

    _archive_cover_letter_for_application(
        record,
        draft_store,
        AppPaths(pdf_output_dir=output_dir, pdf_archive_dir=archive_dir),
    )

    archived_path = archive_dir / f"Hanif-Carroll-Cover-Letter-Acme-Systems-{stored.id[:8]}.pdf"
    assert archived_path.read_bytes() == b"%PDF-1.4\n"
    assert not active_path.exists()


def test_archive_cover_letter_for_application_matches_record_without_draft_id_by_source_url(tmp_path: Path) -> None:
    db_path = tmp_path / "drafts.db"
    draft_store = DraftStore(db_path)
    draft_store.init()
    application_store = ApplicationStore(db_path)
    application_store.init()
    output_dir = tmp_path / "cover-letters"
    archive_dir = output_dir / "archive"
    stored = make_stored_draft(
        DraftRequest(
            opportunity=OpportunitySnapshot(
                source="dice",
                source_url="https://www.dice.com/job-detail/abc123/",
                title="Software Engineer",
                company="Acme Systems",
            )
        ),
        _draft_payload("Draft body."),
    )
    draft_store.insert(stored)
    output_dir.mkdir()
    active_path = cover_letter_pdf_path(stored, output_dir)
    active_path.write_bytes(b"%PDF-1.4\n")
    record = application_store.log(
        ApplicationLogRequest(
            opportunity=OpportunitySnapshot(
                source="dice",
                source_url="https://www.dice.com/job-detail/abc123#submitted",
                title="Software Engineer",
                company="Acme Systems",
            ),
            detected_by="platform_confirmation",
        )
    )

    _archive_cover_letter_for_application(
        record,
        draft_store,
        AppPaths(pdf_output_dir=output_dir, pdf_archive_dir=archive_dir),
    )

    archived_path = archive_dir / f"Hanif-Carroll-Cover-Letter-Acme-Systems-{stored.id[:8]}.pdf"
    assert archived_path.read_bytes() == b"%PDF-1.4\n"
    assert not active_path.exists()


def _draft_payload(text: str) -> dict[str, object]:
    return {
        "draft_text": text,
        "draft_type": "cover_letter",
        "subject_line": "",
        "selected_angle": {
            "key": "saas",
            "label": "SaaS",
            "promise": "Build reliable software",
            "caused_by": ["offer.saas"],
        },
        "role_classification": "software engineering",
        "application_strategy": "Connect product engineering experience to the role.",
        "selected_projects": [],
        "rejected_projects": [],
        "decisions": [],
        "claims": [],
        "warnings": [],
    }

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from job_application_assistant.models import DraftRequest, OpportunitySnapshot
from job_application_assistant.drafts.pdf_export import (
    PdfExportError,
    archive_cover_letter_pdf,
    export_cover_letter_pdf,
    extract_resume_header,
    reveal_pdf,
)
from job_application_assistant.drafts.storage import make_stored_draft


def test_resume_header_uses_resume_contact_line_without_phone(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.pdf"
    _write_resume_pdf(
        resume_path,
        [
            "Hanif Carroll",
            "Product Engineer | Builds AI products end to end",
            "U.S. citizen - works U.S. hours",
            "hanif@example.com | 555-123-4567 | linkedin.com/in/hanifcarroll | github.com/hanifcarroll",
        ],
    )

    header = extract_resume_header(resume_path)

    assert header.name == "Hanif Carroll"
    assert header.headline == "Product Engineer | Builds AI products end to end"
    assert "hanif@example.com" in header.contacts
    assert "linkedin.com/in/hanifcarroll" in header.contacts
    assert "github.com/hanifcarroll" in header.contacts
    assert "555-123-4567" not in header.contacts
    assert header.warnings == []


def test_export_cover_letter_pdf_contains_letterhead_and_draft(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.pdf"
    output_dir = tmp_path / "letters"
    _write_resume_pdf(
        resume_path,
        [
            "Hanif Carroll",
            "Product Engineer | Builds AI products end to end",
            "hanif@example.com | 555-123-4567 | linkedin.com/in/hanifcarroll | hanifcarroll.com",
        ],
    )
    stored = make_stored_draft(
        DraftRequest(
            opportunity=OpportunitySnapshot(
                source="dice",
                title="Software Engineer",
                company="Acme Systems",
            )
        ),
        {
            "draft_text": "Dear Hiring Team,\n\nI can help build this service carefully.\n\nBest,\nHanif",
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
        },
    )

    exported = export_cover_letter_pdf(stored, output_dir, resume_path)

    assert Path(exported.pdf_path).is_file()
    assert exported.filename == "Hanif-Carroll-Cover-Letter-Acme-Systems.pdf"
    text = _pdf_text(Path(exported.pdf_path))
    assert "Hanif Carroll" in text
    assert "hanif@example.com" in text
    assert "555-123-4567" not in text
    assert "Acme Systems" in text
    assert "Re: Software Engineer" in text
    assert "I can help build this service carefully." in text
    assert "Best,\nHanif Carroll" in text
    assert "Best,\nHanif\n" not in text
    assert set(_pdf_uris(Path(exported.pdf_path))) == {
        "mailto:hanif@example.com",
        "https://linkedin.com/in/hanifcarroll",
        "https://hanifcarroll.com",
    }


def test_export_cover_letter_pdf_filename_uses_company_without_full_role_title(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.pdf"
    output_dir = tmp_path / "letters"
    _write_resume_pdf(
        resume_path,
        [
            "Hanif Carroll",
            "Product Engineer",
            "hanif@example.com | hanifcarroll.com",
        ],
    )
    stored = make_stored_draft(
        DraftRequest(
            opportunity=OpportunitySnapshot(
                title="*Senior Fullstack Engineer (Nodejs, Javascript, AWS exp.) - W2 role",
                company="Kellton",
            )
        ),
        _draft_payload("Draft body."),
    )

    exported = export_cover_letter_pdf(stored, output_dir, resume_path)

    assert exported.filename == "Hanif-Carroll-Cover-Letter-Kellton.pdf"
    assert "Senior-Fullstack-Engineer" not in exported.filename
    assert "Nodejs" not in exported.filename
    assert "W2" not in exported.filename


def test_export_cover_letter_pdf_overwrites_same_company_filename(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.pdf"
    output_dir = tmp_path / "letters"
    _write_resume_pdf(
        resume_path,
        [
            "Hanif Carroll",
            "Product Engineer",
            "hanif@example.com | hanifcarroll.com",
        ],
    )
    first = make_stored_draft(
        DraftRequest(opportunity=OpportunitySnapshot(title="Software Engineer", company="Acme Systems")),
        _draft_payload("First draft body."),
    )
    second = make_stored_draft(
        DraftRequest(opportunity=OpportunitySnapshot(title="Software Engineer", company="Acme Systems")),
        _draft_payload("Second draft body."),
    )

    first_export = export_cover_letter_pdf(first, output_dir, resume_path)
    second_export = export_cover_letter_pdf(second, output_dir, resume_path)

    assert first_export.pdf_path == second_export.pdf_path
    assert first_export.filename == "Hanif-Carroll-Cover-Letter-Acme-Systems.pdf"
    text = _pdf_text(Path(second_export.pdf_path))
    assert "Second draft body." in text
    assert "First draft body." not in text


def test_archive_cover_letter_pdf_moves_generated_file_to_archive(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.pdf"
    output_dir = tmp_path / "letters"
    archive_dir = output_dir / "archive"
    _write_resume_pdf(
        resume_path,
        [
            "Hanif Carroll",
            "Product Engineer",
            "hanif@example.com | hanifcarroll.com",
        ],
    )
    stored = make_stored_draft(
        DraftRequest(opportunity=OpportunitySnapshot(title="Software Engineer", company="Acme Systems")),
        _draft_payload("Archived draft body."),
    )
    exported = export_cover_letter_pdf(stored, output_dir, resume_path)
    active_path = Path(exported.pdf_path)
    original_bytes = active_path.read_bytes()

    archive_path = archive_cover_letter_pdf(stored, output_dir, archive_dir)

    assert archive_path is not None
    assert archive_path == archive_dir / f"Hanif-Carroll-Cover-Letter-Acme-Systems-{stored.id[:8]}.pdf"
    assert archive_path.read_bytes() == original_bytes
    assert not active_path.exists()


def test_archive_cover_letter_pdf_ignores_missing_generated_file(tmp_path: Path) -> None:
    stored = make_stored_draft(
        DraftRequest(opportunity=OpportunitySnapshot(title="Software Engineer", company="Acme Systems")),
        _draft_payload("Draft body."),
    )

    archive_path = archive_cover_letter_pdf(stored, tmp_path / "letters", tmp_path / "archive")

    assert archive_path is None
    assert not (tmp_path / "archive").exists()


def test_export_cover_letter_pdf_rejects_upwork_proposal(tmp_path: Path) -> None:
    stored = make_stored_draft(
        DraftRequest(opportunity=OpportunitySnapshot(title="Build a dashboard"), draft_type="upwork_proposal"),
        {
            "draft_text": "I can build this dashboard.",
            "draft_type": "upwork_proposal",
            "subject_line": "",
            "selected_angle": {
                "key": "dashboard",
                "label": "Dashboard",
                "promise": "Build dashboards",
                "caused_by": ["offer.dashboard"],
            },
            "role_classification": "dashboard build",
            "application_strategy": "Keep it concise.",
            "selected_projects": [],
            "rejected_projects": [],
            "decisions": [],
            "claims": [],
            "warnings": [],
        },
    )

    with pytest.raises(PdfExportError, match="cover letters"):
        export_cover_letter_pdf(stored, tmp_path / "letters", tmp_path / "resume.pdf")


def test_reveal_pdf_rejects_paths_outside_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "letters"
    output_dir.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(PdfExportError, match="outside"):
        reveal_pdf(outside, output_dir)


def _write_resume_pdf(path: Path, lines: list[str]) -> None:
    canvas = Canvas(str(path), pagesize=letter)
    y = 740
    for line in lines:
        canvas.drawString(72, y, line)
        y -= 16
    canvas.save()


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


def _pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _pdf_uris(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    uris: list[str] = []
    for page in reader.pages:
        annotations = page.get("/Annots", [])
        for annotation_ref in annotations:
            annotation = annotation_ref.get_object()
            action = annotation.get("/A")
            if action and action.get("/URI"):
                uris.append(str(action["/URI"]))
    return uris

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from job_application_assistant.models import ResumeContext


def extract_resume_context(resume_pdf_path: Path) -> ResumeContext:
    if not resume_pdf_path.is_file():
        return ResumeContext(warnings=[f"Resume PDF was not found at {resume_pdf_path}."])

    try:
        reader = PdfReader(str(resume_pdf_path))
        text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    except Exception as exc:
        return ResumeContext(warnings=[f"Could not read resume PDF: {exc}"])

    if not text:
        return ResumeContext(warnings=["Resume PDF did not contain extractable text."])

    return ResumeContext(text=text)

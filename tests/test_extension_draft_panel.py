from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSION = REPO_ROOT / "extension"


def read(path: str) -> str:
    return (EXTENSION / path).read_text(encoding="utf-8")


def test_draft_panel_html_loads_renamed_orchestrator_and_ui_modules() -> None:
    popup_html = read("popup.html")
    draft_sidepanel_html = read("draft_sidepanel.html")

    for html in [popup_html, draft_sidepanel_html]:
        assert 'src="ui/content_scripts.js"' in html
        assert 'src="ui/draft_form.js"' in html
        assert 'src="ui/application_status.js"' in html
        assert 'src="ui/application_count.js"' in html
        assert 'src="ui/pdf_controls.js"' in html
        assert 'src="ui/posting_picker.js"' in html
        assert 'src="draft_panel.js"' in html
        assert 'src="popup.js"' not in html


def test_draft_panel_uses_source_aware_snapshot_form_modules() -> None:
    popup_html = read("popup.html")
    popup_css = read("popup.css")
    draft_panel = read("draft_panel.js")
    draft_form = read("ui/draft_form.js")

    for field_id in [
        "applied-indicator",
        "applied-summary",
        "applications-dashboard-link",
        "source-url",
        "employment-type",
        "company-context",
        "recruiter-context",
        "responsibilities",
        "requirements",
        "nice-to-haves",
        "questions",
        "warnings",
    ]:
        assert f'id="{field_id}"' in popup_html

    assert "Page context sent to model" not in popup_html
    assert "context-panel" not in popup_html
    assert "Dice context" not in popup_html
    assert "Extraction confidence" not in popup_html
    assert "Compensation" not in popup_html
    assert "short_application_message" not in popup_html
    assert "question_answers" not in popup_html
    assert 'class="grid" data-hide-for-upwork' in popup_html
    assert '<label data-hide-for-upwork>\n        Source URL' in popup_html
    assert '<label data-hide-for-upwork>\n        Draft type' in popup_html
    assert 'body[data-source-mode="upwork"] [data-hide-for-upwork]' in popup_css
    assert 'body[data-source-mode="upwork"] .source-field' in popup_css

    assert "JobApplicationDraftForm.create" in draft_panel
    assert "const { fillOpportunity, fillRequest, readRequest, setSourceMode, syncSourceFields } = draftForm" in draft_panel
    assert "function setSourceMode(source)" in draft_form
    assert 'document.body.dataset.sourceMode = String(source || "").trim().toLowerCase() === "upwork" ? "upwork" : ""' in draft_form
    assert "function fillOpportunity(opportunity)" in draft_form
    assert "function readRequest()" in draft_form
    assert "company_context: companyContext" in draft_form
    assert "remote_status" not in draft_panel
    assert "source_text" not in draft_panel
    assert "raw_text" not in draft_panel
    assert "extraction_confidence" not in draft_panel


def test_draft_panel_injects_ordered_content_script_bundle() -> None:
    draft_panel = read("draft_panel.js")
    content_scripts = read("ui/content_scripts.js")

    assert "CONTENT_SCRIPT_FILES" in content_scripts
    assert '"extractors/common.js"' in content_scripts
    assert '"platforms/dice_opportunity.js"' in content_scripts
    assert '"platforms/linkedin_opportunity.js"' in content_scripts
    assert '"extractors/upwork.js"' in content_scripts
    assert '"extractors/linkedin.js"' in content_scripts
    assert '"content_script.js"' in content_scripts
    assert "LINKEDIN_EASY_APPLY_SCRIPT_FILES" in content_scripts
    assert '"linkedin_easy_apply_assistant.js"' in content_scripts
    assert "function injectLinkedInEasyApply" in content_scripts
    assert "function setSessionStorage" in content_scripts
    assert "chrome.scripting.executeScript({ target: { tabId }, files: CONTENT_SCRIPT_FILES })" in content_scripts
    assert "globalThis.JobApplicationContentScripts.inject(tabId)" in draft_panel
    assert 'files: ["content_script.js"]' not in draft_panel
    assert "async function executeExtractor(tabId)" in draft_panel
    assert "globalThis.__applicationDraftAssistantExtract()" in draft_panel


def test_draft_panel_wires_application_logging_and_pdf_modules() -> None:
    popup_html = read("popup.html")
    draft_panel = read("draft_panel.js")
    app_status = read("ui/application_status.js")
    app_count = read("ui/application_count.js")
    pdf_controls = read("ui/pdf_controls.js")
    background = read("background.js")

    assert 'id="mark-applied"' in popup_html
    for field_id in ["application-count", "application-count-value", "application-count-label", "application-count-status", "application-count-days"]:
        assert f'id="{field_id}"' in popup_html
    assert "LOG_APPLICATION" in draft_panel
    assert "JobApplicationCount.create" in draft_panel
    assert "applicationCount.initialize()" in draft_panel
    assert "await applicationCount.refresh()" in draft_panel
    assert 'detected_by: "manual"' in app_status
    assert "APPLICATION_SUMMARY" in app_count
    assert "jobApplicationAppliedCountDays" in app_count
    assert "jobApplicationLedgerUpdatedAt" in app_count
    assert "let hasRenderedSummary = false" in app_count
    assert "if (!hasRenderedSummary)" in app_count
    assert "hasRenderedSummary = true" in app_count
    assert "window.setInterval" in app_count
    assert "JobApplicationStatusUi.buildApplicationLogRequest" in draft_panel
    assert "JobApplicationStatusUi.setAppliedIndicator" in draft_panel
    assert "Already in application ledger." in draft_panel

    for field_id in ["generate-pdf", "open-pdf-folder", "pdf-status"]:
        assert f'id="{field_id}"' in popup_html
    assert "JobApplicationPdfControls" in pdf_controls
    assert "JobApplicationPdfControls.startPdfExport" in draft_panel
    assert "JobApplicationPdfControls.revealPdf" in draft_panel
    assert "JobApplicationPdfControls.setPdfControls" in draft_panel
    assert "START_PDF_EXPORT" in pdf_controls
    assert "START_PDF_EXPORT" in background
    assert "DOWNLOAD_PDF" in background
    assert "APPLICATION_SUMMARY" in background
    assert "/applications/summary?days=" in background
    assert "APPLICATION_LEDGER_UPDATED_KEY" in background
    assert "function downloadPdf" in background
    assert "arrayBufferToBase64" in background
    assert "pdf_status" in draft_panel
    assert "chrome.storage.onChanged" in draft_panel
    assert "/pdf`" in background
    assert "/pdf/reveal`" in pdf_controls

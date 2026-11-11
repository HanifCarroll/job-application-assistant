from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSION = REPO_ROOT / "extension"


def read(path: str) -> str:
    return (EXTENSION / path).read_text(encoding="utf-8")


def test_application_logger_loads_after_ledger_badge_and_uses_shared_dice_capture() -> None:
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    scripts = manifest["content_scripts"][0]["js"]
    logger = read("application_logger.js")
    badge = read("application/ledger_badge.js")

    assert scripts.index("application/ledger_badge.js") < scripts.index("application_logger.js")
    assert scripts.index("platforms/dice_opportunity.js") < scripts.index("application_logger.js")
    assert scripts.index("platforms/indeed_opportunity.js") < scripts.index("application_logger.js")
    assert scripts.index("ui/cover_letter_runs.js") < scripts.index("application_logger.js")
    assert "JobApplicationLedgerBadge" in badge
    assert "job-application-ledger-badge" in badge
    assert "visibleSourceUrl" in badge

    assert "const diceOpportunity = globalThis.JobApplicationDiceOpportunity" in logger
    assert "const indeedOpportunity = globalThis.JobApplicationIndeedOpportunity" in logger
    assert "const coverLetterRuns = globalThis.JobApplicationCoverLetterRuns" in logger
    assert "const ledgerBadge = globalThis.JobApplicationLedgerBadge" in logger
    assert "diceOpportunity.detailOpportunity" in logger
    assert "diceOpportunity.wizardPageOpportunity" in logger
    assert "function updateCoverLetterRunConfirmed" in logger
    assert "coverLetterRuns.remove(jobId)" in logger
    assert 'setFreshLedgerBadge(response.application, "Submission recorded", sourceUrl)' in logger
    assert "function jobPostingJsonLd" not in logger
    assert 'script[type="application/ld+json"]' not in logger
    assert "function setLedgerBadge" not in logger


def test_application_logger_detects_submit_and_confirmation_contracts() -> None:
    logger = read("application_logger.js")
    background = read("background.js")

    assert "APPLICATION_CAPTURE_PENDING" in background
    assert "APPLICATION_CONFIRMED" in background
    assert "closeTabSoon" in background
    assert "chrome.tabs.remove(tabId)" in background
    assert "message.close_tab && _sender.tab?.id" in background
    assert "LOOKUP_APPLICATION" in background
    assert "Backend offline. Start it with: uv --no-config run jaa serve" in background
    assert "APPLICATION_QUEUE_KEY" in background
    assert "APPLICATION_LEDGER_UPDATED_KEY" in background
    assert "/applications" in background
    assert "/applications/lookup" in background
    assert "message.opportunity || pending?.opportunity" in background

    assert "submitSelectors" in logger
    assert "confirmationSelectors" in logger
    assert "submitButtons" in logger
    assert "event.composedPath" in logger
    assert "matchesSubmitElement" in logger
    assert "scheduleLedgerBadgeRefresh(300, { force: true })" in logger
    assert "attributeFilter" in logger
    for attribute_name in ["applied", "selected", "destination", "headline", "cta-type"]:
        assert f'"{attribute_name}"' in logger
    assert "(rule.confirmationSelectors || []).some" in logger
    assert "document.querySelectorAll(item.selector)" in logger
    assert "text.startsWith(item.textPrefix)" in logger
    assert "(rule.confirmationPathPatterns || []).some" in logger
    assert 'button[data-testid="submit-application-button"]' in logger
    assert "function indeedSmartApplyOpportunity" in logger
    assert "indeedOpportunity?.smartApplyOpportunity?.()" in logger
    assert "/\\/indeedapply\\/.*(?:post-apply|success|confirmation)/" in logger


def test_application_logger_tracks_current_upwork_dice_and_other_success_states() -> None:
    logger = read("application_logger.js")

    assert "Your proposal was submitted." in logger
    assert 'data-test="proposal-details"' in logger
    assert "/\\/nx\\/proposals\\/[^/?#]+\\/?\\?success$/" in logger
    assert "pathWithSearch" in logger
    assert "pattern.test(path) || pattern.test(pathWithSearch)" in logger
    assert '/\\/job-applications\\/[^/]+\\/wizard\\/success\\/?$/' in logger
    assert 'close_tab: rule.source === "dice" && pathConfirms(rule)' in logger
    assert 'button[aria-label="1-Click Apply"]' in logger
    assert 'button[aria-label="Quick Apply"]' in logger
    assert '{ selector: \'button[type="button"]\', text: "Submit" }' in logger
    assert "Your application was submitted!" in logger
    assert 'button[aria-label="Applied"]' in logger
    assert 'button[aria-label="Quick apply"]' in logger
    assert 'rhcl-button[component-title="Quick apply"]' in logger
    assert 'rhcl-job-card[data-testid="job-details"][cta-type="quick-apply"]' in logger
    assert 'rhcl-job-card[data-testid="job-details"][applied=""]' in logger
    assert 'rhcl-job-card[data-testid="job-details"][applied="true"]' in logger
    assert 'rhcl-job-card[selected="true"][applied=""]' in logger
    assert 'rhcl-job-card[selected="true"][applied="true"]' in logger


def test_application_logger_tracks_linkedin_easy_apply_submission_states() -> None:
    logger = read("application_logger.js")

    assert 'source: "linkedin"' in logger
    assert 'hosts: ["linkedin.com"]' in logger
    assert '.jobs-easy-apply-modal__content button[data-live-test-easy-apply-submit-button]' in logger
    assert '{ selector: ".jobs-easy-apply-modal__content button", text: "Submit application" }' in logger
    assert "autoEasyApply: true" in logger
    assert '{ selector: ".jobs-easy-apply-modal__content button", text: "Done" }' in logger
    assert '{ selector: ".jobs-easy-apply-modal__content button", text: "Not now" }' in logger
    assert '{ selector: "#jobs-apply-see-application-link" }' in logger
    assert '{ selector: \'.artdeco-inline-feedback--success[role="alert"]\', textPrefix: "Applied" }' in logger
    assert 'setFreshLedgerBadge(response.application, "Submission recorded", sourceUrl)' in logger


def test_application_logger_automates_linkedin_easy_apply_final_review() -> None:
    logger = read("application_logger.js")

    assert "LINKEDIN_AUTO_SUBMIT_DELAY = 1000" in logger
    assert "LINKEDIN_AUTO_CLOSE_DELAY = 500" in logger
    assert 'document.querySelector(".jobs-easy-apply-modal__content")' in logger
    assert 'root?.querySelector("#follow-company-checkbox")' in logger
    assert 'checkbox.labels?.[0] || checkbox' in logger
    assert 'buttonText(button) === "Submit application"' in logger
    assert '["Done", "Not now"].includes(buttonText(candidate))' in logger
    assert 'element.dataset[datasetKey] = "true"' in logger
    assert "capturePending(rule)" in logger
    assert "element.click()" in logger
    assert "runPlatformAutomation()" in logger
    assert '"disabled"' in logger

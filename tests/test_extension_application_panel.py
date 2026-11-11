from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSION = REPO_ROOT / "extension"


def read(path: str) -> str:
    return (EXTENSION / path).read_text(encoding="utf-8")


def test_application_side_panel_routes_action_and_reuses_posting_picker_module() -> None:
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    background = read("background.js")
    popup_html = read("popup.html")
    popup_router = read("popup_router.js")
    sidepanel_html = read("sidepanel.html")
    sidepanel = read("sidepanel.js")
    sidepanel_css = read("sidepanel.css")
    cover_letter_runs = read("ui/cover_letter_runs.js")
    application_count = read("ui/application_count.js")
    dice_wizard = read("dice_wizard_assistant.js")
    indeed_wizard = read("indeed_smartapply_assistant.js")
    draft_sidepanel_html = read("draft_sidepanel.html")
    check_script = (REPO_ROOT / "scripts" / "check").read_text(encoding="utf-8")

    assert manifest["side_panel"]["default_path"] == "sidepanel.html"
    assert "sidePanel" in manifest["permissions"]
    assert "tabs" in manifest["permissions"]
    assert "default_popup" not in manifest["action"]

    assert "POPUP_PATH" not in background
    assert 'const POSTING_SIDE_PANEL_PATH = "sidepanel.html"' in background
    assert 'const DRAFT_SIDE_PANEL_PATH = "draft_sidepanel.html"' in background
    assert "function isDiceUrl" in background
    assert "function isIndeedResultsUrl" in background
    assert "function isLinkedInResultsUrl" in background
    assert "function isPostingPickerUrl" in background
    assert "function sidePanelPathForUrl" in background
    assert "return isPostingPickerUrl(url) ? POSTING_SIDE_PANEL_PATH : DRAFT_SIDE_PANEL_PATH" in background
    assert 'chrome.action.setPopup({ tabId, popup: "" })' in background
    assert "chrome.sidePanel.setOptions" in background
    assert "enabled: true" in background
    assert "function enableSidePanelActionClick" in background
    assert "chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })" in background
    assert "chrome.action.onClicked.addListener" in background
    assert "configureActionForTab(tab.id, tab.url)" in background
    assert "chrome.sidePanel.open({ tabId: tab.id })" in background
    assert "chrome.tabs.onActivated.addListener" in background
    assert "chrome.tabs.onUpdated.addListener" in background

    assert 'src="popup_router.js"' in popup_html
    assert popup_html.index('src="popup_router.js"') < popup_html.index('class="shell"')
    assert 'const POSTING_SIDE_PANEL_PATH = "sidepanel.html"' in popup_router
    assert 'const DRAFT_SIDE_PANEL_PATH = "draft_sidepanel.html"' in popup_router
    assert "function isDiceUrl" in popup_router
    assert "function isIndeedResultsUrl" in popup_router
    assert "function isLinkedInResultsUrl" in popup_router
    assert "function isPostingPickerUrl" in popup_router
    assert "function redirectPopupToSidePanel" in popup_router
    assert 'extensionApi.action.setPopup({ tabId: tab.id, popup: "" })' in popup_router
    assert "extensionApi.sidePanel.setOptions({ tabId: tab.id, path, enabled: true })" in popup_router
    assert "extensionApi.sidePanel.open({ tabId: tab.id })" in popup_router
    assert "window.close()" in popup_router

    assert 'src="ui/content_scripts.js"' in sidepanel_html
    assert 'src="ui/application_count.js"' in sidepanel_html
    assert 'src="ui/posting_picker.js"' in sidepanel_html
    assert 'src="ui/cover_letter_runs.js"' in sidepanel_html
    assert 'src="sidepanel.js"' in sidepanel_html
    assert 'id="cover-letter-runs"' in sidepanel_html
    assert 'id="cover-letter-list"' in sidepanel_html
    assert 'id="application-count"' in sidepanel_html
    assert 'id="application-count-days"' in sidepanel_html
    assert 'id="posting-picker-title"' in sidepanel_html
    assert 'id="application-count"' in draft_sidepanel_html
    assert 'id="posting-picker-title"' in draft_sidepanel_html
    assert "sidepanel.css" in sidepanel_html
    assert 'src="draft_panel.js"' in draft_sidepanel_html
    assert 'id="draft"' in draft_sidepanel_html
    assert 'id="title"' in draft_sidepanel_html
    assert 'id="description"' in draft_sidepanel_html

    assert "function isDiceResultsUrl" in sidepanel
    assert "function isIndeedResultsUrl" in sidepanel
    assert "function isLinkedInResultsUrl" in sidepanel
    assert "function isPostingResultsUrl" in sidepanel
    assert "function postingResultsTab" in sidepanel
    assert "JobApplicationPostingPicker.create" in sidepanel
    assert "JobApplicationCoverLetterRuns" in sidepanel
    assert "const BUSY_RUN_STATUSES = new Set" in sidepanel
    assert "function sourceFromJobId" in sidepanel
    assert "function runSource" in sidepanel
    assert "function sourceLabel" in sidepanel
    assert "function runSourceLabel" in sidepanel
    assert "function renderCoverLetterRuns" in sidepanel
    assert "function reconcileCoverLetterRuns" in sidepanel
    assert "function reconcileCoverLetterRun" in sidepanel
    assert "function lookupApplicationForRun" in sidepanel
    assert "function ensureWizardAssistant" in sidepanel
    assert "JobApplicationCount.create" in sidepanel
    assert "applicationCount.initialize()" in sidepanel
    assert "applicationCount.scheduleRefresh" in sidepanel
    assert "INDEED_SMARTAPPLY_SCRIPT_FILES" in sidepanel
    assert 'chrome.runtime.sendMessage({ type: "LOOKUP_APPLICATION", source_url: run.source_url })' in sidepanel
    assert 'const files = source === "indeed" ? INDEED_SMARTAPPLY_SCRIPT_FILES : DICE_WIZARD_SCRIPT_FILES' in sidepanel
    assert "await chrome.scripting.executeScript({ target: { tabId: tab.id }, files })" in sidepanel
    assert "await coverLetterRuns.remove(run.job_id)" in sidepanel
    assert 'status: "submitted"' not in sidepanel
    assert "Waiting for the ${runSourceLabel(run)} application workflow." in sidepanel
    assert "Finder opened. Select the generated PDF in the application upload box." in sidepanel
    assert 'dismiss.dataset.action = "dismiss-cover-letter-run"' in sidepanel
    assert 'dismiss.textContent = "Dismiss"' in sidepanel
    assert "coverLetterRuns.remove(jobId)" in sidepanel
    assert 'status: "needs_attention"' in sidepanel
    assert "renderCoverLetterRuns({ reconcile: true })" in sidepanel
    assert "function startCoverLetterFromSidebar" in sidepanel
    assert "DICE_COVER_LETTER_START" in sidepanel
    assert "INDEED_COVER_LETTER_START" in sidepanel
    assert "REVEAL_PDF" in sidepanel
    assert "JobApplicationContentScripts.inject(tabId)" in sidepanel
    assert 'files: ["content_script.js"]' not in sidepanel
    assert "align-content: start" in sidepanel_css
    assert "grid-auto-rows: max-content" in sidepanel_css
    assert ".cover-letter-runs" in sidepanel_css
    assert ".application-count" in (REPO_ROOT / "extension" / "popup.css").read_text(encoding="utf-8")
    assert "find extension -name '*.js'" in check_script
    assert "document.title" not in sidepanel
    assert "innerText" not in sidepanel
    assert "[class*=" not in sidepanel

    assert "jobApplicationCoverLetterRuns" in cover_letter_runs
    assert "jobApplicationDiceCoverLetterRuns" in cover_letter_runs
    assert "chrome.storage.local.set" in cover_letter_runs
    assert "globalThis.JobApplicationCoverLetterRuns" in cover_letter_runs
    assert "globalThis.JobApplicationCount" in application_count
    assert "APPLICATION_SUMMARY" in application_count
    assert "jobApplicationAppliedCountDays" in application_count
    assert "jobApplicationLedgerUpdatedAt" in application_count
    assert "countLabel" in application_count
    assert "function runOrderKey" in cover_letter_runs
    assert "function compareRunsByStart" in cover_letter_runs
    assert 'run?.started_at || run?.updated_at || ""' in cover_letter_runs
    assert "runs.sort(compareRunsByStart)" in cover_letter_runs
    assert "String(right.updated_at" not in cover_letter_runs
    assert "JobApplicationCoverLetterRuns" in dice_wizard
    assert "DICE_COVER_LETTER_START" in dice_wizard
    assert "DOWNLOAD_PDF" in dice_wizard
    assert "function attachGeneratedPdf" in dice_wizard
    assert "function markSubmittedIfSuccess" in dice_wizard
    assert "function markManualQuestionsIfNeeded" in dice_wizard
    assert "function continueWizardAutomation" in dice_wizard
    assert "coverLetterRuns?.remove?.(jobApplicationId())" in dice_wizard
    assert 'status: "submitted"' not in dice_wizard
    assert 'status: "needs_attention"' in dice_wizard
    assert "Application questions need manual answers in this Dice tab." in dice_wizard
    assert "new DataTransfer()" in dice_wizard
    assert "input.dispatchEvent(new Event(\"change\", { bubbles: true }))" in dice_wizard
    assert "Dice did not show the generated PDF as attached." in dice_wizard
    assert "position: fixed" not in dice_wizard
    assert "job-application-cover-letter-panel" not in dice_wizard
    assert "JobApplicationIndeedOpportunity" in indeed_wizard
    assert "function isContactStep" in indeed_wizard
    assert "function isLocationStep" in indeed_wizard
    assert "function isResumeStep" in indeed_wizard
    assert "function isReviewStep" in indeed_wizard
    assert "function captchaIssuePresent" in indeed_wizard
    assert "function cacheOpportunitySnapshot" in indeed_wizard
    assert "APPLICATION_CAPTURE_PENDING" in indeed_wizard
    assert "DOWNLOAD_PDF" in indeed_wizard
    assert "function attachGeneratedPdf" in indeed_wizard
    assert "function markManualQuestionsIfNeeded" in indeed_wizard
    assert "Application questions need manual answers in this Indeed tab." in indeed_wizard
    assert "Indeed submission needs manual attention: reCAPTCHA is blocking submission." in indeed_wizard
    assert "coverLetterRuns?.remove?.(runId())" in indeed_wizard
    assert 'status: "submitted"' not in indeed_wizard
    assert 'status: "needs_attention"' in indeed_wizard


def test_posting_picker_opens_selected_jobs_and_advances_page() -> None:
    picker = read("ui/posting_picker.js")
    popup_html = read("popup.html")
    draft_panel = read("draft_panel.js")

    for field_id in [
        "posting-picker",
        "posting-summary",
        "posting-next-page",
        "posting-select-all",
        "posting-list",
        "posting-open-selected",
        "posting-status",
    ]:
        assert f'id="{field_id}"' in popup_html

    assert "function createPostingPicker" in picker
    assert "function nextDiceResultsUrl" in picker
    assert "function nextIndeedResultsUrl" in picker
    assert "function nextLinkedInResultsUrl" in picker
    assert "function platformForUrl" in picker
    assert 'url.pathname !== "/jobs"' in picker
    assert 'url.hostname !== "www.indeed.com"' in picker
    assert 'url.pathname !== "/jobs/search/"' in picker
    assert 'url.searchParams.set("start"' in picker
    assert 'url.searchParams.delete("vjk")' in picker
    assert 'url.searchParams.delete("currentJobId")' in picker
    assert 'url.searchParams.set("page"' in picker
    assert "function listPostingsFromTab" in picker
    assert "APPLICATION_DRAFT_LIST_POSTINGS" in picker
    assert "APPLICATION_DRAFT_CLICK_APPLY_CONTROL" in picker
    assert "waitForTabComplete" in picker
    assert "function reloadTab" in picker
    assert "await chrome.tabs.reload(tabId)" in picker
    assert "function isDiceApplicationWizardUrl" in picker
    assert "function isIndeedSmartApplyUrl" in picker
    assert "function isApplicationWizardUrl" in picker
    assert "function ensurePostApplyAutomation" in picker
    assert 'contentScripts.setSessionStorage(tabId, response.auto_run_key, "true")' in picker
    assert "contentScripts.injectLinkedInEasyApply(tabId)" in picker
    assert "chrome.tabs.update(tabId, { active: true })" in picker
    assert "chrome.tabs.update(tab.id, { url: nextUrl })" in picker
    assert "await reloadTab(tab.id)" in picker
    assert "function scrollPostingListToTop" in picker
    assert "els.postingList.scrollTop = 0" in picker
    assert "els.postingList.scrollLeft = 0" in picker
    assert "await refresh();\n      scrollPostingListToTop();" in picker
    assert "function openPostingTab" in picker
    assert "function clickApplyControlInOpenedTab" in picker
    assert "function openPostingTabResult" in picker
    assert "function startApplyControlFlowResult" in picker
    assert "function startApplyControlFlowWithoutWaiting" in picker
    assert "function startApplyControlFlows" in picker
    assert "function openSelectedPostings" in picker
    assert "chrome.tabs.create({ url: posting.easy_apply_url || posting.url, active: false })" in picker
    assert "chrome.tabs.update(tabId, { url: response.next_url })" in picker
    assert "response.reload_after_navigation !== false" in picker
    assert "const openedResults = await Promise.all(selectedPostings.map(openPostingTabResult))" in picker
    assert 'if (activePlatform?.source === "dice")' in picker
    assert "openedPostings.forEach(startApplyControlFlowWithoutWaiting)" in picker
    assert 'return openedPostings.map((opened) => ({ opened, error: "" }))' in picker
    assert "const flowResults = await startApplyControlFlows(openedPostings)" in picker
    assert "const flowResults = await Promise.all(openedPostings.map(startApplyControlFlowResult))" not in picker
    assert "const results = await openSelectedPostings(selectedPostings)" in picker
    assert "for (const posting of selectedPostings)" not in picker
    assert "openedTabs.forEach(startApplyControlFlow)" not in picker
    assert "await advanceActivePage()" in picker
    assert "await openPostingAndClickEasyApply(posting)" not in picker
    assert "Loaded next ${platformName()} results page." in picker
    assert "Started ${openedCount} ${platformName()} ${postingNoun()} tab" in picker
    assert "Next page" in popup_html
    assert "Open selected" in popup_html
    assert "Open Easy Apply" in picker
    assert "JobApplicationPostingPicker.create" in draft_panel

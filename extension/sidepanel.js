const els = {
  status: document.querySelector("#status"),
  refresh: document.querySelector("#refresh"),
  applicationCount: document.querySelector("#application-count"),
  applicationCountValue: document.querySelector("#application-count-value"),
  applicationCountLabel: document.querySelector("#application-count-label"),
  applicationCountStatus: document.querySelector("#application-count-status"),
  applicationCountDays: document.querySelector("#application-count-days"),
  postingPicker: document.querySelector("#posting-picker"),
  postingPickerTitle: document.querySelector("#posting-picker-title"),
  postingSummary: document.querySelector("#posting-summary"),
  postingNextPage: document.querySelector("#posting-next-page"),
  postingSelectAll: document.querySelector("#posting-select-all"),
  postingList: document.querySelector("#posting-list"),
  postingOpenSelected: document.querySelector("#posting-open-selected"),
  postingStatus: document.querySelector("#posting-status"),
  coverLetterRunsSection: document.querySelector("#cover-letter-runs"),
  coverLetterSummary: document.querySelector("#cover-letter-summary"),
  coverLetterList: document.querySelector("#cover-letter-list"),
};

let postingResultsTabId = null;
let apiBase = "";

const coverLetterRuns = globalThis.JobApplicationCoverLetterRuns;
const BUSY_RUN_STATUSES = new Set(["reading", "drafting", "pdf_generating", "attaching", "continuing", "submitting", "opening_finder"]);
const DICE_WIZARD_SCRIPT_FILES = [
  "extractors/common.js",
  "platforms/dice_opportunity.js",
  "ui/cover_letter_runs.js",
  "dice_wizard_assistant.js",
];
const INDEED_SMARTAPPLY_SCRIPT_FILES = [
  "extractors/common.js",
  "platforms/indeed_opportunity.js",
  "ui/cover_letter_runs.js",
  "indeed_smartapply_assistant.js",
];

function setStatus(text, state = "idle") {
  els.status.textContent = text;
  els.status.dataset.state = state;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isDiceResultsUrl(value) {
  try {
    const url = new URL(value || "");
    return url.hostname.includes("dice.com") && url.pathname === "/jobs";
  } catch (_error) {
    return false;
  }
}

function isIndeedResultsUrl(value) {
  try {
    const url = new URL(value || "");
    return url.hostname === "www.indeed.com" && url.pathname === "/jobs";
  } catch (_error) {
    return false;
  }
}

function isLinkedInResultsUrl(value) {
  try {
    const url = new URL(value || "");
    return url.hostname.includes("linkedin.com") && url.pathname === "/jobs/search/";
  } catch (_error) {
    return false;
  }
}

function isPostingResultsUrl(value) {
  return isDiceResultsUrl(value) || isIndeedResultsUrl(value) || isLinkedInResultsUrl(value);
}

function isDiceWizardUrl(value, jobId = "") {
  try {
    const url = new URL(value || "");
    if (!url.hostname.includes("dice.com")) return false;
    const pattern = jobId
      ? new RegExp(`^/job-applications/${jobId.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/wizard(?:/|$)`)
      : /^\/job-applications\/[^/]+\/wizard(?:\/|$)/;
    return pattern.test(url.pathname);
  } catch (_error) {
    return false;
  }
}

function isIndeedSmartApplyUrl(value) {
  try {
    const url = new URL(value || "");
    return url.hostname === "smartapply.indeed.com" && url.pathname.includes("/indeedapply/form/");
  } catch (_error) {
    return false;
  }
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("No active tab found.");
  return tab;
}

async function postingResultsTab() {
  if (postingResultsTabId) {
    try {
      const tab = await chrome.tabs.get(postingResultsTabId);
      if (tab?.id && isPostingResultsUrl(tab.url || "")) return tab;
    } catch (_error) {
      postingResultsTabId = null;
    }
  }

  const tab = await activeTab();
  if (!isPostingResultsUrl(tab.url || "")) {
    throw new Error("Open a Dice, Indeed, or LinkedIn results page to use this panel.");
  }
  postingResultsTabId = tab.id;
  return tab;
}

async function injectContentScripts(tabId) {
  await globalThis.JobApplicationContentScripts.inject(tabId);
}

async function backendUrl() {
  if (apiBase) return apiBase;
  const response = await chrome.runtime.sendMessage({ type: "GET_BACKEND_URL" });
  if (!response?.ok) throw new Error(response?.error || "Could not read backend URL.");
  apiBase = response.api_base;
  return apiBase;
}

function runIsBusy(run) {
  return Boolean(run?.busy) || BUSY_RUN_STATUSES.has(run?.status || "");
}

function sourceFromJobId(jobId) {
  return String(jobId || "").startsWith("indeed:") ? "indeed" : "dice";
}

function runSource(run) {
  return run?.source || sourceFromJobId(run?.job_id);
}

function sourceLabel(source) {
  return source === "indeed" ? "Indeed" : "Dice";
}

function runSourceLabel(run) {
  return sourceLabel(runSource(run));
}

function runLabel(run) {
  return run?.title || `${runSourceLabel(run)} application`;
}

function runMeta(run) {
  return [run?.company, run?.job_id].filter(Boolean).join(" • ");
}

function pdfUrl(pdf, baseUrl) {
  if (!pdf?.download_url || !baseUrl) return "";
  try {
    return new URL(pdf.download_url, baseUrl).href;
  } catch (_error) {
    return "";
  }
}

function runWizardTab(tabs, run) {
  if (runSource(run) === "indeed") {
    return tabs.find((tab) => tab?.id && isIndeedSmartApplyUrl(tab.url || "")) || null;
  }
  return tabs.find((tab) => tab?.id && isDiceWizardUrl(tab.url || "", run?.job_id || "")) || null;
}

async function lookupApplicationForRun(run) {
  if (!run?.source_url) return null;
  const response = await chrome.runtime.sendMessage({ type: "LOOKUP_APPLICATION", source_url: run.source_url });
  if (!response?.ok || !response.matched) return null;
  return response.application || null;
}

async function ensureWizardAssistant(tab, source = "dice") {
  if (!tab?.id) return;
  const files = source === "indeed" ? INDEED_SMARTAPPLY_SCRIPT_FILES : DICE_WIZARD_SCRIPT_FILES;
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files }).catch(() => {});
}

async function reconcileCoverLetterRun(run, tabs) {
  if (!runIsBusy(run)) return false;

  const application = await lookupApplicationForRun(run).catch(() => null);
  if (application) {
    await coverLetterRuns.remove(run.job_id);
    return true;
  }

  const tab = runWizardTab(tabs, run);
  if (tab) {
    await ensureWizardAssistant(tab, run?.source || "dice");
    return false;
  }

  await coverLetterRuns.upsert(run.job_id, {
    busy: false,
    message: `${runSourceLabel(run)} tab closed before this run finished.`,
    primary_label: "Try again",
    status: "needs_attention",
  });
  return true;
}

async function reconcileCoverLetterRuns(runs) {
  const busyRuns = runs.filter(runIsBusy);
  if (!busyRuns.length) return runs;
  const tabs = await chrome.tabs.query({}).catch(() => []);
  const changed = await Promise.all(busyRuns.map((run) => reconcileCoverLetterRun(run, tabs)));
  return changed.some(Boolean) ? coverLetterRuns.list() : runs;
}

async function renderCoverLetterRuns({ reconcile = false } = {}) {
  let runs = await coverLetterRuns.list();
  if (reconcile) runs = await reconcileCoverLetterRuns(runs);
  els.coverLetterRunsSection.hidden = runs.length === 0;
  els.coverLetterList.textContent = "";
  if (!runs.length) return runs;

  const activeCount = runs.filter(runIsBusy).length;
  els.coverLetterSummary.textContent = activeCount
    ? `${activeCount} running, ${runs.length} total`
    : `${runs.length} recent PDF ${runs.length === 1 ? "run" : "runs"}`;

  const baseUrl = await backendUrl().catch(() => "");
  runs.forEach((run) => {
    const row = document.createElement("div");
    row.className = "cover-letter-run";
    row.dataset.status = run.status || "";

    const title = document.createElement("div");
    title.className = "cover-letter-run-title";
    const strong = document.createElement("strong");
    strong.textContent = runLabel(run);
    const meta = document.createElement("span");
    meta.textContent = runMeta(run);
    title.append(strong, meta);

    const status = document.createElement("p");
    status.className = "cover-letter-run-status";
    status.textContent = run.message || `Waiting for the ${runSourceLabel(run)} application workflow.`;

    const progress = document.createElement("div");
    progress.className = "cover-letter-run-progress";
    progress.setAttribute("aria-hidden", "true");
    progress.append(document.createElement("span"));

    const actions = document.createElement("div");
    actions.className = "cover-letter-run-actions";

    const openUrl = pdfUrl(run.pdf, baseUrl);
    if (openUrl) {
      const openPdf = document.createElement("a");
      openPdf.href = openUrl;
      openPdf.target = "_blank";
      openPdf.rel = "noreferrer";
      openPdf.textContent = "Open PDF";
      actions.append(openPdf);
    }

    const draftId = run.draft_id || run.pdf?.draft_id || "";
    if (draftId) {
      const reveal = document.createElement("button");
      reveal.type = "button";
      reveal.dataset.action = "reveal-pdf";
      reveal.dataset.draftId = draftId;
      reveal.dataset.jobId = run.job_id || "";
      reveal.textContent = "Finder";
      actions.append(reveal);
    }

    if (!runIsBusy(run)) {
      const start = document.createElement("button");
      start.type = "button";
      start.dataset.action = "start-cover-letter";
      start.dataset.jobId = run.job_id || "";
      start.textContent = run.primary_label || (run.status === "failed" ? "Try again" : "Regenerate PDF");
      actions.append(start);

      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.dataset.action = "dismiss-cover-letter-run";
      dismiss.dataset.jobId = run.job_id || "";
      dismiss.textContent = "Dismiss";
      actions.append(dismiss);
    }

    row.append(title, status, progress, actions);
    els.coverLetterList.append(row);
  });
  return runs;
}

async function findApplicationTab(jobId, source = "") {
  const tabs = await chrome.tabs.query({});
  const resolvedSource = source || sourceFromJobId(jobId);
  if (resolvedSource === "indeed") {
    return tabs.find((tab) => tab?.id && isIndeedSmartApplyUrl(tab.url || "")) || null;
  }
  return tabs.find((tab) => tab?.id && isDiceWizardUrl(tab.url || "", jobId)) || null;
}

async function sendStartCoverLetterMessage(tabId, force, source = "dice") {
  const type = source === "indeed" ? "INDEED_COVER_LETTER_START" : "DICE_COVER_LETTER_START";
  const response = await chrome.tabs.sendMessage(tabId, { type, force });
  if (!response?.ok) throw new Error(response?.error || "Could not start the cover letter PDF.");
  return response;
}

async function startCoverLetterFromSidebar(jobId) {
  const source = sourceFromJobId(jobId);
  const tab = await findApplicationTab(jobId, source);
  if (!tab?.id) throw new Error(`Open the ${sourceLabel(source)} application tab to regenerate this PDF.`);
  try {
    return await sendStartCoverLetterMessage(tab.id, true, source);
  } catch (_error) {
    const files = source === "indeed" ? INDEED_SMARTAPPLY_SCRIPT_FILES : DICE_WIZARD_SCRIPT_FILES;
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files });
    return await sendStartCoverLetterMessage(tab.id, true, source);
  }
}

async function revealPdfFromSidebar({ jobId, draftId }) {
  await coverLetterRuns.upsert(jobId, {
    busy: true,
    message: "Opening Finder...",
    status: "opening_finder",
  });
  const response = await chrome.runtime.sendMessage({ type: "REVEAL_PDF", draft_id: draftId });
  if (!response?.ok || !response.opened) throw new Error(response?.error || "Could not open the generated PDF in Finder.");
  await coverLetterRuns.upsert(jobId, {
    busy: false,
    message: "Finder opened. Select the generated PDF in the application upload box.",
    primary_label: "Regenerate PDF",
    status: "ready",
  });
}

const postingPicker = globalThis.JobApplicationPostingPicker.create({
  els,
  activeTab: postingResultsTab,
  injectContentScripts,
  setStatus,
  sleep,
});
const applicationCount = globalThis.JobApplicationCount.create({ els });

function setBusy(isBusy) {
  els.refresh.disabled = isBusy;
  if (isBusy) {
    els.postingNextPage.disabled = true;
    els.postingOpenSelected.disabled = true;
    els.postingSelectAll.disabled = true;
  }
}

postingPicker.attachEvents();

els.coverLetterList.addEventListener("click", async (event) => {
  const button = event.target instanceof Element ? event.target.closest("button[data-action]") : null;
  if (!(button instanceof HTMLButtonElement)) return;
  const action = button.dataset.action || "";
  const jobId = button.dataset.jobId || "";
  try {
    button.disabled = true;
    if (action === "start-cover-letter") {
      await coverLetterRuns.upsert(jobId, {
        busy: true,
        message: "Starting cover letter PDF...",
        status: "reading",
      });
      await startCoverLetterFromSidebar(jobId);
    } else if (action === "reveal-pdf") {
      await revealPdfFromSidebar({ jobId, draftId: button.dataset.draftId || "" });
    } else if (action === "dismiss-cover-letter-run") {
      await coverLetterRuns.remove(jobId);
      setStatus("Removed cover letter PDF run.");
    }
    await renderCoverLetterRuns({ reconcile: true });
    applicationCount.scheduleRefresh();
  } catch (error) {
    await coverLetterRuns.upsert(jobId, {
      busy: false,
      error: error.message || String(error),
      message: error.message || String(error),
      primary_label: "Try again",
      status: "failed",
    });
    setStatus(error.message, "error");
    await renderCoverLetterRuns();
  } finally {
    button.disabled = false;
  }
});

els.refresh.addEventListener("click", async () => {
  try {
    setBusy(true);
    applicationCount.scheduleRefresh(0);
    await renderCoverLetterRuns();
    const tab = await activeTab();
    if (!isPostingResultsUrl(tab.url || "")) {
      postingPicker.clear();
      setStatus("Cover letter PDFs ready.");
      return;
    }
    els.postingStatus.textContent = "Refreshing...";
    await postingPicker.refresh();
    els.postingStatus.textContent = `${postingPicker.count()} apply-enabled posting${postingPicker.count() === 1 ? "" : "s"} on this page.`;
    setStatus("Results ready.");
  } catch (error) {
    els.postingStatus.textContent = error.message || "Could not refresh postings.";
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
});

async function initializeSidePanel() {
  try {
    setBusy(true);
    applicationCount.initialize().catch(() => {});
    const runs = await renderCoverLetterRuns({ reconcile: true });
    const tab = await activeTab();
    if (!isPostingResultsUrl(tab.url || "")) {
      postingPicker.clear();
      setStatus(runs.length ? "Cover letter PDFs ready." : "Open a Dice, Indeed, or LinkedIn results page to list postings.");
      return;
    }
    await postingPicker.refresh();
    els.postingStatus.textContent = `${postingPicker.count()} apply-enabled posting${postingPicker.count() === 1 ? "" : "s"} on this page.`;
    setStatus("Results ready.");
  } catch (error) {
    postingPicker.clear();
    els.postingStatus.textContent = error.message || "Could not read postings.";
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

initializeSidePanel();

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes[coverLetterRuns.key]) {
    renderCoverLetterRuns().catch((error) => setStatus(error.message, "error"));
    applicationCount.scheduleRefresh();
  }
});

window.setInterval(() => {
  renderCoverLetterRuns().catch(() => {});
}, 2000);

window.setInterval(() => {
  renderCoverLetterRuns({ reconcile: true }).catch(() => {});
}, 10000);

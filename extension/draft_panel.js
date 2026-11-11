const DEFAULT_API_BASE = "http://127.0.0.1:8787";
const API_BASE_KEY = "jobApplicationDraftBackendUrl";
const DRAFT_STATE_KEY = "jobApplicationDraftState";
const SUPPORTED_DRAFT_TYPES = new Set(["cover_letter", "upwork_proposal"]);

const els = {
  status: document.querySelector("#status"),
  settings: document.querySelector("#settings"),
  extract: document.querySelector("#extract"),
  draft: document.querySelector("#draft"),
  markApplied: document.querySelector("#mark-applied"),
  copy: document.querySelector("#copy"),
  generatePdf: document.querySelector("#generate-pdf"),
  openPdfFolder: document.querySelector("#open-pdf-folder"),
  pdfStatus: document.querySelector("#pdf-status"),
  applicationStatus: document.querySelector("#application-status"),
  appliedIndicator: document.querySelector("#applied-indicator"),
  appliedSummary: document.querySelector("#applied-summary"),
  applicationsDashboardLink: document.querySelector("#applications-dashboard-link"),
  applicationCount: document.querySelector("#application-count"),
  applicationCountValue: document.querySelector("#application-count-value"),
  applicationCountLabel: document.querySelector("#application-count-label"),
  applicationCountStatus: document.querySelector("#application-count-status"),
  applicationCountDays: document.querySelector("#application-count-days"),
  source: document.querySelector("#source"),
  sourceUrl: document.querySelector("#source-url"),
  title: document.querySelector("#title"),
  company: document.querySelector("#company"),
  location: document.querySelector("#location"),
  description: document.querySelector("#description"),
  skills: document.querySelector("#skills"),
  employmentType: document.querySelector("#employment-type"),
  companyContext: document.querySelector("#company-context"),
  recruiterContext: document.querySelector("#recruiter-context"),
  responsibilities: document.querySelector("#responsibilities"),
  requirements: document.querySelector("#requirements"),
  niceToHaves: document.querySelector("#nice-to-haves"),
  questions: document.querySelector("#questions"),
  warnings: document.querySelector("#warnings"),
  draftType: document.querySelector("#draft-type"),
  notes: document.querySelector("#notes"),
  proposal: document.querySelector("#proposal"),
  audit: document.querySelector("#audit"),
  progress: document.querySelector("#progress"),
  progressBar: document.querySelector("#progress-bar"),
  stage: document.querySelector("#stage"),
  elapsed: document.querySelector("#elapsed"),
  postingPicker: document.querySelector("#posting-picker"),
  postingPickerTitle: document.querySelector("#posting-picker-title"),
  postingSummary: document.querySelector("#posting-summary"),
  postingNextPage: document.querySelector("#posting-next-page"),
  postingSelectAll: document.querySelector("#posting-select-all"),
  postingList: document.querySelector("#posting-list"),
  postingOpenSelected: document.querySelector("#posting-open-selected"),
  postingStatus: document.querySelector("#posting-status"),
};

let currentState = null;
let currentApplicationMatch = null;
let pollToken = 0;
let saveTimer = 0;
let applicationLookupTimer = 0;
let controlsBusy = false;

const STAGE_LABELS = {
  queued: "Queued",
  codex_draft: "Drafting",
  saving: "Saving audit trail",
  done: "Done",
  failed: "Failed",
};

const STAGE_STATUS = {
  queued: "Draft queued.",
  codex_draft: "Drafting with portfolio context...",
  saving: "Saving the draft and audit trail...",
  done: "Draft ready.",
  failed: "Draft failed.",
};

const STAGE_PROGRESS = {
  queued: 8,
  codex_draft: 55,
  saving: 92,
  done: 100,
  failed: 100,
};

function setStatus(text, state = "idle") {
  els.status.textContent = text;
  els.status.dataset.state = state;
}

function nowIso() {
  return new Date().toISOString();
}

async function loadDraftState() {
  const stored = await chrome.storage.local.get(DRAFT_STATE_KEY);
  return stored[DRAFT_STATE_KEY] || null;
}

async function backendUrl() {
  const stored = await chrome.storage.local.get(API_BASE_KEY);
  return (stored[API_BASE_KEY] || DEFAULT_API_BASE).replace(/\/+$/, "");
}

async function responseErrorMessage(response) {
  const text = await response.text();
  if (!text) return `Backend returned ${response.status}`;
  try {
    const payload = JSON.parse(text);
    return payload?.detail || text;
  } catch (_error) {
    return text;
  }
}

async function writeDraftState(state) {
  currentState = {
    ...state,
    updated_at: nowIso(),
  };
  await chrome.storage.local.set({ [DRAFT_STATE_KEY]: currentState });
}

async function patchDraftState(patch) {
  const existing = (await loadDraftState()) || {};
  await writeDraftState({ ...existing, ...patch });
}

function setProgress(job) {
  const stage = job.stage || "queued";
  els.progress.hidden = false;
  els.stage.textContent = STAGE_LABELS[stage] || stage;
  els.elapsed.textContent = `${Math.max(0, Math.round(job.elapsed_seconds || 0))}s`;
  els.progressBar.style.width = `${STAGE_PROGRESS[stage] || 8}%`;
  setStatus(STAGE_STATUS[stage] || "Drafting through local Codex...");
}

function clearProgress() {
  els.progress.hidden = true;
  els.progressBar.style.width = "8%";
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function setBusy(isBusy) {
  controlsBusy = isBusy;
  els.draft.disabled = isBusy;
  els.extract.disabled = isBusy;
  setApplicationControls();
}

function normalizeUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(value);
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch (_error) {
    return String(value).trim().replace(/#.*$/, "").replace(/\/$/, "");
  }
}

function samePageUrl(left, right) {
  const normalizedLeft = normalizeUrl(left);
  const normalizedRight = normalizeUrl(right);
  return Boolean(normalizedLeft && normalizedRight && normalizedLeft === normalizedRight);
}

function requestSourceUrl(request) {
  return request?.opportunity?.source_url || request?.project?.url || "";
}

function stateSourceUrl(state) {
  return requestSourceUrl(state?.request);
}

function opportunitySourceUrl(opportunity) {
  return opportunity?.source_url || opportunity?.url || "";
}

function clearDraftOutput() {
  els.proposal.value = "";
  els.audit.textContent = "";
  els.copy.disabled = true;
  els.generatePdf.disabled = true;
  els.openPdfFolder.disabled = true;
  els.pdfStatus.textContent = "";
}

function clearApplicationOutput() {
  els.applicationStatus.textContent = "";
  setAppliedIndicator(null);
  setApplicationControls();
}

function setApplicationControls() {
  els.markApplied.disabled = controlsBusy || !els.sourceUrl.value.trim();
  els.markApplied.textContent = currentApplicationMatch ? "Refresh Log" : "Mark Applied";
}

async function updateDashboardLink() {
  const apiBase = await backendUrl();
  els.applicationsDashboardLink.href = `${apiBase}/dashboard`;
}

function setAppliedIndicator(application) {
  globalThis.JobApplicationStatusUi.setAppliedIndicator({
    els,
    application,
    setCurrentApplicationMatch: (nextApplication) => {
      currentApplicationMatch = nextApplication;
    },
    setApplicationControls,
  });
}

async function lookupApplication(sourceUrl) {
  const response = await chrome.runtime.sendMessage({ type: "LOOKUP_APPLICATION", source_url: sourceUrl });
  if (!response?.ok) throw new Error(response?.error || "Could not check application ledger.");
  return response.application || null;
}

async function refreshApplicationLookup() {
  const sourceUrl = els.sourceUrl.value.trim();
  await updateDashboardLink();
  if (!sourceUrl) {
    setAppliedIndicator(null);
    return;
  }
  const application = await lookupApplication(sourceUrl);
  setAppliedIndicator(application);
  if (application && !els.applicationStatus.textContent) {
    els.applicationStatus.textContent = "Already in application ledger.";
  }
}

function scheduleApplicationLookup(delay = 350) {
  window.clearTimeout(applicationLookupTimer);
  applicationLookupTimer = window.setTimeout(() => {
    refreshApplicationLookup().catch((error) => {
      if (!currentApplicationMatch) {
        setAppliedIndicator(null);
      }
      els.applicationStatus.textContent = error.message || "Could not check application ledger.";
    });
  }, delay);
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("No active tab found.");
  return tab;
}

async function injectContentScripts(tabId) {
  await globalThis.JobApplicationContentScripts.inject(tabId);
}

const draftForm = globalThis.JobApplicationDraftForm.create({
  els,
  supportedDraftTypes: SUPPORTED_DRAFT_TYPES,
  setApplicationControls,
  scheduleApplicationLookup,
});
const { fillOpportunity, fillRequest, readRequest, setSourceMode, syncSourceFields } = draftForm;

const postingPicker = globalThis.JobApplicationPostingPicker.create({
  els,
  activeTab,
  injectContentScripts,
  setStatus,
  sleep,
});
const applicationCount = globalThis.JobApplicationCount.create({ els });

async function extractProject() {
  const tab = await activeTab();
  await injectContentScripts(tab.id);
  return executeExtractor(tab.id);
}

async function executeExtractor(tabId) {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    func: async () => {
      if (typeof globalThis.__applicationDraftAssistantExtract !== "function") {
        return { ok: false, error: "The page extractor is unavailable." };
      }
      try {
        return { ok: true, opportunity: await globalThis.__applicationDraftAssistantExtract() };
      } catch (error) {
        return { ok: false, error: error?.message || String(error) };
      }
    },
  });
  const response = result?.result;
  if (!response?.ok) throw new Error("Could not extract job details.");
  if (!response.opportunity) throw new Error("The page extractor did not return an opportunity snapshot.");
  return response.opportunity;
}

function clearPostingPicker() {
  postingPicker.clear();
}

async function refreshPostingPicker() {
  await postingPicker.refresh();
}

async function captureActivePage({ statusText = "Review the current page snapshot before drafting." } = {}) {
  const opportunity = await extractProject();
  currentState = null;
  clearProgress();
  clearDraftOutput();
  clearApplicationOutput();
  fillOpportunity(opportunity);
  await persistEditableSnapshot();
  setStatus(statusText);
  return opportunity;
}

async function currentPageRequest() {
  const existingRequest = readRequest();
  const opportunity = await extractProject();
  const activeUrl = opportunitySourceUrl(opportunity);
  const existingUrl = requestSourceUrl(existingRequest);
  const activeSource = opportunity.source || "";
  const existingSource = existingRequest.opportunity?.source || "";

  if (!samePageUrl(existingUrl, activeUrl) || (activeSource && existingSource !== activeSource)) {
    fillOpportunity(opportunity);
    await persistEditableSnapshot();
    setStatus("Updated snapshot from the active page.");
    return readRequest();
  }

  return existingRequest;
}

function buildAuditPayload(job, draft) {
  return {
    job_id: job.id,
    draft_id: draft.id,
    draft_type: draft.draft_type,
    selected_angle: draft.selected_angle,
    role_classification: draft.role_classification,
    application_strategy: draft.application_strategy,
    selected_projects: draft.selected_projects,
    rejected_projects: draft.rejected_projects,
    decisions: draft.decisions,
    claims: draft.claims,
    warnings: draft.warnings,
    timings: job.timings,
  };
}

function currentDraftId() {
  return currentState?.result?.id || currentState?.job?.result?.id || "";
}

function currentDraftJobId() {
  return currentState?.job_id || currentState?.job?.id || "";
}

function currentPdf() {
  return globalThis.JobApplicationPdfControls.currentPdf(currentState, currentDraftId());
}

function canGeneratePdf() {
  return globalThis.JobApplicationPdfControls.canGeneratePdf(currentDraftId(), els.draftType.value);
}

function setPdfControls(pdf) {
  globalThis.JobApplicationPdfControls.setPdfControls({
    els,
    currentState,
    pdf,
    canExport: canGeneratePdf(),
  });
}

function renderDraft(job, draft) {
  const audit = JSON.stringify(buildAuditPayload(job, draft), null, 2);
  const text = draft.draft_text || "";
  els.proposal.value = text;
  els.audit.textContent = audit;
  els.copy.disabled = !text;
  setPdfControls(currentPdf());
  return audit;
}

async function persistEditableSnapshot() {
  if (currentState?.phase === "starting" || currentState?.phase === "active") return;
  await writeDraftState({
    phase: "editing",
    request: readRequest(),
    draft_text: els.proposal.value,
    audit: els.audit.textContent,
    pdf: currentPdf(),
    pdf_status: currentState?.pdf_status || null,
    pdf_error: currentState?.pdf_error || null,
    application: currentState?.application || null,
    application_status: els.applicationStatus.textContent || null,
    application_error: currentState?.application_error || null,
    error: null,
  });
}

function scheduleEditableSnapshot() {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    persistEditableSnapshot().catch(() => {});
  }, 250);
}

async function createDraftJob(request = readRequest()) {
  const response = await chrome.runtime.sendMessage({ type: "START_DRAFT_JOB", request });
  if (!response?.ok) throw new Error(response?.error || "Could not start draft job.");
  return response.state;
}

async function getDraftJob(jobId) {
  const apiBase = await backendUrl();
  const response = await fetch(`${apiBase}/draft-jobs/${jobId}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Backend returned ${response.status}`);
  }
  return response.json();
}

async function pollDraftJob(jobId) {
  const token = ++pollToken;
  while (true) {
    if (token !== pollToken) throw new Error("Draft polling was cancelled.");
    const job = await getDraftJob(jobId);
    await patchDraftState({
      phase: "active",
      job_id: job.id,
      job,
      request: currentState?.request || readRequest(),
      error: null,
    });
    setProgress(job);
    if (job.status === "succeeded") {
      if (!job.result) throw new Error("Draft job finished without a stored result.");
      return { job, draft: job.result };
    }
    if (job.status === "failed") {
      throw new Error(job.error || "Draft job failed.");
    }
    await sleep(1000);
  }
}

async function waitForStartedJob() {
  const startedAt = Date.parse(currentState?.started_at || currentState?.updated_at || nowIso());
  while (true) {
    const state = await loadDraftState();
    currentState = state;
    if (state?.phase === "active" && state.job_id) return state.job_id;
    if (state?.phase === "failed") throw new Error(state.error || "Could not start draft job.");
    if (Date.now() - startedAt > 30000) throw new Error("Draft job did not start. Check that the backend is running.");
    setProgress({ stage: "queued", elapsed_seconds: Math.max(0, (Date.now() - startedAt) / 1000) });
    await sleep(500);
  }
}

async function finishDraftJob(jobId) {
  setBusy(true);
  const { job, draft } = await pollDraftJob(jobId);
  const audit = renderDraft(job, draft);
  const outputText = draft.draft_text || "";
  await writeDraftState({
    phase: "succeeded",
    request: currentState?.request || readRequest(),
    job_id: job.id,
    job,
    result: draft,
    draft_text: outputText,
    audit,
    pdf: null,
    pdf_status: null,
    pdf_error: null,
    application: currentState?.application || null,
    application_status: els.applicationStatus.textContent || null,
    application_error: currentState?.application_error || null,
    error: null,
    started_at: currentState?.started_at,
  });
  setStatus("Draft ready.");
  clearProgress();
}

async function restoreDraftState(stateToRestore = null) {
  const state = stateToRestore || (await loadDraftState());
  if (!state) return false;

  currentState = state;
  if (state.request) fillRequest(state.request);
  if (state.draft_text) els.proposal.value = state.draft_text;
  if (state.audit) els.audit.textContent = state.audit;
  els.applicationStatus.textContent = state.application_status || "";
  setAppliedIndicator(state.application || null);
  els.copy.disabled = !els.proposal.value;
  setPdfControls(state.pdf || null);
  setApplicationControls();
  scheduleApplicationLookup(0);

  if (state.phase === "succeeded" && state.result && state.job) {
    renderDraft(state.job, state.result);
    setStatus(state.pdf_status === "generating" ? "Generating PDF..." : "Draft ready.");
    clearProgress();
    return true;
  }

  if (state.phase === "failed") {
    clearProgress();
    setStatus(state.error || "Draft failed.", "error");
    return true;
  }

  if (state.phase === "active" && state.job_id) {
    setStatus("Resuming draft job...");
    try {
      await finishDraftJob(state.job_id);
    } finally {
      setBusy(false);
    }
    return true;
  }

  if (state.phase === "starting") {
    setBusy(true);
    setProgress({ stage: "queued", elapsed_seconds: 0 });
    try {
      const jobId = await waitForStartedJob();
      await finishDraftJob(jobId);
    } finally {
      setBusy(false);
    }
    return true;
  }

  if (state.phase === "editing") {
    setStatus("Review the snapshot before drafting.");
    return true;
  }

  return false;
}

els.extract.addEventListener("click", async () => {
  try {
    pollToken += 1;
    setBusy(false);
    setStatus("Extracting job details...");
    await captureActivePage({ statusText: "Review the current page snapshot before drafting." });
  } catch (error) {
    setStatus(error.message, "error");
  }
});

els.draft.addEventListener("click", async () => {
  let wroteStartingState = false;
  try {
    setBusy(true);
    setStatus("Checking active page...");
    const request = await currentPageRequest();
    clearDraftOutput();
    await writeDraftState({
      phase: "starting",
      request,
      draft_text: "",
      audit: "",
      pdf: null,
      pdf_status: null,
      pdf_error: null,
      started_at: nowIso(),
      error: null,
    });
    wroteStartingState = true;
    setProgress({ stage: "queued", elapsed_seconds: 0 });
    const state = await createDraftJob(request);
    currentState = state;
    setProgress({ ...(state.job || {}), stage: state.job?.stage || "queued", elapsed_seconds: 0 });
    await finishDraftJob(state.job_id);
  } catch (error) {
    if (wroteStartingState) {
      await patchDraftState({ phase: "failed", error: error.message }).catch(() => {});
    }
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
});

function buildApplicationLogRequest() {
  return globalThis.JobApplicationStatusUi.buildApplicationLogRequest({
    readRequest,
    nowIso,
    currentDraftId,
    currentDraftJobId,
  });
}

async function logApplication(request) {
  const response = await chrome.runtime.sendMessage({ type: "LOG_APPLICATION", request });
  if (!response?.ok) throw new Error(response?.error || "Could not log application.");
  return response;
}

els.markApplied.addEventListener("click", async () => {
  try {
    els.markApplied.disabled = true;
    els.applicationStatus.textContent = "Logging application...";
    const response = await logApplication(buildApplicationLogRequest());
    const applicationStatus = response.queued ? "Application log queued." : "Application logged.";
    els.applicationStatus.textContent = applicationStatus;
    if (response.application) {
      setAppliedIndicator(response.application);
    }
    await applicationCount.refresh();
    await patchDraftState({
      application: response.application || currentState?.application || null,
      application_status: applicationStatus,
      application_error: response.error || null,
    });
    setStatus(applicationStatus);
  } catch (error) {
    els.applicationStatus.textContent = error.message || "Could not log application.";
    await patchDraftState({
      application_status: els.applicationStatus.textContent,
      application_error: error.message || String(error),
    }).catch(() => {});
    setStatus(error.message, "error");
  } finally {
    setApplicationControls();
  }
});

async function startPdfExport(draftId) {
  return globalThis.JobApplicationPdfControls.startPdfExport(draftId);
}

async function revealPdf(draftId) {
  return globalThis.JobApplicationPdfControls.revealPdf({
    draftId,
    backendUrl,
    responseErrorMessage,
  });
}

els.generatePdf.addEventListener("click", async () => {
  const draftId = currentDraftId();
  if (!draftId) return;
  try {
    currentState = {
      ...currentState,
      pdf_status: "generating",
      pdf_error: null,
      pdf: null,
    };
    setPdfControls(null);
    setStatus("Generating PDF...");
    const state = await startPdfExport(draftId);
    currentState = state;
    setPdfControls(currentPdf());
    setStatus("PDF generated.");
  } catch (error) {
    setPdfControls(currentPdf());
    setStatus(error.message, "error");
  }
});

els.openPdfFolder.addEventListener("click", async () => {
  const draftId = currentDraftId();
  if (!draftId) return;
  try {
    els.openPdfFolder.disabled = true;
    setStatus("Opening Finder...");
    const result = await revealPdf(draftId);
    setStatus(result.opened ? "Opened in Finder." : "Could not open Finder.", result.opened ? "idle" : "error");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setPdfControls(currentPdf());
  }
});

els.copy.addEventListener("click", async () => {
  await navigator.clipboard.writeText(els.proposal.value);
  setStatus("Copied draft.");
});

postingPicker.attachEvents();

els.settings.addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

[els.source, els.sourceUrl, els.title, els.company, els.location, els.description, els.skills, els.employmentType, els.companyContext, els.recruiterContext, els.responsibilities, els.requirements, els.niceToHaves, els.questions, els.draftType, els.notes].forEach((element) => {
  element.addEventListener("input", scheduleEditableSnapshot);
  element.addEventListener("input", () => {
    if (element === els.source) setSourceMode(els.source.value);
  });
  element.addEventListener("input", syncSourceFields);
  element.addEventListener("input", () => setPdfControls(currentPdf()));
  element.addEventListener("input", () => setApplicationControls());
  element.addEventListener("input", () => {
    if (element === els.sourceUrl) scheduleApplicationLookup();
  });
  element.addEventListener("change", scheduleEditableSnapshot);
  element.addEventListener("change", () => {
    if (element === els.source) setSourceMode(els.source.value);
  });
  element.addEventListener("change", syncSourceFields);
  element.addEventListener("change", () => setPdfControls(currentPdf()));
  element.addEventListener("change", () => setApplicationControls());
  element.addEventListener("change", () => {
    if (element === els.sourceUrl) scheduleApplicationLookup(0);
  });
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes[DRAFT_STATE_KEY]?.newValue) return;
  const nextState = changes[DRAFT_STATE_KEY].newValue;
  const previousPdfStatus = currentState?.pdf_status || "";
  currentState = nextState;
  setPdfControls(currentPdf());
  if (nextState.pdf_status === "generating") {
    setStatus("Generating PDF...");
  } else if (previousPdfStatus === "generating" && nextState.pdf_status === "succeeded") {
    setStatus("PDF generated.");
  } else if (previousPdfStatus === "generating" && nextState.pdf_status === "failed") {
    setStatus(nextState.pdf_error || "PDF generation failed.", "error");
  }
});

async function initializePopup() {
  try {
    applicationCount.initialize().catch(() => {});
    setStatus("Reading active page...");
    await refreshPostingPicker().catch(() => clearPostingPicker());
    const opportunity = await extractProject();
    const state = await loadDraftState();
    if (state && samePageUrl(stateSourceUrl(state), opportunitySourceUrl(opportunity))) {
      await restoreDraftState(state);
      return;
    }
    currentState = null;
    clearProgress();
    clearDraftOutput();
    clearApplicationOutput();
    fillOpportunity(opportunity);
    await persistEditableSnapshot();
    setStatus("Review the current page snapshot before drafting.");
  } catch (error) {
    await refreshPostingPicker().catch(() => clearPostingPicker());
    const restored = await restoreDraftState();
    if (restored) {
      setStatus(`Showing saved snapshot. ${error.message || "Active page could not be read."}`, "error");
      return;
    }
    setStatus(error.message || "Open a supported job page, then click Extract.", "error");
  }
}

initializePopup();

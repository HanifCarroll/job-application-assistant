const DEFAULT_API_BASE = "http://127.0.0.1:8787";
const API_BASE_KEY = "jobApplicationDraftBackendUrl";
const DRAFT_STATE_KEY = "jobApplicationDraftState";
const APPLICATION_QUEUE_KEY = "jobApplicationLogQueue";
const APPLICATION_PENDING_KEY = "jobApplicationPendingApplication";
const APPLICATION_LAST_KEY = "jobApplicationLastLogged";
const APPLICATION_LEDGER_UPDATED_KEY = "jobApplicationLedgerUpdatedAt";
const POSTING_SIDE_PANEL_PATH = "sidepanel.html";
const DRAFT_SIDE_PANEL_PATH = "draft_sidepanel.html";

function nowIso() {
  return new Date().toISOString();
}

function closeTabSoon(tabId) {
  if (!tabId) return;
  setTimeout(() => {
    chrome.tabs.remove(tabId).catch(() => {});
  }, 750);
}

function isDiceUrl(value) {
  try {
    const url = new URL(value || "");
    return url.hostname === "dice.com" || url.hostname.endsWith(".dice.com");
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

function isPostingPickerUrl(value) {
  return isDiceUrl(value) || isIndeedResultsUrl(value) || isLinkedInResultsUrl(value);
}

function sidePanelPathForUrl(url) {
  return isPostingPickerUrl(url) ? POSTING_SIDE_PANEL_PATH : DRAFT_SIDE_PANEL_PATH;
}

async function configureActionForTab(tabId, url) {
  if (!tabId) return;
  const sidePanelPath = sidePanelPathForUrl(url);
  await chrome.action.setPopup({ tabId, popup: "" });
  if (chrome.sidePanel?.setOptions) {
    await chrome.sidePanel.setOptions({
      tabId,
      path: sidePanelPath,
      enabled: true,
    });
  }
}

async function configureActiveTabs() {
  const tabs = await chrome.tabs.query({});
  await Promise.all(tabs.map((tab) => configureActionForTab(tab.id, tab.url).catch(() => {})));
}

function enableSidePanelActionClick() {
  if (!chrome.sidePanel?.setPanelBehavior) return;
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
}

function userErrorMessage(error) {
  const message = error?.message || String(error);
  if (message === "Failed to fetch" || message.includes("Load failed") || message.includes("NetworkError")) {
    return "Backend offline. Start it with: uv --no-config run jaa serve";
  }
  return message;
}

async function saveDraftState(state) {
  await chrome.storage.local.set({
    [DRAFT_STATE_KEY]: {
      ...state,
      updated_at: nowIso(),
    },
  });
}

async function loadDraftState() {
  const stored = await chrome.storage.local.get(DRAFT_STATE_KEY);
  return stored[DRAFT_STATE_KEY] || {};
}

async function patchDraftState(patch) {
  const existing = await loadDraftState();
  await saveDraftState({ ...existing, ...patch });
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

function requestSourceUrl(request) {
  return request?.opportunity?.source_url || request?.project?.url || "";
}

function currentDraftId(state) {
  return state?.result?.id || state?.job?.result?.id || "";
}

function draftLinkForOpportunity(state, opportunity) {
  if (!state?.request || normalizeUrl(requestSourceUrl(state.request)) !== normalizeUrl(opportunity?.source_url)) {
    return { draft_id: "", draft_job_id: "" };
  }
  return {
    draft_id: currentDraftId(state),
    draft_job_id: state.job_id || state.job?.id || "",
  };
}

async function postApplicationLog(request) {
  const apiBase = await backendUrl();
  const response = await fetch(`${apiBase}/applications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json();
}

async function lookupApplication(sourceUrl) {
  const apiBase = await backendUrl();
  const response = await fetch(`${apiBase}/applications/lookup?source_url=${encodeURIComponent(sourceUrl || "")}`);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json();
}

async function applicationSummary(days) {
  const apiBase = await backendUrl();
  const response = await fetch(`${apiBase}/applications/summary?days=${encodeURIComponent(String(days || 1))}`);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json();
}

async function lookupDraft(sourceUrl) {
  const apiBase = await backendUrl();
  const response = await fetch(`${apiBase}/drafts/lookup?source_url=${encodeURIComponent(sourceUrl || "")}`);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json();
}

async function revealPdf(draftId) {
  const apiBase = await backendUrl();
  const response = await fetch(`${apiBase}/drafts/${encodeURIComponent(draftId)}/pdf/reveal`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json();
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}

async function downloadPdf(draftId) {
  const apiBase = await backendUrl();
  const response = await fetch(`${apiBase}/drafts/${encodeURIComponent(draftId)}/pdf`);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return {
    ok: true,
    data_base64: arrayBufferToBase64(await response.arrayBuffer()),
    mime_type: response.headers.get("content-type") || "application/pdf",
  };
}

async function loadApplicationQueue() {
  const stored = await chrome.storage.local.get(APPLICATION_QUEUE_KEY);
  return Array.isArray(stored[APPLICATION_QUEUE_KEY]) ? stored[APPLICATION_QUEUE_KEY] : [];
}

async function queueApplicationLog(request, error) {
  const queue = await loadApplicationQueue();
  queue.push({
    request,
    queued_at: nowIso(),
    error: error || "",
  });
  await chrome.storage.local.set({ [APPLICATION_QUEUE_KEY]: queue });
}

async function flushQueuedApplicationLogs() {
  const queue = await loadApplicationQueue();
  if (!queue.length) return { ok: true, flushed: 0, remaining: 0 };
  const remaining = [];
  let flushed = 0;
  for (const item of queue) {
    try {
      const application = await postApplicationLog(item.request);
      await chrome.storage.local.set({ [APPLICATION_LAST_KEY]: application });
      flushed += 1;
    } catch (error) {
      remaining.push({
        ...item,
        error: error?.message || String(error),
      });
    }
  }
  await chrome.storage.local.set({ [APPLICATION_QUEUE_KEY]: remaining });
  if (flushed > 0) {
    await chrome.storage.local.set({ [APPLICATION_LEDGER_UPDATED_KEY]: nowIso() });
  }
  return { ok: remaining.length === 0, flushed, remaining: remaining.length };
}

async function logApplication(request) {
  await flushQueuedApplicationLogs();
  try {
    const application = await postApplicationLog(request);
    await chrome.storage.local.set({
      [APPLICATION_LAST_KEY]: application,
      [APPLICATION_LEDGER_UPDATED_KEY]: nowIso(),
    });
    return { ok: true, queued: false, application };
  } catch (error) {
    const message = userErrorMessage(error);
    await queueApplicationLog(request, message);
    return { ok: true, queued: true, error: message };
  }
}

async function capturePendingApplication(opportunity) {
  if (!opportunity?.source_url) {
    return { ok: false, error: "No source URL was captured for this application." };
  }
  await chrome.storage.local.set({
    [APPLICATION_PENDING_KEY]: {
      opportunity,
      source: opportunity.source || "",
      source_url: opportunity.source_url || "",
      captured_at: nowIso(),
    },
  });
  return { ok: true };
}

async function loadPendingApplication(source) {
  const stored = await chrome.storage.local.get(APPLICATION_PENDING_KEY);
  const pending = stored[APPLICATION_PENDING_KEY] || null;
  if (!pending) return null;
  if (source && pending.source && pending.source !== source) return null;
  return pending;
}

async function logConfirmedApplication(message) {
  const pending = await loadPendingApplication(message.source || "");
  const opportunity = message.opportunity || pending?.opportunity;
  if (!opportunity) {
    return { ok: false, error: "No pending application snapshot was available." };
  }
  const state = await loadDraftState();
  const draftLink = draftLinkForOpportunity(state, opportunity);
  const result = await logApplication({
    opportunity,
    applied_at: nowIso(),
    draft_id: draftLink.draft_id,
    draft_job_id: draftLink.draft_job_id,
    detected_by: "platform_confirmation",
    warnings: message.warnings || [],
  });
  if (result.ok) {
    await chrome.storage.local.remove(APPLICATION_PENDING_KEY);
  }
  return result;
}

async function startDraftJob(request) {
  const startedAt = nowIso();
  await saveDraftState({
    phase: "starting",
    request,
    started_at: startedAt,
    draft_text: "",
    audit: "",
    error: null,
  });

  try {
    const apiBase = await backendUrl();
    const response = await fetch(`${apiBase}/draft-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error(await responseErrorMessage(response));
    }

    const job = await response.json();
    const state = {
      phase: "active",
      request,
      job_id: job.id,
      job,
      started_at: startedAt,
      draft_text: "",
      audit: "",
      error: null,
    };
    await saveDraftState(state);
    return { ok: true, state };
  } catch (error) {
    const message = userErrorMessage(error);
    await saveDraftState({
      phase: "failed",
      request,
      started_at: startedAt,
      draft_text: "",
      audit: "",
      error: message,
    });
    return { ok: false, error: message };
  }
}

async function getDraftJob(jobId) {
  const apiBase = await backendUrl();
  const response = await fetch(`${apiBase}/draft-jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json();
}

async function startPdfExport(draftId) {
  const startedAt = nowIso();
  await patchDraftState({
    pdf_status: "generating",
    pdf_error: null,
    pdf: null,
    pdf_started_at: startedAt,
  });

  try {
    const apiBase = await backendUrl();
    const response = await fetch(`${apiBase}/drafts/${encodeURIComponent(draftId)}/pdf`, { method: "POST" });
    if (!response.ok) {
      throw new Error(await responseErrorMessage(response));
    }

    const pdf = await response.json();
    const state = {
      ...(await loadDraftState()),
      pdf_status: "succeeded",
      pdf_error: null,
      pdf,
      pdf_finished_at: nowIso(),
    };
    await saveDraftState(state);
    return { ok: true, state, pdf };
  } catch (error) {
    const message = userErrorMessage(error);
    const state = {
      ...(await loadDraftState()),
      pdf_status: "failed",
      pdf_error: message,
      pdf_finished_at: nowIso(),
    };
    await saveDraftState(state);
    return { ok: false, state, error: message };
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "GET_BACKEND_URL") {
    backendUrl()
      .then((apiBase) => sendResponse({ ok: true, api_base: apiBase }))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "START_DRAFT_JOB") {
    startDraftJob(message.request)
      .then((response) => sendResponse(response))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "GET_DRAFT_JOB") {
    getDraftJob(message.job_id)
      .then((job) => sendResponse({ ok: true, job }))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "START_PDF_EXPORT") {
    startPdfExport(message.draft_id)
      .then((response) => sendResponse(response))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "LOG_APPLICATION") {
    logApplication(message.request)
      .then((response) => sendResponse(response))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "LOOKUP_APPLICATION") {
    lookupApplication(message.source_url)
      .then((response) => sendResponse({ ok: true, ...response }))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "APPLICATION_SUMMARY") {
    applicationSummary(message.days)
      .then((response) => sendResponse({ ok: true, ...response }))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "LOOKUP_DRAFT") {
    lookupDraft(message.source_url)
      .then((response) => sendResponse({ ok: true, ...response }))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "REVEAL_PDF") {
    revealPdf(message.draft_id)
      .then((response) => sendResponse({ ok: true, ...response }))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "DOWNLOAD_PDF") {
    downloadPdf(message.draft_id)
      .then((response) => sendResponse(response))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "APPLICATION_CAPTURE_PENDING") {
    capturePendingApplication(message.opportunity)
      .then((response) => sendResponse(response))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "APPLICATION_CONFIRMED") {
    logConfirmedApplication(message)
      .then((response) => {
        sendResponse(response);
        if (response?.ok && message.close_tab && _sender.tab?.id) {
          closeTabSoon(_sender.tab.id);
        }
      })
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  if (message?.type === "FLUSH_APPLICATION_LOGS") {
    flushQueuedApplicationLogs()
      .then((response) => sendResponse(response))
      .catch((error) => sendResponse({ ok: false, error: userErrorMessage(error) }));
    return true;
  }

  return false;
});

chrome.action.onClicked.addListener((tab) => {
  if (!tab?.id) return;
  configureActionForTab(tab.id, tab.url).catch(() => {});
  if (!chrome.sidePanel?.open) return;
  try {
    const opened = chrome.sidePanel.open({ tabId: tab.id });
    if (opened?.catch) opened.catch(() => {});
  } catch (_error) {
    // Ignore side panel open failures; the action is already configured for the active tab.
  }
});

chrome.tabs.onActivated.addListener(({ tabId }) => {
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError) return;
    configureActionForTab(tab.id, tab.url).catch(() => {});
  });
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!changeInfo.url && changeInfo.status !== "complete") return;
  configureActionForTab(tabId, changeInfo.url || tab.url).catch(() => {});
});

flushQueuedApplicationLogs().catch(() => {});
enableSidePanelActionClick();
configureActiveTabs().catch(() => {});

if (chrome.runtime.onStartup) {
  chrome.runtime.onStartup.addListener(() => {
    flushQueuedApplicationLogs().catch(() => {});
    enableSidePanelActionClick();
    configureActiveTabs().catch(() => {});
  });
}

if (chrome.runtime.onInstalled) {
  chrome.runtime.onInstalled.addListener(() => {
    enableSidePanelActionClick();
    configureActiveTabs().catch(() => {});
  });
}

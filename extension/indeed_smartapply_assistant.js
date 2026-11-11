(() => {
  if (globalThis.__indeedSmartApplyAssistantLoaded) {
    return;
  }
  globalThis.__indeedSmartApplyAssistantLoaded = true;

  const AUTO_STARTED_KEY = "jobApplicationIndeedCoverLetterAutoStarted";
  const AUTO_CONTINUE_KEY = "jobApplicationIndeedAutoContinue";
  const AUTO_SUBMIT_KEY = "jobApplicationIndeedSubmitAutoClicked";
  const AUTO_SKIP_UPLOAD_KEY = "jobApplicationIndeedNoUploadAvailable";
  const OPPORTUNITY_CACHE_KEY = "jobApplicationIndeedOpportunity";
  const AUTO_CONTINUE_MAX_ATTEMPTS = 3;
  const indeedOpportunity = globalThis.JobApplicationIndeedOpportunity;
  const coverLetterRuns = globalThis.JobApplicationCoverLetterRuns;

  let activeRun = null;
  let currentPdf = null;
  let currentDraftId = "";
  let autoStartedForRunId = "";
  let stepPollTimer = 0;
  let stepPollCount = 0;
  let lastKnownHref = location.href;
  let smartApplyAutomationTimer = 0;
  let smartApplyObserver = null;

  function clean(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function jobKey() {
    return indeedOpportunity?.smartApplyJobKey?.() || "";
  }

  function runId() {
    return `indeed:${jobKey() || location.pathname}`;
  }

  function isIndeedSmartApply() {
    return Boolean(indeedOpportunity?.isIndeedSmartApplyUrl?.());
  }

  function isContactStep() {
    return location.pathname.includes("/contact-info-module") || Boolean(document.querySelector('[data-testid="contact-info-page"]'));
  }

  function isLocationStep() {
    return location.pathname.includes("/profile-location");
  }

  function isResumeStep() {
    return location.pathname.includes("/resume-selection-module") || Boolean(document.querySelector('[data-testid="resume-selection-file-resume-radio-card-input"]'));
  }

  function isReviewStep() {
    return location.pathname.includes("/review-module") || Boolean(document.querySelector('[data-testid="submit-application-button"]'));
  }

  function isSuccessStep() {
    const text = clean(document.body?.textContent || "");
    return (
      location.pathname.includes("/post-apply") ||
      location.pathname.includes("/success") ||
      Boolean(document.querySelector('[data-testid="indeed-apply-confirmation"], [data-testid="ia-ApplicationSubmitted"]')) ||
      text.includes("Application submitted") ||
      text.includes("Your application was submitted")
    );
  }

  function captchaIssuePresent() {
    return clean(document.body?.textContent || "").includes("Could not connect to the reCAPTCHA service");
  }

  function jobScopedKey(prefix) {
    return `${prefix}:${runId()}:${location.pathname}`;
  }

  function sessionCount(key) {
    const count = Number.parseInt(sessionStorage.getItem(key) || "0", 10);
    return Number.isFinite(count) && count > 0 ? count : 0;
  }

  function usableButton(button) {
    return (
      button instanceof HTMLButtonElement &&
      !button.disabled &&
      button.getAttribute("aria-disabled") !== "true" &&
      button.offsetParent !== null
    );
  }

  function buttonText(button) {
    return clean(button?.textContent || button?.getAttribute("aria-label") || "");
  }

  function wizardButton(label) {
    return Array.from(document.querySelectorAll("button")).find((button) => usableButton(button) && buttonText(button) === label) || null;
  }

  function continueButton() {
    const declared = document.querySelector('[data-testid="continue-button"]');
    if (usableButton(declared)) return declared;
    return wizardButton("Continue");
  }

  function submitButton() {
    const declared = document.querySelector('[data-testid="submit-application-button"]');
    if (usableButton(declared)) return declared;
    return wizardButton("Submit your application");
  }

  function supportingDocumentsSection() {
    return document.querySelector('[data-testid="supportingDocumentsSection"]');
  }

  function supportingDocumentsAddControl() {
    const section = supportingDocumentsSection();
    if (!section) return null;
    return Array.from(section.querySelectorAll("button, a")).find((element) => {
      return clean(element.textContent || element.getAttribute("aria-label") || "") === "Add";
    }) || null;
  }

  function coverLetterFileInput() {
    const inputs = Array.from(document.querySelectorAll('input[type="file"]')).filter((input) => input instanceof HTMLInputElement);
    return inputs.find((input) => (input.getAttribute("accept") || "").includes(".pdf")) || inputs[0] || null;
  }

  function uploadOpportunityAvailable() {
    return Boolean(coverLetterFileInput() || supportingDocumentsAddControl());
  }

  function coverLetterAttachmentPresent() {
    const section = supportingDocumentsSection();
    if (!section) return false;
    const text = clean(section.textContent || "");
    if (currentPdf?.filename) return text.includes(currentPdf.filename);
    return /\.pdf/i.test(text) && !text.includes("No cover letter");
  }

  function updateRun(patch) {
    const id = runId();
    if (!id || !coverLetterRuns?.upsert) return;
    coverLetterRuns.upsert(id, {
      source: "indeed",
      job_id: id,
      wizard_url: location.href,
      ...patch,
    }).catch(() => {});
  }

  function setRunStatus(message, { busy = false, label = "", status = "" } = {}) {
    updateRun({
      busy,
      message,
      primary_label: label || (busy ? "Working..." : "Regenerate PDF"),
      status: status || (busy ? "working" : "waiting"),
    });
  }

  function opportunitySnapshot() {
    const snapshot = indeedOpportunity?.smartApplyOpportunity?.();
    const cached = cachedOpportunitySnapshot();
    if (!snapshot && !cached) throw new Error("Indeed smartapply job details were not found.");
    if (!snapshot) return cached;
    if (snapshot.description) return snapshot;
    if (cached?.description) {
      return {
        ...cached,
        captured_at: snapshot.captured_at || cached.captured_at,
        source_url: snapshot.source_url || cached.source_url,
        title: snapshot.title || cached.title,
        company: snapshot.company || cached.company,
        location: snapshot.location || cached.location,
      };
    }
    return snapshot;
  }

  function opportunityCacheKey() {
    return `${OPPORTUNITY_CACHE_KEY}:${runId()}`;
  }

  function cachedOpportunitySnapshot() {
    try {
      const cached = JSON.parse(sessionStorage.getItem(opportunityCacheKey()) || "null");
      return cached && typeof cached === "object" ? cached : null;
    } catch (_error) {
      return null;
    }
  }

  function cacheOpportunitySnapshot() {
    const snapshot = indeedOpportunity?.smartApplyOpportunity?.();
    if (!snapshot?.description) return;
    sessionStorage.setItem(opportunityCacheKey(), JSON.stringify(snapshot));
  }

  function startCoverLetterFlow(options = {}) {
    if (activeRun) return;
    activeRun = runCoverLetterFlow(options)
      .catch((error) => setRunStatus(error.message || String(error), { label: "Try again", status: "failed" }))
      .finally(() => {
        activeRun = null;
      });
  }

  async function runCoverLetterFlow({ force = false } = {}) {
    if (!isReviewStep() || !uploadOpportunityAvailable()) return;
    const id = runId();
    const autoKey = `${AUTO_STARTED_KEY}:${id}`;
    if (!force && sessionStorage.getItem(autoKey)) return;
    sessionStorage.setItem(autoKey, nowIso());

    setRunStatus("Reading Indeed job details...", { busy: true, status: "reading" });
    const opportunity = opportunitySnapshot();
    updateRun({
      company: opportunity.company || "",
      source_url: opportunity.source_url || "",
      title: opportunity.title || "",
    });

    const request = {
      opportunity,
      draft_type: "cover_letter",
      user_notes: "",
      style: "concise",
    };

    const draft = await existingOrGeneratedDraft(opportunity.source_url, request);
    currentDraftId = draft.id;
    updateRun({ draft_id: draft.id });
    setRunStatus("Generating PDF...", { busy: true, status: "pdf_generating" });
    const pdf = await startPdfExport(draft.id);
    currentPdf = pdf;
    updateRun({ draft_id: draft.id, pdf });
    setRunStatus("Attaching generated PDF...", { busy: true, label: "Attaching...", status: "attaching" });
    await attachGeneratedPdf(pdf, draft.id);
    setRunStatus("PDF attached. Submitting...", { busy: true, label: "Submitting...", status: "submitting" });
    scheduleSmartApplyAutomation(0);
  }

  async function existingOrGeneratedDraft(sourceUrl, request) {
    const existing = await chrome.runtime.sendMessage({ type: "LOOKUP_DRAFT", source_url: sourceUrl });
    if (existing?.ok && existing.matched && existing.draft?.id) {
      setRunStatus("Using existing draft...", { busy: true, status: "drafting" });
      return existing.draft;
    }
    if (existing && !existing.ok) {
      throw new Error(existing.error || "Could not check for an existing draft.");
    }

    setRunStatus("Starting cover letter draft...", { busy: true, status: "drafting" });
    const started = await chrome.runtime.sendMessage({ type: "START_DRAFT_JOB", request });
    if (!started?.ok) throw new Error(started?.error || "Could not start the cover letter draft.");
    const draftJobId = started.state?.job_id;
    if (!draftJobId) throw new Error("Draft job did not return an id.");
    return pollDraftJob(draftJobId);
  }

  async function pollDraftJob(draftJobId) {
    const startedAt = Date.now();
    while (Date.now() - startedAt < 240000) {
      const response = await chrome.runtime.sendMessage({ type: "GET_DRAFT_JOB", job_id: draftJobId });
      if (!response?.ok) throw new Error(response?.error || "Could not check draft job status.");
      const job = response.job;
      updateRun({ draft_job_id: job.id || draftJobId });
      setRunStatus(`Drafting cover letter: ${job.stage || job.status}...`, { busy: true, status: "drafting" });
      if (job.status === "succeeded") {
        if (!job.result?.id) throw new Error("Draft job succeeded without a draft id.");
        return job.result;
      }
      if (job.status === "failed") throw new Error(job.error || "Cover letter draft failed.");
      await sleep(1200);
    }
    throw new Error("Cover letter draft timed out.");
  }

  async function startPdfExport(draftId) {
    const response = await chrome.runtime.sendMessage({ type: "START_PDF_EXPORT", draft_id: draftId });
    if (!response?.ok) throw new Error(response?.error || "Could not generate PDF.");
    if (!response.pdf?.download_url || !response.pdf?.filename) throw new Error("PDF export did not return a downloadable file.");
    return response.pdf;
  }

  function bytesFromBase64(value) {
    const binary = atob(value || "");
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  async function generatedPdfFile(pdf, draftId) {
    const response = await chrome.runtime.sendMessage({ type: "DOWNLOAD_PDF", draft_id: draftId });
    if (!response?.ok || !response.data_base64) throw new Error(response?.error || "Could not download the generated PDF.");
    return new File([bytesFromBase64(response.data_base64)], pdf.filename || "cover-letter.pdf", {
      type: response.mime_type || "application/pdf",
    });
  }

  async function waitForCoverLetterFileInput(timeoutMs = 8000) {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      const input = coverLetterFileInput();
      if (input) return input;
      await sleep(200);
    }
    return null;
  }

  async function waitForCoverLetterAttachment(timeoutMs = 8000) {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      if (coverLetterAttachmentPresent()) return true;
      await sleep(200);
    }
    return false;
  }

  async function revealCoverLetterFileInput() {
    const existingInput = coverLetterFileInput();
    if (existingInput) return existingInput;
    const add = supportingDocumentsAddControl();
    if (!add) return null;
    add.click();
    return waitForCoverLetterFileInput();
  }

  async function attachGeneratedPdf(pdf, draftId) {
    const input = await revealCoverLetterFileInput();
    if (!input) throw new Error("Indeed cover-letter upload input was not found.");
    const transfer = new DataTransfer();
    transfer.items.add(await generatedPdfFile(pdf, draftId));
    input.files = transfer.files;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    if (!(await waitForCoverLetterAttachment())) {
      throw new Error("Indeed did not show the generated PDF as attached.");
    }
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function knownContinueStep() {
    return isContactStep() || isLocationStep() || isResumeStep();
  }

  function clickKnownContinueIfReady() {
    if (!isIndeedSmartApply() || !knownContinueStep()) return false;
    const next = continueButton();
    if (!next) return false;

    const key = jobScopedKey(AUTO_CONTINUE_KEY);
    const attempts = sessionCount(key);
    if (attempts >= AUTO_CONTINUE_MAX_ATTEMPTS) return false;
    sessionStorage.setItem(key, String(attempts + 1));

    cacheOpportunitySnapshot();
    setRunStatus("Continuing Indeed application...", { busy: true, label: "Continuing...", status: "continuing" });
    window.setTimeout(() => next.click(), 0);
    return true;
  }

  async function capturePendingApplication() {
    const opportunity = opportunitySnapshot();
    await chrome.runtime.sendMessage({ type: "APPLICATION_CAPTURE_PENDING", opportunity });
    return opportunity;
  }

  function clickSubmitIfReady() {
    if (!isIndeedSmartApply() || !isReviewStep() || isSuccessStep()) return false;
    const submit = submitButton();
    if (!submit) return false;

    const key = `${AUTO_SUBMIT_KEY}:${runId()}`;
    if (sessionStorage.getItem(key)) return false;
    sessionStorage.setItem(key, nowIso());

    setRunStatus("Submitting Indeed application...", { busy: true, label: "Submitting...", status: "submitting" });
    window.setTimeout(() => {
      capturePendingApplication()
        .catch(() => {})
        .then(() => {
          if (submit.isConnected && !submit.disabled) submit.click();
        });
    }, 0);
    return true;
  }

  function handleReviewStep() {
    if (!isReviewStep()) return false;
    if (uploadOpportunityAvailable() && !coverLetterAttachmentPresent()) {
      const id = runId();
      if (autoStartedForRunId === id || activeRun) return true;
      autoStartedForRunId = id;
      startCoverLetterFlow();
      return true;
    }
    if (!uploadOpportunityAvailable()) {
      sessionStorage.setItem(`${AUTO_SKIP_UPLOAD_KEY}:${runId()}`, nowIso());
    }
    return clickSubmitIfReady();
  }

  function markReviewBlockedIfNeeded() {
    if (!isReviewStep() || isSuccessStep()) return false;
    const key = `${AUTO_SUBMIT_KEY}:${runId()}`;
    if (!sessionStorage.getItem(key) || !captchaIssuePresent()) return false;
    setRunStatus("Indeed submission needs manual attention: reCAPTCHA is blocking submission.", {
      busy: false,
      label: "Regenerate PDF",
      status: "needs_attention",
    });
    return true;
  }

  function markSubmittedIfSuccess() {
    if (!isSuccessStep()) return false;
    coverLetterRuns?.remove?.(runId()).catch(() => {});
    return true;
  }

  function markManualQuestionsIfNeeded() {
    if (!isIndeedSmartApply() || isSuccessStep() || knownContinueStep() || isReviewStep()) return false;
    setRunStatus("Application questions need manual answers in this Indeed tab.", {
      busy: false,
      label: "Regenerate PDF",
      status: "needs_attention",
    });
    return true;
  }

  function continueSmartApplyAutomation() {
    if (!isIndeedSmartApply()) return false;
    if (markSubmittedIfSuccess()) return true;
    if (clickKnownContinueIfReady()) return true;
    if (handleReviewStep()) return true;
    if (markReviewBlockedIfNeeded()) return true;
    return markManualQuestionsIfNeeded();
  }

  function scheduleSmartApplyAutomation(delay = 250) {
    window.clearTimeout(smartApplyAutomationTimer);
    smartApplyAutomationTimer = window.setTimeout(() => {
      continueSmartApplyAutomation();
    }, delay);
  }

  function installSmartApplyAutomationWatcher() {
    if (smartApplyObserver) return;
    smartApplyObserver = new MutationObserver(() => scheduleSmartApplyAutomation());
    smartApplyObserver.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
      attributeFilter: ["aria-disabled", "data-testid", "disabled", "type"],
    });
    window.setInterval(() => scheduleSmartApplyAutomation(0), 1200);
  }

  function maybeStart() {
    continueSmartApplyAutomation();
  }

  function startStepPolling() {
    window.clearInterval(stepPollTimer);
    stepPollCount = 0;
    pollForKnownStep();
    stepPollTimer = window.setInterval(pollForKnownStep, 1000);
  }

  function pollForKnownStep() {
    stepPollCount += 1;
    maybeStart();
    if (!isIndeedSmartApply() || isSuccessStep() || stepPollCount >= 120) {
      window.clearInterval(stepPollTimer);
    }
  }

  function handleRouteChange({ force = false } = {}) {
    if (!force && location.href === lastKnownHref) return;
    lastKnownHref = location.href;
    window.clearInterval(stepPollTimer);
    if (!isIndeedSmartApply()) return;
    startStepPolling();
    scheduleSmartApplyAutomation();
  }

  function installRouteWatcher() {
    for (const method of ["pushState", "replaceState"]) {
      const original = history[method];
      history[method] = function patchedHistoryMethod(...args) {
        const result = original.apply(this, args);
        window.setTimeout(() => handleRouteChange(), 0);
        return result;
      };
    }
    window.addEventListener("popstate", () => handleRouteChange());
    window.setInterval(() => handleRouteChange(), 1000);
  }

  if (globalThis.chrome?.runtime?.onMessage && !globalThis.__indeedSmartApplyAssistantMessageListenerInstalled) {
    globalThis.__indeedSmartApplyAssistantMessageListenerInstalled = true;
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message?.type === "INDEED_COVER_LETTER_START") {
        startCoverLetterFlow({ force: Boolean(message.force) });
        sendResponse({ ok: true });
        return false;
      }
      return false;
    });
  }

  installRouteWatcher();
  installSmartApplyAutomationWatcher();
  window.setTimeout(() => handleRouteChange({ force: true }), 600);
})();

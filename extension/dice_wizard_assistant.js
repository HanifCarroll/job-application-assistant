(() => {
  if (globalThis.__diceCoverLetterAssistantLoaded) {
    return;
  }
  globalThis.__diceCoverLetterAssistantLoaded = true;

  const AUTO_STARTED_KEY = "jobApplicationDiceCoverLetterAutoStarted";
  const AUTO_NEXT_KEY = "jobApplicationDiceCoverLetterAutoNext";
  const AUTO_NEXT_MAX_ATTEMPTS = 3;
  const AUTO_SUBMIT_KEY = "jobApplicationDiceSubmitAutoClicked";
  const COVER_LETTER_SELECTOR = '[data-testid="cover-letter"]';
  const diceOpportunity = globalThis.JobApplicationDiceOpportunity;
  const coverLetterRuns = globalThis.JobApplicationCoverLetterRuns;

  function clean(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function jobApplicationId() {
    return location.pathname.match(/^\/job-applications\/([^/]+)\/wizard/)?.[1] || "";
  }

  function isDiceWizard() {
    return location.hostname.includes("dice.com") && Boolean(jobApplicationId());
  }

  function isDiceWizardSuccessStep() {
    return location.hostname.includes("dice.com") && /^\/job-applications\/[^/]+\/wizard\/success\/?$/.test(location.pathname);
  }

  function coverLetterSection() {
    const declared = document.querySelector(COVER_LETTER_SELECTOR);
    if (declared) return declared;
    return Array.from(document.querySelectorAll("form > div")).find((section) => {
      const labels = Array.from(section.querySelectorAll("span")).map((label) => clean(label.textContent));
      return labels.includes("Cover letter") && !labels.some((label) => label === "Resume" || label.startsWith("Resume "));
    }) || null;
  }

  function coverLetterFileInput() {
    const section = coverLetterSection();
    const scopedInput = section?.querySelector('input[type="file"]');
    if (scopedInput instanceof HTMLInputElement) return scopedInput;
    const fileInputs = Array.from(document.querySelectorAll('input[type="file"]')).filter((input) => {
      return input instanceof HTMLInputElement && (input.getAttribute("accept") || "").includes(".pdf");
    });
    return fileInputs.length === 1 ? fileInputs[0] : null;
  }

  function isResumeCoverLetterStep() {
    if (!isDiceWizard()) return false;
    return Boolean(
      coverLetterSection() ||
        coverLetterFileInput() ||
        document.querySelector('input[type="file"]')
    );
  }

  let panelStatus = "";
  let panelBusy = false;
  let panelLabel = "";
  let panelStatusKind = "";

  function setPanelStatus(message, { busy = false, label = "", status = "" } = {}) {
    const resolvedLabel = label || (busy ? "Working..." : "Generate PDF");
    const resolvedStatus = status || (busy ? "working" : "waiting");
    if (message === panelStatus && busy === panelBusy && resolvedLabel === panelLabel && resolvedStatus === panelStatusKind) {
      return;
    }
    panelStatus = message;
    panelBusy = busy;
    panelLabel = resolvedLabel;
    panelStatusKind = resolvedStatus;
    updateRun({
      busy,
      message,
      primary_label: resolvedLabel,
      status: resolvedStatus,
    });
  }

  let activeRun = null;
  let currentPdf = null;
  let currentDraftId = "";
  let autoStartedForJobId = "";
  let stepPollTimer = 0;
  let stepPollCount = 0;
  let lastKnownHref = location.href;
  let wizardAutomationTimer = 0;
  let wizardObserver = null;

  function updateRun(patch) {
    const jobId = jobApplicationId();
    if (!jobId || !coverLetterRuns?.upsert) return;
    coverLetterRuns.upsert(jobId, {
      wizard_url: location.href,
      ...patch,
    }).catch(() => {});
  }

  function startCoverLetterFlow(options = {}) {
    if (activeRun) return;
    activeRun = runCoverLetterFlow(options)
      .catch((error) => setPanelStatus(error.message || String(error), { label: "Try again", status: "failed" }))
      .finally(() => {
        activeRun = null;
      });
  }

  async function runCoverLetterFlow({ force = false } = {}) {
    if (!isResumeCoverLetterStep()) return;
    const jobId = jobApplicationId();
    const autoKey = `${AUTO_STARTED_KEY}:${jobId}`;
    if (!force && sessionStorage.getItem(autoKey)) return;
    sessionStorage.setItem(autoKey, new Date().toISOString());

    setPanelStatus("Reading Dice job details...", { busy: true, status: "reading" });
    const opportunity = await diceDetailOpportunity(jobId);
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
    setPanelStatus("Generating PDF...", { busy: true, status: "pdf_generating" });
    const pdf = await startPdfExport(draft.id);
    await showPdfActions(pdf, draft.id);
    try {
      setPanelStatus("Attaching generated PDF...", { busy: true, label: "Attaching...", status: "attaching" });
      await attachGeneratedPdf(pdf, draft.id);
      setPanelStatus("PDF attached. Continuing to review...", { busy: true, label: "Continuing...", status: "continuing" });
      scheduleWizardAutomation(0);
      return;
    } catch (error) {
      setPanelStatus(`PDF ready: ${pdf.filename}. Automatic upload failed: ${error.message || String(error)}`, {
        label: "Regenerate PDF",
        status: "ready",
      });
      return;
    }
  }

  async function existingOrGeneratedDraft(sourceUrl, request) {
    const existing = await chrome.runtime.sendMessage({ type: "LOOKUP_DRAFT", source_url: sourceUrl });
    if (existing?.ok && existing.matched && existing.draft?.id) {
      setPanelStatus("Using existing draft...", { busy: true, status: "drafting" });
      return existing.draft;
    }
    if (existing && !existing.ok) {
      throw new Error(existing.error || "Could not check for an existing draft.");
    }

    setPanelStatus("Starting cover letter draft...", { busy: true, status: "drafting" });
    const started = await chrome.runtime.sendMessage({ type: "START_DRAFT_JOB", request });
    if (!started?.ok) {
      throw new Error(started?.error || "Could not start the cover letter draft.");
    }
    const jobId = started.state?.job_id;
    if (!jobId) throw new Error("Draft job did not return an id.");
    return pollDraftJob(jobId);
  }

  async function pollDraftJob(jobId) {
    const startedAt = Date.now();
    while (Date.now() - startedAt < 240000) {
      const response = await chrome.runtime.sendMessage({ type: "GET_DRAFT_JOB", job_id: jobId });
      if (!response?.ok) throw new Error(response?.error || "Could not check draft job status.");
      const job = response.job;
      updateRun({ draft_job_id: job.id || jobId });
      setPanelStatus(`Drafting cover letter: ${job.stage || job.status}...`, { busy: true, status: "drafting" });
      if (job.status === "succeeded") {
        if (!job.result?.id) throw new Error("Draft job succeeded without a draft id.");
        return job.result;
      }
      if (job.status === "failed") {
        throw new Error(job.error || "Cover letter draft failed.");
      }
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

  async function showPdfActions(pdf, draftId) {
    currentPdf = pdf;
    currentDraftId = draftId;
    updateRun({ draft_id: draftId, pdf });
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

  async function waitForCoverLetterAttachment(timeoutMs = 8000) {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      if (coverLetterAttachmentPresent()) return true;
      await sleep(200);
    }
    return false;
  }

  async function attachGeneratedPdf(pdf, draftId) {
    const input = coverLetterFileInput();
    if (!input) throw new Error("Dice cover-letter upload input was not found.");
    const transfer = new DataTransfer();
    transfer.items.add(await generatedPdfFile(pdf, draftId));
    input.files = transfer.files;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    if (!(await waitForCoverLetterAttachment())) {
      throw new Error("Dice did not show the generated PDF as attached.");
    }
  }

  async function backendUrl() {
    const response = await chrome.runtime.sendMessage({ type: "GET_BACKEND_URL" });
    if (!response?.ok) throw new Error(response?.error || "Could not read backend URL.");
    return response.api_base;
  }

  async function revealCurrentPdf() {
    if (!currentDraftId && !currentPdf?.draft_id) {
      throw new Error("Generate the PDF before opening Finder.");
    }
    setPanelStatus("Opening Finder...", { busy: true, status: "opening_finder" });
    const response = await chrome.runtime.sendMessage({ type: "REVEAL_PDF", draft_id: currentDraftId || currentPdf.draft_id });
    if (!response?.ok || !response.opened) throw new Error(response?.error || "Could not open the generated PDF in Finder.");
    setPanelStatus(`Finder opened. Select ${currentPdf?.filename || "the generated PDF"} in Dice's upload box.`, {
      label: "Regenerate PDF",
      status: "ready",
    });
  }

  async function diceDetailOpportunity(jobId) {
    const opportunity = await diceOpportunity.detailOpportunity(jobId);
    if (!opportunity) throw new Error("Dice structured job details were not found.");
    return opportunity;
  }

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function jobScopedKey(prefix) {
    return `${prefix}:${jobApplicationId() || location.pathname}`;
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

  function wizardButton(label) {
    return Array.from(document.querySelectorAll("button")).find((button) => {
      return usableButton(button) && clean(button.textContent || button.getAttribute("aria-label") || "") === label;
    }) || null;
  }

  function coverLetterAttachmentPresent() {
    const coverLetter = coverLetterSection();
    if (!coverLetter) return false;
    const text = clean(coverLetter.textContent || "");
    return /\.pdf/i.test(text) && text.includes("New file");
  }

  function clickNextAfterCoverLetterIfReady() {
    if (!isResumeCoverLetterStep() || !coverLetterAttachmentPresent()) return false;
    const next = wizardButton("Next");
    if (!next) return false;

    const key = jobScopedKey(AUTO_NEXT_KEY);
    const attempts = sessionCount(key);
    if (attempts >= AUTO_NEXT_MAX_ATTEMPTS) return false;
    sessionStorage.setItem(key, String(attempts + 1));

    setPanelStatus("Cover letter attached. Continuing to review...", { busy: true, label: "Continuing...", status: "continuing" });
    const hrefBeforeClick = location.href;
    window.setTimeout(() => {
      next.click();
      window.setTimeout(() => {
        if (location.href === hrefBeforeClick && wizardButton("Next") && coverLetterAttachmentPresent()) {
          scheduleWizardAutomation(0);
        }
      }, 1500);
    }, 0);
    return true;
  }

  function clickSubmitIfReady() {
    if (!isDiceWizard() || isDiceWizardSuccessStep()) return false;
    const submit = wizardButton("Submit");
    if (!submit) return false;

    const key = jobScopedKey(AUTO_SUBMIT_KEY);
    if (sessionStorage.getItem(key)) return false;
    sessionStorage.setItem(key, new Date().toISOString());

    setPanelStatus("Submitting Dice application...", { busy: true, label: "Submitting...", status: "submitting" });
    window.setTimeout(() => submit.click(), 0);
    return true;
  }

  function markSubmittedIfSuccess() {
    if (!isDiceWizardSuccessStep()) return false;
    coverLetterRuns?.remove?.(jobApplicationId()).catch(() => {});
    return true;
  }

  function markManualQuestionsIfNeeded() {
    if (!isDiceWizard() || isDiceWizardSuccessStep() || isResumeCoverLetterStep()) return false;
    if (sessionCount(jobScopedKey(AUTO_NEXT_KEY)) <= 0 || !wizardButton("Next")) return false;
    setPanelStatus("Application questions need manual answers in this Dice tab.", {
      busy: false,
      label: "Regenerate PDF",
      status: "needs_attention",
    });
    return true;
  }

  function advanceWizardIfReady() {
    if (!isDiceWizard() || isDiceWizardSuccessStep()) return false;
    return clickSubmitIfReady() || clickNextAfterCoverLetterIfReady();
  }

  function continueWizardAutomation() {
    if (markSubmittedIfSuccess()) return true;
    if (advanceWizardIfReady()) return true;
    return markManualQuestionsIfNeeded();
  }

  function scheduleWizardAutomation(delay = 250) {
    window.clearTimeout(wizardAutomationTimer);
    wizardAutomationTimer = window.setTimeout(() => {
      continueWizardAutomation();
    }, delay);
  }

  function installWizardAutomationWatcher() {
    if (wizardObserver) return;
    wizardObserver = new MutationObserver(() => scheduleWizardAutomation());
    wizardObserver.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
      attributeFilter: ["aria-disabled", "data-testid", "disabled"],
    });
    window.setInterval(() => scheduleWizardAutomation(0), 1200);
  }

  function maybeStart() {
    if (markSubmittedIfSuccess()) {
      return;
    }
    if (!isDiceWizard()) {
      return;
    }
    if (advanceWizardIfReady()) return;
    if (markManualQuestionsIfNeeded()) return;
    if (!isResumeCoverLetterStep()) {
      setPanelStatus("Waiting for the Resume & Cover Letter step.", { status: "waiting" });
      return;
    }
    const jobId = jobApplicationId();
    if (autoStartedForJobId === jobId) return;
    autoStartedForJobId = jobId;
    startCoverLetterFlow();
  }

  function startStepPolling() {
    window.clearInterval(stepPollTimer);
    stepPollCount = 0;
    pollForResumeStep();
    stepPollTimer = window.setInterval(pollForResumeStep, 1000);
  }

  function pollForResumeStep() {
    stepPollCount += 1;
    maybeStart();
    if (!isDiceWizard() || isDiceWizardSuccessStep() || autoStartedForJobId === jobApplicationId() || stepPollCount >= 120) {
      window.clearInterval(stepPollTimer);
    }
  }

  function handleRouteChange({ force = false } = {}) {
    if (!force && location.href === lastKnownHref) return;
    lastKnownHref = location.href;
    window.clearInterval(stepPollTimer);
    if (markSubmittedIfSuccess()) {
      return;
    }
    if (!isDiceWizard()) {
      return;
    }
    startStepPolling();
    scheduleWizardAutomation();
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

  if (globalThis.chrome?.runtime?.onMessage && !globalThis.__diceCoverLetterAssistantMessageListenerInstalled) {
    globalThis.__diceCoverLetterAssistantMessageListenerInstalled = true;
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message?.type === "DICE_COVER_LETTER_START") {
        startCoverLetterFlow({ force: Boolean(message.force) });
        sendResponse({ ok: true });
        return false;
      }
      return false;
    });
  }

  installRouteWatcher();
  installWizardAutomationWatcher();
  window.setTimeout(() => handleRouteChange({ force: true }), 600);
})();

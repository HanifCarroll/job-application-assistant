(() => {
  if (globalThis.__jobApplicationLoggerLoaded) {
    return;
  }
  globalThis.__jobApplicationLoggerLoaded = true;

  const CONFIRMED_KEY = "jobApplicationLoggerConfirmed";
  const LINKEDIN_AUTO_SUBMIT_DELAY = 1000;
  const LINKEDIN_AUTO_CLOSE_DELAY = 500;
  const LINKEDIN_RECENT_SUBMIT_MS = 30000;
  const LINKEDIN_AUTO_SUBMITTED_AT_KEY = "jobApplicationLinkedInAutoSubmittedAt";
  const diceOpportunity = globalThis.JobApplicationDiceOpportunity;
  const indeedOpportunity = globalThis.JobApplicationIndeedOpportunity;
  const coverLetterRuns = globalThis.JobApplicationCoverLetterRuns;
  const ledgerBadge = globalThis.JobApplicationLedgerBadge;

  const PLATFORM_RULES = [
    {
      source: "upwork",
      hosts: ["upwork.com"],
      submitSelectors: [
        'button[data-test="submit-proposal-button"]',
        'button[data-test="submit-proposal"]',
        'button[data-qa="submit-proposal"]',
      ],
      confirmationSelectors: [
        { selector: '[data-test="proposal-submitted-message"]', text: "Your proposal has been submitted" },
        { selector: '[data-test="proposal-submitted"]', text: "Your proposal has been submitted" },
        { selector: '[data-test="proposal-details"] [role="alert"] p', text: "Your proposal was submitted." },
      ],
      confirmationPathPatterns: [/\/ab\/proposals\/submitted\/?$/, /\/nx\/proposals\/[^/?#]+\/?\?success$/],
    },
    {
      source: "dice",
      hosts: ["dice.com"],
      submitSelectors: ['button[type="submit"]'],
      submitText: "Submit",
      captureOpportunity: diceWizardOpportunity,
      confirmationPathPatterns: [/\/job-applications\/[^/]+\/wizard\/success\/?$/],
    },
    {
      source: "indeed",
      hosts: ["indeed.com"],
      submitSelectors: ['button[data-testid="submit-application-button"]', 'button[data-testid="indeed-apply-submit-button"]', 'button[data-testid="ia-continueButton"]'],
      captureOpportunity: indeedSmartApplyOpportunity,
      confirmationSelectors: [
        { selector: '[data-testid="indeed-apply-confirmation"]', text: "Application submitted" },
        { selector: '[data-testid="ia-ApplicationSubmitted"]', text: "Application submitted" },
        { selector: "body", textPattern: /Application submitted|Your application was submitted/ },
      ],
      confirmationPathPatterns: [/\/apply\/confirm\/?$/, /\/indeedapply\/.*(?:post-apply|success|confirmation)/],
    },
    {
      source: "ziprecruiter",
      hosts: ["ziprecruiter.com"],
      submitSelectors: [
        'button[data-testid="submit-application"]',
        'button[data-testid="apply-submit"]',
        'button[aria-label="1-Click Apply"]',
        'button[aria-label="Quick Apply"]',
      ],
      submitButtons: [{ selector: 'button[type="button"]', text: "Submit" }],
      confirmationSelectors: [
        { selector: '[data-testid="application-submitted"]', text: "Application Submitted" },
        { selector: '[data-testid="apply-confirmation"]', text: "Application Submitted" },
        { selector: '[role="status"]', text: "Your application was submitted!" },
        { selector: '[role="alert"]', text: "Your application was submitted!" },
        { selector: 'button[aria-label="Applied"]', text: "Applied" },
      ],
      confirmationPathPatterns: [/\/candidate\/application\/submitted\/?$/],
    },
    {
      source: "roberthalf",
      hosts: ["roberthalf.com"],
      submitSelectors: [
        'button[data-testid="submit-application"]',
        'button[data-testid="apply-submit"]',
        'button[aria-label="Quick apply"]',
        'rhcl-button[component-title="Quick apply"]',
        'rhcl-job-card[data-testid="job-details"][cta-type="quick-apply"]',
      ],
      confirmationSelectors: [
        { selector: '[data-testid="application-confirmation"]', text: "Application submitted" },
        { selector: '[data-testid="application-submitted"]', text: "Application submitted" },
        { selector: 'rhcl-job-card[data-testid="job-details"][applied=""]' },
        { selector: 'rhcl-job-card[data-testid="job-details"][applied="true"]' },
        { selector: 'rhcl-job-card[selected="true"][applied=""]' },
        { selector: 'rhcl-job-card[selected="true"][applied="true"]' },
      ],
      confirmationPathPatterns: [/\/application\/submitted\/?$/],
    },
    {
      source: "linkedin",
      hosts: ["linkedin.com"],
      submitSelectors: ['.jobs-easy-apply-modal__content button[data-live-test-easy-apply-submit-button]'],
      submitText: "Submit application",
      submitButtons: [{ selector: ".jobs-easy-apply-modal__content button", text: "Submit application" }],
      autoEasyApply: true,
      confirmationSelectors: [
        { selector: ".jobs-easy-apply-modal__content button", text: "Done" },
        { selector: ".jobs-easy-apply-modal__content button", text: "Not now" },
        { selector: "#jobs-apply-see-application-link" },
        { selector: '.artdeco-inline-feedback--success[role="alert"]', textPrefix: "Applied" },
      ],
    },
  ];

  function clean(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function currentRule() {
    const host = location.hostname.toLowerCase();
    return PLATFORM_RULES.find((rule) => rule.hosts.some((candidate) => host === candidate || host.endsWith(`.${candidate}`))) || null;
  }

  async function currentOpportunity(rule) {
    if (rule.captureOpportunity) {
      const captured = await rule.captureOpportunity();
      if (captured) return captured;
    }
    if (typeof globalThis.__applicationDraftAssistantExtract !== "function") return null;
    const snapshot = await globalThis.__applicationDraftAssistantExtract();
    if (snapshot?.source !== rule.source) return null;
    if (!snapshot.source_url || !snapshot.title) return null;
    return snapshot;
  }

  function elementConfirms(rule) {
    return (rule.confirmationSelectors || []).some((item) => {
      return Array.from(document.querySelectorAll(item.selector)).some((element) => {
        if (!item.text && !item.textPrefix && !item.textPattern) return true;
        const text = clean(element?.textContent || "");
        if (item.text) return text === item.text;
        if (item.textPrefix) return text.startsWith(item.textPrefix);
        return item.textPattern.test(text);
      });
    });
  }

  function pathConfirms(rule) {
    const path = location.pathname;
    const pathWithSearch = `${location.pathname}${location.search}`;
    return (rule.confirmationPathPatterns || []).some((pattern) => pattern.test(path) || pattern.test(pathWithSearch));
  }

  function buttonText(element) {
    return clean(element?.textContent || element?.getAttribute("aria-label") || "");
  }

  function eventElements(event) {
    const path = typeof event.composedPath === "function" ? event.composedPath() : [event.target];
    return path.filter((item) => item instanceof Element);
  }

  function matchesSubmitElement(rule, target) {
    const submit = rule.submitSelectors.map((selector) => target.closest(selector)).find(Boolean);
    if (submit && (!rule.submitText || buttonText(submit) === rule.submitText)) return true;
    return (rule.submitButtons || []).some((item) => {
      const button = target.closest(item.selector);
      return button && (!item.text || buttonText(button) === item.text);
    });
  }

  function matchesSubmit(rule, event) {
    return eventElements(event).some((target) => matchesSubmitElement(rule, target));
  }

  function activeLinkedInEasyApplyContent() {
    return document.querySelector(".jobs-easy-apply-modal__content");
  }

  function linkedinCheckedFollowLabel(root) {
    const checkbox = root?.querySelector("#follow-company-checkbox");
    if (!(checkbox instanceof HTMLInputElement)) return null;
    if (checkbox.type !== "checkbox" || !checkbox.checked) return null;
    return checkbox.labels?.[0] || checkbox;
  }

  function linkedinFinalSubmitButton(root) {
    return Array.from(root?.querySelectorAll("button") || []).find((button) => {
      return !button.disabled && buttonText(button) === "Submit application";
    });
  }

  function linkedinRecentAutoSubmit() {
    const submittedAt = Number(sessionStorage.getItem(LINKEDIN_AUTO_SUBMITTED_AT_KEY) || 0);
    return submittedAt > 0 && Date.now() - submittedAt < LINKEDIN_RECENT_SUBMIT_MS;
  }

  function linkedinPostSubmitButton() {
    if (!linkedinRecentAutoSubmit()) return null;
    const roots = document.querySelectorAll(".jobs-easy-apply-modal__content, .jobs-easy-apply-modal, .artdeco-modal");
    for (const root of roots) {
      const button = Array.from(root.querySelectorAll("button")).find((candidate) => {
        return !candidate.disabled && ["Done", "Not now"].includes(buttonText(candidate));
      });
      if (button) return button;
    }
    return null;
  }

  function scheduleElementClick(element, delay, datasetKey, beforeClick) {
    if (!element || element.disabled || element.dataset[datasetKey]) return;
    element.dataset[datasetKey] = "true";
    window.setTimeout(() => {
      if (!element.isConnected || element.disabled) return;
      Promise.resolve(beforeClick?.())
        .catch(() => {})
        .then(() => {
          if (element.isConnected && !element.disabled) {
            element.click();
          }
        });
    }, delay);
  }

  function automateLinkedInEasyApply(rule) {
    const root = activeLinkedInEasyApplyContent();
    if (root) {
      const followLabel = linkedinCheckedFollowLabel(root);
      if (followLabel) {
        followLabel.click();
      }
      scheduleElementClick(linkedinFinalSubmitButton(root), LINKEDIN_AUTO_SUBMIT_DELAY, "jobApplicationAutoSubmitClicked", async () => {
        sessionStorage.setItem(LINKEDIN_AUTO_SUBMITTED_AT_KEY, String(Date.now()));
        await capturePending(rule);
      });
    }
    scheduleElementClick(linkedinPostSubmitButton(), LINKEDIN_AUTO_CLOSE_DELAY, "jobApplicationAutoCloseClicked");
  }

  function runPlatformAutomation() {
    const rule = currentRule();
    if (!rule?.autoEasyApply) return;
    if (rule.source === "linkedin") {
      automateLinkedInEasyApply(rule);
    }
  }

  async function diceWizardOpportunity() {
    const wizardMatch = location.pathname.match(/^\/job-applications\/([^/]+)\/wizard(?:\/success)?\/?$/);
    if (!wizardMatch) return null;
    return (await diceOpportunity.detailOpportunity(wizardMatch[1])) || diceOpportunity.wizardPageOpportunity(wizardMatch[1]);
  }

  async function indeedSmartApplyOpportunity() {
    return indeedOpportunity?.smartApplyOpportunity?.() || null;
  }

  function diceJobApplicationId() {
    return location.pathname.match(/^\/job-applications\/([^/]+)\/wizard(?:\/success)?\/?$/)?.[1] || "";
  }

  function coverLetterRunId(rule) {
    if (rule.source === "dice") return diceJobApplicationId();
    if (rule.source === "indeed") {
      const key = indeedOpportunity?.smartApplyJobKey?.() || "";
      return key ? `indeed:${key}` : "";
    }
    return "";
  }

  function updateCoverLetterRunConfirmed(rule) {
    const jobId = coverLetterRunId(rule);
    if (!jobId || !coverLetterRuns?.remove) return;
    coverLetterRuns.remove(jobId).catch(() => {});
  }

  async function lookupApplication(sourceUrl) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "LOOKUP_APPLICATION", source_url: sourceUrl }, (response) => {
        if (chrome.runtime.lastError || !response?.ok) {
          resolve(null);
          return;
        }
        resolve(response.application || null);
      });
    });
  }

  let badgeLookupTimer = 0;
  let lastBadgeLookupKey = "";

  function setFreshLedgerBadge(application, label, sourceUrl) {
    ledgerBadge.set(application, { label, includeAppliedAt: false, sourceUrl });
  }

  async function updateLedgerBadge({ force = false } = {}) {
    const rule = currentRule();
    if (!rule) {
      ledgerBadge.clear();
      return;
    }
    const opportunity = await currentOpportunity(rule);
    const sourceUrl = opportunity?.source_url || location.href;
    if (!sourceUrl) {
      ledgerBadge.clear();
      return;
    }
    if (!force && ledgerBadge.sourceUrl() === sourceUrl) return;
    if (!force && !ledgerBadge.sourceUrl() && sourceUrl === lastBadgeLookupKey) return;
    lastBadgeLookupKey = sourceUrl;
    ledgerBadge.set(await lookupApplication(sourceUrl), { sourceUrl });
  }

  function scheduleLedgerBadgeRefresh(delay = 500, options = {}) {
    window.clearTimeout(badgeLookupTimer);
    badgeLookupTimer = window.setTimeout(() => {
      updateLedgerBadge(options).catch(() => {});
    }, delay);
  }

  async function capturePending(rule) {
    try {
      const opportunity = await currentOpportunity(rule);
      if (!opportunity) return;
      chrome.runtime.sendMessage({ type: "APPLICATION_CAPTURE_PENDING", opportunity }, () => {});
    } catch (_error) {
      return;
    }
  }

  async function confirmIfReady() {
    const rule = currentRule();
    if (!rule) return;
    if (!elementConfirms(rule) && !pathConfirms(rule)) return;
    const opportunity = await currentOpportunity(rule);
    const sourceUrl = opportunity?.source_url || location.href;
    const key = `${rule.source}:${sourceUrl}`;
    if (sessionStorage.getItem(CONFIRMED_KEY) === key) return;
    sessionStorage.setItem(CONFIRMED_KEY, key);
    chrome.runtime.sendMessage(
      {
        type: "APPLICATION_CONFIRMED",
        source: rule.source,
        opportunity,
        close_tab: rule.source === "dice" && pathConfirms(rule),
        warnings: [],
      },
      (response) => {
        lastBadgeLookupKey = "";
        if (chrome.runtime.lastError || !response?.ok) {
          scheduleLedgerBadgeRefresh(500, { force: true });
          return;
        }
        updateCoverLetterRunConfirmed(rule);
        if (response.application) {
          setFreshLedgerBadge(response.application, "Submission recorded", sourceUrl);
          return;
        }
        if (response.queued && opportunity) {
          setFreshLedgerBadge(opportunity, "Application log queued", sourceUrl);
          return;
        }
        scheduleLedgerBadgeRefresh(500, { force: true });
      }
    );
  }

  document.addEventListener(
    "click",
    (event) => {
      const rule = currentRule();
      if (!rule) return;
      scheduleLedgerBadgeRefresh(300, { force: true });
      if (matchesSubmit(rule, event)) {
        if (rule.source === "linkedin") {
          sessionStorage.setItem(LINKEDIN_AUTO_SUBMITTED_AT_KEY, String(Date.now()));
        }
        capturePending(rule).catch(() => {});
      }
    },
    true
  );

  const observer = new MutationObserver(() => {
    runPlatformAutomation();
    confirmIfReady().catch(() => {});
    scheduleLedgerBadgeRefresh(1200);
  });
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["applied", "aria-label", "cta-type", "data-testid", "destination", "disabled", "headline", "href", "selected"],
    childList: true,
    subtree: true,
  });
  runPlatformAutomation();
  confirmIfReady().catch(() => {});
  scheduleLedgerBadgeRefresh(500);
  window.setTimeout(() => {
    runPlatformAutomation();
    confirmIfReady().catch(() => {});
    scheduleLedgerBadgeRefresh(0);
  }, 1000);
})();

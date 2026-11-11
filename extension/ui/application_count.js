(() => {
  if (globalThis.JobApplicationCount) {
    return;
  }

  const DAYS_KEY = "jobApplicationAppliedCountDays";
  const LEDGER_UPDATED_KEY = "jobApplicationLedgerUpdatedAt";
  const DEFAULT_DAYS = 1;
  const MAX_DAYS = 3650;

  function cleanDays(value) {
    const parsed = Number.parseInt(String(value || ""), 10);
    if (!Number.isFinite(parsed) || parsed < 1) return DEFAULT_DAYS;
    return Math.min(parsed, MAX_DAYS);
  }

  function countLabel(days) {
    return days === 1 ? "applied today" : `applied in past ${days} days`;
  }

  async function storedDays() {
    const stored = await chrome.storage.local.get(DAYS_KEY);
    return cleanDays(stored[DAYS_KEY]);
  }

  async function saveDays(days) {
    await chrome.storage.local.set({ [DAYS_KEY]: cleanDays(days) });
  }

  async function loadSummary(days) {
    const response = await chrome.runtime.sendMessage({ type: "APPLICATION_SUMMARY", days });
    if (!response?.ok) throw new Error(response?.error || "Could not load application count.");
    return response;
  }

  function create({ els }) {
    let refreshTimer = 0;
    let currentDays = DEFAULT_DAYS;
    let hasRenderedSummary = false;

    function renderPending(days) {
      currentDays = cleanDays(days);
      els.applicationCountDays.value = String(currentDays);
      els.applicationCountLabel.textContent = countLabel(currentDays);
      if (!hasRenderedSummary) {
        els.applicationCountValue.textContent = "-";
        els.applicationCountStatus.textContent = "Updating...";
      }
    }

    function renderSummary(summary) {
      currentDays = cleanDays(summary.days);
      hasRenderedSummary = true;
      els.applicationCountDays.value = String(currentDays);
      els.applicationCountValue.textContent = String(summary.count ?? 0);
      els.applicationCountLabel.textContent = countLabel(currentDays);
      els.applicationCountStatus.textContent = currentDays === 1
        ? summary.end_date || ""
        : `${summary.start_date || ""} to ${summary.end_date || ""}`;
    }

    function renderError(error) {
      if (!hasRenderedSummary) {
        els.applicationCountValue.textContent = "-";
      }
      els.applicationCountLabel.textContent = countLabel(currentDays);
      els.applicationCountStatus.textContent = error.message || "Could not load application count.";
    }

    async function refresh(days = currentDays) {
      const nextDays = cleanDays(days);
      renderPending(nextDays);
      try {
        renderSummary(await loadSummary(nextDays));
      } catch (error) {
        renderError(error);
      }
    }

    function scheduleRefresh(delay = 250) {
      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => {
        refresh().catch(renderError);
      }, delay);
    }

    async function setDays(value) {
      const nextDays = cleanDays(value);
      currentDays = nextDays;
      els.applicationCountDays.value = String(nextDays);
      await saveDays(nextDays);
      await refresh(nextDays);
    }

    async function initialize() {
      currentDays = await storedDays();
      els.applicationCountDays.value = String(currentDays);
      els.applicationCountDays.addEventListener("change", () => {
        setDays(els.applicationCountDays.value).catch(renderError);
      });
      els.applicationCountDays.addEventListener("input", () => {
        currentDays = cleanDays(els.applicationCountDays.value);
        els.applicationCountLabel.textContent = countLabel(currentDays);
      });
      chrome.storage.onChanged.addListener((changes, areaName) => {
        if (areaName !== "local") return;
        if (changes[LEDGER_UPDATED_KEY]) {
          scheduleRefresh();
          return;
        }
        if (changes[DAYS_KEY]) {
          const nextDays = cleanDays(changes[DAYS_KEY].newValue);
          if (nextDays === currentDays) return;
          refresh(nextDays).catch(renderError);
        }
      });
      await refresh(currentDays);
      window.setInterval(() => {
        refresh().catch(renderError);
      }, 30000);
    }

    return {
      initialize,
      refresh,
      scheduleRefresh,
    };
  }

  globalThis.JobApplicationCount = {
    create,
    key: DAYS_KEY,
    ledgerUpdatedKey: LEDGER_UPDATED_KEY,
  };
})();

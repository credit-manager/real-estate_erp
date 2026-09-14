/* ============================================================
   Accounting Module - shared helpers
   ============================================================ */

const ACCT_TYPE_LABELS = {
  asset: "accounting.asset",
  liability: "accounting.liability",
  equity: "accounting.equity",
  revenue: "accounting.revenue",
  expense: "accounting.expense",
};

function acctTypeLabel(type) {
  const k = ACCT_TYPE_LABELS[type];
  return k ? t(k) : type;
}

function acctTypeBadge(type) {
  const map = {
    asset: "badge-primary",
    liability: "badge-warning",
    equity: "badge-success",
    revenue: "badge-success",
    expense: "badge-danger",
  };
  return `<span class="badge ${map[type] || "badge-primary"}">${escapeHtml(acctTypeLabel(type))}</span>`;
}

// Full-number money format (accounting needs exact values, no K/M compression)
function fmtMoney(num, decimals) {
  const d = Number.isFinite(decimals) ? decimals : DECIMALS;
  const n = num || 0;
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  }).format(n);
}

function moneyClass(num) {
  if (!num) return "";
  return num < 0 ? "text-danger" : "text-success";
}

function accountOptions(accounts, selectedId, includeAll) {
  const opts = [];
  if (includeAll) opts.push(`<option value="">${t("common.all")}</option>`);
  for (const a of accounts) {
    opts.push(`<option value="${a.id}" ${a.id == selectedId ? "selected" : ""}>
      ${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`);
  }
  return opts.join("");
}

function costCenterOptions(costCenters) {
  return `<option value="">${t("common.none")}</option>` +
    costCenters.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
}

function yearOptions(years, selectedId) {
  const opts = [];
  if (selectedId !== undefined && selectedId !== "none") opts.push(`<option value="">${t("common.all")}</option>`);
  for (const y of years) {
    opts.push(`<option value="${y.id}" ${y.id == selectedId ? "selected" : ""}>${escapeHtml(y.name)}</option>`);
  }
  return opts.join("");
}

function fillYearSelect(id, years, selectedId) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = yearOptions(years, selectedId);
  if (selectedId) el.value = selectedId;
}

function fillAccountSelect(id, accounts, selectedId, typeFilter) {
  const el = document.getElementById(id);
  if (!el) return;
  let list = accounts;
  if (typeFilter) list = accounts.filter((a) => a.type === typeFilter);
  el.innerHTML = `<option value="">${t("common.select")}</option>` + accountOptions(list, selectedId, false);
  if (selectedId) el.value = selectedId;
}

function toastError(err) {
  showToast((err && err.message) || t("common.error"), "error");
}

async function accFetch(url, opts) {
  try {
    return await api.request(url, opts);
  } catch (err) {
    toastError(err);
    throw err;
  }
}

// Tabs helper
function initTabs(containerId, onSwitch) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      if (onSwitch) onSwitch(btn.dataset.tab);
    });
  });
}

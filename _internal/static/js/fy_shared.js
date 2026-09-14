/* ============================================================
   Shared Financial Year helpers (used by document modals)
   ============================================================ */

let FY_OPTIONS = [];
let FY_LOADED = false;

async function loadFinancialYearOptions(force) {
  if (FY_LOADED && !force) return FY_OPTIONS;
  try {
    FY_OPTIONS = (await api.get("/api/financial-years/options")).years || [];
    FY_LOADED = true;
  } catch (e) {
    FY_OPTIONS = [];
  }
  return FY_OPTIONS;
}

function financialYearLabel(y) {
  const parts = [y.name];
  if (y.company_name) parts.unshift(y.company_name);
  return parts.join(" — ");
}

function fillFinancialYearSelect(selectId, selectedId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const open = FY_OPTIONS;
  const opts = open.map((y) =>
    `<option value="${y.id}"${y.is_active ? ' data-active="1"' : ""}>${escapeHtml(financialYearLabel(y))}</option>`).join("");
  sel.innerHTML = `<option value="">${t("common.select")}</option>` + opts;
  if (selectedId) {
    sel.value = String(selectedId);
    if (!sel.value && open.some((y) => y.id === selectedId)) {
      sel.innerHTML = `<option value="">${t("common.select")}</option>` +
        open.concat([{ id: selectedId, name: "—", company_name: "" }])
          .map((y) => `<option value="${y.id}">${escapeHtml(financialYearLabel(y))}</option>`).join("");
      sel.value = String(selectedId);
    }
  } else {
    const preferred = window.APP_SETTINGS && window.APP_SETTINGS.default_financial_year_id;
    const target =
      open.find((y) => String(y.id) === String(preferred)) ||
      open.find((y) => y.is_active) ||
      open[0];
    if (target) sel.value = String(target.id);
  }
}

function financialYearValue(selectId) {
  const sel = document.getElementById(selectId);
  if (!sel) return null;
  const v = sel.value;
  return v ? parseInt(v, 10) : null;
}

function buildFinancialYearFilter(selectId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const opts = FY_OPTIONS.map((y) =>
    `<option value="${y.id}">${escapeHtml(financialYearLabel(y))}</option>`).join("");
  sel.innerHTML = `<option value="">${t("common.allYears")}</option>` + opts;
}

function selectedFinancialYear(selectId) {
  return financialYearValue(selectId);
}

function moneyWithCurrency(v, doc) {
  const cur = doc && doc.currency ? (doc.currency.symbol || doc.currency.code || "") : "";
  return cur ? `${formatMoney(v)} ${cur}` : formatMoney(v);
}

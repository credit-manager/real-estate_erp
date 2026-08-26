/* Financial reports */
let repMeta = null;
let repTab = "tb";

const REP_TITLES = {
  tb: "accounting.trialBalance",
  ledger: "accounting.generalLedger",
  pl: "accounting.plReport",
  bs: "accounting.balanceSheet",
  cf: "accounting.cashFlow",
};

function repParams() {
  const p = new URLSearchParams();
  const start = document.getElementById("rep-start").value;
  const end = document.getElementById("rep-end").value;
  const year = document.getElementById("rep-year").value;
  const account = document.getElementById("rep-account").value;
  if (start) p.set("start", start);
  if (end) p.set("end", end);
  if (year) p.set("year_id", year);
  if (account) p.set("account_id", account);
  return p;
}

function showFilters(accounts, year, dates) {
  document.getElementById("rep-account-wrap").style.display = accounts ? "" : "none";
  document.getElementById("rep-year-wrap").style.display = year ? "" : "none";
  document.getElementById("rep-start-wrap").style.display = dates ? "" : "none";
  document.getElementById("rep-end-wrap").style.display = dates ? "" : "none";
}

function repPeriodText() {
  const start = document.getElementById("rep-start").value;
  const end = document.getElementById("rep-end").value;
  const year = document.getElementById("rep-year");
  const yearName = year && year.value && year.selectedOptions[0] ? year.selectedOptions[0].text : "";
  if (start && end) return `${start} → ${end}`;
  if (start) return `${t("accounting.fromDate")}: ${start}`;
  if (end) return `${t("accounting.toDate")}: ${end}`;
  return yearName || "";
}

function setHead(title, sub) {
  document.getElementById("rep-title").textContent = title;
  const now = new Date();
  const metaParts = [];
  if (sub) metaParts.push(sub);
  metaParts.push(`${t("accounting.generatedAt")}: ${now.toLocaleDateString()} ${now.toLocaleTimeString().slice(0, 5)}`);
  document.getElementById("rep-meta").textContent = metaParts.join("  •  ");
}

function setKPIs(items) {
  const grid = document.getElementById("rep-kpis");
  if (!items || !items.length) {
    grid.innerHTML = "";
    return;
  }
  grid.innerHTML = items.map((it) => `
    <div class="kpi-card">
      <div class="kpi-top">
        <div>
          <div class="kpi-label">${it.label}</div>
          <div class="kpi-value">${it.value}</div>
        </div>
        <div class="kpi-icon ${it.tone || "kpi-olive"}">${it.icon}</div>
      </div>
    </div>`).join("");
}

function kpi(label, value, icon, tone) {
  return { label, value, icon, tone };
}

function renderActive() {
  const m = { tb: renderTB, ledger: renderLedger, pl: renderPL, bs: renderBS, cf: renderCF };
  (m[repTab] || renderTB)();
}

async function renderTB() {
  showFilters(false, false, true);
  const p = repParams();
  p.delete("account_id");
  p.delete("start");
  const end = document.getElementById("rep-end").value;
  if (end) p.set("end_date", end);
  try {
    const d = await api.get("/accounting/api/reports/trial-balance?" + p.toString());
    setHead(t(REP_TITLES.tb), repPeriodText());
    setKPIs([
      kpi(t("accounting.totalDebit"), fmtMoney(d.total_debit), "💳", "kpi-sage"),
      kpi(t("accounting.totalCredit"), fmtMoney(d.total_credit), "🧾", "kpi-sand"),
      kpi(t("accounting.totalBalance"), fmtMoney(d.total_debit - d.total_credit), "⚖️", "kpi-clay"),
      kpi(t("accounting.accountsCount"), (d.rows || []).length, "📚", "kpi-olive"),
    ]);
    const rows = d.rows.map((r) => `
      <tr>
        <td><strong>${escapeHtml(r.code)}</strong></td>
        <td>${escapeHtml(r.name)}</td>
        <td class="num ${moneyClass(r.balance)}">${fmtMoney(r.debit)}</td>
        <td class="num ${moneyClass(r.balance)}">${fmtMoney(r.credit)}</td>
        <td class="num"><strong class="${moneyClass(r.balance)}">${fmtMoney(r.balance)}</strong></td>
      </tr>`).join("");
    setReport(`
      <table class="rep-table">
        <thead><tr>
          <th>${t("accounting.code")}</th><th>${t("common.name")}</th>
          <th>${t("accounting.debit")}</th><th>${t("accounting.credit")}</th>
          <th>${t("accounting.balance")}</th>
        </tr></thead>
        <tbody>${rows || `<tr><td colspan="5"><div class="empty-state">${t("accounting.noData")}</div></td></tr>`}</tbody>
        <tfoot><tr>
          <td colspan="2">${t("accounting.totals")}</td>
          <td class="num"><strong>${fmtMoney(d.total_debit)}</strong></td>
          <td class="num"><strong>${fmtMoney(d.total_credit)}</strong></td>
          <td></td>
        </tr></tfoot>
      </table>`);
  } catch (e) { toastError(e); }
}

async function renderLedger() {
  showFilters(true, false, true);
  if (!repMeta) { try { repMeta = await api.get("/accounting/api/meta"); } catch (e) {} }
  const accSel = document.getElementById("rep-account");
  if (!accSel.dataset.built) {
    accSel.innerHTML = `<option value="">${t("accounting.selectAccount")}</option>` + repMeta.accounts.map((a) =>
      `<option value="${a.id}">${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
    accSel.dataset.built = "1";
    accSel.addEventListener("change", renderLedger);
  }
  const account = accSel.value;
  if (!account) {
    setKPIs([]);
    setHead(t(REP_TITLES.ledger), repPeriodText());
    setReport(`<div class="empty-state">${t("accounting.selectAccount")}</div>`);
    return;
  }
  const p = repParams();
  try {
    const d = await api.get("/accounting/api/reports/ledger?" + p.toString());
    let sumDebit = 0, sumCredit = 0;
    (d.rows || []).forEach((r) => { sumDebit += r.debit || 0; sumCredit += r.credit || 0; });
    setHead(`${d.account.code} - ${d.account.name}`, repPeriodText());
    setKPIs([
      kpi(t("accounting.entriesCount"), (d.rows || []).length, "📒", "kpi-olive"),
      kpi(t("accounting.debit"), fmtMoney(sumDebit), "💳", "kpi-sage"),
      kpi(t("accounting.credit"), fmtMoney(sumCredit), "🧾", "kpi-sand"),
      kpi(t("accounting.closingBalance"), fmtMoney(d.balance), "⚖️", "kpi-clay"),
    ]);
    const rows = d.rows.map((r) => `
      <tr>
        <td>${formatDate(r.date)}</td>
        <td>${escapeHtml(r.entry_number || "")}</td>
        <td>${escapeHtml(r.description || "")}</td>
        <td class="num text-success">${r.debit ? fmtMoney(r.debit) : "—"}</td>
        <td class="num text-danger">${r.credit ? fmtMoney(r.credit) : "—"}</td>
        <td class="num"><strong class="${moneyClass(r.balance)}">${fmtMoney(r.balance)}</strong></td>
      </tr>`).join("");
    setReport(`
      <table class="rep-table">
        <thead><tr>
          <th>${t("accounting.date")}</th><th>${t("accounting.entryNumber")}</th>
          <th>${t("common.description")}</th><th>${t("accounting.debit")}</th>
          <th>${t("accounting.credit")}</th><th>${t("accounting.balance")}</th>
        </tr></thead>
        <tbody>${rows || `<tr><td colspan="6"><div class="empty-state">${t("accounting.noData")}</div></td></tr>`}</tbody>
        <tfoot><tr>
          <td colspan="5">${t("accounting.closingBalance")}</td>
          <td class="num"><strong class="${moneyClass(d.balance)}">${fmtMoney(d.balance)}</strong></td>
        </tr></tfoot>
      </table>`);
  } catch (e) { toastError(e); }
}

async function renderPL() {
  showFilters(false, false, true);
  const p = repParams();
  p.delete("account_id");
  p.delete("year_id");
  try {
    const d = await api.get("/accounting/api/reports/pl?" + p.toString());
    setHead(t(REP_TITLES.pl), repPeriodText());
    setKPIs([
      kpi(t("accounting.totalRevenues"), fmtMoney(d.total_revenue), "💰", "kpi-sage"),
      kpi(t("accounting.totalExpenses"), fmtMoney(d.total_expense), "💸", "kpi-terracotta"),
      kpi(t("accounting.netIncome"), fmtMoney(d.net_income), "📈", d.net_income < 0 ? "kpi-terra" : "kpi-moss"),
    ]);
    const revRows = d.revenues.map((r) => `<tr><td>${escapeHtml(r.code)}</td><td>${escapeHtml(r.name)}</td><td></td><td class="num">${fmtMoney(r.amount)}</td></tr>`).join("");
    const expRows = d.expenses.map((r) => `<tr><td>${escapeHtml(r.code)}</td><td>${escapeHtml(r.name)}</td><td></td><td class="num">${fmtMoney(r.amount)}</td></tr>`).join("");
    setReport(`
      <table class="rep-table">
        <thead><tr><th>${t("accounting.code")}</th><th>${t("common.name")}</th><th></th><th>${t("accounting.amount")}</th></tr></thead>
        <tbody>
          <tr class="rep-section"><td colspan="4">📥 ${t("accounting.revenues")}</td></tr>
          ${revRows || `<tr><td colspan="4" class="muted">${t("accounting.noData")}</td></tr>`}
          <tr class="rep-total"><td colspan="3">${t("accounting.totalRevenues")}</td><td class="num"><strong>${fmtMoney(d.total_revenue)}</strong></td></tr>
          <tr class="rep-section"><td colspan="4">📤 ${t("accounting.expenses")}</td></tr>
          ${expRows || `<tr><td colspan="4" class="muted">${t("accounting.noData")}</td></tr>`}
          <tr class="rep-total"><td colspan="3">${t("accounting.totalExpenses")}</td><td class="num"><strong>${fmtMoney(d.total_expense)}</strong></td></tr>
          <tr class="rep-grand-total"><td colspan="3">${t("accounting.netIncome")}</td><td class="num"><strong class="${moneyClass(d.net_income)}">${fmtMoney(d.net_income)}</strong></td></tr>
        </tbody>
      </table>`);
  } catch (e) { toastError(e); }
}

async function renderBS() {
  showFilters(false, false, true);
  const p = repParams();
  p.delete("account_id");
  p.delete("start");
  p.delete("year_id");
  const end = document.getElementById("rep-end").value;
  if (end) p.set("end_date", end);
  try {
    const d = await api.get("/accounting/api/reports/balance-sheet?" + p.toString());
    setHead(t(REP_TITLES.bs), repPeriodText());
    setKPIs([
      kpi(t("accounting.totalAssets"), fmtMoney(d.total_assets), "🏢", "kpi-sage"),
      kpi(t("accounting.totalLiabilities"), fmtMoney(d.total_liabilities), "🧾", "kpi-sand"),
      kpi(t("accounting.totalEquity"), fmtMoney(d.total_equity), "👥", "kpi-clay"),
      kpi(d.balanced ? t("accounting.balanced") : t("accounting.unbalanced"), d.balanced ? "✓" : "✕", d.balanced ? "✅" : "⚠️", d.balanced ? "kpi-moss" : "kpi-terra"),
    ]);
    const section = (title, list) => `
      <tr class="rep-section"><td colspan="3">${title}</td></tr>
      ${list.map((r) => `<tr><td>${escapeHtml(r.code)}</td><td>${escapeHtml(r.name)}</td><td class="num ${moneyClass(r.amount)}">${fmtMoney(r.amount)}</td></tr>`).join("")}`;
    setReport(`
      <table class="rep-table">
        <thead><tr><th>${t("accounting.code")}</th><th>${t("common.name")}</th><th>${t("accounting.amount")}</th></tr></thead>
        <tbody>
          ${section(t("accounting.assets"), d.assets) || ""}
          <tr class="rep-total"><td colspan="2">${t("accounting.totalAssets")}</td><td class="num"><strong>${fmtMoney(d.total_assets)}</strong></td></tr>
          ${section(t("accounting.liabilities"), d.liabilities) || ""}
          <tr class="rep-total"><td colspan="2">${t("accounting.totalLiabilities")}</td><td class="num"><strong>${fmtMoney(d.total_liabilities)}</strong></td></tr>
          ${section(t("accounting.equity"), d.equity) || ""}
          <tr class="rep-total"><td colspan="2">${t("accounting.totalEquity")}</td><td class="num"><strong>${fmtMoney(d.total_equity)}</strong></td></tr>
          <tr class="rep-grand-total"><td colspan="2">${t("accounting.totalLiabEq")}</td><td class="num"><strong>${fmtMoney(d.total_liabilities + d.total_equity)}</strong></td></tr>
        </tbody>
      </table>`);
  } catch (e) { toastError(e); }
}

async function renderCF() {
  showFilters(false, false, true);
  const p = repParams();
  p.delete("account_id");
  p.delete("year_id");
  try {
    const d = await api.get("/accounting/api/reports/cash-flow?" + p.toString());
    setHead(t(REP_TITLES.cf), repPeriodText());
    setKPIs([
      kpi(t("accounting.netOperating"), fmtMoney(d.net_operating), "🔄", "kpi-sage"),
      kpi(t("accounting.netInvesting"), fmtMoney(d.net_investing), "📦", "kpi-sand"),
      kpi(t("accounting.netFinancing"), fmtMoney(d.net_financing), "🏦", "kpi-clay"),
      kpi(t("accounting.netCashChange"), fmtMoney(d.net_cash), "💵", "kpi-moss"),
    ]);
    setReport(`
      <table class="rep-table">
        <thead><tr><th>${t("accounting.cfItem")}</th><th>${t("accounting.inflows")}</th><th>${t("accounting.outflows")}</th><th>${t("accounting.net")}</th></tr></thead>
        <tbody>
          <tr class="rep-section"><td colspan="4">🔵 ${t("accounting.operating")}</td></tr>
          <tr><td>${t("accounting.receipts")}</td><td class="num text-success">${fmtMoney(d.operating_in)}</td><td></td><td></td></tr>
          <tr><td>${t("accounting.payments")}</td><td></td><td class="num text-danger">${fmtMoney(d.operating_out)}</td><td></td></tr>
          <tr class="rep-total"><td colspan="3">${t("accounting.netOperating")}</td><td class="num"><strong class="${moneyClass(d.net_operating)}">${fmtMoney(d.net_operating)}</strong></td></tr>
          <tr class="rep-section"><td colspan="4">🟠 ${t("accounting.investing")}</td></tr>
          <tr><td>${t("accounting.receipts")}</td><td class="num text-success">${fmtMoney(d.investing_in)}</td><td></td><td></td></tr>
          <tr><td>${t("accounting.payments")}</td><td></td><td class="num text-danger">${fmtMoney(d.investing_out)}</td><td></td></tr>
          <tr class="rep-total"><td colspan="3">${t("accounting.netInvesting")}</td><td class="num"><strong class="${moneyClass(d.net_investing)}">${fmtMoney(d.net_investing)}</strong></td></tr>
          <tr class="rep-section"><td colspan="4">🟣 ${t("accounting.financing")}</td></tr>
          <tr><td>${t("accounting.receipts")}</td><td class="num text-success">${fmtMoney(d.financing_in)}</td><td></td><td></td></tr>
          <tr><td>${t("accounting.payments")}</td><td></td><td class="num text-danger">${fmtMoney(d.financing_out)}</td><td></td></tr>
          <tr class="rep-total"><td colspan="3">${t("accounting.netFinancing")}</td><td class="num"><strong class="${moneyClass(d.net_financing)}">${fmtMoney(d.net_financing)}</strong></td></tr>
          <tr class="rep-grand-total"><td colspan="3">${t("accounting.netCashChange")}</td><td class="num"><strong class="${moneyClass(d.net_cash)}">${fmtMoney(d.net_cash)}</strong></td></tr>
        </tbody>
      </table>`);
  } catch (e) { toastError(e); }
}

function setReport(html) {
  document.getElementById("report-body").innerHTML = html;
}

function printReport() {
  const content = document.getElementById("report-body").innerHTML;
  const title = document.getElementById("rep-title").textContent;
  const meta = document.getElementById("rep-meta").textContent;
  const area = document.getElementById("print-area");
  area.innerHTML = `<div class="print-header"><h2>${t("accounting.title")}</h2><h3 class="rep-print-title">${title}</h3><p class="rep-print-meta">${meta}</p></div>` + content;
  area.style.display = "block";
  window.print();
  setTimeout(() => { area.style.display = "none"; area.innerHTML = ""; }, 100);
}

function exportReport() {
  const table = document.querySelector("#report-body table");
  if (!table) return;
  const headers = Array.from(table.querySelectorAll("thead th")).map((th) => th.textContent);
  const rows = Array.from(table.querySelectorAll("tbody tr")).map((tr) =>
    Array.from(tr.querySelectorAll("td")).map((td) => td.textContent.trim()));
  exportCSV("accounting-report.csv", headers, rows);
}

function onTabSwitch(tab) {
  repTab = tab;
  const yearSel = document.getElementById("rep-year");
  if (!yearSel.dataset.built && repMeta) {
    yearSel.innerHTML = `<option value="">${t("accounting.allYears")}</option>` + repMeta.years.map((y) =>
      `<option value="${y.id}">${escapeHtml(y.name)}</option>`).join("");
    yearSel.dataset.built = "1";
  }
  renderActive();
}

window.renderActive = renderActive;
window.printReport = printReport;
window.exportReport = exportReport;

document.addEventListener("DOMContentLoaded", async () => {
  try { repMeta = await api.get("/accounting/api/meta"); } catch (e) {}
  initTabs("rep-tabs", onTabSwitch);
  renderActive();
});

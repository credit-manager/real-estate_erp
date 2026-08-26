const TAXT = window.T || {};

function tt(key) {
  if (TAXT[key] !== undefined && TAXT[key] !== null) return TAXT[key];
  return key;
}

let taxTypesData = [];
let reportData = null;
let companiesData = [];
let yearsData = [];

function fmtFull(v) {
  const n = parseFloat(v || 0);
  return n.toLocaleString(LANG === "ar" ? "ar-EG" : "en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function moneyFull(v, suffix) {
  return fmtFull(v) + (suffix ? " " + suffix : "");
}

function curSuffix(report) {
  const cur = report && report.currency;
  return (cur && (cur.symbol || cur.code)) || "";
}

/* ===== Tabs ===== */
function showTab(name) {
  document.getElementById("tab-report").style.display = name === "report" ? "" : "none";
  document.getElementById("tab-types").style.display = name === "types" ? "" : "none";
  const r = document.getElementById("tab-report-btn");
  const t = document.getElementById("tab-types-btn");
  r.classList.toggle("btn-primary", name === "report");
  r.classList.toggle("btn-secondary", name !== "report");
  t.classList.toggle("btn-primary", name === "types");
  t.classList.toggle("btn-secondary", name !== "types");
  if (name === "report" && !reportData) loadReport();
  if (name === "types") loadTaxTypes();
}
window.showTab = showTab;

/* ===== Tax types ===== */
async function loadTaxTypes() {
  const res = await api.get("/api/taxes");
  taxTypesData = res.tax_types || [];
  renderTaxTypes();
}

function renderTaxTypes() {
  document.getElementById("types-empty").style.display = taxTypesData.length ? "none" : "block";
  const canEdit = canAction("taxes", "edit");
  const canDelete = canAction("taxes", "delete");

  document.getElementById("types-table").innerHTML = taxTypesData.map((x) => {
    const badges = [
      x.is_default ? `<span class="badge badge-primary">${tt("taxes.default")}</span>` : "",
      x.is_active ? `<span class="badge badge-success">${tt("taxes.active")}</span>` : `<span class="badge badge-danger">${tt("taxes.inactive")}</span>`,
    ].join(" ");
    return `<tr>
      <td><div class="cell-main">${escapeHtml(x.name)}</div></td>
      <td><div class="table-sub">${x.rate}%</div></td>
      <td>${badges}</td>
      <td><div class="table-actions">
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editTax(${JSON.stringify(x)})'>${tt("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteTax(${x.id})">${tt("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

function openTaxModal() {
  document.getElementById("tax-modal-title").textContent = tt("taxes.addType");
  document.getElementById("tax-id").value = "";
  document.getElementById("tax-name").value = "";
  document.getElementById("tax-rate").value = "15";
  document.getElementById("tax-active").checked = true;
  document.getElementById("tax-default").checked = false;
  document.getElementById("tax-modal").style.display = "flex";
  setTimeout(() => document.getElementById("tax-name").focus(), 50);
}
window.openTaxModal = openTaxModal;

function editTax(x) {
  document.getElementById("tax-modal-title").textContent = tt("taxes.editType");
  document.getElementById("tax-id").value = x.id;
  document.getElementById("tax-name").value = x.name || "";
  document.getElementById("tax-rate").value = x.rate;
  document.getElementById("tax-active").checked = !!x.is_active;
  document.getElementById("tax-default").checked = !!x.is_default;
  document.getElementById("tax-modal").style.display = "flex";
}
window.editTax = editTax;

function closeTaxModal() { document.getElementById("tax-modal").style.display = "none"; }
window.closeTaxModal = closeTaxModal;

async function saveTax() {
  const id = document.getElementById("tax-id").value;
  const payload = {
    name: document.getElementById("tax-name").value,
    rate: document.getElementById("tax-rate").value,
    is_active: document.getElementById("tax-active").checked,
    is_default: document.getElementById("tax-default").checked,
  };
  if (!payload.name.trim()) { showToast(tt("taxes.nameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/taxes/${id}`, payload);
    else await api.post("/api/taxes", payload);
    showToast(tt("taxes.saved"));
    closeTaxModal();
    loadTaxTypes();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveTax = saveTax;

async function deleteTax(id) {
  const x = taxTypesData.find((t) => t.id === id);
  if (!confirm(tt("taxes.confirmDelete") + " " + (x ? x.name : ""))) return;
  try {
    await api.delete(`/api/taxes/${id}`);
    showToast(tt("taxes.deleted"));
    loadTaxTypes();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteTax = deleteTax;

/* ===== Report ===== */
function onFilterChange() {
  const year = document.getElementById("report-year").value;
  if (year) {
    document.getElementById("report-start").value = "";
    document.getElementById("report-end").value = "";
  }
  loadReport();
}
window.onFilterChange = onFilterChange;

function reportQuery() {
  const p = new URLSearchParams();
  const year = document.getElementById("report-year").value;
  const company = document.getElementById("report-company").value;
  const start = document.getElementById("report-start").value;
  const end = document.getElementById("report-end").value;
  if (year) p.set("year_id", year);
  if (company) p.set("company_id", company);
  if (!year && start) p.set("start", start);
  if (!year && end) p.set("end", end);
  return p.toString();
}

async function loadReport() {
  let q = reportQuery();
  if (!q) {
    const yearSel = document.getElementById("report-year");
    if (yearSel && yearSel.options && yearSel.options.length > 1) {
      yearSel.value = yearSel.options[1].value;
      q = reportQuery();
    } else {
      const now = new Date();
      const to = now.toISOString().slice(0, 10);
      const from = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
      document.getElementById("report-start").value = from;
      document.getElementById("report-end").value = to;
      q = reportQuery();
    }
  }
  const btn = document.getElementById("report-generate-btn");
  const origText = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = tt("taxes.generating"); }
  try {
    reportData = await api.get("/api/taxes/report?" + q);
    renderReport();
    showToast(tt("taxes.reportDone"), "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = origText; }
  }
}
window.loadReport = loadReport;

function renderReport() {
  const r = reportData;
  const suffix = curSuffix(r);

  document.getElementById("kpi-output").textContent = moneyFull(r.output_tax, suffix);
  document.getElementById("kpi-output-docs").textContent = `${tt("taxes.docCount")}: ${r.output_docs}`;
  document.getElementById("kpi-input").textContent = moneyFull(r.input_tax, suffix);
  document.getElementById("kpi-input-docs").textContent = `${tt("taxes.docCount")}: ${r.input_docs}`;

  const net = parseFloat(r.net_tax || 0);
  const netEl = document.getElementById("kpi-net");
  netEl.textContent = moneyFull(Math.abs(net), suffix);
  netEl.style.color = net < 0 ? "var(--red)" : "var(--primary)";
  document.getElementById("kpi-net-sub").textContent = net < 0 ? tt("taxes.refundable") : "";
  document.getElementById("kpi-docs").textContent = r.documents_count || 0;

  const breakdown = r.breakdown || [];
  document.getElementById("breakdown-empty").style.display = breakdown.length ? "none" : "block";
  document.getElementById("breakdown-table").innerHTML = breakdown.map((b) => {
    const netV = parseFloat(b.net || 0);
    return `<tr>
      <td><div class="cell-main">${b.rate}%</div></td>
      <td class="num">${moneyFull(b.output_base, suffix)}</td>
      <td class="num">${moneyFull(b.output_tax, suffix)}</td>
      <td class="num">${moneyFull(b.input_base, suffix)}</td>
      <td class="num">${moneyFull(b.input_tax, suffix)}</td>
      <td class="num" style="color:${netV < 0 ? "var(--red)" : "var(--primary)"}">${moneyFull(Math.abs(netV), suffix)}</td>
    </tr>`;
  }).join("");

  const docs = r.documents || [];
  document.getElementById("docs-empty").style.display = docs.length ? "none" : "block";
  document.getElementById("docs-table").innerHTML = docs.map((d) => {
    const kindBadge = d.kind === "sales"
      ? `<span class="badge badge-success">${tt("taxes.typeSales")}</span>`
      : d.kind === "purchase"
        ? `<span class="badge badge-info">${tt("taxes.typePurchase")}</span>`
        : d.kind === "expense"
          ? `<span class="badge badge-warning">${tt("taxes.typeExpense")}</span>`
          : `<span class="badge badge-neutral">${tt("taxes.typePO")}</span>`;
    const rates = (d.rates || []).map((x) => x + "%").join(" / ") || "0%";
    return `<tr>
      <td>${kindBadge}</td>
      <td><div class="cell-main">${escapeHtml(d.number)}</div></td>
      <td><div class="table-sub">${formatDate(d.date)}</div></td>
      <td>${escapeHtml(d.party)}</td>
      <td class="num">${moneyFull(d.base, suffix)}</td>
      <td class="num">${moneyFull(d.tax, suffix)}</td>
      <td><div class="table-sub">${rates}</div></td>
    </tr>`;
  }).join("");
}

function downloadReport() {
  const q = reportQuery();
  if (!q) { showToast(tt("taxes.selectPeriod"), "warning"); return; }
  window.open("/documents/tax-report/pdf?" + q, "_blank");
}
window.downloadReport = downloadReport;

/* ===== Init ===== */
async function loadData() {
  const [cRes, yRes] = await Promise.all([
    api.get("/api/companies"),
    api.get("/api/financial-years"),
  ]);
  companiesData = cRes.companies || [];
  yearsData = yRes.years || [];
  document.getElementById("report-company").innerHTML =
    `<option value="">${tt("taxes.filterCompany")}</option>` +
    companiesData.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  document.getElementById("report-year").innerHTML =
    `<option value="">${tt("taxes.allYears")}</option>` +
    yearsData.map((y) => `<option value="${y.id}">${escapeHtml(y.name)} — ${escapeHtml(y.company_name || "")}</option>`).join("");

  const activeYear = yearsData.find((y) => y.is_active);
  if (activeYear) {
    document.getElementById("report-year").value = activeYear.id;
    loadReport();
  } else {
    const now = new Date();
    const to = now.toISOString().slice(0, 10);
    const from = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
    document.getElementById("report-start").value = from;
    document.getElementById("report-end").value = to;
    loadReport();
  }
}

document.addEventListener("DOMContentLoaded", loadData);

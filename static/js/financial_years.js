const FYT = window.T || {};

function ct(key) {
  if (FYT[key] !== undefined && FYT[key] !== null) return FYT[key];
  return key;
}

let yearsData = [];
let companiesData = [];
let companyFilter = "";

async function loadData() {
  const [yRes, cRes] = await Promise.all([
    api.get("/api/financial-years"),
    api.get("/api/companies"),
  ]);
  yearsData = yRes.years || [];
  companiesData = cRes.companies || [];
  fillCompanySelects();
  renderKPI();
  renderYears();
}

function companyName(id) {
  const c = companiesData.find((x) => x.id === id);
  return c ? c.name : "—";
}

function fillCompanySelects() {
  const options = companiesData.map((c) =>
    `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  document.getElementById("filter-company").innerHTML =
    `<option value="">${ct("financialYears.selectCompany")}</option>` + options;
  document.getElementById("year-company").innerHTML =
    `<option value="">${ct("financialYears.selectCompany")}</option>` + options;
}

function renderKPI() {
  const open = yearsData.filter((y) => !y.is_closed).length;
  const closed = yearsData.filter((y) => y.is_closed).length;
  const docs = yearsData.reduce((acc, y) => acc + (y.invoices || 0) + (y.orders || 0) + (y.contracts || 0) + (y.plans || 0), 0);
  document.getElementById("kpi-total").textContent = yearsData.length;
  document.getElementById("kpi-open").textContent = open;
  document.getElementById("kpi-closed").textContent = closed;
  document.getElementById("kpi-docs").textContent = docs;
}

function filterYears() {
  companyFilter = document.getElementById("filter-company").value || "";
  renderYears();
}
window.filterYears = filterYears;

function renderYears() {
  const list = companyFilter
    ? yearsData.filter((y) => String(y.company_id) === companyFilter)
    : yearsData;

  document.getElementById("years-empty").style.display = list.length ? "none" : "block";
  const emptyText = companiesData.length
    ? ct("financialYears.noYears")
    : ct("financialYears.noCompanies");
  document.getElementById("years-empty-text").textContent = emptyText;

  const canEdit = canAction("financial_years", "edit");
  const canDelete = canAction("financial_years", "delete");

  document.getElementById("years-table").innerHTML = list.map((y) => {
    const totalDocs = (y.invoices || 0) + (y.orders || 0) + (y.contracts || 0) + (y.plans || 0);
    const status = [
      y.is_active ? `<span class="badge badge-primary">${ct("financialYears.active")}</span>` : "",
      y.is_closed ? `<span class="badge badge-danger">${ct("financialYears.closed")}</span>` : `<span class="badge badge-success">${ct("financialYears.open")}</span>`,
    ].join(" ");
    return `<tr>
      <td><div class="cell-main">${escapeHtml(y.name)}</div></td>
      <td><a href="javascript:void(0)" class="fy-company-link" onclick="openCompanyDocs(${y.company_id})">${escapeHtml(y.company_name || companyName(y.company_id))}</a></td>
      <td><div class="table-sub">${formatDate(y.start_date)} → ${formatDate(y.end_date)}</div></td>
      <td>${status}</td>
      <td>
        <div class="doc-counts">
          <span class="doc-count">🧾 ${y.invoices || 0}</span>
          <span class="doc-count">📦 ${y.orders || 0}</span>
          <span class="doc-count">🏢 ${y.contracts || 0}</span>
          <span class="doc-count">💳 ${y.plans || 0}</span>
        </div>
      </td>
      <td><div class="table-actions">
        ${`<button class="btn btn-outline btn-sm" onclick="window.open('/reports/financial-year/${y.id}', '_blank')">${ct("fyReport.reportBtn")}</button>`}
        ${canEdit && !y.is_closed && !y.is_active ? `<button class="btn btn-secondary btn-sm" onclick="activateYear(${y.id})">${ct("financialYears.activate")}</button>` : ""}
        ${canEdit && !y.is_closed ? `<button class="btn btn-secondary btn-sm" onclick="closeYear(${y.id})">${ct("financialYears.closeYear")}</button>` : ""}
        ${canEdit && y.is_closed ? `<button class="btn btn-outline btn-sm" onclick="openYear(${y.id})">${ct("financialYears.openYear")}</button>` : ""}
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editYear(${JSON.stringify(y)})'>${ct("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteYear(${y.id})">${ct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

/* ===== Modal ===== */
function fyOpenModal(id) { document.getElementById(id).style.display = "flex"; }
function fyCloseModal(id) { document.getElementById(id).style.display = "none"; }

function openYearModal() {
  document.getElementById("year-modal-title").textContent = ct("financialYears.addYear");
  document.getElementById("year-id").value = "";
  document.getElementById("year-name").value = "";
  document.getElementById("year-start").value = "";
  document.getElementById("year-end").value = "";
  document.getElementById("year-active").checked = true;
  fillCompanySelects();
  const active = companiesData.find((c) => c.is_active);
  if (active) document.getElementById("year-company").value = active.id;
  fyOpenModal("year-modal");
  setTimeout(() => document.getElementById("year-name").focus(), 50);
}
window.openYearModal = openYearModal;

function editYear(y) {
  document.getElementById("year-modal-title").textContent = ct("financialYears.editYear");
  document.getElementById("year-id").value = y.id;
  document.getElementById("year-company").value = y.company_id;
  document.getElementById("year-name").value = y.name || "";
  document.getElementById("year-start").value = y.start_date || "";
  document.getElementById("year-end").value = y.end_date || "";
  document.getElementById("year-active").checked = !!y.is_active;
  fyOpenModal("year-modal");
}
window.editYear = editYear;

function closeYearModal() { fyCloseModal("year-modal"); }
window.closeYearModal = closeYearModal;

function closeDocsModal() { fyCloseModal("docs-modal"); }
window.closeDocsModal = closeDocsModal;

function openCompanyDocs(companyId) {
  const company = companiesData.find((c) => c.id === companyId);
  const rows = yearsData.filter((y) => y.company_id === companyId);
  const body = document.getElementById("docs-modal-body");
  if (!rows.length) {
    body.innerHTML = `<div class="empty-state"><div class="empty-icon">🗓️</div>${ct("financialYears.noYears")}</div>`;
  } else {
    body.innerHTML = `<h4 style="margin:0 0 14px;">${escapeHtml(company ? company.name : "")}</h4>` +
      rows.map((y) => {
        const status = [
          y.is_active ? `<span class="badge badge-primary">${ct("financialYears.active")}</span>` : "",
          y.is_closed ? `<span class="badge badge-danger">${ct("financialYears.closed")}</span>` : `<span class="badge badge-success">${ct("financialYears.open")}</span>`,
        ].join(" ");
        return `<div class="doc-card">
          <div class="cell-main">${escapeHtml(y.name)}</div>
          <div class="table-sub">${formatDate(y.start_date)} → ${formatDate(y.end_date)}</div>
          <div style="margin:6px 0;">${status}</div>
          <div class="doc-counts">
            <span class="doc-count">🧾 ${y.invoices || 0}</span>
            <span class="doc-count">📦 ${y.orders || 0}</span>
            <span class="doc-count">🏢 ${y.contracts || 0}</span>
            <span class="doc-count">💳 ${y.plans || 0}</span>
          </div>
          <div style="margin-top:8px;"><button class="btn btn-outline btn-sm" onclick="window.open('/reports/financial-year/${y.id}', '_blank')">${ct("fyReport.reportBtn")}</button></div>
        </div>`;
      }).join("");
  }
  document.getElementById("docs-modal-title").textContent = ct("financialYears.documentsSummary");
  fyOpenModal("docs-modal");
}
window.openCompanyDocs = openCompanyDocs;

async function saveYear() {
  const id = document.getElementById("year-id").value;
  const payload = {
    company_id: document.getElementById("year-company").value,
    name: document.getElementById("year-name").value,
    start_date: document.getElementById("year-start").value,
    end_date: document.getElementById("year-end").value,
    is_active: document.getElementById("year-active").checked,
  };
  if (!payload.company_id) { showToast(ct("financialYears.companyRequired"), "warning"); return; }
  if (!payload.name.trim()) { showToast(ct("financialYears.nameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/financial-years/${id}`, payload);
    else await api.post("/api/financial-years", payload);
    showToast(ct("financialYears.saved"));
    closeYearModal();
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveYear = saveYear;

async function deleteYear(id) {
  const y = yearsData.find((x) => x.id === id);
  if (!confirm(ct("financialYears.confirmDelete") + " " + (y ? y.name : ""))) return;
  try {
    await api.delete(`/api/financial-years/${id}`);
    showToast(ct("financialYears.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteYear = deleteYear;

async function closeYear(id) {
  if (!confirm(ct("financialYears.confirmClose"))) return;
  try {
    await api.post(`/api/financial-years/${id}/close`, {});
    showToast(ct("financialYears.closedMsg"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.closeYear = closeYear;

async function openYear(id) {
  try {
    await api.post(`/api/financial-years/${id}/open`, {});
    showToast(ct("financialYears.openedMsg"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.openYear = openYear;

async function activateYear(id) {
  try {
    await api.post(`/api/financial-years/${id}/activate`, {});
    showToast(ct("financialYears.activated"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.activateYear = activateYear;

document.addEventListener("DOMContentLoaded", loadData);

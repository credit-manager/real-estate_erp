/* ============================================================
   Currencies Module JavaScript
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

let currenciesData = [];
let companiesData = [];
let companyFilter = "";

async function loadData() {
  const [cRes, compRes] = await Promise.all([
    api.get("/api/currencies"),
    api.get("/api/companies"),
  ]);
  currenciesData = cRes.currencies || [];
  companiesData = compRes.companies || [];
  fillCompanySelects();
  renderKPI();
  renderCurrencies();
}

function companyName(id) {
  const c = companiesData.find((x) => x.id === id);
  return c ? c.name : "—";
}

function fillCompanySelects() {
  const options = companiesData.map((c) =>
    `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  document.getElementById("filter-company").innerHTML =
    `<option value="">${cct("currencies.selectCompany")}</option>` + options;
  document.getElementById("currency-company").innerHTML =
    `<option value="">${cct("currencies.selectCompany")}</option>` + options;
}

function renderKPI() {
  const base = currenciesData.filter((c) => c.is_base).length;
  const active = currenciesData.filter((c) => c.is_active).length;
  document.getElementById("kpi-total").textContent = currenciesData.length;
  document.getElementById("kpi-base").textContent = base;
  document.getElementById("kpi-active").textContent = active;
}

function filterCurrencies() {
  companyFilter = document.getElementById("filter-company").value || "";
  renderCurrencies();
}
window.filterCurrencies = filterCurrencies;

function renderCurrencies() {
  const list = companyFilter
    ? currenciesData.filter((c) => String(c.company_id) === companyFilter)
    : currenciesData;

  document.getElementById("currencies-empty").style.display = list.length ? "none" : "block";
  const emptyText = companiesData.length
    ? cct("currencies.noCurrencies")
    : cct("currencies.noCompanies");
  document.getElementById("currencies-empty-text").textContent = emptyText;

  const canEdit = canAction("currencies", "edit");
  const canDelete = canAction("currencies", "delete");

  document.getElementById("currencies-table").innerHTML = list.map((c) => {
    const status = c.is_base
      ? `<span class="badge badge-primary">${cct("currencies.base")}</span>`
      : c.is_active
        ? `<span class="badge badge-success">${cct("currencies.active")}</span>`
        : `<span class="badge badge-neutral">${cct("currencies.inactive")}</span>`;
    return `<tr>
      <td><div class="cell-main">${escapeHtml(c.code)}</div>${c.symbol ? `<div class="table-sub">${escapeHtml(c.symbol)}</div>` : ""}</td>
      <td>${escapeHtml(c.company_name || companyName(c.company_id))}</td>
      <td>${escapeHtml(c.name)}</td>
      <td><div class="table-sub">${escapeHtml(c.symbol || "—")}</div></td>
      <td><strong>${formatNumber(c.rate)}</strong></td>
      <td>${status}</td>
      <td><div class="table-actions">
        ${canEdit && !c.is_base ? `<button class="btn btn-outline btn-sm" onclick="setBase(${c.id})">${cct("currencies.setBase")}</button>` : ""}
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editCurrency(${JSON.stringify(c)})'>${cct("common.edit")}</button>` : ""}
        ${canDelete && !c.is_base ? `<button class="btn btn-danger btn-sm" onclick="deleteCurrency(${c.id})">${cct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

/* ===== Modal ===== */
function curOpenModal(id) { document.getElementById(id).style.display = "flex"; }
function curCloseModal(id) { document.getElementById(id).style.display = "none"; }

function openCurrencyModal() {
  document.getElementById("currency-modal-title").textContent = cct("currencies.add");
  document.getElementById("currency-id").value = "";
  document.getElementById("currency-code").value = "";
  document.getElementById("currency-name").value = "";
  document.getElementById("currency-symbol").value = "";
  document.getElementById("currency-rate").value = "1";
  document.getElementById("currency-base").checked = false;
  fillCompanySelects();
  const active = companiesData.find((c) => c.is_active);
  if (active) document.getElementById("currency-company").value = active.id;
  curOpenModal("currency-modal");
  setTimeout(() => document.getElementById("currency-code").focus(), 50);
}
window.openCurrencyModal = openCurrencyModal;

function editCurrency(c) {
  document.getElementById("currency-modal-title").textContent = cct("currencies.edit");
  document.getElementById("currency-id").value = c.id;
  document.getElementById("currency-company").value = c.company_id;
  document.getElementById("currency-code").value = c.code || "";
  document.getElementById("currency-name").value = c.name || "";
  document.getElementById("currency-symbol").value = c.symbol || "";
  document.getElementById("currency-rate").value = c.rate;
  document.getElementById("currency-base").checked = !!c.is_base;
  curOpenModal("currency-modal");
}
window.editCurrency = editCurrency;

function closeCurrencyModal() { curCloseModal("currency-modal"); }
window.closeCurrencyModal = closeCurrencyModal;

async function saveCurrency() {
  const id = document.getElementById("currency-id").value;
  const payload = {
    company_id: document.getElementById("currency-company").value,
    code: document.getElementById("currency-code").value,
    name: document.getElementById("currency-name").value,
    symbol: document.getElementById("currency-symbol").value,
    rate: document.getElementById("currency-rate").value,
    is_base: document.getElementById("currency-base").checked,
  };
  if (!payload.company_id) { showToast(cct("currencies.companyRequired"), "warning"); return; }
  if (!payload.name.trim()) { showToast(cct("currencies.nameRequired"), "warning"); return; }
  if (!payload.code.trim()) { showToast(cct("currencies.codeRequired"), "warning"); return; }
  if (!payload.rate || parseFloat(payload.rate) <= 0) { showToast(cct("currencies.rateInvalid"), "warning"); return; }
  try {
    if (id) await api.put(`/api/currencies/${id}`, payload);
    else await api.post("/api/currencies", payload);
    showToast(cct("currencies.saved"));
    closeCurrencyModal();
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveCurrency = saveCurrency;

async function deleteCurrency(id) {
  const c = currenciesData.find((x) => x.id === id);
  if (!confirm(cct("currencies.confirmDelete") + " " + (c ? c.code : ""))) return;
  try {
    await api.delete(`/api/currencies/${id}`);
    showToast(cct("currencies.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteCurrency = deleteCurrency;

async function setBase(id) {
  try {
    await api.put(`/api/currencies/${id}`, { is_base: true });
    showToast(cct("currencies.baseMsg"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.setBase = setBase;

document.addEventListener("DOMContentLoaded", loadData);

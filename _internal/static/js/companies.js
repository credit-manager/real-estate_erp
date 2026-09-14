const CS = window.CS || "ar";
const CT = window.T || {};

function ct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

let companiesData = [];
let branchesData = [];
let activeTab = "companies";
let companyQuery = "";

const COMPANY_ICONS = ["🏢", "🏗️", "🏘️", "🏬", "🏭", "🏦", "🧱", "🏠", "📊", "🔨"];

function companyColor(i) {
  const colors = ["kpi-olive", "kpi-sage", "kpi-brown", "kpi-terracotta", "kpi-clay", "kpi-moss", "kpi-sand", "kpi-terra"];
  return colors[i % colors.length];
}

function switchTab(tab) {
  activeTab = tab;
  document.getElementById("tab-companies").classList.toggle("chip-active", tab === "companies");
  document.getElementById("tab-branches").classList.toggle("chip-active", tab === "branches");
  document.getElementById("panel-companies").style.display = tab === "companies" ? "" : "none";
  document.getElementById("panel-branches").style.display = tab === "branches" ? "" : "none";
}
window.switchTab = switchTab;

function openModal(id) {
  document.getElementById(id).style.display = "flex";
}
function closeModal(id) {
  document.getElementById(id).style.display = "none";
}

async function loadData() {
  const [cRes, bRes] = await Promise.all([
    api.get("/api/companies"),
    api.get("/api/companies/branches"),
  ]);
  companiesData = cRes.companies || [];
  branchesData = bRes.branches || [];
  renderKPI();
  renderCompanies();
  renderBranches();
  fillBranchCompanies();
}

function renderKPI() {
  const active = companiesData.filter((c) => c.is_active).length;
  document.getElementById("kpi-companies").textContent = companiesData.length;
  document.getElementById("kpi-active").textContent = active;
  document.getElementById("kpi-branches").textContent = branchesData.length;
  document.getElementById("tab-companies-count").textContent = `(${companiesData.length})`;
  document.getElementById("tab-branches-count").textContent = `(${branchesData.length})`;
}

function companyName(id) {
  const c = companiesData.find((x) => x.id === id);
  return c ? c.name : "—";
}

function statusBadge(active) {
  return active
    ? `<span class="badge badge-success">${ct("companies.activeStatus")}</span>`
    : `<span class="badge badge-secondary">${ct("companies.inactiveStatus")}</span>`;
}

function detail(label, value) {
  if (!value) return "";
  return `<div class="company-detail"><span>${label}</span><b>${escapeHtml(value)}</b></div>`;
}

function renderCompanies() {
  const q = companyQuery.trim().toLowerCase();
  const list = q
    ? companiesData.filter((c) =>
        (c.name + " " + (c.legal_name || "") + " " + (c.tax_number || "") + " " + (c.commercial_registration || ""))
          .toLowerCase().includes(q)
      )
    : companiesData;

  document.getElementById("companies-empty").style.display = list.length ? "none" : "block";
  document.getElementById("companies-count").textContent = `(${list.length})`;
  const canEdit = canAction("companies", "edit");
  const canDelete = canAction("companies", "delete");

  document.getElementById("companies-table").innerHTML = list.map((c) => {
    const branches = c.branches || [];
    return `<tr>
      <td><div class="cell-main">${escapeHtml(c.name)}</div></td>
      <td><div class="table-sub">${escapeHtml(c.legal_name || "—")}</div></td>
      <td>${escapeHtml(c.tax_number || "—")}</td>
      <td>${escapeHtml(c.commercial_registration || "—")}</td>
      <td>${escapeHtml(c.phone || "—")}</td>
      <td><span class="badge badge-neutral">${escapeHtml(c.currency || "EGP")}</span></td>
      <td>${branches.length}</td>
      <td>${statusBadge(c.is_active)}</td>
      <td><div class="table-actions">
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editCompany(${JSON.stringify(c)})'>${ct("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteCompany(${c.id})">${ct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

function filterCompanies() {
  companyQuery = document.getElementById("company-search").value || "";
  renderCompanies();
}
window.filterCompanies = filterCompanies;

function renderBranches() {
  const tbody = document.getElementById("branches-table");
  document.getElementById("branches-empty").style.display =
    branchesData.length ? "none" : "block";
  document.getElementById("branches-count").textContent = `(${branchesData.length})`;
  const canEdit = canAction("companies", "edit");
  const canDelete = canAction("companies", "delete");
  tbody.innerHTML = branchesData.map((b) => {
    return `<tr>
      <td><div class="cell-main">${escapeHtml(b.name)}</div></td>
      <td>${escapeHtml(companyName(b.company_id))}</td>
      <td><span class="badge badge-neutral">${escapeHtml(b.code || "—")}</span></td>
      <td>${escapeHtml(b.city || "—")}</td>
      <td>${escapeHtml(b.manager_name || "—")}</td>
      <td>${escapeHtml(b.phone || "—")}</td>
      <td>${statusBadge(b.is_active)}</td>
      <td><div class="table-actions">
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editBranch(${JSON.stringify(b)})'>${ct("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteBranch(${b.id})">${ct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

function fillBranchCompanies() {
  const sel = document.getElementById("branch-company");
  const active = companiesData.filter((c) => c.is_active);
  sel.innerHTML = active.map((c) =>
    `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  sel.value = active.length ? String(active[0].id) : "";
}

/* ===== Company ===== */
function openCompanyModal() {
  document.getElementById("company-id").value = "";
  ["company-name", "company-legal-name", "company-tax", "company-reg",
   "company-phone", "company-email", "company-website", "company-address"].forEach(
    (id) => (document.getElementById(id).value = "")
  );
  document.getElementById("company-currency").value = "EGP";
  document.getElementById("company-active").checked = true;
  document.getElementById("company-modal-title").textContent = ct("companies.addCompany");
  openModal("company-modal");
  setTimeout(() => document.getElementById("company-name").focus(), 50);
}
window.openCompanyModal = openCompanyModal;

function closeCompanyModal() { closeModal("company-modal"); }
window.closeCompanyModal = closeCompanyModal;

function editCompany(c) {
  document.getElementById("company-id").value = c.id;
  document.getElementById("company-name").value = c.name || "";
  document.getElementById("company-legal-name").value = c.legal_name || "";
  document.getElementById("company-tax").value = c.tax_number || "";
  document.getElementById("company-reg").value = c.commercial_registration || "";
  document.getElementById("company-phone").value = c.phone || "";
  document.getElementById("company-email").value = c.email || "";
  document.getElementById("company-website").value = c.website || "";
  document.getElementById("company-currency").value = c.currency || "EGP";
  document.getElementById("company-address").value = c.address || "";
  document.getElementById("company-active").checked = !!c.is_active;
  document.getElementById("company-modal-title").textContent = ct("companies.editCompany");
  openModal("company-modal");
}
window.editCompany = editCompany;

async function saveCompany() {
  const id = document.getElementById("company-id").value;
  const payload = {
    name: document.getElementById("company-name").value,
    legal_name: document.getElementById("company-legal-name").value,
    tax_number: document.getElementById("company-tax").value,
    commercial_registration: document.getElementById("company-reg").value,
    phone: document.getElementById("company-phone").value,
    email: document.getElementById("company-email").value,
    website: document.getElementById("company-website").value,
    currency: document.getElementById("company-currency").value,
    address: document.getElementById("company-address").value,
    is_active: document.getElementById("company-active").checked,
  };
  if (!payload.name.trim()) {
    showToast(ct("companies.nameRequired"), "warning");
    return;
  }
  try {
    if (id) {
      await api.put(`/api/companies/${id}`, payload);
    } else {
      await api.post("/api/companies", payload);
    }
    closeCompanyModal();
    showToast(ct("companies.saved"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveCompany = saveCompany;

async function deleteCompany(id) {
  const c = companiesData.find((x) => x.id === id);
  if (!confirm(ct("companies.confirmDelete") + " " + (c ? c.name : ""))) return;
  try {
    await api.delete(`/api/companies/${id}`);
    showToast(ct("companies.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteCompany = deleteCompany;

/* ===== Branch ===== */
function openBranchModal() {
  document.getElementById("branch-id").value = "";
  ["branch-name", "branch-code", "branch-city", "branch-manager",
   "branch-phone", "branch-address"].forEach(
    (id) => (document.getElementById(id).value = "")
  );
  document.getElementById("branch-active").checked = true;
  fillBranchCompanies();
  document.getElementById("branch-modal-title").textContent = ct("companies.addBranch");
  openModal("branch-modal");
  setTimeout(() => document.getElementById("branch-name").focus(), 50);
}
window.openBranchModal = openBranchModal;

function closeBranchModal() { closeModal("branch-modal"); }
window.closeBranchModal = closeBranchModal;

function editBranch(b) {
  document.getElementById("branch-id").value = b.id;
  document.getElementById("branch-company").value = b.company_id;
  document.getElementById("branch-name").value = b.name || "";
  document.getElementById("branch-code").value = b.code || "";
  document.getElementById("branch-city").value = b.city || "";
  document.getElementById("branch-manager").value = b.manager_name || "";
  document.getElementById("branch-phone").value = b.phone || "";
  document.getElementById("branch-address").value = b.address || "";
  document.getElementById("branch-active").checked = !!b.is_active;
  document.getElementById("branch-modal-title").textContent = ct("companies.editBranch");
  openModal("branch-modal");
}
window.editBranch = editBranch;

async function saveBranch() {
  const id = document.getElementById("branch-id").value;
  const payload = {
    company_id: document.getElementById("branch-company").value,
    name: document.getElementById("branch-name").value,
    code: document.getElementById("branch-code").value,
    city: document.getElementById("branch-city").value,
    manager_name: document.getElementById("branch-manager").value,
    phone: document.getElementById("branch-phone").value,
    address: document.getElementById("branch-address").value,
    is_active: document.getElementById("branch-active").checked,
  };
  if (!payload.name.trim()) {
    showToast(ct("companies.nameRequired"), "warning");
    return;
  }
  try {
    if (id) {
      await api.put(`/api/companies/branches/${id}`, payload);
    } else {
      await api.post(`/api/companies/${payload.company_id}/branches`, payload);
    }
    closeBranchModal();
    showToast(ct("companies.saved"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveBranch = saveBranch;

async function deleteBranch(id) {
  const b = branchesData.find((x) => x.id === id);
  if (!confirm(ct("companies.confirmDelete") + " " + (b ? b.name : ""))) return;
  try {
    await api.delete(`/api/companies/branches/${id}`);
    showToast(ct("companies.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteBranch = deleteBranch;

document.addEventListener("DOMContentLoaded", loadData);

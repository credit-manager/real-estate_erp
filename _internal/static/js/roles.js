/* ============================================================
   Roles & Permissions Module JavaScript
   ============================================================ */

let allRoles = [];
let allUsers = [];
let META = { modules: [], actions: ["view", "create", "edit", "delete"] };
let currentPerms = {};

const MODULE_LABEL_KEYS = {
  dashboard: "nav.dashboard",
  projects: "nav.projects",
  sales: "nav.sales",
  procurement: "nav.procurement",
  inventory: "nav.inventory",
  manufacturing: "nav.manufacturing",
  finance: "nav.finance",
  accounting: "nav.accounting",
  hr: "nav.hr",
  payroll: "nav.payroll",
  realestate: "nav.realestate",
  rentals: "nav.rentals",
  crm: "nav.crm",
  reports: "nav.reports",
  audit: "nav.audit",
  backup: "nav.backup",
  users: "nav.users",
  roles: "nav.roles",
  settings: "nav.serverSettings",
  companies: "nav.companies",
  financial_years: "nav.financialYears",
  currencies: "nav.currencies",
  taxes: "nav.taxes",
  workflow: "nav.workflowApprovals",
};

function moduleLabel(module) {
  const key = MODULE_LABEL_KEYS[module] || module;
  return t(key);
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const [meta, roles, users] = await Promise.all([
      api.get("/api/roles/meta"),
      api.get("/api/roles"),
      api.get("/api/users"),
    ]);
    META = meta;
    allRoles = roles;
    allUsers = users;
    renderRoles();
    renderSummary();
  } catch (err) {
    console.error(err);
  }
});

function roleUsersCount(name) {
  return allUsers.filter((u) => u.role === name).length;
}

function permSummary(role) {
  const perms = role.permissions || {};
  const modules = META.modules || [];
  const viewCount = modules.filter((m) => perms[m] && perms[m].view).length;
  const editCount = modules.filter((m) => perms[m] && (perms[m].create || perms[m].edit || perms[m].delete)).length;
  return `<span class="perm-summary">${viewCount}/${modules.length} ${t("roles.modules")}${editCount ? ` · ${t("roles.actionEdit")} ${editCount}` : ""}</span>`;
}

function renderRoles() {
  const tbody = document.getElementById("roles-table");
  if (!allRoles.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><div class="empty-icon">🛡️</div>${t("roles.noRoles")}</div></td></tr>`;
    return;
  }
  const canEdit = canAction("roles", "edit");
  const canDelete = canAction("roles", "delete");
  tbody.innerHTML = allRoles.map((r) => {
    const usersCount = roleUsersCount(r.name);
    const actions = [];
    if (canEdit) actions.push(`<button class="btn btn-secondary btn-sm" onclick='editRole(${JSON.stringify(r)})'>${t("common.edit")}</button>`);
    if (canDelete && !r.is_system) actions.push(`<button class="btn btn-danger btn-sm" onclick="deleteRole(${r.id})">${t("common.delete")}</button>`);
    return `
    <tr>
      <td>
        <strong>${escapeHtml(r.name)}</strong>
        ${r.is_system ? ` <span class="badge badge-neutral">${t("roles.systemBadge")}</span>` : ""}
      </td>
      <td style="color:var(--muted-foreground);">${escapeHtml(r.description) || "—"}</td>
      <td style="color:var(--muted-foreground);">${formatNumber(usersCount)}</td>
      <td>${permSummary(r)}</td>
      <td>
        <div class="table-actions">${actions.join("")}</div>
      </td>
    </tr>`;
  }).join("");
}

function renderSummary() {
  const totalUsers = allUsers.length;
  animateCount(document.getElementById("role-total"), allRoles.length, formatNumber);
  animateCount(document.getElementById("role-users"), totalUsers, formatNumber);
}

function emptyPerms() {
  const p = {};
  META.modules.forEach((m) => {
    p[m] = {};
    META.actions.forEach((a) => (p[m][a] = false));
  });
  return p;
}

function renderPermMatrix() {
  const container = document.getElementById("perm-matrix");
  const actionLabels = {
    view: t("roles.actionView"),
    create: t("roles.actionCreate"),
    edit: t("roles.actionEdit"),
    delete: t("roles.actionDelete"),
  };
  let html = `<div class="perm-row perm-head">
      <span class="perm-module">${t("roles.modules")}</span>
      ${META.actions.map((a) => `<span class="perm-action">${actionLabels[a] || a}</span>`).join("")}
    </div>`;
  META.modules.forEach((m) => {
    html += `<div class="perm-row">
      <span class="perm-module">${escapeHtml(moduleLabel(m))}</span>
      ${META.actions.map((a) => `
        <span class="perm-action">
          <input type="checkbox" class="perm-check" data-module="${m}" data-action="${a}"
            ${currentPerms[m] && currentPerms[m][a] ? "checked" : ""}>
        </span>`).join("")}
    </div>`;
  });
  container.innerHTML = html;
}

function collectPerms() {
  document.querySelectorAll(".perm-check").forEach((cb) => {
    const m = cb.dataset.module;
    const a = cb.dataset.action;
    if (!currentPerms[m]) currentPerms[m] = {};
    currentPerms[m][a] = cb.checked;
  });
}

function setAllPerms(value) {
  document.querySelectorAll(".perm-check").forEach((cb) => (cb.checked = value));
}

// ===== Modal =====
function openRoleModal() {
  document.getElementById("role-modal-title").textContent = t("roles.newRole");
  document.getElementById("role-id").value = "";
  document.getElementById("role-name").value = "";
  document.getElementById("role-description").value = "";
  currentPerms = emptyPerms();
  renderPermMatrix();
  document.getElementById("role-modal").classList.add("active");
  document.getElementById("role-name").focus();
}

function editRole(r) {
  document.getElementById("role-modal-title").textContent = t("roles.editRole");
  document.getElementById("role-id").value = r.id;
  document.getElementById("role-name").value = r.name || "";
  document.getElementById("role-description").value = r.description || "";
  currentPerms = emptyPerms();
  META.modules.forEach((m) => {
    META.actions.forEach((a) => {
      currentPerms[m][a] = !!(r.permissions && r.permissions[m] && r.permissions[m][a]);
    });
  });
  renderPermMatrix();
  document.getElementById("role-modal").classList.add("active");
}

function closeRoleModal() {
  document.getElementById("role-modal").classList.remove("active");
}

async function saveRole() {
  collectPerms();
  const id = document.getElementById("role-id").value;
  const body = {
    name: document.getElementById("role-name").value.trim(),
    description: document.getElementById("role-description").value.trim(),
    permissions: currentPerms,
  };

  if (!body.name) { showToast(t("roles.nameRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/roles/${id}`, body);
    else await api.post("/api/roles", body);
    showToast(t("roles.saved"));
    closeRoleModal();
    allRoles = await api.get("/api/roles");
    renderRoles();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteRole(id) {
  if (!confirm(t("roles.confirmDelete"))) return;
  try {
    await api.delete(`/api/roles/${id}`);
    showToast(t("common.deleted"));
    allRoles = await api.get("/api/roles");
    renderRoles();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openRoleModal = openRoleModal;
window.closeRoleModal = closeRoleModal;
window.editRole = editRole;
window.deleteRole = deleteRole;
window.saveRole = saveRole;
window.setAllPerms = setAllPerms;

/* ============================================================
   User Management Module JavaScript
   ============================================================ */

let allUsers = [];
let allRoles = [];
let currentUserId = null;

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const me = await api.get("/api/me");
    currentUserId = me.user.id;
  } catch (err) {
    currentUserId = null;
  }
  try {
    const [users, roles] = await Promise.all([
      api.get("/api/users"),
      api.get("/api/roles"),
    ]);
    allUsers = users;
    allRoles = roles;
    renderRoles();
    renderUsers();
    renderSummary();
  } catch (err) {
    console.error(err);
  }
});

function renderRoles() {
  const select = document.getElementById("user-role");
  if (!select) return;
  const options = allRoles
    .map((r) => `<option value="${escapeHtml(r.name)}">${escapeHtml(r.name)}</option>`)
    .join("");
  select.innerHTML = options || `<option value="employee">employee</option>`;
}

function roleBadge(role) {
  const r = allRoles.find((x) => x.name === role);
  if (role === "admin") return `<span class="badge badge-info">${escapeHtml(role)}</span>`;
  if (r && r.is_system) return `<span class="badge badge-neutral">${escapeHtml(role)}</span>`;
  return `<span class="badge badge-neutral">${escapeHtml(role)}</span>`;
}

function activeBadge(active) {
  if (active) return `<span class="badge badge-success">${t("users.activeStatus")}</span>`;
  return `<span class="badge badge-danger">${t("users.inactiveStatus")}</span>`;
}

function renderUsers() {
  const tbody = document.getElementById("users-table");
  const canEdit = canAction("users", "edit");
  const canDelete = canAction("users", "delete");
  if (!allUsers.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">👤</div>${t("users.noUsers")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allUsers.map((u) => `
    <tr>
      <td><strong>${escapeHtml(u.username)}</strong></td>
      <td style="color:var(--muted-foreground);">${escapeHtml(u.full_name)}</td>
      <td>${roleBadge(u.role)}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(u.email) || "—"}</td>
      <td>${activeBadge(u.is_active)}</td>
      <td>
        <div class="table-actions">
          ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editUser(${JSON.stringify(u)})'>${t("common.edit")}</button>` : ""}
          ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function renderSummary() {
  animateCount(document.getElementById("user-total"), allUsers.length, formatNumber);
  animateCount(document.getElementById("user-active"), allUsers.filter((u) => u.is_active).length, formatNumber);
  animateCount(document.getElementById("user-admins"), allUsers.filter((u) => u.role === "admin").length, formatNumber);
}

function exportUsers() {
  const headers = [
    t("users.colUsername"), t("users.colName"), t("users.colRole"),
    t("users.colEmail"), t("users.colStatus"),
  ];
  const rows = allUsers.map((u) => [
    u.username, u.full_name,
    u.role === "admin" ? t("users.roleAdmin") : t("users.roleEmployee"),
    u.email || "",
    u.is_active ? t("users.activeStatus") : t("users.inactiveStatus"),
  ]);
  exportCSV("users.csv", headers, rows);
}

// ===== Modal =====
function openUserModal() {
  document.getElementById("user-modal-title").textContent = t("users.newUser");
  document.getElementById("user-id").value = "";
  ["user-username", "user-fullname", "user-email", "user-password"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("user-role").value = "employee";
  document.getElementById("user-active").value = "1";
  document.getElementById("password-hint").textContent = t("users.passwordHint");
  document.getElementById("user-modal").classList.add("active");
  document.getElementById("user-username").focus();
}

function editUser(u) {
  document.getElementById("user-modal-title").textContent = t("users.editUser");
  document.getElementById("user-id").value = u.id;
  document.getElementById("user-username").value = u.username || "";
  document.getElementById("user-fullname").value = u.full_name || "";
  document.getElementById("user-email").value = u.email || "";
  document.getElementById("user-password").value = "";
  document.getElementById("user-role").value = u.role || "employee";
  document.getElementById("user-active").value = u.is_active ? "1" : "0";
  document.getElementById("password-hint").textContent = t("users.passwordHint");
  document.getElementById("user-modal").classList.add("active");
}

function closeUserModal() {
  document.getElementById("user-modal").classList.remove("active");
}

async function saveUser() {
  const id = document.getElementById("user-id").value;
  const body = {
    username: document.getElementById("user-username").value.trim(),
    full_name: document.getElementById("user-fullname").value.trim(),
    email: document.getElementById("user-email").value.trim(),
    role: document.getElementById("user-role").value,
    is_active: document.getElementById("user-active").value === "1",
    password: document.getElementById("user-password").value,
  };

  if (!body.username) { showToast(t("users.usernameRequired"), "warning"); return; }
  if (!body.full_name) { showToast(t("users.fullNameRequired"), "warning"); return; }
  if (!id && !body.password) { showToast(t("users.passwordRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/users/${id}`, body);
    else await api.post("/api/users", body);
    showToast(t("common.saved"));
    closeUserModal();
    allUsers = await api.get("/api/users");
    renderUsers();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteUser(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/users/${id}`);
    showToast(t("common.deleted"));
    allUsers = await api.get("/api/users");
    renderUsers();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openUserModal = openUserModal;
window.closeUserModal = closeUserModal;
window.editUser = editUser;
window.deleteUser = deleteUser;
window.saveUser = saveUser;

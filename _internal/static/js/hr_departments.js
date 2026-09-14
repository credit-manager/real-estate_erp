/* HR Departments */
let deptsData = [];
let deptManagers = [];

async function loadDepartments() {
  try {
    const [depts, emps] = await Promise.all([
      api.get("/api/hr/departments"),
      api.get("/api/hr/employees"),
    ]);
    deptsData = depts;
    deptManagers = emps;
    populateDeptManagers();
    renderDepartments();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function populateDeptManagers() {
  document.getElementById("dept-manager").innerHTML =
    `<option value="">${t("common.select")}</option>` +
    deptManagers.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
}

function renderDepartments() {
  const tbody = document.getElementById("depts-table");
  document.getElementById("depts-count").textContent = `(${deptsData.length})`;
  document.getElementById("depts-empty").style.display = deptsData.length ? "none" : "";
  tbody.innerHTML = deptsData.map((d) => `
    <tr>
      <td><b>${escapeHtml(d.name)}</b></td>
      <td>${escapeHtml(d.code || "—")}</td>
      <td>${escapeHtml(d.manager_name || "—")}</td>
      <td>${d.employees_count || 0}</td>
      <td>${hrActiveBadge(d.is_active)}</td>
      <td>${hrActionButtons("Dept", d, "openDeptModal", "deleteDept")}</td>
    </tr>`).join("");
}

function openDeptModal(dept) {
  document.getElementById("dept-modal-title").textContent = dept ? t("hr.editDepartment") : t("hr.addDepartment");
  document.getElementById("dept-id").value = dept ? dept.id : "";
  document.getElementById("dept-name").value = dept ? dept.name : "";
  document.getElementById("dept-code").value = dept ? (dept.code || "") : "";
  document.getElementById("dept-manager").value = dept ? (dept.manager_id || "") : "";
  document.getElementById("dept-description").value = dept ? (dept.description || "") : "";
  document.getElementById("dept-active").checked = dept ? dept.is_active : true;
  document.getElementById("dept-modal").classList.add("active");
}

function closeDeptModal() {
  document.getElementById("dept-modal").classList.remove("active");
}

async function saveDept() {
  const id = document.getElementById("dept-id").value;
  const body = {
    name: document.getElementById("dept-name").value.trim(),
    code: document.getElementById("dept-code").value.trim(),
    manager_id: document.getElementById("dept-manager").value || null,
    description: document.getElementById("dept-description").value.trim(),
    is_active: document.getElementById("dept-active").checked,
  };
  if (!body.name) { showToast(t("hr.deptNameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/departments/${id}`, body);
    else await api.post("/api/hr/departments", body);
    showToast(t("hr.saved"));
    closeDeptModal();
    loadDepartments();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteDept(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/departments/${id}`);
    showToast(t("hr.deleted"));
    loadDepartments();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openDeptModal = openDeptModal;
window.closeDeptModal = closeDeptModal;
window.saveDept = saveDept;
window.deleteDept = deleteDept;

loadDepartments();

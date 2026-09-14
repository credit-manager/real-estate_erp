/* HR Employees */
let employeesData = [];
let hrDepartments = [];
let hrPositions = [];
let hrUsers = [];

function populateFilters() {
  const deptFilter = document.getElementById("filter-dept");
  const deptSelect = document.getElementById("employee-department");
  const posSelect = document.getElementById("employee-position");
  const manSelect = document.getElementById("employee-manager");
  const opt = (arr, val, label) => arr.map((x) =>
    `<option value="${x.id}" ${x.id === val ? "selected" : ""}>${escapeHtml(x.name || x.full_name)}</option>`
  ).join("");

  deptFilter.innerHTML = `<option value="">${t("hr.allDepartments")}</option>` + opt(hrDepartments);
  deptSelect.innerHTML = `<option value="">${t("common.select")}</option>` + opt(hrDepartments);
  posSelect.innerHTML = `<option value="">${t("common.select")}</option>` + opt(hrPositions);
  manSelect.innerHTML = `<option value="">${t("common.select")}</option>` + opt(employeesData);
}

function populateUserSelect(selectedId) {
  const userSelect = document.getElementById("employee-user");
  const linked = employeesData.map((e) => e.user_id).filter(Boolean);
  const opts = hrUsers
    .filter((u) => u.is_active || u.id === selectedId)
    .map((u) =>
      `<option value="${u.id}" ${u.id === selectedId ? "selected" : ""}>${escapeHtml(u.full_name || u.username)} (${escapeHtml(u.username)})</option>`
    ).join("");
  userSelect.innerHTML = `<option value="">${t("hr.noAccount")}</option>` + opts;
}

async function loadEmployees() {
  try {
    const [emps, depts, poss, users] = await Promise.all([
      api.get("/api/hr/employees"),
      api.get("/api/hr/departments"),
      api.get("/api/hr/positions"),
      api.get("/api/hr/users"),
    ]);
    employeesData = emps;
    hrDepartments = depts;
    hrPositions = poss;
    hrUsers = users;
    populateFilters();
    populateUserSelect();
    renderEmployees();
    renderSummary();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderEmployees() {
  const dept = document.getElementById("filter-dept").value;
  const status = document.getElementById("filter-status").value;
  const search = document.getElementById("filter-search").value.trim();
  const filtered = employeesData.filter((e) => {
    const dOk = !dept || e.department_id === dept || (e.department_id && String(e.department_id) === dept);
    const sOk = !status || e.status === status;
    const sText = `${e.full_name} ${e.national_id || ""} ${e.position_name || ""}`;
    const qOk = !search || sText.toLowerCase().includes(search.toLowerCase());
    return dOk && sOk && qOk;
  });

  const tbody = document.getElementById("employees-table");
  document.getElementById("employees-empty").style.display = filtered.length ? "none" : "";
  tbody.innerHTML = filtered.map((e) => `
    <tr>
      <td><b>${escapeHtml(e.full_name)}</b><br><small style="color:var(--muted-foreground);">${escapeHtml(e.email || "")}</small></td>
      <td>${e.department_name ? `<span class="badge badge-neutral">${escapeHtml(e.department_name)}</span>` : "—"}</td>
      <td>${escapeHtml(e.position_name || "") || "—"}</td>
      <td style="direction:ltr;text-align:right;">${escapeHtml(e.national_id || "—")}</td>
      <td style="direction:ltr;text-align:right;">${escapeHtml(e.phone || "—")}</td>
      <td><b>${formatMoney(e.salary)}</b></td>
      <td>${hrStatusBadge(e.status)}</td>
      <td>
        <div class="table-actions">
          ${hrCan("edit") ? `<button class="icon-btn" title="${t("common.edit")}" onclick='editEmployee(${JSON.stringify(e)})'>✏️</button>` : ""}
          ${hrCan("delete") ? `<button class="icon-btn" title="${t("common.delete")}" onclick="deleteEmployee(${e.id})">🗑️</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function renderSummary() {
  animateCount(document.getElementById("emp-total"), employeesData.length, formatNumber);
  animateCount(document.getElementById("emp-active"), employeesData.filter((e) => e.status === "active").length, formatNumber);
  const totalSalary = employeesData.reduce((acc, e) => acc + (e.salary || 0), 0);
  animateCount(document.getElementById("emp-salary"), totalSalary, formatMoney);
  animateCount(document.getElementById("emp-depts"), hrDepartments.length, formatNumber);
}

function exportEmployeesToCSV() {
  const headers = [
    t("hr.fullName"), t("hr.nationalId"), t("hr.department"), t("hr.position"),
    t("hr.phone"), t("hr.email"), t("hr.salary"), t("common.status"),
  ];
  const rows = employeesData.map((e) => [
    e.full_name, e.national_id || "", e.department_name || "", e.position_name || "",
    e.phone || "", e.email || "", e.salary || 0, STATUS_LABELS[e.status] || e.status,
  ]);
  exportCSV("employees.csv", headers, rows);
}

function openEmployeeModal(emp) {
  const id = emp ? emp.id : "";
  document.getElementById("employee-modal-title").textContent = emp ? t("hr.editEmployee") : t("hr.newEmployee");
  document.getElementById("employee-id").value = id;
  document.getElementById("employee-full-name").value = emp ? emp.full_name : "";
  document.getElementById("employee-national-id").value = emp ? (emp.national_id || "") : "";
  document.getElementById("employee-phone").value = emp ? (emp.phone || "") : "";
  document.getElementById("employee-email").value = emp ? (emp.email || "") : "";
  document.getElementById("employee-department").value = emp ? (emp.department_id || "") : "";
  document.getElementById("employee-position").value = emp ? (emp.position_id || "") : "";
  document.getElementById("employee-manager").value = emp ? (emp.manager_id || "") : "";
  document.getElementById("employee-employment-type").value = emp ? (emp.employment_type || "full_time") : "full_time";
  document.getElementById("employee-gender").value = emp ? (emp.gender || "") : "";
  document.getElementById("employee-birth-date").value = emp ? (emp.birth_date || "") : "";
  document.getElementById("employee-hire-date").value = emp ? (emp.hire_date || "") : "";
  document.getElementById("employee-salary").value = emp ? (emp.salary || "") : "";
  document.getElementById("employee-status").value = emp ? (emp.status || "active") : "active";
  document.getElementById("employee-address").value = emp ? (emp.address || "") : "";
  populateUserSelect(emp ? emp.user_id : null);
  document.getElementById("employee-modal").classList.add("active");
}

function closeEmployeeModal() {
  document.getElementById("employee-modal").classList.remove("active");
}

async function saveEmployee() {
  const id = document.getElementById("employee-id").value;
  const body = {
    full_name: document.getElementById("employee-full-name").value.trim(),
    national_id: document.getElementById("employee-national-id").value.trim(),
    phone: document.getElementById("employee-phone").value.trim(),
    email: document.getElementById("employee-email").value.trim(),
    department_id: document.getElementById("employee-department").value || null,
    position_id: document.getElementById("employee-position").value || null,
    manager_id: document.getElementById("employee-manager").value || null,
    user_id: document.getElementById("employee-user").value || null,
    employment_type: document.getElementById("employee-employment-type").value,
    gender: document.getElementById("employee-gender").value || null,
    birth_date: document.getElementById("employee-birth-date").value || null,
    hire_date: document.getElementById("employee-hire-date").value || null,
    salary: parseFloat(document.getElementById("employee-salary").value) || 0,
    status: document.getElementById("employee-status").value,
    address: document.getElementById("employee-address").value.trim(),
  };
  if (!body.full_name) { showToast(t("hr.nameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/employees/${id}`, body);
    else await api.post("/api/hr/employees", body);
    showToast(t("hr.saved"));
    closeEmployeeModal();
    loadEmployees();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteEmployee(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/employees/${id}`);
    showToast(t("hr.deleted"));
    loadEmployees();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openEmployeeModal = openEmployeeModal;
window.closeEmployeeModal = closeEmployeeModal;
window.editEmployee = openEmployeeModal;
window.deleteEmployee = deleteEmployee;
window.saveEmployee = saveEmployee;
window.renderEmployees = renderEmployees;
window.exportEmployeesToCSV = exportEmployeesToCSV;

loadEmployees();

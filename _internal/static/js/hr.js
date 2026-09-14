/* ============================================================
   HR Module JavaScript
   ============================================================ */

let allEmployees = [];

document.addEventListener("DOMContentLoaded", async () => {
  try {
    allEmployees = await api.get("/api/employees");
    renderEmployees();
    renderSummary();

    document.getElementById("filter-dept").addEventListener("change", renderEmployees);
    document.getElementById("filter-search").addEventListener("input", renderEmployees);
  } catch (err) {
    console.error(err);
  }
});

function renderEmployees() {
  const dept = document.getElementById("filter-dept").value;
  const search = document.getElementById("filter-search").value.trim();

  const filtered = allEmployees.filter((e) => {
    const dOk = !dept || e.department === dept;
    const sOk = !search || (e.full_name || "").includes(search) || (e.position || "").includes(search);
    return dOk && sOk;
  });

  const tbody = document.getElementById("employees-table");
  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">👥</div>${t("hr.noEmployees")}</div></td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((e) => `
    <tr>
      <td><strong>${e.full_name}</strong><br><small style="color:var(--muted-foreground);">${e.email || ""}</small></td>
      <td><span class="badge badge-neutral">${tv(e.department)}</span></td>
      <td style="color:var(--muted-foreground);">${e.position || "—"}</td>
      <td style="direction:ltr;text-align:right;">${e.phone || "—"}</td>
      <td><strong>${formatMoney(e.salary)}</strong></td>
      <td>${statusBadge(e.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("hr", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editEmployee(${JSON.stringify(e)})'>${t("common.edit")}</button>` : ""}
          ${canAction("hr", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteEmployee(${e.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function renderSummary() {
  animateCount(document.getElementById("emp-total"), allEmployees.length, formatNumber);
  animateCount(document.getElementById("emp-active"), allEmployees.filter((e) => e.status === "active").length, formatNumber);
  const totalSalary = allEmployees.reduce((acc, e) => acc + (e.salary || 0), 0);
  animateCount(document.getElementById("emp-salary"), totalSalary, formatMoney);
}

function exportEmployees() {
  const headers = [
    t("common.fullName"), t("common.department"), t("common.position"),
    t("common.phone"), t("common.email"), t("common.salary"), t("common.status"),
  ];
  const rows = allEmployees.map((e) => [
    e.full_name, tv(e.department), e.position || "",
    e.phone || "", e.email || "", e.salary || 0,
    STATUS_LABELS[e.status] || e.status,
  ]);
  exportCSV("employees.csv", headers, rows);
}

// ===== Modal =====
function openEmployeeModal() {
  document.getElementById("employee-modal-title").textContent = t("hr.newEmployee");
  document.getElementById("employee-id").value = "";
  ["employee-name", "employee-position", "employee-phone", "employee-email", "employee-salary"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("employee-dept").value = "الهندسة";
  document.getElementById("employee-status").value = "active";
  document.getElementById("employee-modal").classList.add("active");
}

function editEmployee(e) {
  document.getElementById("employee-modal-title").textContent = t("hr.editEmployee");
  document.getElementById("employee-id").value = e.id;
  document.getElementById("employee-name").value = e.full_name || "";
  document.getElementById("employee-dept").value = e.department || "الهندسة";
  document.getElementById("employee-position").value = e.position || "";
  document.getElementById("employee-phone").value = e.phone || "";
  document.getElementById("employee-email").value = e.email || "";
  document.getElementById("employee-salary").value = e.salary || "";
  document.getElementById("employee-status").value = e.status || "active";
  document.getElementById("employee-modal").classList.add("active");
}

function closeEmployeeModal() {
  document.getElementById("employee-modal").classList.remove("active");
}

async function saveEmployee() {
  const id = document.getElementById("employee-id").value;
  const body = {
    full_name: document.getElementById("employee-name").value,
    department: document.getElementById("employee-dept").value,
    position: document.getElementById("employee-position").value,
    phone: document.getElementById("employee-phone").value,
    email: document.getElementById("employee-email").value,
    salary: parseFloat(document.getElementById("employee-salary").value) || 0,
    status: document.getElementById("employee-status").value,
  };
  if (!body.full_name) { showToast(t("hr.nameRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/employees/${id}`, body);
    else await api.post("/api/employees", body);
    showToast(t("common.saved"));
    closeEmployeeModal();
    allEmployees = await api.get("/api/employees");
    renderEmployees();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteEmployee(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/employees/${id}`);
    showToast(t("common.deleted"));
    allEmployees = await api.get("/api/employees");
    renderEmployees();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openEmployeeModal = openEmployeeModal;
window.closeEmployeeModal = closeEmployeeModal;
window.editEmployee = editEmployee;
window.deleteEmployee = deleteEmployee;
window.saveEmployee = saveEmployee;

/* Payroll - Salaries */
let salaryEmployees = [];

async function loadSalaries() {
  try {
    const [salaries, emps] = await Promise.all([
      api.get("/api/payroll/salaries"),
      api.get("/api/hr/employees"),
    ]);
    salaryEmployees = emps;
    document.getElementById("salary-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` + prEmployeesOptions(emps);
    renderSalaries(salaries);
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderSalaries(salaries) {
  document.getElementById("salaries-count").textContent = `(${salaries.length})`;
  document.getElementById("salaries-empty").style.display = salaries.length ? "none" : "";
  document.getElementById("salaries-table").innerHTML = salaries.map((s) => `
    <tr>
      <td><b>${escapeHtml(s.employee_name || "—")}</b></td>
      <td>${prAmountCell(s.base_salary)}</td>
      <td>${formatDate(s.effective_date)}</td>
      <td>${escapeHtml(s.notes || "—")}</td>
      <td>${prActionButtons("Salary", s, "openSalaryModal", "deleteSalary")}</td>
    </tr>`).join("");
}

function openSalaryModal(salary) {
  document.getElementById("salary-modal-title").textContent = salary ? t("payroll.editSalary") : t("payroll.addSalary");
  document.getElementById("salary-id").value = salary ? salary.id : "";
  document.getElementById("salary-employee").value = salary ? (salary.employee_id || "") : "";
  document.getElementById("salary-base").value = salary ? (salary.base_salary || "") : "";
  document.getElementById("salary-effective").value = salary ? (salary.effective_date || "") : "";
  document.getElementById("salary-notes").value = salary ? (salary.notes || "") : "";
  document.getElementById("salary-modal").classList.add("active");
}

function closeSalaryModal() {
  document.getElementById("salary-modal").classList.remove("active");
}

async function saveSalary() {
  const id = document.getElementById("salary-id").value;
  const body = {
    employee_id: document.getElementById("salary-employee").value || null,
    base_salary: parseFloat(document.getElementById("salary-base").value) || 0,
    effective_date: document.getElementById("salary-effective").value || null,
    notes: document.getElementById("salary-notes").value.trim(),
  };
  if (!body.employee_id) { showToast(t("payroll.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/payroll/salaries/${id}`, body);
    else await api.post("/api/payroll/salaries", body);
    showToast(t("payroll.saved"));
    closeSalaryModal();
    loadSalaries();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteSalary(id) {
  if (!confirm(t("payroll.confirmDelete"))) return;
  try {
    await api.delete(`/api/payroll/salaries/${id}`);
    showToast(t("payroll.deleted"));
    loadSalaries();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openSalaryModal = openSalaryModal;
window.closeSalaryModal = closeSalaryModal;
window.saveSalary = saveSalary;
window.deleteSalary = deleteSalary;

loadSalaries();

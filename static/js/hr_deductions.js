/* Payroll - Deductions */
let deductionEmployees = [];

function deductionAmount(d) {
  if (d.is_percentage) return `${d.percentage}%`;
  return prMoney(d.amount);
}

async function loadDeductions() {
  try {
    const [deductions, emps] = await Promise.all([
      api.get("/api/payroll/deductions"),
      api.get("/api/hr/employees"),
    ]);
    deductionEmployees = emps;
    document.getElementById("deduction-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` + prEmployeesOptions(emps);
    renderDeductions(deductions);
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderDeductions(deductions) {
  document.getElementById("deductions-count").textContent = `(${deductions.length})`;
  document.getElementById("deductions-empty").style.display = deductions.length ? "none" : "";
  document.getElementById("deductions-table").innerHTML = deductions.map((d) => `
    <tr>
      <td><b>${escapeHtml(d.employee_name || "—")}</b></td>
      <td>${escapeHtml(d.name)}</td>
      <td>${prAmountCell(deductionAmount(d))}</td>
      <td>${d.is_percentage ? t("payroll.percentage") : t("payroll.fixedAmount")}</td>
      <td>${escapeHtml(d.notes || "—")}</td>
      <td>${prActionButtons("Deduction", d, "openDeductionModal", "deleteDeduction")}</td>
    </tr>`).join("");
}

function openDeductionModal(deduction) {
  document.getElementById("deduction-modal-title").textContent = deduction ? t("payroll.editDeduction") : t("payroll.addDeduction");
  document.getElementById("deduction-id").value = deduction ? deduction.id : "";
  document.getElementById("deduction-employee").value = deduction ? (deduction.employee_id || "") : "";
  document.getElementById("deduction-name").value = deduction ? (deduction.name || "") : "";
  document.getElementById("deduction-type").value = deduction && deduction.is_percentage ? "percentage" : "fixed";
  document.getElementById("deduction-amount").value = deduction ? (deduction.amount || "") : "";
  document.getElementById("deduction-percentage").value = deduction ? (deduction.percentage || "") : "";
  document.getElementById("deduction-notes").value = deduction ? (deduction.notes || "") : "";
  document.getElementById("deduction-modal").classList.add("active");
}

function closeDeductionModal() {
  document.getElementById("deduction-modal").classList.remove("active");
}

async function saveDeduction() {
  const id = document.getElementById("deduction-id").value;
  const isPercentage = document.getElementById("deduction-type").value === "percentage";
  const body = {
    employee_id: document.getElementById("deduction-employee").value || null,
    name: document.getElementById("deduction-name").value.trim(),
    amount: parseFloat(document.getElementById("deduction-amount").value) || 0,
    is_percentage: isPercentage,
    percentage: parseFloat(document.getElementById("deduction-percentage").value) || 0,
    notes: document.getElementById("deduction-notes").value.trim(),
  };
  if (!body.employee_id) { showToast(t("payroll.employeeRequired"), "warning"); return; }
  if (!body.name) { showToast(t("payroll.nameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/payroll/deductions/${id}`, body);
    else await api.post("/api/payroll/deductions", body);
    showToast(t("payroll.saved"));
    closeDeductionModal();
    loadDeductions();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteDeduction(id) {
  if (!confirm(t("payroll.confirmDelete"))) return;
  try {
    await api.delete(`/api/payroll/deductions/${id}`);
    showToast(t("payroll.deleted"));
    loadDeductions();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openDeductionModal = openDeductionModal;
window.closeDeductionModal = closeDeductionModal;
window.saveDeduction = saveDeduction;
window.deleteDeduction = deleteDeduction;

loadDeductions();

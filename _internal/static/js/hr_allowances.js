/* Payroll - Allowances */
let allowanceEmployees = [];

function allowanceAmount(a) {
  if (a.is_percentage) return `${a.percentage}%`;
  return prMoney(a.amount);
}

async function loadAllowances() {
  try {
    const [allowances, emps] = await Promise.all([
      api.get("/api/payroll/allowances"),
      api.get("/api/hr/employees"),
    ]);
    allowanceEmployees = emps;
    document.getElementById("allowance-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` + prEmployeesOptions(emps);
    renderAllowances(allowances);
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderAllowances(allowances) {
  document.getElementById("allowances-count").textContent = `(${allowances.length})`;
  document.getElementById("allowances-empty").style.display = allowances.length ? "none" : "";
  document.getElementById("allowances-table").innerHTML = allowances.map((a) => `
    <tr>
      <td><b>${escapeHtml(a.employee_name || "—")}</b></td>
      <td>${escapeHtml(a.name)}</td>
      <td>${prAmountCell(allowanceAmount(a))}</td>
      <td>${a.is_percentage ? t("payroll.percentage") : t("payroll.fixedAmount")}</td>
      <td>${escapeHtml(a.notes || "—")}</td>
      <td>${prActionButtons("Allowance", a, "openAllowanceModal", "deleteAllowance")}</td>
    </tr>`).join("");
}

function openAllowanceModal(allowance) {
  document.getElementById("allowance-modal-title").textContent = allowance ? t("payroll.editAllowance") : t("payroll.addAllowance");
  document.getElementById("allowance-id").value = allowance ? allowance.id : "";
  document.getElementById("allowance-employee").value = allowance ? (allowance.employee_id || "") : "";
  document.getElementById("allowance-name").value = allowance ? (allowance.name || "") : "";
  document.getElementById("allowance-type").value = allowance && allowance.is_percentage ? "percentage" : "fixed";
  document.getElementById("allowance-amount").value = allowance ? (allowance.amount || "") : "";
  document.getElementById("allowance-percentage").value = allowance ? (allowance.percentage || "") : "";
  document.getElementById("allowance-notes").value = allowance ? (allowance.notes || "") : "";
  document.getElementById("allowance-modal").classList.add("active");
}

function closeAllowanceModal() {
  document.getElementById("allowance-modal").classList.remove("active");
}

async function saveAllowance() {
  const id = document.getElementById("allowance-id").value;
  const isPercentage = document.getElementById("allowance-type").value === "percentage";
  const body = {
    employee_id: document.getElementById("allowance-employee").value || null,
    name: document.getElementById("allowance-name").value.trim(),
    amount: parseFloat(document.getElementById("allowance-amount").value) || 0,
    is_percentage: isPercentage,
    percentage: parseFloat(document.getElementById("allowance-percentage").value) || 0,
    notes: document.getElementById("allowance-notes").value.trim(),
  };
  if (!body.employee_id) { showToast(t("payroll.employeeRequired"), "warning"); return; }
  if (!body.name) { showToast(t("payroll.nameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/payroll/allowances/${id}`, body);
    else await api.post("/api/payroll/allowances", body);
    showToast(t("payroll.saved"));
    closeAllowanceModal();
    loadAllowances();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteAllowance(id) {
  if (!confirm(t("payroll.confirmDelete"))) return;
  try {
    await api.delete(`/api/payroll/allowances/${id}`);
    showToast(t("payroll.deleted"));
    loadAllowances();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openAllowanceModal = openAllowanceModal;
window.closeAllowanceModal = closeAllowanceModal;
window.saveAllowance = saveAllowance;
window.deleteAllowance = deleteAllowance;

loadAllowances();

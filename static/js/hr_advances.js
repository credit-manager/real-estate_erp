/* HR Advances */
let advancesData = [];
let advanceEmployees = [];

async function loadAdvances() {
  try {
    const [advances, emps] = await Promise.all([
      api.get("/api/hr/advances"),
      api.get("/api/hr/employees"),
    ]);
    advancesData = advances;
    advanceEmployees = emps;
    document.getElementById("advance-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` +
      emps.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
    renderAdvances();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderAdvances() {
  const tbody = document.getElementById("advances-table");
  document.getElementById("advances-count").textContent = `(${advancesData.length})`;
  document.getElementById("advances-empty").style.display = advancesData.length ? "none" : "";
  tbody.innerHTML = advancesData.map((a) => `
    <tr>
      <td><b>${escapeHtml(a.employee_name || "—")}</b></td>
      <td>${formatDate(a.advance_date)}</td>
      <td><b>${formatMoney(a.amount)}</b></td>
      <td>${a.installments || 1}</td>
      <td>${formatMoney(a.paid_amount)}</td>
      <td style="color:var(--amber);">${formatMoney(a.remaining)}</td>
      <td>${hrStatusBadge(a.status)}</td>
      <td>${hrActionButtons("Advance", a, "openAdvanceModal", "deleteAdvance")}</td>
    </tr>`).join("");
}

function openAdvanceModal(advance) {
  document.getElementById("advance-modal-title").textContent = advance ? t("hr.editAdvance") : t("hr.addAdvance");
  document.getElementById("advance-id").value = advance ? advance.id : "";
  document.getElementById("advance-employee").value = advance ? (advance.employee_id || "") : "";
  document.getElementById("advance-amount").value = advance ? (advance.amount || "") : "";
  document.getElementById("advance-date").value = advance ? (advance.advance_date || "") : "";
  document.getElementById("advance-installments").value = advance ? (advance.installments || 1) : 1;
  document.getElementById("advance-paid").value = advance ? (advance.paid_amount || 0) : 0;
  document.getElementById("advance-status").value = advance ? (advance.status || "open") : "open";
  document.getElementById("advance-reason").value = advance ? (advance.reason || "") : "";
  document.getElementById("advance-modal").classList.add("active");
}

function closeAdvanceModal() {
  document.getElementById("advance-modal").classList.remove("active");
}

async function saveAdvance() {
  const id = document.getElementById("advance-id").value;
  const body = {
    employee_id: document.getElementById("advance-employee").value || null,
    amount: parseFloat(document.getElementById("advance-amount").value) || 0,
    advance_date: document.getElementById("advance-date").value || null,
    installments: parseInt(document.getElementById("advance-installments").value) || 1,
    paid_amount: parseFloat(document.getElementById("advance-paid").value) || 0,
    status: document.getElementById("advance-status").value,
    reason: document.getElementById("advance-reason").value.trim(),
  };
  if (!body.employee_id) { showToast(t("hr.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/advances/${id}`, body);
    else await api.post("/api/hr/advances", body);
    showToast(t("hr.saved"));
    closeAdvanceModal();
    loadAdvances();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteAdvance(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/advances/${id}`);
    showToast(t("hr.deleted"));
    loadAdvances();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openAdvanceModal = openAdvanceModal;
window.closeAdvanceModal = closeAdvanceModal;
window.saveAdvance = saveAdvance;
window.deleteAdvance = deleteAdvance;

loadAdvances();

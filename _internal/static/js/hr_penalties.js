/* HR Penalties */
let penaltiesData = [];
let penaltyEmployees = [];

async function loadPenalties() {
  try {
    const [penalties, emps] = await Promise.all([
      api.get("/api/hr/penalties"),
      api.get("/api/hr/employees"),
    ]);
    penaltiesData = penalties;
    penaltyEmployees = emps;
    document.getElementById("penalty-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` +
      emps.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
    renderPenalties();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderPenalties() {
  const tbody = document.getElementById("penalties-table");
  document.getElementById("penalties-count").textContent = `(${penaltiesData.length})`;
  document.getElementById("penalties-empty").style.display = penaltiesData.length ? "none" : "";
  tbody.innerHTML = penaltiesData.map((p) => `
    <tr>
      <td><b>${escapeHtml(p.employee_name || "—")}</b></td>
      <td>${escapeHtml(p.penalty_type || "—")}</td>
      <td><b style="color:var(--red);">${formatMoney(p.amount)}</b></td>
      <td>${formatDate(p.penalty_date)}</td>
      <td>${escapeHtml(p.reason || "—")}</td>
      <td>${hrActionButtons("Penalty", p, "openPenaltyModal", "deletePenalty")}</td>
    </tr>`).join("");
}

function openPenaltyModal(penalty) {
  document.getElementById("penalty-modal-title").textContent = penalty ? t("hr.editPenalty") : t("hr.addPenalty");
  document.getElementById("penalty-id").value = penalty ? penalty.id : "";
  document.getElementById("penalty-employee").value = penalty ? (penalty.employee_id || "") : "";
  document.getElementById("penalty-type").value = penalty ? (penalty.penalty_type || "") : "";
  document.getElementById("penalty-date").value = penalty ? (penalty.penalty_date || "") : "";
  document.getElementById("penalty-amount").value = penalty ? (penalty.amount || "") : "";
  document.getElementById("penalty-reason").value = penalty ? (penalty.reason || "") : "";
  document.getElementById("penalty-modal").classList.add("active");
}

function closePenaltyModal() {
  document.getElementById("penalty-modal").classList.remove("active");
}

async function savePenalty() {
  const id = document.getElementById("penalty-id").value;
  const body = {
    employee_id: document.getElementById("penalty-employee").value || null,
    penalty_type: document.getElementById("penalty-type").value.trim(),
    penalty_date: document.getElementById("penalty-date").value || null,
    amount: parseFloat(document.getElementById("penalty-amount").value) || 0,
    reason: document.getElementById("penalty-reason").value.trim(),
  };
  if (!body.employee_id) { showToast(t("hr.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/penalties/${id}`, body);
    else await api.post("/api/hr/penalties", body);
    showToast(t("hr.saved"));
    closePenaltyModal();
    loadPenalties();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deletePenalty(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/penalties/${id}`);
    showToast(t("hr.deleted"));
    loadPenalties();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openPenaltyModal = openPenaltyModal;
window.closePenaltyModal = closePenaltyModal;
window.savePenalty = savePenalty;
window.deletePenalty = deletePenalty;

loadPenalties();

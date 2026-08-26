/* Payroll - Bonuses */
let bonusEmployees = [];

async function loadBonuses() {
  try {
    const [bonuses, emps] = await Promise.all([
      api.get("/api/payroll/bonuses"),
      api.get("/api/hr/employees"),
    ]);
    bonusEmployees = emps;
    document.getElementById("bonus-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` + prEmployeesOptions(emps);
    renderBonuses(bonuses);
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderBonuses(bonuses) {
  document.getElementById("bonuses-count").textContent = `(${bonuses.length})`;
  document.getElementById("bonuses-empty").style.display = bonuses.length ? "none" : "";
  document.getElementById("bonuses-table").innerHTML = bonuses.map((b) => `
    <tr>
      <td><b>${escapeHtml(b.employee_name || "—")}</b></td>
      <td>${escapeHtml(b.name)}</td>
      <td>${prAmountCell(b.amount)}</td>
      <td>${formatDate(b.bonus_date)}</td>
      <td>${escapeHtml(b.notes || "—")}</td>
      <td>${prActionButtons("Bonus", b, "openBonusModal", "deleteBonus")}</td>
    </tr>`).join("");
}

function openBonusModal(bonus) {
  document.getElementById("bonus-modal-title").textContent = bonus ? t("payroll.editBonus") : t("payroll.addBonus");
  document.getElementById("bonus-id").value = bonus ? bonus.id : "";
  document.getElementById("bonus-employee").value = bonus ? (bonus.employee_id || "") : "";
  document.getElementById("bonus-name").value = bonus ? (bonus.name || "") : "";
  document.getElementById("bonus-amount").value = bonus ? (bonus.amount || "") : "";
  document.getElementById("bonus-date").value = bonus ? (bonus.bonus_date || "") : "";
  document.getElementById("bonus-notes").value = bonus ? (bonus.notes || "") : "";
  document.getElementById("bonus-modal").classList.add("active");
}

function closeBonusModal() {
  document.getElementById("bonus-modal").classList.remove("active");
}

async function saveBonus() {
  const id = document.getElementById("bonus-id").value;
  const body = {
    employee_id: document.getElementById("bonus-employee").value || null,
    name: document.getElementById("bonus-name").value.trim(),
    amount: parseFloat(document.getElementById("bonus-amount").value) || 0,
    bonus_date: document.getElementById("bonus-date").value || null,
    notes: document.getElementById("bonus-notes").value.trim(),
  };
  if (!body.employee_id) { showToast(t("payroll.employeeRequired"), "warning"); return; }
  if (!body.name) { showToast(t("payroll.nameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/payroll/bonuses/${id}`, body);
    else await api.post("/api/payroll/bonuses", body);
    showToast(t("payroll.saved"));
    closeBonusModal();
    loadBonuses();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteBonus(id) {
  if (!confirm(t("payroll.confirmDelete"))) return;
  try {
    await api.delete(`/api/payroll/bonuses/${id}`);
    showToast(t("payroll.deleted"));
    loadBonuses();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openBonusModal = openBonusModal;
window.closeBonusModal = closeBonusModal;
window.saveBonus = saveBonus;
window.deleteBonus = deleteBonus;

loadBonuses();

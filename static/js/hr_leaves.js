/* HR Leaves */
let leavesData = [];
let leaveEmployees = [];

const LEAVE_TYPES = {
  annual: "hr.leaveAnnual", sick: "hr.leaveSick", unpaid: "hr.leaveUnpaid",
  emergency: "hr.leaveEmergency", maternity: "hr.leaveMaternity",
};

async function loadLeaves() {
  try {
    const [leaves, emps] = await Promise.all([
      api.get("/api/hr/leaves"),
      api.get("/api/hr/employees"),
    ]);
    leavesData = leaves;
    leaveEmployees = emps;
    document.getElementById("leave-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` +
      emps.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
    renderLeaves();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function calcLeaveDays() {
  const s = document.getElementById("leave-start").value;
  const e = document.getElementById("leave-end").value;
  if (!s || !e) return;
  const days = Math.floor((new Date(e) - new Date(s)) / 86400000) + 1;
  if (days > 0) document.getElementById("leave-days").value = days;
}
window.calcLeaveDays = calcLeaveDays;

function renderLeaves() {
  const tbody = document.getElementById("leaves-table");
  document.getElementById("leaves-count").textContent = `(${leavesData.length})`;
  document.getElementById("leaves-empty").style.display = leavesData.length ? "none" : "";
  tbody.innerHTML = leavesData.map((l) => `
    <tr>
      <td><b>${escapeHtml(l.employee_name || "—")}</b></td>
      <td>${LEAVE_TYPES[l.leave_type] ? t(LEAVE_TYPES[l.leave_type]) : escapeHtml(l.leave_type)}</td>
      <td>${formatDate(l.start_date)}</td>
      <td>${formatDate(l.end_date)}</td>
      <td>${l.days || 0}</td>
      <td>${hrStatusBadge(l.status)}</td>
      <td>${hrActionButtons("Leave", l, "openLeaveModal", "deleteLeave")}</td>
    </tr>`).join("");
}

function openLeaveModal(leave) {
  document.getElementById("leave-modal-title").textContent = leave ? t("hr.editLeave") : t("hr.addLeave");
  document.getElementById("leave-id").value = leave ? leave.id : "";
  document.getElementById("leave-employee").value = leave ? (leave.employee_id || "") : "";
  document.getElementById("leave-type").value = leave ? (leave.leave_type || "annual") : "annual";
  document.getElementById("leave-status").value = leave ? (leave.status || "pending") : "pending";
  document.getElementById("leave-start").value = leave ? (leave.start_date || "") : "";
  document.getElementById("leave-end").value = leave ? (leave.end_date || "") : "";
  document.getElementById("leave-days").value = leave ? (leave.days || "") : "";
  document.getElementById("leave-reason").value = leave ? (leave.reason || "") : "";
  document.getElementById("leave-modal").classList.add("active");
}

function closeLeaveModal() {
  document.getElementById("leave-modal").classList.remove("active");
}

async function saveLeave() {
  const id = document.getElementById("leave-id").value;
  const body = {
    employee_id: document.getElementById("leave-employee").value || null,
    leave_type: document.getElementById("leave-type").value,
    status: document.getElementById("leave-status").value,
    start_date: document.getElementById("leave-start").value || null,
    end_date: document.getElementById("leave-end").value || null,
    days: parseFloat(document.getElementById("leave-days").value) || 0,
    reason: document.getElementById("leave-reason").value.trim(),
  };
  if (!body.employee_id) { showToast(t("hr.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/leaves/${id}`, body);
    else await api.post("/api/hr/leaves", body);
    showToast(t("hr.saved"));
    closeLeaveModal();
    loadLeaves();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteLeave(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/leaves/${id}`);
    showToast(t("hr.deleted"));
    loadLeaves();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openLeaveModal = openLeaveModal;
window.closeLeaveModal = closeLeaveModal;
window.saveLeave = saveLeave;
window.deleteLeave = deleteLeave;

loadLeaves();

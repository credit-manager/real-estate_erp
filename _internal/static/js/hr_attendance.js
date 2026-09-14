/* HR Attendance */
let attendanceData = [];
let attendanceEmployees = [];

function attQuery() {
  const d = document.getElementById("filter-att-date").value;
  return d ? `?date=${encodeURIComponent(d)}` : "";
}

async function loadAttendance() {
  try {
    const [records, emps] = await Promise.all([
      api.get("/api/hr/attendance" + attQuery()),
      api.get("/api/hr/employees"),
    ]);
    attendanceData = records;
    attendanceEmployees = emps;
    document.getElementById("att-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` +
      emps.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
    renderAttendance();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderAttendance() {
  const tbody = document.getElementById("att-table");
  document.getElementById("att-count").textContent = `(${attendanceData.length})`;
  document.getElementById("att-empty").style.display = attendanceData.length ? "none" : "";
  tbody.innerHTML = attendanceData.map((a) => `
    <tr>
      <td><b>${escapeHtml(a.employee_name || "—")}</b></td>
      <td>${formatDate(a.date)}</td>
      <td>${escapeHtml(a.check_in || "—")}</td>
      <td>${escapeHtml(a.check_out || "—")}</td>
      <td>${a.working_hours || 0}</td>
      <td>${hrStatusBadge(a.status)}</td>
      <td>${hrActionButtons("Att", a, "openAttModal", "deleteAttendance")}</td>
    </tr>`).join("");
}

function openAttModal(record) {
  document.getElementById("att-modal-title").textContent = record ? t("hr.editAttendance") : t("hr.addAttendance");
  document.getElementById("att-id").value = record ? record.id : "";
  document.getElementById("att-employee").value = record ? (record.employee_id || "") : "";
  document.getElementById("att-date").value = record ? (record.date || "") : "";
  document.getElementById("att-status").value = record ? (record.status || "present") : "present";
  document.getElementById("att-check-in").value = record ? (record.check_in || "") : "";
  document.getElementById("att-check-out").value = record ? (record.check_out || "") : "";
  document.getElementById("att-hours").value = record ? (record.working_hours || "") : "";
  document.getElementById("att-notes").value = record ? (record.notes || "") : "";
  document.getElementById("att-modal").classList.add("active");
}

function closeAttModal() {
  document.getElementById("att-modal").classList.remove("active");
}

async function saveAttendance() {
  const id = document.getElementById("att-id").value;
  const body = {
    employee_id: document.getElementById("att-employee").value || null,
    date: document.getElementById("att-date").value || null,
    status: document.getElementById("att-status").value,
    check_in: document.getElementById("att-check-in").value,
    check_out: document.getElementById("att-check-out").value,
    working_hours: parseFloat(document.getElementById("att-hours").value) || 0,
    notes: document.getElementById("att-notes").value.trim(),
  };
  if (!body.employee_id) { showToast(t("hr.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/attendance/${id}`, body);
    else await api.post("/api/hr/attendance", body);
    showToast(t("hr.saved"));
    closeAttModal();
    loadAttendance();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteAttendance(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/attendance/${id}`);
    showToast(t("hr.deleted"));
    loadAttendance();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openAttModal = openAttModal;
window.closeAttModal = closeAttModal;
window.saveAttendance = saveAttendance;
window.deleteAttendance = deleteAttendance;
window.loadAttendance = loadAttendance;

loadAttendance();

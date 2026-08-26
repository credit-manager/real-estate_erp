/* HR Training */
let trainingsData = [];
let enrollmentsData = [];
let trainingEmployees = [];
let currentTrainingId = null;

const TRAINING_STATUS = {
  planned: "hr.trainingPlanned", ongoing: "hr.trainingOngoing",
  completed: "hr.trainingCompleted", cancelled: "hr.trainingCancelled",
};
const ENROLL_STATUS = { enrolled: "hr.enrEnrolled", completed: "hr.enrCompleted", dropped: "hr.enrDropped" };

async function loadTrainings() {
  try {
    const [trainings, emps] = await Promise.all([
      api.get("/api/hr/trainings"),
      api.get("/api/hr/employees"),
    ]);
    trainingsData = trainings;
    trainingEmployees = emps;
    renderTrainings();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderTrainings() {
  const tbody = document.getElementById("trainings-table");
  document.getElementById("trainings-count").textContent = `(${trainingsData.length})`;
  document.getElementById("trainings-empty").style.display = trainingsData.length ? "none" : "";
  tbody.innerHTML = trainingsData.map((tr) => `
    <tr>
      <td><b>${escapeHtml(tr.title)}</b></td>
      <td>${escapeHtml(tr.provider || "—")}</td>
      <td>${formatDate(tr.start_date)}</td>
      <td>${formatDate(tr.end_date)}</td>
      <td>${formatMoney(tr.cost)}</td>
      <td>
        ${hrCan("edit") ? `<button class="btn btn-sm btn-outline" onclick="openEnrollModal(${tr.id})">${tr.trainees_count || 0} ${t("hr.traineesCount")}</button>` : (tr.trainees_count || 0)}
      </td>
      <td>${hrStatusBadge(tr.status)}</td>
      <td>${hrActionButtons("Training", tr, "openTrainingModal", "deleteTraining")}</td>
    </tr>`).join("");
}

function openTrainingModal(training) {
  document.getElementById("training-modal-title").textContent = training ? t("hr.editTraining") : t("hr.addTraining");
  document.getElementById("training-id").value = training ? training.id : "";
  document.getElementById("training-title").value = training ? training.title : "";
  document.getElementById("training-provider").value = training ? (training.provider || "") : "";
  document.getElementById("training-cost").value = training ? (training.cost || "") : "";
  document.getElementById("training-start").value = training ? (training.start_date || "") : "";
  document.getElementById("training-end").value = training ? (training.end_date || "") : "";
  document.getElementById("training-status").value = training ? (training.status || "planned") : "planned";
  document.getElementById("training-notes").value = training ? (training.notes || "") : "";
  document.getElementById("training-modal").classList.add("active");
}

function closeTrainingModal() {
  document.getElementById("training-modal").classList.remove("active");
}

async function saveTraining() {
  const id = document.getElementById("training-id").value;
  const body = {
    title: document.getElementById("training-title").value.trim(),
    provider: document.getElementById("training-provider").value.trim(),
    cost: parseFloat(document.getElementById("training-cost").value) || 0,
    start_date: document.getElementById("training-start").value || null,
    end_date: document.getElementById("training-end").value || null,
    status: document.getElementById("training-status").value,
    notes: document.getElementById("training-notes").value.trim(),
  };
  if (!body.title) { showToast(t("hr.trainingTitleRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/trainings/${id}`, body);
    else await api.post("/api/hr/trainings", body);
    showToast(t("hr.saved"));
    closeTrainingModal();
    loadTrainings();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteTraining(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/trainings/${id}`);
    showToast(t("hr.deleted"));
    loadTrainings();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

/* ===== Enrollments ===== */
async function openEnrollModal(trainingId) {
  currentTrainingId = trainingId;
  document.getElementById("enroll-modal-title").textContent = t("hr.enrolledEmployees");
  document.getElementById("enroll-employee").innerHTML =
    `<option value="">${t("common.select")}</option>` +
    trainingEmployees.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
  try {
    enrollmentsData = await api.get(`/api/hr/trainings/${trainingId}/enrollments`);
  } catch (e) {
    enrollmentsData = [];
  }
  renderEnrollments();
  document.getElementById("enroll-modal").classList.add("active");
}

function closeEnrollModal() {
  document.getElementById("enroll-modal").classList.remove("active");
}

function renderEnrollments() {
  const tbody = document.getElementById("enrollments-table");
  document.getElementById("enrollments-empty").style.display = enrollmentsData.length ? "none" : "";
  tbody.innerHTML = enrollmentsData.map((en) => `
    <tr>
      <td><b>${escapeHtml(en.employee_name || "—")}</b></td>
      <td>${en.status}</td>
      <td>${en.score || "—"}</td>
      <td>${formatDate(en.completed_at)}</td>
      <td>
        <div class="table-actions">
          ${hrCan("delete") ? `<button class="icon-btn" title="${t("common.delete")}" onclick="deleteEnrollment(${en.id})">🗑️</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

async function addEnrollment() {
  const employeeId = document.getElementById("enroll-employee").value;
  if (!employeeId) { showToast(t("hr.employeeRequired"), "warning"); return; }
  try {
    await api.post(`/api/hr/trainings/${currentTrainingId}/enrollments`, { employee_id: parseInt(employeeId, 10) });
    showToast(t("hr.saved"));
    enrollmentsData = await api.get(`/api/hr/trainings/${currentTrainingId}/enrollments`);
    renderEnrollments();
    loadTrainings();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteEnrollment(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/enrollments/${id}`);
    showToast(t("hr.deleted"));
    enrollmentsData = await api.get(`/api/hr/trainings/${currentTrainingId}/enrollments`);
    renderEnrollments();
    loadTrainings();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openTrainingModal = openTrainingModal;
window.closeTrainingModal = closeTrainingModal;
window.saveTraining = saveTraining;
window.deleteTraining = deleteTraining;
window.openEnrollModal = openEnrollModal;
window.closeEnrollModal = closeEnrollModal;
window.addEnrollment = addEnrollment;
window.deleteEnrollment = deleteEnrollment;

loadTrainings();

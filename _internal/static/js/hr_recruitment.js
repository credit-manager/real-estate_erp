/* HR Recruitment */
let recsData = [];
let recPositions = [];
let recDepartments = [];

const REC_STATUS = {
  applied: "hr.recApplied", interview: "hr.recInterview", offered: "hr.recOffered",
  hired: "hr.recHired", rejected: "hr.recRejected",
};

async function loadRecruitments() {
  try {
    const [recs, poss, depts] = await Promise.all([
      api.get("/api/hr/recruitments"),
      api.get("/api/hr/positions"),
      api.get("/api/hr/departments"),
    ]);
    recsData = recs;
    recPositions = poss;
    recDepartments = depts;
    document.getElementById("rec-position").innerHTML =
      `<option value="">${t("common.select")}</option>` + poss.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
    document.getElementById("rec-department").innerHTML =
      `<option value="">${t("common.select")}</option>` + depts.map((d) => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join("");
    renderRecruitments();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderRecruitments() {
  const tbody = document.getElementById("recs-table");
  document.getElementById("recs-count").textContent = `(${recsData.length})`;
  document.getElementById("recs-empty").style.display = recsData.length ? "none" : "";
  tbody.innerHTML = recsData.map((r) => `
    <tr>
      <td><b>${escapeHtml(r.candidate_name)}</b></td>
      <td>${escapeHtml(r.position_name || "—")}</td>
      <td>${escapeHtml(r.department_name || "—")}</td>
      <td style="direction:ltr;text-align:right;">${escapeHtml(r.phone || "—")}</td>
      <td>${formatDate(r.application_date)}</td>
      <td>${hrStatusBadge(r.status)}</td>
      <td>${hrActionButtons("Rec", r, "openRecModal", "deleteRec")}</td>
    </tr>`).join("");
}

function openRecModal(rec) {
  document.getElementById("rec-modal-title").textContent = rec ? t("hr.editRecruitment") : t("hr.addRecruitment");
  document.getElementById("rec-id").value = rec ? rec.id : "";
  document.getElementById("rec-name").value = rec ? rec.candidate_name : "";
  document.getElementById("rec-source").value = rec ? (rec.source || "") : "";
  document.getElementById("rec-position").value = rec ? (rec.position_id || "") : "";
  document.getElementById("rec-department").value = rec ? (rec.department_id || "") : "";
  document.getElementById("rec-phone").value = rec ? (rec.phone || "") : "";
  document.getElementById("rec-email").value = rec ? (rec.email || "") : "";
  document.getElementById("rec-app-date").value = rec ? (rec.application_date || "") : "";
  document.getElementById("rec-hire-date").value = rec ? (rec.hire_date || "") : "";
  document.getElementById("rec-salary").value = rec ? (rec.salary || "") : "";
  document.getElementById("rec-status").value = rec ? (rec.status || "applied") : "applied";
  document.getElementById("rec-notes").value = rec ? (rec.notes || "") : "";
  document.getElementById("rec-modal").classList.add("active");
}

function closeRecModal() {
  document.getElementById("rec-modal").classList.remove("active");
}

async function saveRec() {
  const id = document.getElementById("rec-id").value;
  const body = {
    candidate_name: document.getElementById("rec-name").value.trim(),
    source: document.getElementById("rec-source").value.trim(),
    position_id: document.getElementById("rec-position").value || null,
    department_id: document.getElementById("rec-department").value || null,
    phone: document.getElementById("rec-phone").value.trim(),
    email: document.getElementById("rec-email").value.trim(),
    application_date: document.getElementById("rec-app-date").value || null,
    hire_date: document.getElementById("rec-hire-date").value || null,
    salary: parseFloat(document.getElementById("rec-salary").value) || 0,
    status: document.getElementById("rec-status").value,
    notes: document.getElementById("rec-notes").value.trim(),
  };
  if (!body.candidate_name) { showToast(t("hr.candidateRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/recruitments/${id}`, body);
    else await api.post("/api/hr/recruitments", body);
    showToast(t("hr.saved"));
    closeRecModal();
    loadRecruitments();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteRec(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/recruitments/${id}`);
    showToast(t("hr.deleted"));
    loadRecruitments();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openRecModal = openRecModal;
window.closeRecModal = closeRecModal;
window.saveRec = saveRec;
window.deleteRec = deleteRec;

loadRecruitments();

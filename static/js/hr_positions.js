/* HR Positions */
let positionsData = [];

async function loadPositions() {
  try {
    positionsData = await api.get("/api/hr/positions");
    renderPositions();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderPositions() {
  const tbody = document.getElementById("positions-table");
  document.getElementById("positions-count").textContent = `(${positionsData.length})`;
  document.getElementById("positions-empty").style.display = positionsData.length ? "none" : "";
  tbody.innerHTML = positionsData.map((p) => `
    <tr>
      <td><b>${escapeHtml(p.name)}</b></td>
      <td>${escapeHtml(p.code || "—")}</td>
      <td>${p.employees_count || 0}</td>
      <td>${hrActiveBadge(p.is_active)}</td>
      <td>${hrActionButtons("Pos", p, "openPosModal", "deletePosition")}</td>
    </tr>`).join("");
}

function openPosModal(pos) {
  document.getElementById("pos-modal-title").textContent = pos ? t("hr.editPosition") : t("hr.addPosition");
  document.getElementById("pos-id").value = pos ? pos.id : "";
  document.getElementById("pos-name").value = pos ? pos.name : "";
  document.getElementById("pos-code").value = pos ? (pos.code || "") : "";
  document.getElementById("pos-description").value = pos ? (pos.description || "") : "";
  document.getElementById("pos-active").checked = pos ? pos.is_active : true;
  document.getElementById("pos-modal").classList.add("active");
}

function closePosModal() {
  document.getElementById("pos-modal").classList.remove("active");
}

async function savePosition() {
  const id = document.getElementById("pos-id").value;
  const body = {
    name: document.getElementById("pos-name").value.trim(),
    code: document.getElementById("pos-code").value.trim(),
    description: document.getElementById("pos-description").value.trim(),
    is_active: document.getElementById("pos-active").checked,
  };
  if (!body.name) { showToast(t("hr.posNameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/positions/${id}`, body);
    else await api.post("/api/hr/positions", body);
    showToast(t("hr.saved"));
    closePosModal();
    loadPositions();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deletePosition(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/positions/${id}`);
    showToast(t("hr.deleted"));
    loadPositions();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openPosModal = openPosModal;
window.closePosModal = closePosModal;
window.savePosition = savePosition;
window.deletePosition = deletePosition;

loadPositions();

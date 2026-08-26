/* ============================================================
   Manufacturing - Work Centers
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

let workCenters = [];

async function loadData() {
  try {
    workCenters = (await api.get("/api/mf/work-centers")) || [];
    renderWorkCenters();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function typeLabel(t) {
  return cct("mf.type." + (t || "machine"));
}

function renderWorkCenters() {
  document.getElementById("work-centers-empty").style.display = workCenters.length ? "none" : "block";
  const canEdit = canAction("manufacturing", "edit");
  const canDelete = canAction("manufacturing", "delete");
  document.getElementById("work-centers-table").innerHTML = workCenters.map((wc) => {
    const status = wc.is_active
      ? `<span class="badge badge-success">${cct("mf.active")}</span>`
      : `<span class="badge badge-neutral">${cct("mf.inactive")}</span>`;
    return `<tr>
      <td><div class="cell-main">${escapeHtml(wc.code)}</div></td>
      <td><div class="cell-main">${escapeHtml(wc.name)}</div>${wc.notes ? `<div class="table-sub">${escapeHtml(wc.notes)}</div>` : ""}</td>
      <td><span class="badge badge-primary">${escapeHtml(typeLabel(wc.wc_type))}</span></td>
      <td><strong>${formatNumber(wc.hourly_cost)}</strong></td>
      <td>${formatNumber(wc.capacity)}</td>
      <td>${status}</td>
      <td><div class="table-actions">
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editWorkCenter(${JSON.stringify(wc)})'>${cct("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteWorkCenter(${wc.id})">${cct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

/* ===== Modal ===== */
function openWorkCenterModal() {
  document.getElementById("work-center-modal-title").textContent = cct("mf.addWorkCenter");
  document.getElementById("work-center-id").value = "";
  document.getElementById("work-center-code").value = "";
  document.getElementById("work-center-name").value = "";
  document.getElementById("work-center-type").value = "machine";
  document.getElementById("work-center-hourly-cost").value = "0";
  document.getElementById("work-center-capacity").value = "0";
  document.getElementById("work-center-active").checked = true;
  document.getElementById("work-center-notes").value = "";
  document.getElementById("work-center-modal").style.display = "flex";
  setTimeout(() => document.getElementById("work-center-name").focus(), 50);
}
window.openWorkCenterModal = openWorkCenterModal;

function editWorkCenter(wc) {
  document.getElementById("work-center-modal-title").textContent = cct("mf.editWorkCenter");
  document.getElementById("work-center-id").value = wc.id;
  document.getElementById("work-center-code").value = wc.code || "";
  document.getElementById("work-center-name").value = wc.name || "";
  document.getElementById("work-center-type").value = wc.wc_type || "machine";
  document.getElementById("work-center-hourly-cost").value = wc.hourly_cost || 0;
  document.getElementById("work-center-capacity").value = wc.capacity || 0;
  document.getElementById("work-center-active").checked = !!wc.is_active;
  document.getElementById("work-center-notes").value = wc.notes || "";
  document.getElementById("work-center-modal").style.display = "flex";
}
window.editWorkCenter = editWorkCenter;

function closeWorkCenterModal() {
  document.getElementById("work-center-modal").style.display = "none";
}
window.closeWorkCenterModal = closeWorkCenterModal;

async function saveWorkCenter() {
  const id = document.getElementById("work-center-id").value;
  const payload = {
    code: document.getElementById("work-center-code").value.trim(),
    name: document.getElementById("work-center-name").value.trim(),
    wc_type: document.getElementById("work-center-type").value,
    hourly_cost: document.getElementById("work-center-hourly-cost").value,
    capacity: document.getElementById("work-center-capacity").value,
    is_active: document.getElementById("work-center-active").checked,
    notes: document.getElementById("work-center-notes").value,
  };
  if (!payload.name) { showToast(cct("mf.nameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/mf/work-centers/${id}`, payload);
    else await api.post("/api/mf/work-centers", payload);
    showToast(cct("mf.saved"));
    closeWorkCenterModal();
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveWorkCenter = saveWorkCenter;

async function deleteWorkCenter(id) {
  const wc = workCenters.find((x) => x.id === id);
  if (!confirm(cct("mf.confirmDelete") + " " + (wc ? wc.name : ""))) return;
  try {
    await api.delete(`/api/mf/work-centers/${id}`);
    showToast(cct("mf.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteWorkCenter = deleteWorkCenter;

document.addEventListener("DOMContentLoaded", loadData);

/* ============================================================
   Manufacturing - Quality Inspections
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

let inspections = [];
let optionsData = { orders: [] };

async function loadData() {
  try {
    const [opts, list] = await Promise.all([
      api.get("/api/mf/options"),
      api.get("/api/mf/inspections"),
    ]);
    optionsData = opts || {};
    inspections = list || [];
    renderInspections();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function statusBadge(status) {
  const map = {
    in_progress: "badge-primary",
    passed: "badge-success",
    failed: "badge-danger",
  };
  return `<span class="badge ${map[status] || "badge-neutral"}">${cct("mf.status." + status)}</span>`;
}

function renderInspections() {
  document.getElementById("inspections-empty").style.display = inspections.length ? "none" : "block";
  const canEdit = canAction("manufacturing", "edit");
  const canDelete = canAction("manufacturing", "delete");
  document.getElementById("inspections-table").innerHTML = inspections.map((i) => {
    return `<tr>
      <td><div class="cell-main">${escapeHtml(i.inspection_number)}</div></td>
      <td>${escapeHtml(i.order_number || "—")}</td>
      <td><div class="cell-main">${escapeHtml(i.product_name || i.item_name || "—")}</div></td>
      <td>${escapeHtml(i.inspector || "—")}</td>
      <td>${escapeHtml(i.inspection_date || "—")}</td>
      <td>${formatNumber(i.sample_size)}</td>
      <td>${formatNumber(i.passed_qty)}</td>
      <td>${formatNumber(i.failed_qty)}</td>
      <td>${statusBadge(i.status)}</td>
      <td><div class="table-actions">
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editInspection(${JSON.stringify(i)})'>${cct("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteInspection(${i.id})">${cct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

function fillSelects(ins) {
  ins = ins || {};
  const ordOpts = optionsData.orders.map((o) =>
    `<option value="${o.id}" ${String(o.id) === String(ins.order_id) ? "selected" : ""}>${escapeHtml((o.order_number || "") + " - " + (o.product_name || ""))}</option>`).join("");
  document.getElementById("inspection-order").innerHTML =
    `<option value="">${cct("mf.selectOrder")}</option>` + ordOpts;
}

/* ===== Modal ===== */
function openInspectionModal() {
  document.getElementById("inspection-modal-title").textContent = cct("mf.addInspection");
  document.getElementById("inspection-id").value = "";
  fillSelects();
  document.getElementById("inspection-inspector").value = "";
  document.getElementById("inspection-date").value = "";
  document.getElementById("inspection-status").value = "in_progress";
  document.getElementById("inspection-sample-size").value = "0";
  document.getElementById("inspection-passed-qty").value = "0";
  document.getElementById("inspection-failed-qty").value = "0";
  document.getElementById("inspection-notes").value = "";
  document.getElementById("inspection-modal").style.display = "flex";
}
window.openInspectionModal = openInspectionModal;

function editInspection(ins) {
  document.getElementById("inspection-modal-title").textContent = cct("mf.editInspection");
  document.getElementById("inspection-id").value = ins.id;
  fillSelects(ins);
  document.getElementById("inspection-inspector").value = ins.inspector || "";
  document.getElementById("inspection-date").value = ins.inspection_date || "";
  document.getElementById("inspection-status").value = ins.status || "in_progress";
  document.getElementById("inspection-sample-size").value = ins.sample_size || 0;
  document.getElementById("inspection-passed-qty").value = ins.passed_qty || 0;
  document.getElementById("inspection-failed-qty").value = ins.failed_qty || 0;
  document.getElementById("inspection-notes").value = ins.notes || "";
  document.getElementById("inspection-modal").style.display = "flex";
}
window.editInspection = editInspection;

function closeInspectionModal() {
  document.getElementById("inspection-modal").style.display = "none";
}
window.closeInspectionModal = closeInspectionModal;

async function saveInspection() {
  const id = document.getElementById("inspection-id").value;
  const payload = {
    order_id: document.getElementById("inspection-order").value,
    inspector: document.getElementById("inspection-inspector").value.trim(),
    inspection_date: document.getElementById("inspection-date").value || null,
    status: document.getElementById("inspection-status").value,
    sample_size: document.getElementById("inspection-sample-size").value,
    passed_qty: document.getElementById("inspection-passed-qty").value,
    failed_qty: document.getElementById("inspection-failed-qty").value,
    notes: document.getElementById("inspection-notes").value,
  };
  if (!payload.order_id) { showToast(cct("mf.orderRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/mf/inspections/${id}`, payload);
    else await api.post("/api/mf/inspections", payload);
    showToast(cct("mf.saved"));
    closeInspectionModal();
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveInspection = saveInspection;

async function deleteInspection(id) {
  const ins = inspections.find((x) => x.id === id);
  if (!confirm(cct("mf.confirmDelete") + " " + (ins ? ins.inspection_number : ""))) return;
  try {
    await api.delete(`/api/mf/inspections/${id}`);
    showToast(cct("mf.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteInspection = deleteInspection;

document.addEventListener("DOMContentLoaded", loadData);

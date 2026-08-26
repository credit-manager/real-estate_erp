/* ============================================================
   Manufacturing - Operations
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

let operations = [];
let optionsData = { orders: [], work_centers: [] };

async function loadData() {
  try {
    const [opts, list] = await Promise.all([
      api.get("/api/mf/options"),
      api.get("/api/mf/operations"),
    ]);
    optionsData = opts || {};
    operations = list || [];
    renderOperations();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function statusBadge(status) {
  const map = {
    pending: "badge-neutral",
    in_progress: "badge-primary",
    completed: "badge-success",
    cancelled: "badge-danger",
  };
  return `<span class="badge ${map[status] || "badge-neutral"}">${cct("mf.status." + status)}</span>`;
}

function renderOperations() {
  document.getElementById("operations-empty").style.display = operations.length ? "none" : "block";
  const canEdit = canAction("manufacturing", "edit");
  const canDelete = canAction("manufacturing", "delete");
  document.getElementById("operations-table").innerHTML = operations.map((op) => {
    return `<tr>
      <td><div class="cell-main">${escapeHtml(op.order_number || "—")}</div><div class="table-sub">${escapeHtml(op.product_name || "")}</div></td>
      <td><div class="cell-main">${escapeHtml(op.name)}</div>${op.notes ? `<div class="table-sub">${escapeHtml(op.notes)}</div>` : ""}</td>
      <td>${op.work_center_name ? escapeHtml(op.work_center_name) : "—"}</td>
      <td>${formatNumber(op.planned_hours)}</td>
      <td>${formatNumber(op.actual_hours)}</td>
      <td><strong>${formatNumber(op.operation_cost)}</strong></td>
      <td>${statusBadge(op.status)}</td>
      <td><div class="table-actions">
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editOperation(${JSON.stringify(op)})'>${cct("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteOperation(${op.id})">${cct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

function fillSelects(op) {
  op = op || {};
  const ordOpts = optionsData.orders.map((o) =>
    `<option value="${o.id}" ${String(o.id) === String(op.order_id) ? "selected" : ""}>${escapeHtml((o.order_number || "") + " - " + (o.product_name || ""))}</option>`).join("");
  document.getElementById("operation-order").innerHTML =
    `<option value="">${cct("mf.selectOrder")}</option>` + ordOpts;
  const wcOpts = optionsData.work_centers.map((w) =>
    `<option value="${w.id}" ${String(w.id) === String(op.work_center_id) ? "selected" : ""}>${escapeHtml(w.code + " - " + w.name)}</option>`).join("");
  document.getElementById("operation-work-center").innerHTML =
    `<option value="">${cct("mf.selectWorkCenter")}</option>` + wcOpts;
}

/* ===== Modal ===== */
function openOperationModal() {
  document.getElementById("operation-modal-title").textContent = cct("mf.addOperation");
  document.getElementById("operation-id").value = "";
  fillSelects();
  document.getElementById("operation-name").value = "";
  document.getElementById("operation-start-date").value = "";
  document.getElementById("operation-end-date").value = "";
  document.getElementById("operation-planned-hours").value = "0";
  document.getElementById("operation-actual-hours").value = "0";
  document.getElementById("operation-labor-cost").value = "0";
  document.getElementById("operation-status").value = "pending";
  document.getElementById("operation-notes").value = "";
  document.getElementById("operation-modal").style.display = "flex";
}
window.openOperationModal = openOperationModal;

function editOperation(op) {
  document.getElementById("operation-modal-title").textContent = cct("mf.editOperation");
  document.getElementById("operation-id").value = op.id;
  fillSelects(op);
  document.getElementById("operation-name").value = op.name || "";
  document.getElementById("operation-start-date").value = op.start_date || "";
  document.getElementById("operation-end-date").value = op.end_date || "";
  document.getElementById("operation-planned-hours").value = op.planned_hours || 0;
  document.getElementById("operation-actual-hours").value = op.actual_hours || 0;
  document.getElementById("operation-labor-cost").value = op.labor_cost || 0;
  document.getElementById("operation-status").value = op.status || "pending";
  document.getElementById("operation-notes").value = op.notes || "";
  document.getElementById("operation-modal").style.display = "flex";
}
window.editOperation = editOperation;

function closeOperationModal() {
  document.getElementById("operation-modal").style.display = "none";
}
window.closeOperationModal = closeOperationModal;

async function saveOperation() {
  const id = document.getElementById("operation-id").value;
  const orderId = document.getElementById("operation-order").value;
  const payload = {
    work_center_id: document.getElementById("operation-work-center").value,
    name: document.getElementById("operation-name").value.trim(),
    start_date: document.getElementById("operation-start-date").value || null,
    end_date: document.getElementById("operation-end-date").value || null,
    planned_hours: document.getElementById("operation-planned-hours").value,
    actual_hours: document.getElementById("operation-actual-hours").value,
    labor_cost: document.getElementById("operation-labor-cost").value,
    status: document.getElementById("operation-status").value,
    notes: document.getElementById("operation-notes").value,
  };
  if (!payload.name) { showToast(cct("mf.nameRequired"), "warning"); return; }
  try {
    if (id) {
      await api.put(`/api/mf/operations/${id}`, payload);
    } else {
      if (!orderId) { showToast(cct("mf.orderRequired"), "warning"); return; }
      await api.post(`/api/mf/orders/${orderId}/operations`, payload);
    }
    showToast(cct("mf.saved"));
    closeOperationModal();
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveOperation = saveOperation;

async function deleteOperation(id) {
  const op = operations.find((x) => x.id === id);
  if (!confirm(cct("mf.confirmDelete") + " " + (op ? op.name : ""))) return;
  try {
    await api.delete(`/api/mf/operations/${id}`);
    showToast(cct("mf.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteOperation = deleteOperation;

document.addEventListener("DOMContentLoaded", loadData);

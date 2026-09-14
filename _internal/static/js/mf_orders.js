/* ============================================================
   Manufacturing - Production Orders
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

let orders = [];
let optionsData = { boms: [], warehouses: [] };

async function loadData() {
  try {
    const [opts, list] = await Promise.all([
      api.get("/api/mf/options"),
      api.get("/api/mf/orders"),
    ]);
    optionsData = opts || {};
    orders = list || [];
    renderKPI();
    renderOrders();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderKPI() {
  document.getElementById("kpi-orders").textContent = orders.length;
  document.getElementById("kpi-planned").textContent = orders.filter((o) => o.status === "planned").length;
  document.getElementById("kpi-in-progress").textContent = orders.filter((o) => o.status === "in_progress").length;
  document.getElementById("kpi-completed").textContent = orders.filter((o) => o.status === "completed").length;
}

function statusBadge(status) {
  const map = {
    planned: "badge-neutral",
    in_progress: "badge-primary",
    completed: "badge-success",
    cancelled: "badge-danger",
  };
  return `<span class="badge ${map[status] || "badge-neutral"}">${cct("mf.status." + status)}</span>`;
}

function progressBar(pct) {
  const p = Math.max(0, Math.min(100, Number(pct) || 0));
  return `<div style="width:120px;height:8px;background:var(--muted);border-radius:99px;overflow:hidden;">
    <div style="width:${p}%;height:100%;background:${p >= 100 ? "var(--success)" : "var(--primary)"};border-radius:99px;"></div>
  </div><div class="table-sub">${p}%</div>`;
}

function renderOrders() {
  document.getElementById("orders-empty").style.display = orders.length ? "none" : "block";
  const canEdit = canAction("manufacturing", "edit");
  const canDelete = canAction("manufacturing", "delete");
  document.getElementById("orders-table").innerHTML = orders.map((o) => {
    const actions = [];
    if (canEdit && (o.status === "planned" || o.status === "in_progress")) {
      if (o.status === "planned") actions.push(`<button class="btn btn-info btn-sm" onclick="startOrder(${o.id})">${cct("mf.startProduction")}</button>`);
      actions.push(`<button class="btn btn-outline btn-sm" onclick="produceOrder(${o.id})">${cct("mf.recordProduction")}</button>`);
      actions.push(`<button class="btn btn-success btn-sm" onclick="completeOrder(${o.id})">${cct("mf.completeOrder")}</button>`);
    }
    if (canEdit && o.status !== "completed" && o.status !== "cancelled") {
      actions.push(`<button class="btn btn-secondary btn-sm" onclick='editOrder(${JSON.stringify(o)})'>${cct("common.edit")}</button>`);
      actions.push(`<button class="btn btn-danger btn-sm" onclick="cancelOrder(${o.id})">${cct("mf.cancelOrder")}</button>`);
    }
    if (canDelete && o.status !== "completed") {
      actions.push(`<button class="btn btn-danger btn-sm" onclick="deleteOrder(${o.id})">${cct("common.delete")}</button>`);
    }
    return `<tr>
      <td><div class="cell-main">${escapeHtml(o.order_number)}</div><div class="table-sub">${escapeHtml(o.bom_name || "")}</div></td>
      <td><div class="cell-main">${escapeHtml(o.product_name || "—")}</div><div class="table-sub">${escapeHtml(o.warehouse_name || "")}</div></td>
      <td>${formatNumber(o.quantity)}</td>
      <td>${formatNumber(o.produced_qty)}</td>
      <td>${progressBar(o.progress)}</td>
      <td>${statusBadge(o.status)}</td>
      <td><strong>${formatNumber(o.total_cost)}</strong></td>
      <td><div class="table-actions">${actions.join("")}</div></td>
    </tr>`;
  }).join("");
}

function fillOrderSelects(order) {
  order = order || {};
  const bomOpts = optionsData.boms.map((b) =>
    `<option value="${b.id}" ${String(b.id) === String(order.bom_id) ? "selected" : ""}>${escapeHtml(b.code + " - " + b.name + (b.product_name ? " (" + b.product_name + ")" : ""))}</option>`).join("");
  document.getElementById("order-bom").innerHTML =
    `<option value="">${cct("mf.selectBom")}</option>` + bomOpts;
  const whOpts = optionsData.warehouses.map((w) =>
    `<option value="${w.id}" ${String(w.id) === String(order.warehouse_id) ? "selected" : ""}>${escapeHtml(w.name)}</option>`).join("");
  document.getElementById("order-warehouse").innerHTML =
    `<option value="">${cct("mf.selectWarehouse")}</option>` + whOpts;
}

/* ===== Modal ===== */
function openOrderModal() {
  document.getElementById("order-modal-title").textContent = cct("mf.addOrder");
  document.getElementById("order-id").value = "";
  fillOrderSelects();
  document.getElementById("order-quantity").value = "1";
  document.getElementById("order-produced-qty").value = "0";
  document.getElementById("order-start-date").value = "";
  document.getElementById("order-due-date").value = "";
  document.getElementById("order-labor-cost").value = "0";
  document.getElementById("order-overhead-cost").value = "0";
  document.getElementById("order-notes").value = "";
  document.getElementById("order-modal").style.display = "flex";
}
window.openOrderModal = openOrderModal;

function editOrder(o) {
  document.getElementById("order-modal-title").textContent = cct("mf.editOrder");
  document.getElementById("order-id").value = o.id;
  fillOrderSelects(o);
  document.getElementById("order-quantity").value = o.quantity;
  document.getElementById("order-produced-qty").value = o.produced_qty;
  document.getElementById("order-start-date").value = o.start_date || "";
  document.getElementById("order-due-date").value = o.due_date || "";
  document.getElementById("order-labor-cost").value = o.labor_cost || 0;
  document.getElementById("order-overhead-cost").value = o.overhead_cost || 0;
  document.getElementById("order-notes").value = o.notes || "";
  document.getElementById("order-modal").style.display = "flex";
}
window.editOrder = editOrder;

function closeOrderModal() {
  document.getElementById("order-modal").style.display = "none";
}
window.closeOrderModal = closeOrderModal;

async function saveOrder() {
  const id = document.getElementById("order-id").value;
  const payload = {
    bom_id: document.getElementById("order-bom").value,
    warehouse_id: document.getElementById("order-warehouse").value,
    quantity: document.getElementById("order-quantity").value,
    produced_qty: document.getElementById("order-produced-qty").value,
    start_date: document.getElementById("order-start-date").value || null,
    due_date: document.getElementById("order-due-date").value || null,
    labor_cost: document.getElementById("order-labor-cost").value,
    overhead_cost: document.getElementById("order-overhead-cost").value,
    notes: document.getElementById("order-notes").value,
  };
  if (!payload.bom_id) { showToast(cct("mf.bomRequired"), "warning"); return; }
  if (!payload.warehouse_id) { showToast(cct("mf.warehouseRequired"), "warning"); return; }
  if (parseFloat(payload.quantity) <= 0) { showToast(cct("mf.qtyRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/mf/orders/${id}`, payload);
    else await api.post("/api/mf/orders", payload);
    showToast(cct("mf.saved"));
    closeOrderModal();
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveOrder = saveOrder;

/* ===== Actions ===== */
async function startOrder(id) {
  try {
    await api.post(`/api/mf/orders/${id}/start`);
    showToast(cct("mf.saved"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.startOrder = startOrder;

async function produceOrder(id) {
  const qty = prompt(cct("mf.produceQty"));
  if (qty === null || qty === "") return;
  if (parseFloat(qty) <= 0) { showToast(cct("mf.qtyRequired"), "warning"); return; }
  try {
    await api.post(`/api/mf/orders/${id}/produce`, { qty: parseFloat(qty) });
    showToast(cct("mf.saved"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.produceOrder = produceOrder;

async function completeOrder(id) {
  if (!confirm(cct("mf.completeOrder") + "?")) return;
  try {
    await api.post(`/api/mf/orders/${id}/complete`);
    showToast(cct("mf.saved"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.completeOrder = completeOrder;

async function cancelOrder(id) {
  if (!confirm(cct("mf.cancelOrder") + "?")) return;
  try {
    await api.post(`/api/mf/orders/${id}/cancel`);
    showToast(cct("mf.saved"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.cancelOrder = cancelOrder;

async function deleteOrder(id) {
  const o = orders.find((x) => x.id === id);
  if (!confirm(cct("mf.confirmDelete") + " " + (o ? o.order_number : ""))) return;
  try {
    await api.delete(`/api/mf/orders/${id}`);
    showToast(cct("mf.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteOrder = deleteOrder;

document.addEventListener("DOMContentLoaded", loadData);

let batchesData = [];
let batchItems = [];
let batchWarehouses = [];

async function loadBatches() {
  try {
    const [batRes, itemsRes, whRes] = await Promise.all([
      api.get("/api/inventory/batches"),
      api.get("/api/inventory/items"),
      api.get("/api/inventory/warehouses"),
    ]);
    batchesData = batRes.batches || [];
    batchItems = itemsRes.items || [];
    batchWarehouses = whRes.warehouses || [];
    fillBatchSelects();
    renderBatches();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function fillBatchSelects() {
  const itemSel = document.getElementById("batch-item");
  const whSel = document.getElementById("batch-warehouse");
  itemSel.innerHTML = batchItems.map((i) =>
    `<option value="${i.id}">${escapeHtml(i.code)} — ${escapeHtml(i.name)}</option>`).join("");
  whSel.innerHTML = batchWarehouses.map((w) =>
    `<option value="${w.id}">${escapeHtml(w.name)}</option>`).join("");
}

function openBatchModal(batch) {
  document.getElementById("batch-id").value = batch ? batch.id : "";
  document.getElementById("batch-item").value = batch ? batch.item_id : (batchItems[0] ? batchItems[0].id : "");
  document.getElementById("batch-warehouse").value = batch ? batch.warehouse_id : (batchWarehouses[0] ? batchWarehouses[0].id : "");
  document.getElementById("batch-number").value = batch ? batch.batch_number : "";
  document.getElementById("batch-qty").value = batch ? batch.quantity : "";
  document.getElementById("batch-received").value = batch ? (batch.received_date || "") : "";
  document.getElementById("batch-expiry").value = batch ? (batch.expiry_date || "") : "";
  document.getElementById("batch-modal-title").textContent = batch ? invT("inventory.editBatch") : invT("inventory.addBatch");
  document.getElementById("batch-modal").classList.add("active");
}
window.openBatchModal = openBatchModal;

function closeBatchModal() {
  document.getElementById("batch-modal").classList.remove("active");
}
window.closeBatchModal = closeBatchModal;

function editBatch(batch) { openBatchModal(batch); }
window.editBatch = editBatch;

function renderBatches() {
  const q = (document.getElementById("batch-search").value || "").trim().toLowerCase();
  const list = q ? batchesData.filter((b) =>
    (b.batch_number + " " + (b.item_name || "")).toLowerCase().includes(q)) : batchesData;
  const tbody = document.getElementById("batches-table");
  document.getElementById("batches-count").textContent = `(${list.length})`;
  document.getElementById("batches-empty").style.display = list.length ? "none" : "";
  tbody.innerHTML = list.map((b) => `
    <tr>
      <td><b>${escapeHtml(b.batch_number)}</b></td>
      <td>${escapeHtml(b.item_name || "—")}</td>
      <td>${escapeHtml(b.warehouse_name || "—")}</td>
      <td><b>${formatNumber(b.quantity)}</b></td>
      <td>${b.received_date ? formatDate(b.received_date) : "—"}</td>
      <td>${b.expiry_date ? formatDate(b.expiry_date) : "—"}</td>
      <td>${b.is_expired
        ? `<span class="badge badge-danger">${invT("inventory.expired")}</span>`
        : `<span class="badge badge-success">${invT("inventory.inStock")}</span>`}</td>
      <td>
        ${invCan("edit") ? `<button class="icon-btn" title="${invT("common.edit")}" onclick='editBatch(${JSON.stringify(b)})'>✏️</button>` : ""}
        ${invCan("delete") ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteBatch(${b.id})">🗑️</button>` : ""}
      </td>
    </tr>
  `).join("");
}
window.renderBatches = renderBatches;

async function saveBatch() {
  const id = document.getElementById("batch-id").value;
  const payload = {
    item_id: document.getElementById("batch-item").value,
    warehouse_id: document.getElementById("batch-warehouse").value,
    batch_number: document.getElementById("batch-number").value.trim(),
    quantity: parseFloat(document.getElementById("batch-qty").value) || 0,
    received_date: document.getElementById("batch-received").value || null,
    expiry_date: document.getElementById("batch-expiry").value || null,
  };
  if (!payload.batch_number || !payload.item_id || !payload.warehouse_id) {
    showToast(invT("inventory.noBatches"), "error");
    return;
  }
  try {
    if (id) {
      await api.request(`/api/inventory/batches/${id}`, "PUT", payload);
    } else {
      await api.request("/api/inventory/batches", "POST", payload);
    }
    showToast(t("common.saved"));
    closeBatchModal();
    loadBatches();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.saveBatch = saveBatch;

async function deleteBatch(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/batches/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadBatches();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteBatch = deleteBatch;

loadBatches();

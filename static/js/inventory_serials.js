let serialsData = [];
let serialItems = [];
let serialWarehouses = [];
let serialBatches = [];

async function loadSerials() {
  try {
    const [serRes, itemsRes, whRes, batRes] = await Promise.all([
      api.get("/api/inventory/serials"),
      api.get("/api/inventory/items"),
      api.get("/api/inventory/warehouses"),
      api.get("/api/inventory/batches"),
    ]);
    serialsData = serRes.serials || [];
    serialItems = itemsRes.items || [];
    serialWarehouses = whRes.warehouses || [];
    serialBatches = batRes.batches || [];
    fillSerialSelects();
    renderSerials();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function fillSerialSelects() {
  const itemSel = document.getElementById("serial-item");
  const whSel = document.getElementById("serial-warehouse");
  itemSel.innerHTML = serialItems.map((i) =>
    `<option value="${i.id}">${escapeHtml(i.code)} — ${escapeHtml(i.name)}</option>`).join("");
  whSel.innerHTML = serialWarehouses.map((w) =>
    `<option value="${w.id}">${escapeHtml(w.name)}</option>`).join("");
}

function onSerialItemChange() {
  const itemId = document.getElementById("serial-item").value;
  const batchSel = document.getElementById("serial-batch");
  batchSel.innerHTML = `<option value="">—</option>` + serialBatches
    .filter((b) => !itemId || String(b.item_id) === String(itemId))
    .map((b) => `<option value="${b.id}">${escapeHtml(b.batch_number)}</option>`).join("");
}
window.onSerialItemChange = onSerialItemChange;

function openSerialModal(serial) {
  document.getElementById("serial-id").value = serial ? serial.id : "";
  document.getElementById("serial-item").value = serial ? serial.item_id : (serialItems[0] ? serialItems[0].id : "");
  document.getElementById("serial-warehouse").value = serial ? serial.warehouse_id : (serialWarehouses[0] ? serialWarehouses[0].id : "");
  document.getElementById("serial-number").value = serial ? serial.serial_number : "";
  document.getElementById("serial-status").value = serial ? serial.status : "in_stock";
  onSerialItemChange();
  document.getElementById("serial-batch").value = serial ? (serial.batch_id || "") : "";
  document.getElementById("serial-modal-title").textContent = serial ? invT("inventory.editSerial") : invT("inventory.addSerial");
  document.getElementById("serial-modal").classList.add("active");
}
window.openSerialModal = openSerialModal;

function closeSerialModal() {
  document.getElementById("serial-modal").classList.remove("active");
}
window.closeSerialModal = closeSerialModal;

function editSerial(serial) { openSerialModal(serial); }
window.editSerial = editSerial;

function renderSerials() {
  const q = (document.getElementById("serial-search").value || "").trim().toLowerCase();
  const list = q ? serialsData.filter((s) =>
    (s.serial_number + " " + (s.item_name || "")).toLowerCase().includes(q)) : serialsData;
  const tbody = document.getElementById("serials-table");
  document.getElementById("serials-count").textContent = `(${list.length})`;
  document.getElementById("serials-empty").style.display = list.length ? "none" : "";
  tbody.innerHTML = list.map((s) => `
    <tr>
      <td><b>${escapeHtml(s.serial_number)}</b></td>
      <td>${escapeHtml(s.item_name || "—")}</td>
      <td>${escapeHtml(s.warehouse_name || "—")}</td>
      <td>${escapeHtml(s.batch_number || "—")}</td>
      <td>${invBadge(s.status)}</td>
      <td>${s.created_at ? formatDate(s.created_at) : "—"}</td>
      <td>
        ${invCan("edit") ? `<button class="icon-btn" title="${invT("common.edit")}" onclick='editSerial(${JSON.stringify(s)})'>✏️</button>` : ""}
        ${invCan("delete") ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteSerial(${s.id})">🗑️</button>` : ""}
      </td>
    </tr>
  `).join("");
}
window.renderSerials = renderSerials;

async function saveSerial() {
  const id = document.getElementById("serial-id").value;
  const payload = {
    item_id: document.getElementById("serial-item").value,
    warehouse_id: document.getElementById("serial-warehouse").value,
    serial_number: document.getElementById("serial-number").value.trim(),
    batch_id: document.getElementById("serial-batch").value || null,
    status: document.getElementById("serial-status").value,
  };
  if (!payload.serial_number || !payload.item_id || !payload.warehouse_id) {
    showToast(invT("inventory.noSerials"), "error");
    return;
  }
  try {
    if (id) {
      await api.request(`/api/inventory/serials/${id}`, "PUT", payload);
    } else {
      await api.request("/api/inventory/serials", "POST", payload);
    }
    showToast(t("common.saved"));
    closeSerialModal();
    loadSerials();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.saveSerial = saveSerial;

async function deleteSerial(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/serials/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadSerials();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteSerial = deleteSerial;

loadSerials();

let transfersData = [];
let transferItems = [];
let transferWarehouses = [];
let transferLines = [];

async function loadTransfers() {
  try {
    const [trRes, itemsRes, whRes] = await Promise.all([
      api.get("/api/inventory/transfers"),
      api.get("/api/inventory/items"),
      api.get("/api/inventory/warehouses"),
    ]);
    transfersData = trRes.transfers || [];
    transferItems = itemsRes.items || [];
    transferWarehouses = whRes.warehouses || [];
    fillTransferSelects();
    renderTransfers();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function fillTransferSelects() {
  const fromSel = document.getElementById("tr-from");
  const toSel = document.getElementById("tr-to");
  const itemSel = document.getElementById("tr-line-item");
  const whOpts = transferWarehouses.map((w) =>
    `<option value="${w.id}">${escapeHtml(w.name)}</option>`).join("");
  fromSel.innerHTML = whOpts;
  toSel.innerHTML = whOpts;
  itemSel.innerHTML = transferItems.map((i) =>
    `<option value="${i.id}">${escapeHtml(i.code)} — ${escapeHtml(i.name)}</option>`).join("");
}

function openTransferModal() {
  transferLines = [];
  document.getElementById("tr-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("tr-notes").value = "";
  document.getElementById("tr-line-qty").value = "";
  renderTransferLines();
  document.getElementById("transfer-modal").classList.add("active");
}
window.openTransferModal = openTransferModal;

function closeTransferModal() {
  document.getElementById("transfer-modal").classList.remove("active");
}
window.closeTransferModal = closeTransferModal;

function addTransferLine() {
  const itemId = document.getElementById("tr-line-item").value;
  const qty = parseFloat(document.getElementById("tr-line-qty").value);
  if (!itemId || !qty || qty <= 0) {
    showToast(invT("inventory.noItems"), "error");
    return;
  }
  const existing = transferLines.find((l) => String(l.item_id) === String(itemId));
  if (existing) {
    existing.quantity += qty;
  } else {
    const item = transferItems.find((i) => String(i.id) === String(itemId));
    transferLines.push({ item_id: Number(itemId), item_name: item ? item.name : "", quantity: qty });
  }
  document.getElementById("tr-line-qty").value = "";
  renderTransferLines();
}
window.addTransferLine = addTransferLine;

function removeTransferLine(idx) {
  transferLines.splice(idx, 1);
  renderTransferLines();
}
window.removeTransferLine = removeTransferLine;

function renderTransferLines() {
  const tbody = document.getElementById("tr-lines");
  document.getElementById("tr-lines-empty")?.remove();
  tbody.innerHTML = transferLines.map((l, idx) => `
    <tr>
      <td>${escapeHtml(l.item_name)}</td>
      <td>${formatNumber(l.quantity)}</td>
      <td><button class="icon-btn" title="${invT("common.delete")}" onclick="removeTransferLine(${idx})">🗑️</button></td>
    </tr>
  `).join("");
  if (!transferLines.length) {
    tbody.innerHTML = `<tr><td colspan="3" class="table-empty">—</td></tr>`;
  }
}

function renderTransfers() {
  const tbody = document.getElementById("transfers-table");
  document.getElementById("transfers-count").textContent = `(${transfersData.length})`;
  document.getElementById("transfers-empty").style.display = transfersData.length ? "none" : "";
  tbody.innerHTML = transfersData.map((tr) => `
    <tr>
      <td><b>${escapeHtml(tr.transfer_number)}</b></td>
      <td>${escapeHtml(tr.from_warehouse_name || "—")}</td>
      <td>${escapeHtml(tr.to_warehouse_name || "—")}</td>
      <td>${tr.transfer_date ? formatDate(tr.transfer_date) : "—"}</td>
      <td>${(tr.items || []).length}</td>
      <td>${invBadge(tr.status)}</td>
      <td>
        ${invCan("delete")
          ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteTransfer(${tr.id})">🗑️</button>`
          : ""}
      </td>
    </tr>
  `).join("");
}
window.renderTransfers = renderTransfers;

async function saveTransfer() {
  if (!transferLines.length) {
    showToast(invT("inventory.noTransfers"), "error");
    return;
  }
  const payload = {
    from_warehouse_id: document.getElementById("tr-from").value,
    to_warehouse_id: document.getElementById("tr-to").value,
    transfer_date: document.getElementById("tr-date").value || null,
    notes: document.getElementById("tr-notes").value.trim(),
    items: transferLines,
  };
  if (payload.from_warehouse_id === payload.to_warehouse_id) {
    showToast(invT("inventory.noTransfers"), "error");
    return;
  }
  try {
    await api.request("/api/inventory/transfers", "POST", payload);
    showToast(t("common.saved"));
    closeTransferModal();
    loadTransfers();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.saveTransfer = saveTransfer;

async function deleteTransfer(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/transfers/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadTransfers();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteTransfer = deleteTransfer;

loadTransfers();

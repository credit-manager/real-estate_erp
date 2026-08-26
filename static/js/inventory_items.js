let itemsData = [];
let itemCategories = [];
let itemUnits = [];

async function loadItems() {
  try {
    const [itemsRes, catsRes, unitsRes] = await Promise.all([
      api.get("/api/inventory/items"),
      api.get("/api/inventory/categories"),
      api.get("/api/inventory/units"),
    ]);
    itemsData = itemsRes.items || [];
    itemCategories = catsRes.categories || [];
    itemUnits = unitsRes.units || [];
    fillItemSelects();
    renderItems();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function fillItemSelects() {
  const catSel = document.getElementById("item-category");
  const unitSel = document.getElementById("item-unit");
  catSel.innerHTML = `<option value="">—</option>` + itemCategories.map((c) =>
    `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  unitSel.innerHTML = `<option value="">—</option>` + itemUnits.map((u) =>
    `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
}

function openItemModal(item) {
  document.getElementById("item-id").value = item ? item.id : "";
  document.getElementById("item-code").value = item ? item.code : "";
  document.getElementById("item-name").value = item ? item.name : "";
  document.getElementById("item-category").value = item ? (item.category_id || "") : "";
  document.getElementById("item-unit").value = item ? (item.unit_id || "") : "";
  document.getElementById("item-barcode").value = item ? (item.barcode || "") : "";
  document.getElementById("item-reorder").value = item ? item.reorder_level : "";
  document.getElementById("item-cost").value = item ? item.cost_price : "";
  document.getElementById("item-sale").value = item ? item.sale_price : "";
  document.getElementById("item-track-batch").checked = item ? !!item.track_batch : false;
  document.getElementById("item-track-serial").checked = item ? !!item.track_serial : false;
  document.getElementById("item-track-expiry").checked = item ? !!item.track_expiry : false;
  document.getElementById("item-notes").value = item ? (item.description || "") : "";
  document.getElementById("item-active").checked = item ? item.is_active : true;
  document.getElementById("item-modal-title").textContent = item ? invT("inventory.editItem") : invT("inventory.addItem");
  document.getElementById("item-modal").classList.add("active");
}
window.openItemModal = openItemModal;

function closeItemModal() {
  document.getElementById("item-modal").classList.remove("active");
}
window.closeItemModal = closeItemModal;

function editItem(item) { openItemModal(item); }
window.editItem = editItem;

function renderItems() {
  const q = (document.getElementById("item-search").value || "").trim().toLowerCase();
  const list = q ? itemsData.filter((i) =>
    (i.code + " " + i.name + " " + (i.barcode || "")).toLowerCase().includes(q)) : itemsData;
  const tbody = document.getElementById("items-table");
  document.getElementById("items-count").textContent = `(${list.length})`;
  document.getElementById("items-empty").style.display = list.length ? "none" : "";
  tbody.innerHTML = list.map((i) => `
    <tr>
      <td><b>${escapeHtml(i.code)}</b></td>
      <td>${escapeHtml(i.name)}</td>
      <td>${escapeHtml(i.category_name || "—")}</td>
      <td>${escapeHtml(i.unit_name || "—")}</td>
      <td>${formatMoney(i.cost_price)}</td>
      <td>${formatMoney(i.sale_price)}</td>
      <td><b>${formatNumber(i.quantity)}</b></td>
      <td>${formatNumber(i.reorder_level)}</td>
      <td>${invStatusBadge(i.is_active)}</td>
      <td>
        ${invCan("edit") ? `<button class="icon-btn" title="${invT("common.edit")}" onclick='editItem(${JSON.stringify(i)})'>✏️</button>` : ""}
        ${invCan("delete") ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteItem(${i.id})">🗑️</button>` : ""}
      </td>
    </tr>
  `).join("");
}
window.renderItems = renderItems;

async function saveItem() {
  const id = document.getElementById("item-id").value;
  const payload = {
    code: document.getElementById("item-code").value.trim(),
    name: document.getElementById("item-name").value.trim(),
    category_id: document.getElementById("item-category").value || null,
    unit_id: document.getElementById("item-unit").value || null,
    barcode: document.getElementById("item-barcode").value.trim(),
    description: document.getElementById("item-notes").value.trim(),
    cost_price: parseFloat(document.getElementById("item-cost").value) || 0,
    sale_price: parseFloat(document.getElementById("item-sale").value) || 0,
    reorder_level: parseFloat(document.getElementById("item-reorder").value) || 0,
    track_batch: document.getElementById("item-track-batch").checked,
    track_serial: document.getElementById("item-track-serial").checked,
    track_expiry: document.getElementById("item-track-expiry").checked,
    is_active: document.getElementById("item-active").checked,
  };
  if (!payload.code || !payload.name) {
    showToast(invT("inventory.noItems"), "error");
    return;
  }
  try {
    if (id) {
      await api.request(`/api/inventory/items/${id}`, "PUT", payload);
    } else {
      await api.request("/api/inventory/items", "POST", payload);
    }
    showToast(t("common.saved"));
    closeItemModal();
    loadItems();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.saveItem = saveItem;

async function deleteItem(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/items/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadItems();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteItem = deleteItem;

loadItems();

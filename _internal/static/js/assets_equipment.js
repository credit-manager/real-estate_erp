/* المعدات */
let editingItemId = null;

async function loadItems() {
  try {
    const status = document.getElementById("filter-status")?.value || "";
    const params = new URLSearchParams();
    params.set("kind", "equipment");
    if (status) params.set("status", status);
    const items = await api.get(`/assets/api/items?${params.toString()}`);
    const tbody = document.getElementById("items-table");
    tbody.innerHTML = items.length ? items.map((a) => `
      <tr>
        <td><strong>${escapeHtml(a.code)}</strong></td>
        <td>${escapeHtml(a.name)}</td>
        <td>${escapeHtml(a.category_name || "—")}</td>
        <td>${escapeHtml(a.serial_number || "—")}</td>
        <td>${escapeHtml(a.brand || "—")}</td>
        <td>${escapeHtml(a.model || "—")}</td>
        <td>${escapeHtml(a.location_name || "—")}</td>
        <td>${fmtMoney(a.cost)}</td>
        <td>${statusBadge(a.status)}</td>
        <td>${a.custody_employee_name ? escapeHtml(a.custody_employee_name) : "—"}</td>
        <td>
          <div class="table-actions">
            ${canAction("accounting", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editItem(${JSON.stringify(a)})'>${t("common.edit")}</button>` : ""}
            ${canAction("accounting", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteItem(${a.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="11"><div class="empty-state">${t("assets.noItems")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

async function loadMeta() {
  const meta = await loadAssetsMeta();
  if (!meta) return;
  fillSelect("it-category", meta.categories.filter(c => c.kind === "equipment"), t("common.select"));
  fillSelect("it-location", meta.warehouses, t("common.select"));
  fillSelect("it-supplier", meta.suppliers, t("common.select"));
}

function openItemModal(a) {
  editingItemId = a ? a.id : null;
  document.getElementById("item-modal-title").textContent = a ? t("common.edit") : t("assets.newEquipment");
  document.getElementById("it-code").value = a ? a.code : "";
  document.getElementById("it-name").value = a ? a.name : "";
  document.getElementById("it-category").value = a ? a.category_id || "" : "";
  document.getElementById("it-type").value = a ? a.asset_type || "" : "";
  document.getElementById("it-serial").value = a ? a.serial_number || "" : "";
  document.getElementById("it-brand").value = a ? a.brand || "" : "";
  document.getElementById("it-model").value = a ? a.model || "" : "";
  document.getElementById("it-location").value = a ? a.location_id || "" : "";
  document.getElementById("it-supplier").value = a ? a.supplier_id || "" : "";
  document.getElementById("it-purchase-date").value = a ? a.purchase_date || "" : "";
  document.getElementById("it-purchase-price").value = a ? a.purchase_price || "" : "";
  document.getElementById("it-cost").value = a ? a.cost || "" : "";
  document.getElementById("it-life").value = a ? a.useful_life_years || 5 : 5;
  document.getElementById("it-salvage").value = a ? a.salvage_value || 0 : 0;
  document.getElementById("it-dep-method").value = a ? a.depreciation_method || "straight" : "straight";
  document.getElementById("it-condition").value = a ? a.condition || "good" : "good";
  document.getElementById("it-status").value = a ? a.status || "active" : "active";
  document.getElementById("it-warranty").value = a ? a.warranty_until || "" : "";
  document.getElementById("it-notes").value = a ? a.notes || "" : "";
  document.getElementById("item-modal").classList.add("active");
}

function editItem(a) { openItemModal(a); }
function closeItemModal() { document.getElementById("item-modal").classList.remove("active"); }

async function saveItem() {
  const code = document.getElementById("it-code").value.trim();
  const name = document.getElementById("it-name").value.trim();
  if (!code || !name) { showToast(t("common.required"), "warning"); return; }
  const body = {
    code,
    name,
    kind: "equipment",
    category_id: parseInt(document.getElementById("it-category").value) || null,
    asset_type: document.getElementById("it-type").value.trim(),
    serial_number: document.getElementById("it-serial").value.trim(),
    brand: document.getElementById("it-brand").value.trim(),
    model: document.getElementById("it-model").value.trim(),
    location_id: parseInt(document.getElementById("it-location").value) || null,
    supplier_id: parseInt(document.getElementById("it-supplier").value) || null,
    purchase_date: document.getElementById("it-purchase-date").value,
    purchase_price: parseFloat(document.getElementById("it-purchase-price").value) || 0,
    cost: parseFloat(document.getElementById("it-cost").value) || 0,
    useful_life_years: parseInt(document.getElementById("it-life").value) || 5,
    salvage_value: parseFloat(document.getElementById("it-salvage").value) || 0,
    depreciation_method: document.getElementById("it-dep-method").value,
    condition: document.getElementById("it-condition").value,
    status: document.getElementById("it-status").value,
    warranty_until: document.getElementById("it-warranty").value,
    notes: document.getElementById("it-notes").value.trim(),
  };
  try {
    if (editingItemId) await api.put(`/assets/api/items/${editingItemId}`, body);
    else await api.post("/assets/api/items", body);
    showToast(t("common.savedSuccess"));
    closeItemModal();
    loadItems();
  } catch (e) { toastError(e); }
}

async function deleteItem(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/assets/api/items/${id}`);
    showToast(t("common.deleted"));
    loadItems();
  } catch (e) { toastError(e); }
}

window.openItemModal = openItemModal;
window.editItem = editItem;
window.closeItemModal = closeItemModal;
window.saveItem = saveItem;
window.deleteItem = deleteItem;
window.loadItems = loadItems;

document.addEventListener("DOMContentLoaded", () => {
  loadMeta();
  loadItems();
});

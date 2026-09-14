let warehousesData = [];

function openWarehouseModal(wh) {
  document.getElementById("wh-id").value = wh ? wh.id : "";
  document.getElementById("wh-code").value = wh ? wh.code : "";
  document.getElementById("wh-name").value = wh ? wh.name : "";
  document.getElementById("wh-location").value = wh ? (wh.location || "") : "";
  document.getElementById("wh-manager").value = wh ? (wh.manager_name || "") : "";
  document.getElementById("wh-phone").value = wh ? (wh.phone || "") : "";
  document.getElementById("wh-notes").value = wh ? (wh.notes || "") : "";
  document.getElementById("wh-active").checked = wh ? wh.is_active : true;
  document.getElementById("warehouse-modal-title").textContent = wh ? invT("inventory.editWarehouse") : invT("inventory.addWarehouse");
  document.getElementById("warehouse-modal").classList.add("active");
}
window.openWarehouseModal = openWarehouseModal;

function closeWarehouseModal() {
  document.getElementById("warehouse-modal").classList.remove("active");
}
window.closeWarehouseModal = closeWarehouseModal;

function editWarehouse(wh) { openWarehouseModal(wh); }
window.editWarehouse = editWarehouse;

async function loadWarehouses() {
  try {
    const res = await api.get("/api/inventory/warehouses");
    warehousesData = res.warehouses || [];
    renderWarehouses();
    document.getElementById("kpi-warehouses").textContent = warehousesData.length;
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderWarehouses() {
  const q = (document.getElementById("wh-search").value || "").trim().toLowerCase();
  const list = q ? warehousesData.filter((w) =>
    (w.code + " " + w.name + " " + (w.location || "") + " " + (w.manager_name || "")).toLowerCase().includes(q)
  ) : warehousesData;
  const tbody = document.getElementById("warehouses-table");
  document.getElementById("warehouses-count").textContent = `(${list.length})`;
  document.getElementById("warehouses-empty").style.display = list.length ? "none" : "";
  tbody.innerHTML = list.map((w) => `
    <tr>
      <td><b>${escapeHtml(w.code)}</b></td>
      <td>${escapeHtml(w.name)}</td>
      <td>${escapeHtml(w.location || "—")}</td>
      <td>${escapeHtml(w.manager_name || "—")}</td>
      <td>${escapeHtml(w.phone || "—")}</td>
      <td>${invStatusBadge(w.is_active)}</td>
      <td>
        ${invCan("edit") ? `<button class="icon-btn" title="${invT("common.edit")}" onclick='editWarehouse(${JSON.stringify(w)})'>✏️</button>` : ""}
        ${invCan("delete") ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteWarehouse(${w.id})">🗑️</button>` : ""}
      </td>
    </tr>
  `).join("");
}

window.renderWarehouses = renderWarehouses;

async function saveWarehouse() {
  const id = document.getElementById("wh-id").value;
  const payload = {
    code: document.getElementById("wh-code").value.trim(),
    name: document.getElementById("wh-name").value.trim(),
    location: document.getElementById("wh-location").value.trim(),
    manager_name: document.getElementById("wh-manager").value.trim(),
    phone: document.getElementById("wh-phone").value.trim(),
    notes: document.getElementById("wh-notes").value.trim(),
    is_active: document.getElementById("wh-active").checked,
  };
  if (!payload.code || !payload.name) {
    showToast(invT("inventory.noWarehouses"), "error");
    return;
  }
  try {
    if (id) {
      await api.request(`/api/inventory/warehouses/${id}`, "PUT", payload);
    } else {
      await api.request("/api/inventory/warehouses", "POST", payload);
    }
    showToast(t("common.saved"));
    closeWarehouseModal();
    loadWarehouses();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.saveWarehouse = saveWarehouse;

async function deleteWarehouse(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/warehouses/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadWarehouses();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteWarehouse = deleteWarehouse;

loadWarehouses();

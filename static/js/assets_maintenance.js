/* صيانة الأصول والمعدات */
let editingMaintenanceId = null;

async function loadMaintenance() {
  try {
    const assetId = document.getElementById("filter-asset")?.value || "";
    const params = new URLSearchParams();
    if (assetId) params.set("asset_id", assetId);
    const records = await api.get(`/assets/api/maintenance?${params.toString()}`);
    const tbody = document.getElementById("maintenance-table");
    tbody.innerHTML = records.length ? records.map((r) => `
      <tr>
        <td><strong>${escapeHtml(r.asset_code)}</strong> - ${escapeHtml(r.asset_name)}</td>
        <td>${formatDate(r.maintenance_date)}</td>
        <td>${maintenanceTypeLabel(r.maintenance_type)}</td>
        <td>${fmtMoney(r.cost)}</td>
        <td>${escapeHtml(r.vendor || "—")}</td>
        <td>${escapeHtml(r.technician || "—")}</td>
        <td>${statusBadge(r.status)}</td>
        <td>${r.next_maintenance_date ? formatDate(r.next_maintenance_date) : "—"}</td>
        <td>
          <div class="table-actions">
            ${canAction("accounting", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editMaintenance(${JSON.stringify(r)})'>${t("common.edit")}</button>` : ""}
            ${canAction("accounting", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteMaintenance(${r.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="9"><div class="empty-state">${t("assets.noMaintenance")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

async function loadMeta() {
  const meta = await loadAssetsMeta();
  if (!meta) return;
  fillAssetSelect("mt-asset", meta.items || [], t("common.select"));
  fillAssetSelect("filter-asset", meta.items || [], t("assets.allAssets"));
}

async function loadAssetsForFilter() {
  try {
    const items = await api.get("/assets/api/items");
    fillAssetSelect("filter-asset", items, t("assets.allAssets"));
    fillAssetSelect("mt-asset", items, t("common.select"));
  } catch (e) { toastError(e); }
}

function openMaintenanceModal(r) {
  editingMaintenanceId = r ? r.id : null;
  document.getElementById("maintenance-modal-title").textContent = r ? t("common.edit") : t("assets.newMaintenance");
  document.getElementById("mt-asset").value = r ? r.asset_id || "" : "";
  document.getElementById("mt-date").value = r ? r.maintenance_date || "" : new Date().toISOString().slice(0, 10);
  document.getElementById("mt-type").value = r ? r.maintenance_type || "preventive" : "preventive";
  document.getElementById("mt-cost").value = r ? r.cost || 0 : 0;
  document.getElementById("mt-vendor").value = r ? r.vendor || "" : "";
  document.getElementById("mt-technician").value = r ? r.technician || "" : "";
  document.getElementById("mt-status").value = r ? r.status || "completed" : "completed";
  document.getElementById("mt-next").value = r ? r.next_maintenance_date || "" : "";
  document.getElementById("mt-desc").value = r ? r.description || "" : "";
  document.getElementById("maintenance-modal").classList.add("active");
}

function editMaintenance(r) { openMaintenanceModal(r); }
function closeMaintenanceModal() { document.getElementById("maintenance-modal").classList.remove("active"); }

async function saveMaintenance() {
  const assetId = document.getElementById("mt-asset").value;
  const date = document.getElementById("mt-date").value;
  if (!assetId || !date) { showToast(t("common.required"), "warning"); return; }
  const body = {
    asset_id: parseInt(assetId),
    maintenance_date: date,
    maintenance_type: document.getElementById("mt-type").value,
    cost: parseFloat(document.getElementById("mt-cost").value) || 0,
    vendor: document.getElementById("mt-vendor").value.trim(),
    technician: document.getElementById("mt-technician").value.trim(),
    status: document.getElementById("mt-status").value,
    next_maintenance_date: document.getElementById("mt-next").value,
    description: document.getElementById("mt-desc").value.trim(),
  };
  try {
    if (editingMaintenanceId) await api.put(`/assets/api/maintenance/${editingMaintenanceId}`, body);
    else await api.post("/assets/api/maintenance", body);
    showToast(t("common.savedSuccess"));
    closeMaintenanceModal();
    loadMaintenance();
  } catch (e) { toastError(e); }
}

async function deleteMaintenance(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/assets/api/maintenance/${id}`);
    showToast(t("common.deleted"));
    loadMaintenance();
  } catch (e) { toastError(e); }
}

window.openMaintenanceModal = openMaintenanceModal;
window.editMaintenance = editMaintenance;
window.closeMaintenanceModal = closeMaintenanceModal;
window.saveMaintenance = saveMaintenance;
window.deleteMaintenance = deleteMaintenance;
window.loadMaintenance = loadMaintenance;

document.addEventListener("DOMContentLoaded", () => {
  loadAssetsForFilter();
  loadMaintenance();
});

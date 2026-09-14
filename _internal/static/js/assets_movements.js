/* حركة الأصول والمعدات */

async function loadMovements() {
  try {
    const assetId = document.getElementById("filter-asset")?.value || "";
    const params = new URLSearchParams();
    if (assetId) params.set("asset_id", assetId);
    const records = await api.get(`/assets/api/movements?${params.toString()}`);
    const tbody = document.getElementById("movements-table");
    tbody.innerHTML = records.length ? records.map((r) => `
      <tr>
        <td><strong>${escapeHtml(r.asset_code)}</strong> - ${escapeHtml(r.asset_name)}</td>
        <td>${formatDate(r.movement_date)}</td>
        <td>${movementTypeLabel(r.movement_type)}</td>
        <td>${escapeHtml(r.from_location_name || "—")}</td>
        <td>${escapeHtml(r.to_location_name || "—")}</td>
        <td>${escapeHtml(r.from_employee_name || "—")}</td>
        <td>${escapeHtml(r.to_employee_name || "—")}</td>
        <td>${escapeHtml(r.reference || "—")}</td>
        <td>${escapeHtml(r.notes || "—")}</td>
        <td>
          <div class="table-actions">
            ${canAction("accounting", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteMovement(${r.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="10"><div class="empty-state">${t("assets.noMovements")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

async function loadAssetsForFilter() {
  try {
    const items = await api.get("/assets/api/items");
    fillAssetSelect("filter-asset", items, t("assets.allAssets"));
    fillAssetSelect("mv-asset", items, t("common.select"));
  } catch (e) { toastError(e); }
}

async function loadMeta() {
  const meta = await loadAssetsMeta();
  if (!meta) return;
  fillSelect("mv-from-location", meta.warehouses, t("common.select"));
  fillSelect("mv-to-location", meta.warehouses, t("common.select"));
  fillSelect("mv-from-employee", meta.employees, t("common.select"));
  fillSelect("mv-to-employee", meta.employees, t("common.select"));
}

function openMovementModal() {
  document.getElementById("mv-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("movement-modal").classList.add("active");
}

function closeMovementModal() { document.getElementById("movement-modal").classList.remove("active"); }

async function saveMovement() {
  const assetId = document.getElementById("mv-asset").value;
  const date = document.getElementById("mv-date").value;
  const type = document.getElementById("mv-type").value;
  if (!assetId || !date || !type) { showToast(t("common.required"), "warning"); return; }
  const body = {
    asset_id: parseInt(assetId),
    movement_date: date,
    movement_type: type,
    from_location_id: parseInt(document.getElementById("mv-from-location").value) || null,
    to_location_id: parseInt(document.getElementById("mv-to-location").value) || null,
    from_employee_id: parseInt(document.getElementById("mv-from-employee").value) || null,
    to_employee_id: parseInt(document.getElementById("mv-to-employee").value) || null,
    reference: document.getElementById("mv-reference").value.trim(),
    notes: document.getElementById("mv-notes").value.trim(),
  };
  try {
    await api.post("/assets/api/movements", body);
    showToast(t("common.savedSuccess"));
    closeMovementModal();
    loadMovements();
  } catch (e) { toastError(e); }
}

async function deleteMovement(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/assets/api/movements/${id}`);
    showToast(t("common.deleted"));
    loadMovements();
  } catch (e) { toastError(e); }
}

window.openMovementModal = openMovementModal;
window.closeMovementModal = closeMovementModal;
window.saveMovement = saveMovement;
window.deleteMovement = deleteMovement;
window.loadMovements = loadMovements;

document.addEventListener("DOMContentLoaded", () => {
  loadMeta();
  loadAssetsForFilter();
  loadMovements();
});

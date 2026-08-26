/* العهدة */
let editingCustodyId = null;

async function loadCustody() {
  try {
    const status = document.getElementById("filter-status")?.value || "";
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    const records = await api.get(`/assets/api/custody?${params.toString()}`);
    const tbody = document.getElementById("custody-table");
    tbody.innerHTML = records.length ? records.map((r) => `
      <tr>
        <td><strong>${escapeHtml(r.asset_code)}</strong> - ${escapeHtml(r.asset_name)}</td>
        <td>${escapeHtml(r.employee_name || "—")}</td>
        <td>${formatDate(r.custody_date)}</td>
        <td>${r.return_date ? formatDate(r.return_date) : "—"}</td>
        <td>${statusBadge(r.status)}</td>
        <td>${escapeHtml(r.notes || "—")}</td>
        <td>
          <div class="table-actions">
            ${r.status === "active" && canAction("accounting", "edit") ? `<button class="btn btn-warning btn-sm" onclick="returnCustody(${r.id})">${t("assets.returnCustody")}</button>` : ""}
            ${canAction("accounting", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteCustody(${r.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="7"><div class="empty-state">${t("assets.noCustody")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

async function loadMeta() {
  const meta = await loadAssetsMeta();
  if (!meta) return;
  fillSelect("cu-employee", meta.employees, t("common.select"));
}

async function loadAssetsForSelect() {
  try {
    const items = await api.get("/assets/api/items");
    fillAssetSelect("cu-asset", items, t("common.select"));
  } catch (e) { toastError(e); }
}

function openCustodyModal() {
  document.getElementById("cu-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("custody-modal").classList.add("active");
}

function closeCustodyModal() { document.getElementById("custody-modal").classList.remove("active"); }

async function saveCustody() {
  const assetId = document.getElementById("cu-asset").value;
  const employeeId = document.getElementById("cu-employee").value;
  const date = document.getElementById("cu-date").value;
  if (!assetId || !employeeId || !date) { showToast(t("common.required"), "warning"); return; }
  const body = {
    asset_id: parseInt(assetId),
    employee_id: parseInt(employeeId),
    custody_date: date,
    notes: document.getElementById("cu-notes").value.trim(),
  };
  try {
    await api.post("/assets/api/custody", body);
    showToast(t("common.savedSuccess"));
    closeCustodyModal();
    loadCustody();
  } catch (e) { toastError(e); }
}

async function returnCustody(id) {
  if (!confirm(t("assets.confirmReturn"))) return;
  try {
    await api.post(`/assets/api/custody/${id}/return`, {});
    showToast(t("common.savedSuccess"));
    loadCustody();
  } catch (e) { toastError(e); }
}

async function deleteCustody(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/assets/api/custody/${id}`);
    showToast(t("common.deleted"));
    loadCustody();
  } catch (e) { toastError(e); }
}

window.openCustodyModal = openCustodyModal;
window.closeCustodyModal = closeCustodyModal;
window.saveCustody = saveCustody;
window.returnCustody = returnCustody;
window.deleteCustody = deleteCustody;
window.loadCustody = loadCustody;

document.addEventListener("DOMContentLoaded", () => {
  loadMeta();
  loadAssetsForSelect();
  loadCustody();
});

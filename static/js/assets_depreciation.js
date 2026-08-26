/* الإهلاك */
let activeDepItemId = null;

async function loadItems() {
  try {
    const assetId = document.getElementById("filter-asset")?.value || "";
    const params = new URLSearchParams();
    if (assetId) params.set("asset_id", assetId);
    const items = await api.get(`/assets/api/items?${params.toString()}`);
    const tbody = document.getElementById("items-table");
    tbody.innerHTML = items.length ? items.map((a) => `
      <tr>
        <td><strong>${escapeHtml(a.code)}</strong></td>
        <td>${escapeHtml(a.name)}</td>
        <td>${fmtMoney(a.cost)}</td>
        <td class="text-danger">${fmtMoney(a.accumulated_depreciation)}</td>
        <td><strong>${fmtMoney(a.net_book_value)}</strong></td>
        <td>${fmtMoney(a.monthly_depreciation)}</td>
        <td>${statusBadge(a.status)}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-outline btn-sm" onclick='viewDepRecords(${JSON.stringify(a)})'>${t("assets.depreciationHistory")}</button>
            ${canAction("accounting", "create") && a.status === "active" && a.net_book_value > 0 ? `<button class="btn btn-success btn-sm" onclick="runDepreciation(${a.id})">${t("accounting.depreciate")}</button>` : ""}
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="8"><div class="empty-state">${t("assets.noItems")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

async function loadAssetsForFilter() {
  try {
    const items = await api.get("/assets/api/items");
    fillAssetSelect("filter-asset", items, t("assets.allAssets"));
  } catch (e) { toastError(e); }
}

async function runDepreciation(id) {
  const period = new Date().toISOString().slice(0, 7);
  if (!confirm(t("accounting.confirmDepreciate").replace("{period}", period))) return;
  try {
    await api.post(`/assets/api/items/${id}/depreciate`, { period });
    showToast(t("common.savedSuccess"));
    loadItems();
  } catch (e) { toastError(e); }
}

async function viewDepRecords(a) {
  activeDepItemId = a.id;
  document.getElementById("dep-modal-title").textContent = `${t("assets.depreciationHistory")} - ${a.name}`;
  try {
    const records = await api.get(`/accounting/api/assets/${a.id}/records`);
    const tbody = document.getElementById("dep-table");
    tbody.innerHTML = records.length ? records.map((r) => `
      <tr>
        <td>${escapeHtml(r.period)}</td>
        <td>${formatDate(r.date)}</td>
        <td>${fmtMoney(r.amount)}</td>
      </tr>`).join("") : `<tr><td colspan="3"><div class="empty-state">${t("assets.noDepreciation")}</div></td></tr>`;
    document.getElementById("dep-modal").classList.add("active");
  } catch (e) { toastError(e); }
}

function closeDepModal() { document.getElementById("dep-modal").classList.remove("active"); }

window.runDepreciation = runDepreciation;
window.viewDepRecords = viewDepRecords;
window.closeDepModal = closeDepModal;
window.loadItems = loadItems;

document.addEventListener("DOMContentLoaded", () => {
  loadAssetsForFilter();
  loadItems();
});

/* Fixed assets + depreciation */
let assetsMeta = null;
let editingAssetId = null;
let activeAssetId = null;

async function loadAssets() {
  try {
    const assets = await api.get("/accounting/api/assets");
    const tbody = document.getElementById("assets-table");
    tbody.innerHTML = assets.length ? assets.map((a) => `
      <tr>
        <td><strong>${escapeHtml(a.asset_code)}</strong></td>
        <td>${escapeHtml(a.name)}
          ${a.status === "disposed" ? `<div class="table-sub"><span class="badge badge-danger">${t("accounting.disposed")}</span></div>` : ""}
        </td>
        <td>${escapeHtml(a.category || "—")}</td>
        <td>${fmtMoney(a.cost)}</td>
        <td class="text-danger">${fmtMoney(a.accumulated_depreciation)}</td>
        <td><strong>${fmtMoney(a.net_book_value)}</strong></td>
        <td>${fmtMoney(a.monthly_depreciation)}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-outline btn-sm" onclick='viewRecords(${JSON.stringify(a)})'>${t("accounting.deprHistory")}</button>
            ${canAction("accounting", "create") && a.status === "active" && a.net_book_value > 0 ? `<button class="btn btn-success btn-sm" onclick="runDepreciation(${a.id})">${t("accounting.depreciate")}</button>` : ""}
            ${canAction("accounting", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editAsset(${JSON.stringify(a)})'>${t("common.edit")}</button>` : ""}
            ${canAction("accounting", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteAsset(${a.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="8"><div class="empty-state">${t("accounting.noAssets")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

async function loadAssetsMeta() {
  try {
    assetsMeta = await api.get("/accounting/api/meta");
    const cashSel = document.getElementById("as-cashaccount");
    cashSel.innerHTML = `<option value="">${t("common.select")}</option>` +
      [...assetsMeta.cash_accounts, ...assetsMeta.bank_accounts]
        .map((a) => `<option value="${a.id}">${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
  } catch (e) { toastError(e); }
}

function openAssetModal(a) {
  editingAssetId = a ? a.id : null;
  document.getElementById("asset-modal-title").textContent = a ? t("common.edit") : t("accounting.newAsset");
  document.getElementById("as-code").value = a ? a.asset_code : "";
  document.getElementById("as-name").value = a ? a.name : "";
  document.getElementById("as-category").value = a ? a.category || "" : "";
  document.getElementById("as-date").value = a ? a.purchase_date || "" : "";
  document.getElementById("as-cost").value = a ? a.cost || "" : "";
  document.getElementById("as-life").value = a ? a.useful_life_years || 5 : 5;
  document.getElementById("as-salvage").value = a ? a.salvage_value || 0 : 0;
  document.getElementById("as-method").value = a ? a.method || "straight" : "straight";
  document.getElementById("as-desc").value = a ? a.description || "" : "";
  document.getElementById("asset-modal").classList.add("active");
}

function editAsset(a) { openAssetModal(a); }
function closeAssetModal() { document.getElementById("asset-modal").classList.remove("active"); }

async function saveAsset() {
  const code = document.getElementById("as-code").value.trim();
  const name = document.getElementById("as-name").value.trim();
  const cost = parseFloat(document.getElementById("as-cost").value) || 0;
  if (!code || !name) { showToast(t("common.required"), "warning"); return; }
  const body = {
    asset_code: code,
    name,
    category: document.getElementById("as-category").value.trim(),
    purchase_date: document.getElementById("as-date").value,
    cost,
    useful_life_years: parseInt(document.getElementById("as-life").value) || 5,
    salvage_value: parseFloat(document.getElementById("as-salvage").value) || 0,
    method: document.getElementById("as-method").value,
    funding: document.getElementById("as-funding").value,
    cash_account_id: parseInt(document.getElementById("as-cashaccount").value) || null,
    description: document.getElementById("as-desc").value.trim(),
  };
  try {
    if (editingAssetId) await api.put(`/accounting/api/assets/${editingAssetId}`, body);
    else await api.post("/accounting/api/assets", body);
    showToast(t("common.savedSuccess"));
    closeAssetModal();
    loadAssets();
  } catch (e) { toastError(e); }
}

async function deleteAsset(id) {
  if (!confirm(t("accounting.confirmDelete"))) return;
  try {
    await api.delete(`/accounting/api/assets/${id}`);
    showToast(t("common.deleted"));
    loadAssets();
  } catch (e) { toastError(e); }
}

async function runDepreciation(id) {
  const period = new Date().toISOString().slice(0, 7);
  if (!confirm(t("accounting.confirmDepreciate").replace("{period}", period))) return;
  try {
    await api.post(`/accounting/api/assets/${id}/depreciate`, { period });
    showToast(t("common.savedSuccess"));
    loadAssets();
  } catch (e) { toastError(e); }
}

async function viewRecords(a) {
  activeAssetId = a.id;
  document.getElementById("rec-modal-title").textContent = `${t("accounting.depreciationHistory")} - ${a.name}`;
  try {
    const records = await api.get(`/accounting/api/assets/${a.id}/records`);
    const tbody = document.getElementById("rec-table");
    tbody.innerHTML = records.length ? records.map((r) => `
      <tr>
        <td>${escapeHtml(r.period)}</td>
        <td>${formatDate(r.date)}</td>
        <td>${fmtMoney(r.amount)}</td>
      </tr>`).join("") : `<tr><td colspan="3"><div class="empty-state">${t("accounting.noDepreciation")}</div></td></tr>`;
    document.getElementById("rec-modal").classList.add("active");
  } catch (e) { toastError(e); }
}

function closeRecModal() { document.getElementById("rec-modal").classList.remove("active"); }

window.openAssetModal = openAssetModal;
window.editAsset = editAsset;
window.closeAssetModal = closeAssetModal;
window.saveAsset = saveAsset;
window.deleteAsset = deleteAsset;
window.runDepreciation = runDepreciation;
window.viewRecords = viewRecords;
window.closeRecModal = closeRecModal;
window.loadAssets = loadAssets;

document.addEventListener("DOMContentLoaded", () => {
  loadAssetsMeta();
  loadAssets();
});

/* إدارة الأصول والمعدات - ملف مشترك */
let assetsMeta = null;

function toastError(err) {
  showToast((err && err.message) || t("common.error"), "error");
}

async function loadAssetsMeta() {
  try {
    assetsMeta = await api.get("/assets/api/meta");
    return assetsMeta;
  } catch (e) { toastError(e); return null; }
}

function fillSelect(selId, items, placeholder, valueKey = "id", labelKey = "name") {
  const sel = document.getElementById(selId);
  if (!sel) return;
  sel.innerHTML = `<option value="">${placeholder}</option>` +
    (items || []).map((i) => `<option value="${i[valueKey]}">${escapeHtml(i[labelKey])}</option>`).join("");
}

function fillAssetSelect(selId, items, placeholder) {
  const sel = document.getElementById(selId);
  if (!sel) return;
  sel.innerHTML = `<option value="">${placeholder}</option>` +
    (items || []).map((i) => `<option value="${i.id}">${escapeHtml(i.code)} - ${escapeHtml(i.name)}</option>`).join("");
}

function statusBadge(status) {
  const map = {
    "active": "badge-success",
    "in_maintenance": "badge-warning",
    "disposed": "badge-danger",
    "retired": "badge-secondary",
    "scheduled": "badge-info",
    "in_progress": "badge-warning",
    "completed": "badge-success",
    "cancelled": "badge-danger",
    "returned": "badge-secondary",
  };
  const cls = map[status] || "badge-secondary";
  return `<span class="badge ${cls}">${t("assets.status_" + status) || status}</span>`;
}

function movementTypeLabel(type) {
  const map = {
    "received": t("assets.mvReceived"),
    "transferred": t("assets.mvTransferred"),
    "returned": t("assets.mvReturned"),
    "disposed": t("assets.mvDisposed"),
  };
  return map[type] || type;
}

function maintenanceTypeLabel(type) {
  const map = {
    "preventive": t("assets.typePreventive"),
    "corrective": t("assets.typeCorrective"),
    "emergency": t("assets.typeEmergency"),
  };
  return map[type] || type;
}

function conditionLabel(cond) {
  const map = {
    "new": t("assets.condNew"),
    "good": t("assets.condGood"),
    "fair": t("assets.condFair"),
    "poor": t("assets.condPoor"),
  };
  return map[cond] || cond;
}

window.assetsMeta = assetsMeta;
window.loadAssetsMeta = loadAssetsMeta;
window.fillSelect = fillSelect;
window.fillAssetSelect = fillAssetSelect;
window.statusBadge = statusBadge;
window.movementTypeLabel = movementTypeLabel;
window.maintenanceTypeLabel = maintenanceTypeLabel;
window.conditionLabel = conditionLabel;

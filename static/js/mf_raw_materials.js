/* ============================================================
   Manufacturing - Raw Materials
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

let rawMaterials = [];
let optionsData = { items: [], suppliers: [] };

async function loadData() {
  try {
    const [opts, list] = await Promise.all([
      api.get("/api/mf/options"),
      api.get("/api/mf/raw-materials"),
    ]);
    optionsData = opts || {};
    rawMaterials = list || [];
    renderKPI();
    renderRawMaterials();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderKPI() {
  const low = rawMaterials.filter((r) => r.is_low).length;
  const active = rawMaterials.filter((r) => r.is_active).length;
  document.getElementById("kpi-materials").textContent = rawMaterials.length;
  document.getElementById("kpi-low").textContent = low;
  document.getElementById("kpi-active").textContent = active;
}

function renderRawMaterials() {
  document.getElementById("raw-materials-empty").style.display = rawMaterials.length ? "none" : "block";
  const canEdit = canAction("manufacturing", "edit");
  const canDelete = canAction("manufacturing", "delete");
  document.getElementById("raw-materials-table").innerHTML = rawMaterials.map((r) => {
    const low = r.is_low
      ? `<span class="badge badge-danger">${cct("mf.lowStock")}</span>`
      : r.is_active
        ? `<span class="badge badge-success">${cct("mf.active")}</span>`
        : `<span class="badge badge-neutral">${cct("mf.inactive")}</span>`;
    return `<tr>
      <td><div class="cell-main">${escapeHtml(r.item_name || "—")}</div><div class="table-sub">${escapeHtml(r.item_code || "")}${r.unit_name ? " • " + escapeHtml(r.unit_name) : ""}</div></td>
      <td><strong>${formatNumber(r.quantity)}</strong></td>
      <td>${formatNumber(r.standard_cost)}</td>
      <td>${formatNumber(r.reorder_level)}</td>
      <td>${formatNumber(r.min_stock)}</td>
      <td>${escapeHtml(r.supplier_name || "—")}</td>
      <td>${low}</td>
      <td><div class="table-actions">
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editRawMaterial(${JSON.stringify(r)})'>${cct("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteRawMaterial(${r.id})">${cct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

function fillSelects(selectedItem, selectedSupplier) {
  const itemOpts = optionsData.items.map((i) =>
    `<option value="${i.id}" ${String(i.id) === String(selectedItem) ? "selected" : ""}>${escapeHtml(i.code + " - " + i.name)}</option>`).join("");
  document.getElementById("raw-material-item").innerHTML =
    `<option value="">${cct("mf.selectItem")}</option>` + itemOpts;
  const supOpts = optionsData.suppliers.map((s) =>
    `<option value="${s.id}" ${String(s.id) === String(selectedSupplier) ? "selected" : ""}>${escapeHtml(s.company_name)}</option>`).join("");
  document.getElementById("raw-material-supplier").innerHTML =
    `<option value="">${cct("mf.selectSupplier")}</option>` + supOpts;
}

/* ===== Modal ===== */
function openRawMaterialModal() {
  document.getElementById("raw-material-modal-title").textContent = cct("mf.addRawMaterial");
  document.getElementById("raw-material-id").value = "";
  fillSelects("", "");
  document.getElementById("raw-material-standard-cost").value = "0";
  document.getElementById("raw-material-reorder-level").value = "0";
  document.getElementById("raw-material-min-stock").value = "0";
  document.getElementById("raw-material-active").checked = true;
  document.getElementById("raw-material-notes").value = "";
  document.getElementById("raw-material-modal").style.display = "flex";
}
window.openRawMaterialModal = openRawMaterialModal;

function editRawMaterial(r) {
  document.getElementById("raw-material-modal-title").textContent = cct("mf.editRawMaterial");
  document.getElementById("raw-material-id").value = r.id;
  fillSelects(r.item_id, r.supplier_id);
  document.getElementById("raw-material-standard-cost").value = r.standard_cost || 0;
  document.getElementById("raw-material-reorder-level").value = r.reorder_level || 0;
  document.getElementById("raw-material-min-stock").value = r.min_stock || 0;
  document.getElementById("raw-material-active").checked = !!r.is_active;
  document.getElementById("raw-material-notes").value = r.notes || "";
  document.getElementById("raw-material-modal").style.display = "flex";
}
window.editRawMaterial = editRawMaterial;

function closeRawMaterialModal() {
  document.getElementById("raw-material-modal").style.display = "none";
}
window.closeRawMaterialModal = closeRawMaterialModal;

async function saveRawMaterial() {
  const id = document.getElementById("raw-material-id").value;
  const payload = {
    item_id: document.getElementById("raw-material-item").value,
    supplier_id: document.getElementById("raw-material-supplier").value,
    standard_cost: document.getElementById("raw-material-standard-cost").value,
    reorder_level: document.getElementById("raw-material-reorder-level").value,
    min_stock: document.getElementById("raw-material-min-stock").value,
    is_active: document.getElementById("raw-material-active").checked,
    notes: document.getElementById("raw-material-notes").value,
  };
  if (!payload.item_id) { showToast(cct("mf.itemRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/mf/raw-materials/${id}`, payload);
    else await api.post("/api/mf/raw-materials", payload);
    showToast(cct("mf.saved"));
    closeRawMaterialModal();
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveRawMaterial = saveRawMaterial;

async function deleteRawMaterial(id) {
  const r = rawMaterials.find((x) => x.id === id);
  if (!confirm(cct("mf.confirmDelete") + " " + (r ? r.item_name : ""))) return;
  try {
    await api.delete(`/api/mf/raw-materials/${id}`);
    showToast(cct("mf.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteRawMaterial = deleteRawMaterial;

document.addEventListener("DOMContentLoaded", loadData);

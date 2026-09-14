/* ============================================================
   Manufacturing - Bill of Materials (BOM)
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

let boms = [];
let optionsData = { items: [] };
let bomLines = [];

async function loadData() {
  try {
    const [opts, list] = await Promise.all([
      api.get("/api/mf/options"),
      api.get("/api/mf/boms"),
    ]);
    optionsData = opts || {};
    boms = list || [];
    renderBoms();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderBoms() {
  document.getElementById("boms-empty").style.display = boms.length ? "none" : "block";
  const canEdit = canAction("manufacturing", "edit");
  const canDelete = canAction("manufacturing", "delete");
  document.getElementById("boms-table").innerHTML = boms.map((b) => {
    const status = b.is_active
      ? `<span class="badge badge-success">${cct("mf.active")}</span>`
      : `<span class="badge badge-neutral">${cct("mf.inactive")}</span>`;
    const lineCount = (b.lines || []).length;
    return `<tr>
      <td><div class="cell-main">${escapeHtml(b.code)}</div></td>
      <td><div class="cell-main">${escapeHtml(b.name)}</div>${b.notes ? `<div class="table-sub">${escapeHtml(b.notes)}</div>` : ""}</td>
      <td><div class="cell-main">${escapeHtml(b.product_name || "—")}</div><div class="table-sub">${escapeHtml(b.product_code || "")}</div></td>
      <td>${escapeHtml(b.version || "1.0")}</td>
      <td><span class="badge badge-primary">${lineCount}</span></td>
      <td><strong>${formatNumber(b.total_cost)}</strong></td>
      <td>${status}</td>
      <td><div class="table-actions">
        ${canEdit ? `<button class="btn btn-secondary btn-sm" onclick='editBom(${JSON.stringify(b)})'>${cct("common.edit")}</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" onclick="deleteBom(${b.id})">${cct("common.delete")}</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");
}

/* ===== Lines ===== */
function bomLineRow(line) {
  line = line || {};
  const itemOpts = optionsData.items.map((i) =>
    `<option value="${i.id}" ${String(i.id) === String(line.item_id) ? "selected" : ""}>${escapeHtml(i.code + " - " + i.name)}</option>`).join("");
  const row = document.createElement("tr");
  row.innerHTML = `
    <td><select class="bom-line-item">${cct("mf.selectItem") ? `<option value="">${cct("mf.selectItem")}</option>` : ""}${itemOpts}</select></td>
    <td><input type="number" class="bom-line-qty" step="any" min="0" value="${line.quantity != null ? line.quantity : 1}"></td>
    <td><input type="number" class="bom-line-cost" step="any" min="0" value="${line.cost_estimate != null ? line.cost_estimate : 0}"></td>
    <td><button class="btn btn-danger btn-sm" type="button" onclick="this.closest('tr').remove()">✕</button></td>`;
  return row;
}

function addBomLine(line) {
  const body = document.getElementById("bom-lines-body");
  body.appendChild(bomLineRow(line));
}
window.addBomLine = addBomLine;

function collectBomLines() {
  const rows = document.querySelectorAll("#bom-lines-body tr");
  const out = [];
  rows.forEach((tr) => {
    const itemId = tr.querySelector(".bom-line-item").value;
    const qty = parseFloat(tr.querySelector(".bom-line-qty").value) || 0;
    const cost = parseFloat(tr.querySelector(".bom-line-cost").value) || 0;
    if (itemId && qty > 0) {
      out.push({ item_id: itemId, quantity: qty, cost_estimate: cost });
    }
  });
  return out;
}

function fillProductSelect(selected) {
  const opts = optionsData.items.map((i) =>
    `<option value="${i.id}" ${String(i.id) === String(selected) ? "selected" : ""}>${escapeHtml(i.code + " - " + i.name)}</option>`).join("");
  document.getElementById("bom-product-item").innerHTML =
    `<option value="">${cct("mf.selectItem")}</option>` + opts;
}

/* ===== Modal ===== */
function openBomModal() {
  document.getElementById("bom-modal-title").textContent = cct("mf.addBom");
  document.getElementById("bom-id").value = "";
  document.getElementById("bom-code").value = "";
  document.getElementById("bom-name").value = "";
  fillProductSelect("");
  document.getElementById("bom-version").value = "1.0";
  document.getElementById("bom-active").checked = true;
  document.getElementById("bom-notes").value = "";
  document.getElementById("bom-lines-body").innerHTML = "";
  addBomLine();
  document.getElementById("bom-modal").style.display = "flex";
}
window.openBomModal = openBomModal;

function editBom(b) {
  document.getElementById("bom-modal-title").textContent = cct("mf.editBom");
  document.getElementById("bom-id").value = b.id;
  document.getElementById("bom-code").value = b.code || "";
  document.getElementById("bom-name").value = b.name || "";
  fillProductSelect(b.product_item_id);
  document.getElementById("bom-version").value = b.version || "1.0";
  document.getElementById("bom-active").checked = !!b.is_active;
  document.getElementById("bom-notes").value = b.notes || "";
  document.getElementById("bom-lines-body").innerHTML = "";
  (b.lines || []).forEach((ln) => addBomLine(ln));
  if (!(b.lines || []).length) addBomLine();
  document.getElementById("bom-modal").style.display = "flex";
}
window.editBom = editBom;

function closeBomModal() {
  document.getElementById("bom-modal").style.display = "none";
}
window.closeBomModal = closeBomModal;

async function saveBom() {
  const id = document.getElementById("bom-id").value;
  const payload = {
    code: document.getElementById("bom-code").value.trim(),
    name: document.getElementById("bom-name").value.trim(),
    product_item_id: document.getElementById("bom-product-item").value,
    version: document.getElementById("bom-version").value.trim(),
    is_active: document.getElementById("bom-active").checked,
    notes: document.getElementById("bom-notes").value,
    lines: collectBomLines(),
  };
  if (!payload.name) { showToast(cct("mf.nameRequired"), "warning"); return; }
  if (!payload.product_item_id) { showToast(cct("mf.itemRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/mf/boms/${id}`, payload);
    else await api.post("/api/mf/boms", payload);
    showToast(cct("mf.saved"));
    closeBomModal();
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.saveBom = saveBom;

async function deleteBom(id) {
  const b = boms.find((x) => x.id === id);
  if (!confirm(cct("mf.confirmDelete") + " " + (b ? b.name : ""))) return;
  try {
    await api.delete(`/api/mf/boms/${id}`);
    showToast(cct("mf.deleted"));
    loadData();
  } catch (err) {
    showToast(err.message, "error");
  }
}
window.deleteBom = deleteBom;

document.addEventListener("DOMContentLoaded", loadData);

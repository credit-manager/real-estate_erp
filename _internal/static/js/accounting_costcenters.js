/* Cost centers */
let costCenters = [];
let editingCC = null;

async function loadCC() {
  try {
    costCenters = await api.get("/accounting/api/cost-centers");
    const tbody = document.getElementById("cc-table");
    tbody.innerHTML = costCenters.length ? costCenters.map((c) => `
      <tr>
        <td><strong>${escapeHtml(c.code)}</strong></td>
        <td>${escapeHtml(c.name)}</td>
        <td>${c.is_active ? `<span class="badge badge-success">${t("accounting.active")}</span>` : `<span class="badge badge-danger">${t("accounting.inactive")}</span>`}</td>
        <td>
          <div class="table-actions">
            ${canAction("accounting", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editCC(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
            ${canAction("accounting", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteCC(${c.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="4"><div class="empty-state">${t("accounting.noCostCenters")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

function openCCModal(cc) {
  editingCC = cc ? cc.id : null;
  document.getElementById("cc-modal-title").textContent = cc ? t("common.edit") : t("accounting.newCostCenter");
  document.getElementById("cc-code").value = cc ? cc.code : "";
  document.getElementById("cc-name").value = cc ? cc.name : "";
  document.getElementById("cc-active").checked = cc ? cc.is_active !== false : true;
  document.getElementById("cc-modal").classList.add("active");
}

function editCC(cc) { openCCModal(cc); }
function closeCCModal() { document.getElementById("cc-modal").classList.remove("active"); }

async function saveCC() {
  const code = document.getElementById("cc-code").value.trim();
  const name = document.getElementById("cc-name").value.trim();
  if (!code || !name) { showToast(t("common.required"), "warning"); return; }
  const body = { code, name, is_active: document.getElementById("cc-active").checked };
  try {
    if (editingCC) await api.put(`/accounting/api/cost-centers/${editingCC}`, body);
    else await api.post("/accounting/api/cost-centers", body);
    showToast(t("common.savedSuccess"));
    closeCCModal();
    loadCC();
  } catch (e) { toastError(e); }
}

async function deleteCC(id) {
  if (!confirm(t("accounting.confirmDelete"))) return;
  try {
    await api.delete(`/accounting/api/cost-centers/${id}`);
    showToast(t("common.deleted"));
    loadCC();
  } catch (e) { toastError(e); }
}

window.openCCModal = openCCModal;
window.editCC = editCC;
window.closeCCModal = closeCCModal;
window.saveCC = saveCC;
window.deleteCC = deleteCC;

document.addEventListener("DOMContentLoaded", loadCC);

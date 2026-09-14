/* ============================================================
   Workflow Templates Module JavaScript
   ============================================================ */

let templatesData = [];
let templateRoles = [];
let editingTemplateId = null;

const WF_DOC_LABELS = {
  invoice: "workflow.docInvoice",
  po: "workflow.docPo",
  rental_contract: "workflow.docRental",
};

document.addEventListener("DOMContentLoaded", () => {
  loadMetaAndTemplates();
});

async function loadMetaAndTemplates() {
  try {
    const meta = await api.get("/workflow/api/meta");
    templateRoles = meta.roles || [];
    templatesData = await api.get("/workflow/api/templates");
    renderTemplates();
  } catch (err) { showToast(err.message, "error"); }
}

function renderTemplates() {
  const tbody = document.getElementById("templates-table");
  if (!templatesData.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><div class="empty-icon">📋</div>${t("workflow.noTemplates")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = templatesData.map((tp) => {
    const roles = (tp.steps || []).map((s) => `<span class="badge badge-neutral">${escapeHtml(s.role)}</span>`).join(" ");
    return `
      <tr>
        <td><strong>${escapeHtml(tp.name)}</strong></td>
        <td>${WF_DOC_LABELS[tp.doc_type] ? t(WF_DOC_LABELS[tp.doc_type]) : tp.doc_type}</td>
        <td>${roles || "—"}</td>
        <td>${tp.is_active
          ? `<span class="badge badge-success">${t("workflow.templateActive")}</span>`
          : `<span class="badge badge-neutral">${t("workflow.inactive")}</span>`}</td>
        <td><div class="table-actions">
          <button class="btn btn-secondary btn-sm" onclick='editTemplate(${JSON.stringify(tp)})'>${t("common.edit")}</button>
          <button class="btn btn-danger btn-sm" onclick="deleteTemplate(${tp.id})">${t("workflow.deleteTemplate")}</button>
        </div></td>
      </tr>`;
  }).join("");
}

function openTemplateModal() {
  editingTemplateId = null;
  document.getElementById("template-modal-title").textContent = t("workflow.newTemplate");
  document.getElementById("tpl-name").value = "";
  document.getElementById("tpl-doctype").value = "invoice";
  document.getElementById("tpl-active").checked = true;
  document.getElementById("tpl-steps").innerHTML = "";
  addStepRow();
  document.getElementById("template-modal").style.display = "flex";
}

function closeTemplateModal() {
  document.getElementById("template-modal").style.display = "none";
  editingTemplateId = null;
}

function addStepRow() {
  const container = document.getElementById("tpl-steps");
  const div = document.createElement("div");
  div.className = "step-row";
  div.style.cssText = "display:flex;gap:8px;margin-bottom:8px;";
  div.innerHTML = `<select class="step-role" style="flex:1;">${stepOptions("")}</select>
    <button type="button" class="btn btn-ghost btn-sm" onclick="this.closest('.step-row').remove()">✕</button>`;
  container.appendChild(div);
}

function stepOptions(role) {
  return templateRoles.map((r) =>
    `<option value="${escapeHtml(r)}" ${r === role ? "selected" : ""}>${escapeHtml(r)}</option>`).join("");
}

function editTemplate(tp) {
  editingTemplateId = tp.id;
  document.getElementById("template-modal-title").textContent = t("workflow.editTemplate");
  document.getElementById("tpl-name").value = tp.name;
  document.getElementById("tpl-doctype").value = tp.doc_type;
  document.getElementById("tpl-active").checked = !!tp.is_active;
  const container = document.getElementById("tpl-steps");
  container.innerHTML = "";
  (tp.steps || []).forEach((s) => {
    const div = document.createElement("div");
    div.className = "step-row";
    div.style.cssText = "display:flex;gap:8px;margin-bottom:8px;";
    div.innerHTML = `<select class="step-role" style="flex:1;">${stepOptions(s.role)}</select>
      <button type="button" class="btn btn-ghost btn-sm" onclick="this.closest('.step-row').remove()">✕</button>`;
    container.appendChild(div);
  });
  if (!container.children.length) addStepRow();
  document.getElementById("template-modal").style.display = "flex";
}

async function saveTemplate() {
  const name = document.getElementById("tpl-name").value.trim();
  const docType = document.getElementById("tpl-doctype").value;
  const isActive = document.getElementById("tpl-active").checked;
  const steps = Array.from(document.querySelectorAll("#tpl-steps .step-role"))
    .map((sel) => ({ role: sel.value }))
    .filter((s) => s.role);
  if (!name) { showToast(t("workflow.nameRequired"), "error"); return; }
  if (!steps.length) { showToast(t("workflow.stepsRequired"), "error"); return; }
  const payload = { name, doc_type: docType, is_active: isActive, steps };
  try {
    if (editingTemplateId) {
      await api.put(`/workflow/api/templates/${editingTemplateId}`, payload);
    } else {
      await api.post("/workflow/api/templates", payload);
    }
    showToast(t("workflow.toastSaved"));
    closeTemplateModal();
    templatesData = await api.get("/workflow/api/templates");
    renderTemplates();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteTemplate(id) {
  const tp = templatesData.find((x) => x.id === id);
  if (!tp) return;
  if (!confirm(t("workflow.deleteTemplate") + " " + tp.name + "؟")) return;
  try {
    await api.delete(`/workflow/api/templates/${id}`);
    showToast(t("workflow.toastDeleted"));
    templatesData = templatesData.filter((x) => x.id !== id);
    renderTemplates();
  } catch (err) { showToast(err.message, "error"); }
}

window.openTemplateModal = openTemplateModal;
window.closeTemplateModal = closeTemplateModal;
window.addStepRow = addStepRow;
window.saveTemplate = saveTemplate;
window.deleteTemplate = deleteTemplate;
window.editTemplate = editTemplate;

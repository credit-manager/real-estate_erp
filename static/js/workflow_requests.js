/* ============================================================
   Workflow Requests Log Module JavaScript
   ============================================================ */

let requestsData = [];
const CAN_EDIT = canAction("workflow", "edit");

const WF_DOC_LABELS = {
  invoice: "workflow.docInvoice",
  po: "workflow.docPo",
  rental_contract: "workflow.docRental",
};

const WF_STATUS_LABELS = {
  pending: "workflow.statusPending",
  approved: "workflow.statusApproved",
  rejected: "workflow.statusRejected",
  cancelled: "workflow.cancelled",
};

const WF_STATUS_CLS = {
  pending: "badge-warning",
  approved: "badge-success",
  rejected: "badge-danger",
  cancelled: "badge-neutral",
};

document.addEventListener("DOMContentLoaded", () => {
  ["wf-filter-status", "wf-filter-doctype"].forEach((id) => {
    document.getElementById(id).addEventListener("change", loadRequests);
  });
  loadRequests();
});

function docTypeLabel(dt) {
  const key = WF_DOC_LABELS[dt];
  return key ? t(key) : dt;
}

function statusBadge(status) {
  const key = WF_STATUS_LABELS[status];
  return `<span class="badge ${WF_STATUS_CLS[status] || "badge-neutral"}">${key ? t(key) : status}</span>`;
}

function stepBadge(step) {
  const cls = step.status === "approved" ? "badge-success"
    : step.status === "rejected" ? "badge-danger"
    : "badge-warning";
  const key = WF_STATUS_LABELS[step.status];
  const who = step.approver_name ? ` — ${escapeHtml(step.approver_name)}` : "";
  return `<span class="badge ${cls}">${key ? t(key) : step.status}${who}</span>`;
}

async function loadRequests() {
  const tbody = document.getElementById("requests-table");
  const status = document.getElementById("wf-filter-status").value;
  const docType = document.getElementById("wf-filter-doctype").value;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (docType) params.set("doc_type", docType);
  try {
    requestsData = await api.get(`/workflow/api/requests?${params.toString()}`);
    if (!requestsData.length) {
      tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">📋</div>${t("workflow.noResults")}</div></td></tr>`;
      return;
    }
    tbody.innerHTML = requestsData.map((r) => {
      const d = r.doc || {};
      const cur = d.currency ? ` ${escapeHtml(d.currency)}` : "";
      return `
        <tr>
          <td>${docTypeLabel(r.doc_type)}</td>
          <td><strong>${escapeHtml(d.number || r.doc_id)}</strong></td>
          <td style="color:var(--muted-foreground);">${escapeHtml(d.title || "—")}</td>
          <td>${formatNumber(d.amount || 0)}${cur}</td>
          <td>${statusBadge(r.status)}</td>
          <td>${r.status === "pending" ? `<span class="badge badge-warning">${escapeHtml(r.current_role || "—")}</span>` : "—"}</td>
          <td>${escapeHtml(r.submitted_by_name || "—")}</td>
          <td style="color:var(--muted-foreground); white-space:nowrap;">${r.submitted_at ? r.submitted_at.replace("T", " ").slice(0, 19) : "—"}</td>
          <td><div class="table-actions">
            <button class="btn btn-outline btn-sm" onclick="openDetailModal(${r.id})">${t("workflow.actions")}</button>
          </div></td>
        </tr>`;
    }).join("");
  } catch (err) { showToast(err.message, "error"); }
}

function openDetailModal(id) {
  const r = requestsData.find((x) => x.id === id);
  if (!r) return;
  const d = r.doc || {};
  const body = document.getElementById("request-detail-body");
  const rows = (r.steps || []).map((s) => `
    <tr>
      <td>${t("workflow.stepOf").replace("{current}", s.position).replace("{total}", r.steps.length)}</td>
      <td>${escapeHtml(s.role || "—")}</td>
      <td>${stepBadge(s)}</td>
      <td>${s.decided_at ? s.decided_at.replace("T", " ").slice(0, 19) : "—"}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(s.comment || "—")}</td>
    </tr>`).join("");
  body.innerHTML = `
    <div class="settings-row">
      <div>
        <div class="settings-row-title">${docTypeLabel(r.doc_type)} #${escapeHtml(d.number || r.doc_id)}</div>
        <div class="form-hint">${escapeHtml(d.title || "")}</div>
      </div>
      <div>${statusBadge(r.status)}</div>
    </div>
    <div class="settings-row">
      <div>
        <div class="settings-row-title">${t("workflow.amount")}</div>
        <div class="form-hint">${formatNumber(d.amount || 0)} ${d.currency ? escapeHtml(d.currency) : ""}</div>
      </div>
      <div>
        <div class="settings-row-title">${t("workflow.currentStep")}</div>
        <div class="form-hint">${r.status === "pending" ? escapeHtml(r.current_role || "—") : "—"}</div>
      </div>
    </div>
    <div class="settings-row">
      <div>
        <div class="settings-row-title">${t("workflow.submittedBy")}</div>
        <div class="form-hint">${escapeHtml(r.submitted_by_name || "—")}</div>
      </div>
      <div>
        <div class="settings-row-title">${t("workflow.submittedAt")}</div>
        <div class="form-hint">${r.submitted_at ? r.submitted_at.replace("T", " ").slice(0, 19) : "—"}</div>
      </div>
    </div>
    ${r.comment ? `<div class="settings-row">
      <div>
        <div class="settings-row-title">${t("workflow.comment")}</div>
        <div class="form-hint">${escapeHtml(r.comment)}</div>
      </div>
    </div>` : ""}
    <div class="table-wrapper">
      <table>
        <thead><tr>
          <th>${t("workflow.stepOf").replace("{current}", "1").replace("{total}", (r.steps || []).length)}</th>
          <th>${t("workflow.role")}</th>
          <th>${t("workflow.status")}</th>
          <th>${t("workflow.decidedAt")}</th>
          <th>${t("workflow.comment")}</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  document.getElementById("request-detail-modal").style.display = "flex";

  const actions = document.getElementById("request-detail-actions");
  if (r.status === "pending" && CAN_EDIT) {
    actions.style.display = "flex";
    actions.innerHTML = `
      <button class="btn btn-primary" onclick="approveFromDetail(${r.id})">${t("workflow.approve")}</button>
      <button class="btn btn-danger" onclick="rejectFromDetail(${r.id})">${t("workflow.reject")}</button>
      <button class="btn btn-outline" onclick="cancelFromDetail(${r.id})">${t("workflow.cancel")}</button>`;
  } else {
    actions.style.display = "none";
    actions.innerHTML = "";
  }
}

async function approveFromDetail(id) {
  const r = requestsData.find((x) => x.id === id);
  if (!r) return;
  if (!confirm(t("workflow.confirmApprove") + "؟")) return;
  try {
    await api.post(`/workflow/api/requests/${id}/approve`, { comment: "" });
    showToast(t("workflow.toastApproved"));
    closeDetailModal();
    loadRequests();
  } catch (err) { showToast(err.message, "error"); }
}

async function rejectFromDetail(id) {
  const r = requestsData.find((x) => x.id === id);
  if (!r) return;
  const comment = (window.prompt(t("workflow.rejectCommentPlaceholder")) || "").trim();
  if (!comment) {
    showToast(t("workflow.rejectCommentRequired"), "error");
    return;
  }
  try {
    await api.post(`/workflow/api/requests/${id}/reject`, { comment });
    showToast(t("workflow.toastRejected"));
    closeDetailModal();
    loadRequests();
  } catch (err) { showToast(err.message, "error"); }
}

async function cancelFromDetail(id) {
  const r = requestsData.find((x) => x.id === id);
  if (!r) return;
  if (!confirm(t("workflow.confirmCancel") + "؟")) return;
  try {
    await api.post(`/workflow/api/requests/${id}/cancel`, {});
    showToast(t("workflow.toastCancelled"));
    closeDetailModal();
    loadRequests();
  } catch (err) { showToast(err.message, "error"); }
}

function closeDetailModal() {
  document.getElementById("request-detail-modal").style.display = "none";
}

function exportWorkflowRequests() {
  const headers = [
    t("workflow.docType"), t("workflow.docNumber"), t("workflow.docTitle"),
    t("workflow.amount"), t("workflow.status"), t("workflow.currentStep"),
    t("workflow.submittedBy"), t("workflow.submittedAt"), t("workflow.comment"),
  ];
  const rows = requestsData.map((r) => {
    const d = r.doc || {};
    return [
      docTypeLabel(r.doc_type), d.number || r.doc_id, d.title || "",
      d.amount || 0, t(WF_STATUS_LABELS[r.status]) || r.status,
      r.current_role || "", r.submitted_by_name || "", r.submitted_at || "",
      r.comment || "",
    ];
  });
  exportCSV("workflow_requests.csv", headers, rows);
}

window.openDetailModal = openDetailModal;
window.closeDetailModal = closeDetailModal;
window.approveFromDetail = approveFromDetail;
window.rejectFromDetail = rejectFromDetail;
window.cancelFromDetail = cancelFromDetail;
window.exportWorkflowRequests = exportWorkflowRequests;

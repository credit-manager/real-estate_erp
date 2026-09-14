/* ============================================================
   Workflow Approvals Module JavaScript
   ============================================================ */

let approvalsData = [];
let currentApproveId = null;
let currentRejectId = null;
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

document.addEventListener("DOMContentLoaded", () => {
  loadMeta();
  loadApprovals();
});

async function loadMeta() {
  try {
    const meta = await api.get("/workflow/api/meta");
    document.getElementById("wf-stat-pending").textContent = meta.counts.pending;
    document.getElementById("wf-stat-mine").textContent = meta.my_pending;
    document.getElementById("wf-stat-approved").textContent = meta.counts.approved;
    document.getElementById("wf-stat-rejected").textContent = meta.counts.rejected;
  } catch (err) { showToast(err.message, "error"); }
}

function docTypeLabel(dt) {
  const key = WF_DOC_LABELS[dt];
  return key ? t(key) : dt;
}

function docSummary(r) {
  const d = r.doc || {};
  const title = d.title ? ` — ${d.title}` : "";
  return `${docTypeLabel(r.doc_type)} #${escapeHtml(d.number || r.doc_id)}${title}`;
}

async function loadApprovals() {
  const tbody = document.getElementById("approvals-table");
  try {
    approvalsData = await api.get("/workflow/api/approvals");
    if (!approvalsData.length) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">✔</div>${t("workflow.pendingEmpty")}</div></td></tr>`;
      return;
    }
    tbody.innerHTML = approvalsData.map((r) => {
      const d = r.doc || {};
      const cur = d.currency ? ` ${escapeHtml(d.currency)}` : "";
      return `
        <tr>
          <td>${docTypeLabel(r.doc_type)}</td>
          <td><strong>${escapeHtml(d.number || r.doc_id)}</strong></td>
          <td style="color:var(--muted-foreground);">${escapeHtml(d.title || "—")}</td>
          <td>${formatNumber(d.amount || 0)}${cur}</td>
          <td><span class="badge badge-warning">${escapeHtml(r.current_role || "—")}</span></td>
          <td>${escapeHtml(r.submitted_by_name || "—")}</td>
          <td style="color:var(--muted-foreground); white-space:nowrap;">${r.submitted_at ? r.submitted_at.replace("T", " ").slice(0, 19) : "—"}</td>
          <td><div class="table-actions">
            ${CAN_EDIT ? `
            <button class="btn btn-primary btn-sm" onclick="openApproveModal(${r.id})">${t("workflow.approve")}</button>
            <button class="btn btn-danger btn-sm" onclick="openRejectModal(${r.id})">${t("workflow.reject")}</button>` : "—"}
          </div></td>
        </tr>`;
    }).join("");
  } catch (err) { showToast(err.message, "error"); }
}

function openApproveModal(id) {
  const r = approvalsData.find((x) => x.id === id);
  if (!r) return;
  currentApproveId = id;
  document.getElementById("approve-doc-summary").textContent = docSummary(r);
  document.getElementById("approve-comment").value = "";
  document.getElementById("approve-modal").style.display = "flex";
}

function closeApproveModal() {
  document.getElementById("approve-modal").style.display = "none";
  currentApproveId = null;
}

async function confirmApprove() {
  const comment = document.getElementById("approve-comment").value.trim();
  const btn = document.getElementById("approve-confirm");
  btn.disabled = true;
  try {
    await api.post(`/workflow/api/requests/${currentApproveId}/approve`, { comment });
    showToast(t("workflow.toastApproved"));
    closeApproveModal();
    loadMeta();
    loadApprovals();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

function openRejectModal(id) {
  const r = approvalsData.find((x) => x.id === id);
  if (!r) return;
  currentRejectId = id;
  document.getElementById("reject-doc-summary").textContent = docSummary(r);
  document.getElementById("reject-comment").value = "";
  document.getElementById("reject-modal").style.display = "flex";
}

function closeRejectModal() {
  document.getElementById("reject-modal").style.display = "none";
  currentRejectId = null;
}

async function confirmReject() {
  const comment = document.getElementById("reject-comment").value.trim();
  if (!comment) {
    showToast(t("workflow.rejectCommentRequired"), "error");
    return;
  }
  const btn = document.getElementById("reject-confirm");
  btn.disabled = true;
  try {
    await api.post(`/workflow/api/requests/${currentRejectId}/reject`, { comment });
    showToast(t("workflow.toastRejected"));
    closeRejectModal();
    loadMeta();
    loadApprovals();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

window.openApproveModal = openApproveModal;
window.closeApproveModal = closeApproveModal;
window.confirmApprove = confirmApprove;
window.openRejectModal = openRejectModal;
window.closeRejectModal = closeRejectModal;
window.confirmReject = confirmReject;

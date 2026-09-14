/* ============================================================
   Audit Log Module JavaScript
   ============================================================ */

let allLogs = [];

const AUDIT_ACTION_LABELS = {
  create: "audit.create",
  update: "audit.update",
  delete: "audit.delete",
  payment: "audit.payment",
  login: "audit.login",
  logout: "audit.logout",
  submit: "audit.submit",
  approve: "audit.approve",
  reject: "audit.reject",
};

const AUDIT_ENTITY_LABELS = {
  unit: "audit.unit",
  project: "audit.project",
  employee: "audit.employee",
  customer: "audit.customer",
  supplier: "audit.supplier",
  invoice: "audit.invoice",
  order: "audit.order",
  rental: "audit.rental",
  plan: "audit.plan",
  installment: "audit.installment",
  user: "audit.user",
  company: "audit.company",
  branch: "audit.branch",
  financial_year: "audit.financialYear",
  currency: "audit.currency",
  workflow: "audit.workflow",
  approval: "audit.approval",
};

document.addEventListener("DOMContentLoaded", () => {
  loadLogs();
  ["filter-entity", "filter-action"].forEach((id) => {
    document.getElementById(id).addEventListener("change", loadLogs);
  });
  document.getElementById("filter-search").addEventListener("input", () => {
    clearTimeout(window.__auditTimer);
    window.__auditTimer = setTimeout(loadLogs, 250);
  });
});

async function loadLogs() {
  const entity = document.getElementById("filter-entity").value;
  const action = document.getElementById("filter-action").value;
  const search = document.getElementById("filter-search").value.trim();
  const params = new URLSearchParams();
  if (entity) params.set("entity", entity);
  if (action) params.set("action", action);
  if (search) params.set("q", search);
  params.set("limit", "300");
  try {
    allLogs = await api.get(`/api/users/audit-logs?${params.toString()}`);
    renderLogs();
  } catch (err) { showToast(err.message, "error"); }
}

function renderLogs() {
  const tbody = document.getElementById("audit-table");
  if (!allLogs.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><div class="empty-icon">📋</div>${t("audit.noLogs")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allLogs.map((l) => `
    <tr>
      <td style="color:var(--muted-foreground); white-space:nowrap;">${l.created_at ? l.created_at.replace("T", " ").slice(0, 19) : "—"}</td>
      <td><strong>${escapeHtml(l.username || "—")}</strong></td>
      <td>${actionBadge(l.action)}</td>
      <td>${entityBadge(l.entity)}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(l.description || "")}</td>
    </tr>`).join("");
}

const AUDIT_ACTION_CLS = {
  create: "badge-success",
  update: "badge-info",
  delete: "badge-danger",
  payment: "badge-warning",
  login: "badge-success",
  logout: "badge-neutral",
  submit: "badge-info",
  approve: "badge-success",
  reject: "badge-danger",
};

function actionBadge(action) {
  const key = AUDIT_ACTION_LABELS[action];
  const cls = AUDIT_ACTION_CLS[action] || "badge-neutral";
  return `<span class="badge ${cls}">${key ? t(key) : action}</span>`;
}

function entityBadge(entity) {
  const key = AUDIT_ENTITY_LABELS[entity];
  return `<span class="badge badge-neutral">${key ? t(key) : entity}</span>`;
}

function exportAudit() {
  const headers = [
    t("audit.when"), t("audit.user"), t("audit.action"),
    t("audit.entity"), t("audit.details"),
  ];
  const rows = allLogs.map((l) => [
    l.created_at || "",
    l.username || "",
    AUDIT_ACTION_LABELS[l.action] ? t(AUDIT_ACTION_LABELS[l.action]) : l.action,
    AUDIT_ENTITY_LABELS[l.entity] ? t(AUDIT_ENTITY_LABELS[l.entity]) : l.entity,
    l.description || "",
  ]);
  exportCSV("audit_logs.csv", headers, rows);
}

window.exportAudit = exportAudit;

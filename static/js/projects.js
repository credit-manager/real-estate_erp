/* ============================================================
   Projects & Contracting Module JavaScript
   ============================================================ */

let allProjects = [];
let allEmployees = [];
let allSubcontractors = [];
let allEquipment = [];
let ws = null;          // workspace data (summary + sub-modules)
let currentTab = "overview";

// ===== i18n / helpers =====
function pv(value) {
  if (value === null || value === undefined || value === "") return "—";
  const T = window.T || {};
  const k = "pval." + value;
  if (T[k] !== undefined) return t(k);
  const sk = "status." + value;
  if (T[sk] !== undefined) return t(sk);
  return value;
}

function fmtDate(v) {
  return v ? v : "—";
}

function progressCell(value) {
  const v = Number(value) || 0;
  const cls = v < 40 ? "danger" : v < 70 ? "warning" : "";
  return `<div class="progress-bar" style="min-width:80px;"><div class="progress-fill ${cls}" style="width:${v}%"></div></div>
          <small style="color:var(--muted-foreground);">${v}%</small>`;
}

function emptyState(msg) {
  return `<tr><td colspan="12"><div class="empty-state"><div class="empty-icon">📋</div>${msg}</div></td></tr>`;
}

const PM_BADGES = {
  active: "badge-success", completed: "badge-primary", available: "badge-success",
  paid: "badge-success", approved: "badge-info", signed: "badge-info", executed: "badge-info",
  mitigated: "badge-info", pass: "badge-success", done: "badge-success", running: "badge-success",
  in_progress: "badge-warning", pending: "badge-warning", submitted: "badge-warning",
  open: "badge-warning", on_hold: "badge-warning", under_maintenance: "badge-warning", medium: "badge-warning",
  suspended: "badge-danger", rejected: "badge-danger", terminated: "badge-danger",
  fail: "badge-danger", out_of_service: "badge-danger", high: "badge-danger",
  draft: "badge-neutral", closed: "badge-neutral", low: "badge-info", in_use: "badge-info", not_started: "badge-neutral",
};

function pmBadge(value) {
  return `<span class="badge ${PM_BADGES[value] || "badge-neutral"}">${pv(value)}</span>`;
}

// ===== Tab definitions =====
const TABS = [
  { key: "overview", label: "projects.overview" },
  { key: "phases", label: "projects.phases" },
  { key: "wbs", label: "projects.wbs" },
  { key: "boq", label: "projects.boq" },
  { key: "contracts", label: "projects.contracts" },
  { key: "subcontractors", label: "projects.subcontractors" },
  { key: "statements", label: "projects.statements" },
  { key: "changeOrders", label: "projects.changeOrders" },
  { key: "progress", label: "projects.progress" },
  { key: "execution", label: "projects.execution" },
  { key: "costs", label: "projects.costs" },
  { key: "risks", label: "projects.risks" },
  { key: "quality", label: "projects.quality" },
  { key: "siteLogs", label: "projects.siteLogs" },
  { key: "equipment", label: "projects.equipment" },
  { key: "labor", label: "projects.labor" },
];

function opt(v, label) { return { value: v, label: label }; }

// ===== Entity configs =====
const STATUS_P = ["not_started", "in_progress", "completed", "on_hold"];
const STATUS_C = ["draft", "signed", "running", "completed", "terminated"];
const STATUS_S = ["draft", "submitted", "approved", "rejected", "paid"];
const STATUS_R = ["open", "mitigated", "closed"];
const STATUS_E = ["planned", "in_progress", "done"];
const STATUS_Q = ["open", "closed"];
const STATUS_EQ = ["available", "in_use", "under_maintenance", "out_of_service"];
const LEVELS = ["low", "medium", "high"];
const COST_TYPES = ["material", "labor", "equipment", "subcontract", "administrative", "other"];
const WBS_TYPES = ["phase", "package", "control_account", "work_package"];
const BOQ_CATS = ["material", "labor", "equipment", "subcontract", "other"];

const ENTITIES = {
  phases: {
    title: "projects.phases", newBtn: "projects.newPhase", empty: "projects.noPhases",
    api: (pid) => `/api/projects/${pid}/phases`,
    fields: [
      { name: "name", label: "projects.phaseName", type: "text", required: true, wide: true },
      { name: "description", label: "common.description", type: "textarea", wide: true },
      { name: "order", label: "projects.order", type: "number" },
      { name: "start_date", label: "common.start", type: "date" },
      { name: "end_date", label: "common.end", type: "date" },
      { name: "status", label: "common.status", type: "select", options: STATUS_P.map((s) => opt(s, pv(s))) },
      { name: "completion", label: "projects.percentage", type: "number", min: "0", max: "100" },
      { name: "budget", label: "projects.phaseBudget", type: "number", step: "0.01" },
    ],
    columns: [
      { label: "projects.phaseName", key: "name", render: (r) => `<strong>${escapeHtml(r.name)}</strong>` },
      { label: "common.status", key: "status", fmt: "status" },
      { label: "projects.order", key: "order" },
      { label: "common.start", key: "start_date", fmt: "date" },
      { label: "common.end", key: "end_date", fmt: "date" },
      { label: "common.completion", key: "completion", fmt: "progress" },
      { label: "projects.phaseBudget", key: "budget", fmt: "money" },
    ],
  },
  wbs: {
    title: "projects.wbs", newBtn: "projects.newWbs", empty: "projects.noWbs",
    api: (pid) => `/api/projects/${pid}/wbs`,
    fields: [
      { name: "parent_id", label: "projects.parent", type: "select", placeholder: "projects.selectParent",
        options: (ctx) => ctx.wbs.map((w) => opt(w.id, (w.code ? w.code + " - " : "") + w.name)) },
      { name: "code", label: "projects.code", type: "text" },
      { name: "name", label: "projects.nameLabel", type: "text", required: true, wide: true },
      { name: "type", label: "projects.wbsType", type: "select", options: WBS_TYPES.map((s) => opt(s, pv(s))) },
      { name: "description", label: "common.description", type: "textarea", wide: true },
    ],
    columns: [
      { label: "projects.code", key: "code" },
      { label: "projects.nameLabel", key: "name", render: (r) => `<strong>${escapeHtml(r.name)}</strong>` },
      { label: "projects.wbsType", key: "type", fmt: "enum" },
      { label: "projects.parent", key: "parent_name", render: (r) => escapeHtml(r.parent_name || "—") },
      { label: "common.description", key: "description" },
    ],
  },
  boq: {
    title: "projects.boq", newBtn: "projects.newBoq", empty: "projects.noBoq",
    api: (pid) => `/api/projects/${pid}/boq`,
    fields: [
      { name: "code", label: "projects.code", type: "text" },
      { name: "wbs_id", label: "projects.selectWbs", type: "select", placeholder: "projects.choose",
        options: (ctx) => ctx.wbs.map((w) => opt(w.id, (w.code ? w.code + " - " : "") + w.name)) },
      { name: "description", label: "common.description", type: "text", required: true, wide: true },
      { name: "unit", label: "common.unit", type: "text" },
      { name: "quantity", label: "projects.quantity", type: "number", step: "0.001" },
      { name: "unit_price", label: "projects.unitPrice", type: "number", step: "0.01" },
      { name: "category", label: "projects.boqCategory", type: "select", options: BOQ_CATS.map((s) => opt(s, pv(s))) },
      { name: "status", label: "common.status", type: "select", options: ["pending", "approved", "rejected"].map((s) => opt(s, pv(s))) },
      { name: "notes", label: "projects.notes", type: "textarea", wide: true },
    ],
    columns: [
      { label: "projects.code", key: "code" },
      { label: "common.description", key: "description", render: (r) => `<strong>${escapeHtml(r.description)}</strong>` },
      { label: "common.unit", key: "unit" },
      { label: "projects.quantity", key: "quantity" },
      { label: "projects.unitPrice", key: "unit_price", fmt: "money" },
      { label: "projects.totalPrice", key: "total", fmt: "money" },
      { label: "projects.boqCategory", key: "category", fmt: "enum" },
      { label: "common.status", key: "status", fmt: "status" },
    ],
    extraActions: (r) =>
      canAction("projects", "view")
        ? `<button class="btn btn-outline btn-sm" onclick="openAnalysisModal(${r.id}, '${escapeHtml(String(r.description).replace(/'/g, ""))}')">${t("projects.analyze")}</button>`
        : "",
  },
  contracts: {
    title: "projects.contracts", newBtn: "projects.newContract", empty: "projects.noContracts",
    api: (pid) => `/api/projects/${pid}/contracts`,
    fields: [
      { name: "contract_no", label: "projects.contractNo", type: "text", required: true },
      { name: "title", label: "projects.contractTitle", type: "text", required: true, wide: true },
      { name: "contract_type", label: "projects.contractType", type: "select", options: ["main", "subcontract"].map((s) => opt(s, pv(s))) },
      { name: "party_name", label: "projects.party", type: "text" },
      { name: "subcontractor_id", label: "projects.selectSubcontractor", type: "select", placeholder: "projects.choose",
        options: (ctx) => ctx.subcontractors.map((s) => opt(s.id, s.name)) },
      { name: "start_date", label: "common.start", type: "date" },
      { name: "end_date", label: "common.end", type: "date" },
      { name: "contract_value", label: "projects.contractValue", type: "number", step: "0.01" },
      { name: "advance_payment", label: "projects.advance", type: "number", step: "0.01" },
      { name: "retention_pct", label: "projects.retention", type: "number", step: "0.01" },
      { name: "status", label: "common.status", type: "select", options: STATUS_C.map((s) => opt(s, pv(s))) },
      { name: "description", label: "common.description", type: "textarea", wide: true },
    ],
    columns: [
      { label: "projects.contractNo", key: "contract_no", render: (r) => `<strong>${escapeHtml(r.contract_no)}</strong>` },
      { label: "projects.contractTitle", key: "title" },
      { label: "projects.contractType", key: "contract_type", fmt: "enum" },
      { label: "projects.party", key: "party_name" },
      { label: "projects.contractValue", key: "contract_value", fmt: "money" },
      { label: "projects.retention", key: "retention_pct", render: (r) => `${r.retention_pct ?? 0}%` },
      { label: "common.status", key: "status", fmt: "status" },
    ],
  },
  subcontractors: {
    title: "projects.subcontractors", newBtn: "projects.newSubcontractor", empty: "projects.noSubcontractors",
    api: () => `/api/projects/subcontractors`,
    fields: [
      { name: "name", label: "common.name", type: "text", required: true, wide: true },
      { name: "contact_person", label: "projects.contactPerson", type: "text" },
      { name: "phone", label: "common.phone", type: "text" },
      { name: "email", label: "common.email", type: "text" },
      { name: "address", label: "common.address", type: "text", wide: true },
      { name: "specialty", label: "projects.specialty", type: "text" },
      { name: "commercial_registration", label: "projects.commercialReg", type: "text" },
      { name: "rating", label: "projects.rating", type: "number", min: "0", max: "5", step: "1" },
      { name: "status", label: "common.status", type: "select", options: ["active", "inactive"].map((s) => opt(s, pv(s))) },
      { name: "notes", label: "projects.notes", type: "textarea", wide: true },
    ],
    columns: [
      { label: "common.name", key: "name", render: (r) => `<strong>${escapeHtml(r.name)}</strong>` },
      { label: "projects.contactPerson", key: "contact_person" },
      { label: "common.phone", key: "phone" },
      { label: "projects.specialty", key: "specialty" },
      { label: "projects.rating", key: "rating", render: (r) => (r.rating ? "⭐ ".repeat(Math.min(5, r.rating)) : "—") },
      { label: "common.status", key: "status", fmt: "status" },
    ],
  },
  statements: {
    title: "projects.statements", newBtn: "projects.newStatement", empty: "projects.noStatements",
    api: (pid) => `/api/projects/${pid}/statements`,
    createApi: (pid, body) => `/api/projects/contracts/${body.contract_id}/statements`,
    itemApi: (pid, id, rec) => `/api/projects/contracts/${rec.contract_id}/statements/${id}`,
    fields: [
      { name: "contract_id", label: "projects.selectContract", type: "select", required: true,
        options: (ctx) => ctx.contracts.map((c) => opt(c.id, c.contract_no + " - " + c.title)) },
      { name: "statement_no", label: "projects.statementNo", type: "text", required: true },
      { name: "statement_date", label: "common.date", type: "date" },
      { name: "period_from", label: "projects.periodFrom", type: "date" },
      { name: "period_to", label: "projects.periodTo", type: "date" },
      { name: "work_value", label: "projects.workValue", type: "number", step: "0.01" },
      { name: "advance_deduction", label: "projects.advanceDeduction", type: "number", step: "0.01" },
      { name: "retention_deduction", label: "projects.retentionDeduction", type: "number", step: "0.01" },
      { name: "net_value", label: "projects.netValue", type: "number", step: "0.01" },
      { name: "cumulative_total", label: "projects.cumulative", type: "number", step: "0.01" },
      { name: "status", label: "common.status", type: "select", options: STATUS_S.map((s) => opt(s, pv(s))) },
      { name: "notes", label: "projects.notes", type: "textarea", wide: true },
    ],
    columns: [
      { label: "projects.statementNo", key: "statement_no", render: (r) => `<strong>${escapeHtml(r.statement_no)}</strong>` },
      { label: "projects.contractNo", key: "contract_no", render: (r) => escapeHtml(r.contract_no || "—") },
      { label: "common.date", key: "statement_date", fmt: "date" },
      { label: "projects.workValue", key: "work_value", fmt: "money" },
      { label: "projects.netValue", key: "net_value", fmt: "money" },
      { label: "projects.cumulative", key: "cumulative_total", fmt: "money" },
      { label: "common.status", key: "status", fmt: "status" },
    ],
    onOpen: () => { /* statements refresh handled generically */ },
  },
  changeOrders: {
    title: "projects.changeOrders", newBtn: "projects.newChangeOrder", empty: "projects.noChangeOrders",
    api: (pid) => `/api/projects/${pid}/change-orders`,
    fields: [
      { name: "contract_id", label: "projects.selectContract", type: "select", placeholder: "projects.choose",
        options: (ctx) => ctx.contracts.map((c) => opt(c.id, c.contract_no + " - " + c.title)) },
      { name: "change_no", label: "projects.code", type: "text" },
      { name: "description", label: "common.description", type: "textarea", required: true, wide: true },
      { name: "reason", label: "projects.reason", type: "text", wide: true },
      { name: "change_type", label: "projects.changeType", type: "select", options: ["addition", "reduction", "neutral"].map((s) => opt(s, pv(s))) },
      { name: "amount", label: "common.amount", type: "number", step: "0.01" },
      { name: "change_date", label: "common.date", type: "date" },
      { name: "status", label: "common.status", type: "select", options: ["pending", "approved", "rejected", "executed"].map((s) => opt(s, pv(s))) },
    ],
    columns: [
      { label: "projects.code", key: "change_no" },
      { label: "common.description", key: "description", render: (r) => `<strong>${escapeHtml(r.description)}</strong>` },
      { label: "projects.changeType", key: "change_type", fmt: "enum" },
      { label: "common.amount", key: "amount", fmt: "money" },
      { label: "common.date", key: "change_date", fmt: "date" },
      { label: "common.status", key: "status", fmt: "status" },
    ],
  },
  progress: {
    title: "projects.progress", newBtn: "projects.newProgress", empty: "projects.noProgress",
    api: (pid) => `/api/projects/${pid}/progress`,
    fields: [
      { name: "boq_id", label: "projects.selectBoqItem", type: "select", placeholder: "projects.choose",
        options: (ctx) => ctx.boq.map((b) => opt(b.id, (b.code ? b.code + " - " : "") + b.description)) },
      { name: "record_date", label: "projects.recordDate", type: "date" },
      { name: "percentage", label: "projects.percentage", type: "number", min: "0", max: "100", required: true },
      { name: "note", label: "projects.notes", type: "textarea", wide: true },
    ],
    columns: [
      { label: "projects.recordDate", key: "record_date", fmt: "date" },
      { label: "projects.selectBoqItem", key: "boq_desc", render: (r) => escapeHtml(r.boq_desc || "—") },
      { label: "projects.percentage", key: "percentage", fmt: "progress" },
      { label: "projects.notes", key: "note" },
    ],
  },
  execution: {
    title: "projects.execution", newBtn: "projects.newExecution", empty: "projects.noExecution",
    api: (pid) => `/api/projects/${pid}/execution`,
    fields: [
      { name: "log_date", label: "common.date", type: "date" },
      { name: "activity", label: "projects.activity", type: "text", required: true, wide: true },
      { name: "description", label: "common.description", type: "textarea", wide: true },
      { name: "responsible", label: "projects.responsible", type: "text" },
      { name: "status", label: "common.status", type: "select", options: STATUS_E.map((s) => opt(s, pv(s))) },
    ],
    columns: [
      { label: "common.date", key: "log_date", fmt: "date" },
      { label: "projects.activity", key: "activity", render: (r) => `<strong>${escapeHtml(r.activity)}</strong>` },
      { label: "common.description", key: "description" },
      { label: "projects.responsible", key: "responsible" },
      { label: "common.status", key: "status", fmt: "status" },
    ],
  },
  costs: {
    title: "projects.costs", newBtn: "projects.newCost", empty: "projects.noCosts",
    api: (pid) => `/api/projects/${pid}/costs`,
    fields: [
      { name: "cost_date", label: "common.date", type: "date" },
      { name: "category", label: "projects.costCategory", type: "select", options: COST_TYPES.map((s) => opt(s, pv(s))) },
      { name: "description", label: "common.description", type: "text", required: true, wide: true },
      { name: "amount", label: "common.amount", type: "number", step: "0.01", required: true },
      { name: "reference", label: "projects.code", type: "text" },
      { name: "notes", label: "projects.notes", type: "textarea", wide: true },
    ],
    columns: [
      { label: "common.date", key: "cost_date", fmt: "date" },
      { label: "projects.costCategory", key: "category", fmt: "enum" },
      { label: "common.description", key: "description", render: (r) => `<strong>${escapeHtml(r.description)}</strong>` },
      { label: "common.amount", key: "amount", fmt: "money" },
      { label: "projects.code", key: "reference" },
    ],
  },
  risks: {
    title: "projects.risks", newBtn: "projects.newRisk", empty: "projects.noRisks",
    api: (pid) => `/api/projects/${pid}/risks`,
    fields: [
      { name: "description", label: "common.description", type: "textarea", required: true, wide: true },
      { name: "category", label: "common.category", type: "text" },
      { name: "probability", label: "projects.probability", type: "select", options: LEVELS.map((s) => opt(s, pv(s))) },
      { name: "impact", label: "projects.impact", type: "select", options: LEVELS.map((s) => opt(s, pv(s))) },
      { name: "mitigation", label: "projects.mitigation", type: "textarea", wide: true },
      { name: "owner", label: "projects.owner", type: "text" },
      { name: "status", label: "common.status", type: "select", options: STATUS_R.map((s) => opt(s, pv(s))) },
    ],
    columns: [
      { label: "common.description", key: "description", render: (r) => `<strong>${escapeHtml(r.description)}</strong>` },
      { label: "common.category", key: "category" },
      { label: "projects.probability", key: "probability", fmt: "enum" },
      { label: "projects.impact", key: "impact", fmt: "enum" },
      { label: "projects.level", key: "level", fmt: "status" },
      { label: "projects.owner", key: "owner" },
      { label: "common.status", key: "status", fmt: "status" },
    ],
  },
  quality: {
    title: "projects.quality", newBtn: "projects.newQuality", empty: "projects.noQuality",
    api: (pid) => `/api/projects/${pid}/quality`,
    fields: [
      { name: "check_date", label: "common.date", type: "date" },
      { name: "check_type", label: "projects.checkType", type: "select", options: ["inspection", "test", "audit"].map((s) => opt(s, pv(s))) },
      { name: "description", label: "common.description", type: "textarea", required: true, wide: true },
      { name: "result", label: "projects.result", type: "select", options: ["pass", "fail", "pending"].map((s) => opt(s, pv(s))) },
      { name: "inspector", label: "projects.inspector", type: "text" },
      { name: "corrective_action", label: "projects.correctiveAction", type: "textarea", wide: true },
      { name: "status", label: "common.status", type: "select", options: STATUS_Q.map((s) => opt(s, pv(s))) },
    ],
    columns: [
      { label: "common.date", key: "check_date", fmt: "date" },
      { label: "projects.checkType", key: "check_type", fmt: "enum" },
      { label: "common.description", key: "description", render: (r) => `<strong>${escapeHtml(r.description)}</strong>` },
      { label: "projects.result", key: "result", fmt: "status" },
      { label: "projects.inspector", key: "inspector" },
      { label: "common.status", key: "status", fmt: "status" },
    ],
  },
  siteLogs: {
    title: "projects.siteLogs", newBtn: "projects.newSiteLog", empty: "projects.noSiteLogs",
    api: (pid) => `/api/projects/${pid}/site-logs`,
    fields: [
      { name: "log_date", label: "common.date", type: "date" },
      { name: "report_type", label: "projects.reportType", type: "select", options: ["daily", "site", "meeting"].map((s) => opt(s, pv(s))) },
      { name: "weather", label: "projects.weather", type: "text" },
      { name: "description", label: "common.description", type: "textarea", required: true, wide: true },
      { name: "notes", label: "projects.notes", type: "textarea", wide: true },
    ],
    columns: [
      { label: "common.date", key: "log_date", fmt: "date" },
      { label: "projects.reportType", key: "report_type", fmt: "enum" },
      { label: "projects.weather", key: "weather" },
      { label: "common.description", key: "description" },
    ],
  },
  equipment: {
    title: "projects.equipment", newBtn: "projects.newEquipment", empty: "projects.noEquipment",
    api: () => `/api/projects/equipment`,
    fields: [
      { name: "code", label: "projects.equipmentCode", type: "text" },
      { name: "name", label: "projects.equipmentName", type: "text", required: true, wide: true },
      { name: "type", label: "projects.equipmentType", type: "text" },
      { name: "status", label: "common.status", type: "select", options: STATUS_EQ.map((s) => opt(s, pv(s))) },
      { name: "location", label: "common.location", type: "text" },
      { name: "project_id", label: "common.project", type: "select", placeholder: "projects.choose",
        options: () => allProjects.map((p) => opt(p.id, p.name)) },
      { name: "daily_cost", label: "projects.dailyCost", type: "number", step: "0.01" },
      { name: "notes", label: "projects.notes", type: "textarea", wide: true },
    ],
    columns: [
      { label: "projects.equipmentCode", key: "code" },
      { label: "projects.equipmentName", key: "name", render: (r) => `<strong>${escapeHtml(r.name)}</strong>` },
      { label: "projects.equipmentType", key: "type" },
      { label: "common.status", key: "status", fmt: "status" },
      { label: "common.project", key: "project_name", render: (r) => escapeHtml(r.project_name || "—") },
      { label: "projects.dailyCost", key: "daily_cost", fmt: "money" },
    ],
  },
  labor: {
    title: "projects.labor", newBtn: "projects.newLabor", empty: "projects.noLabor",
    api: (pid) => `/api/projects/${pid}/labor`,
    fields: [
      { name: "employee_id", label: "common.employee", type: "select", placeholder: "projects.choose",
        options: () => allEmployees.map((e) => opt(e.id, e.full_name)) },
      { name: "name", label: "common.name", type: "text" },
      { name: "trade", label: "projects.trade", type: "text" },
      { name: "start_date", label: "common.start", type: "date" },
      { name: "end_date", label: "common.end", type: "date" },
      { name: "daily_rate", label: "projects.dailyRate", type: "number", step: "0.01" },
      { name: "status", label: "common.status", type: "select", options: ["active", "completed"].map((s) => opt(s, pv(s))) },
    ],
    columns: [
      { label: "common.name", key: "name", render: (r) => `<strong>${escapeHtml(r.name || "—")}</strong>` },
      { label: "projects.trade", key: "trade" },
      { label: "common.start", key: "start_date", fmt: "date" },
      { label: "common.end", key: "end_date", fmt: "date" },
      { label: "projects.dailyRate", key: "daily_rate", fmt: "money" },
      { label: "common.status", key: "status", fmt: "status" },
    ],
  },
};

// ===== List view =====
document.addEventListener("DOMContentLoaded", async () => {
  try {
    [allProjects, allEmployees, allSubcontractors, allEquipment] = await Promise.all([
      api.get("/api/projects"),
      api.get("/api/employees"),
      api.get("/api/projects/subcontractors"),
      api.get("/api/projects/equipment"),
    ]);
    renderProjects();
    renderSummary();
    populateManagerSelect();

    document.getElementById("filter-status").addEventListener("change", renderProjects);
    document.getElementById("filter-priority").addEventListener("change", renderProjects);
    document.getElementById("filter-search").addEventListener("input", renderProjects);
  } catch (err) {
    console.error(err);
  }
});

function populateManagerSelect() {
  const select = document.getElementById("project-manager");
  if (!select) return;
  const options = allEmployees.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`);
  select.innerHTML = `<option value="">${t("projects.selectManager")}</option>` + options.join("");
}

function renderProjects() {
  const status = document.getElementById("filter-status").value;
  const priority = document.getElementById("filter-priority").value;
  const search = document.getElementById("filter-search").value.trim();

  const filtered = allProjects.filter((p) => {
    const sOk = !status || p.status === status;
    const pOk = !priority || p.priority === priority;
    const searchOk = !search || (p.name || "").includes(search) || (p.location || "").includes(search);
    return sOk && pOk && searchOk;
  });

  const tbody = document.getElementById("projects-table");
  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="10"><div class="empty-state"><div class="empty-icon">🗂️</div>${t("projects.noProjects")}</div></td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((p) => {
    const fillClass = p.completion < 40 ? "danger" : p.completion < 70 ? "warning" : "";
    const manager = allEmployees.find((e) => e.id === p.manager_id);
    return `
      <tr>
        <td><a class="link" href="#" onclick="event.preventDefault();openProject(${p.id});">${escapeHtml(p.name)}</a><br><small style="color:var(--muted-foreground);">${escapeHtml(p.description || "")}</small></td>
        <td>${statusBadge(p.status)}</td>
        <td>${statusBadge(p.priority)}</td>
        <td>${formatMoney(p.budget)}</td>
        <td>${formatMoney(p.spent)}</td>
        <td style="min-width:120px;">${progressCell(p.completion)}</td>
        <td style="color:var(--muted-foreground);">${manager ? escapeHtml(manager.full_name) : "—"}</td>
        <td style="color:var(--muted-foreground);">${escapeHtml(p.location || "—")}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-primary btn-sm" onclick="openProject(${p.id})">${t("projects.open")}</button>
            ${canAction("projects", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editProject(${JSON.stringify(p)})'>${t("common.edit")}</button>` : ""}
            ${canAction("projects", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteProject(${p.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`;
  }).join("");
}

function renderSummary() {
  animateCount(document.getElementById("sum-total"), allProjects.length, formatNumber);
  animateCount(document.getElementById("sum-active"), allProjects.filter((p) => p.status === "active").length, formatNumber);
  animateCount(document.getElementById("sum-finishing"), allProjects.filter((p) => p.status === "finishing").length, formatNumber);
  animateCount(document.getElementById("sum-completed"), allProjects.filter((p) => p.status === "completed").length, formatNumber);
}

function exportProjects() {
  const headers = [
    t("projects.colName"), t("common.status"), t("common.priority"),
    t("common.budget"), t("common.spent"), t("common.completion"),
    t("projects.managerLabel"), t("common.location"), t("common.description"),
  ];
  const rows = allProjects.map((p) => {
    const manager = allEmployees.find((e) => e.id === p.manager_id);
    return [
      p.name, tv(p.status), tv(p.priority),
      p.budget || 0, p.spent || 0, (p.completion || 0) + "%",
      manager ? manager.full_name : "",
      p.location || "", p.description || "",
    ];
  });
  exportCSV("projects.csv", headers, rows);
}

// ===== Project modal (list view) =====
function openProjectModal() {
  document.getElementById("project-modal-title").textContent = t("common.newProject");
  document.getElementById("project-id").value = "";
  ["project-name", "project-location", "project-budget", "project-spent", "project-completion", "project-description", "project-start-date", "project-deadline"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  document.getElementById("project-status").value = "active";
  document.getElementById("project-priority").value = "medium";
  document.getElementById("project-completion").value = "0";
  document.getElementById("project-manager").value = "";
  populateManagerSelect();
  document.getElementById("project-modal").classList.add("active");
}

function editProject(p) {
  document.getElementById("project-modal-title").textContent = t("projects.editTitle");
  document.getElementById("project-id").value = p.id;
  document.getElementById("project-name").value = p.name || "";
  document.getElementById("project-location").value = p.location || "";
  document.getElementById("project-status").value = p.status || "active";
  document.getElementById("project-priority").value = p.priority || "medium";
  document.getElementById("project-budget").value = p.budget || "";
  document.getElementById("project-spent").value = p.spent || "";
  document.getElementById("project-completion").value = p.completion || 0;
  document.getElementById("project-description").value = p.description || "";
  document.getElementById("project-start-date").value = p.start_date || "";
  document.getElementById("project-deadline").value = p.deadline || "";
  populateManagerSelect();
  document.getElementById("project-manager").value = p.manager_id || "";
  document.getElementById("project-modal").classList.add("active");
}

function closeProjectModal() {
  document.getElementById("project-modal").classList.remove("active");
}

async function saveProject() {
  const id = document.getElementById("project-id").value;
  const body = {
    name: document.getElementById("project-name").value,
    location: document.getElementById("project-location").value,
    status: document.getElementById("project-status").value,
    priority: document.getElementById("project-priority").value,
    budget: parseFloat(document.getElementById("project-budget").value) || 0,
    spent: parseFloat(document.getElementById("project-spent").value) || 0,
    manager_id: parseInt(document.getElementById("project-manager").value) || null,
    completion: parseInt(document.getElementById("project-completion").value) || 0,
    description: document.getElementById("project-description").value,
    start_date: document.getElementById("project-start-date").value,
    deadline: document.getElementById("project-deadline").value,
  };

  if (!body.name) { showToast(t("projects.nameRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/projects/${id}`, body);
    else await api.post("/api/projects", body);
    showToast(t("common.savedSuccess"));
    closeProjectModal();
    allProjects = await api.get("/api/projects");
    renderProjects();
    renderSummary();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteProject(id) {
  if (!confirm(t("projects.confirmDelete"))) return;
  try {
    await api.delete(`/api/projects/${id}`);
    showToast(t("common.deleted"));
    allProjects = await api.get("/api/projects");
    renderProjects();
    renderSummary();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ===== Workspace =====
async function openProject(id) {
  try {
    const summary = await api.get(`/api/projects/${id}/summary`);
    ws = { summary, phases: [], wbs: [], boq: [], contracts: [], statements: [], changeOrders: [], progress: [], execution: [], costs: [], risks: [], quality: [], siteLogs: [], labor: [] };
    ws.project = summary.project;
    await refreshAllData();
    document.getElementById("projects-list-view").style.display = "none";
    document.getElementById("project-workspace").style.display = "block";
    renderWorkspaceHeader();
    renderWorkspaceSummary();
    buildTabs();
    switchTab("overview");
  } catch (err) {
    showToast(err.message, "error");
  }
}

function closeWorkspace() {
  ws = null;
  document.getElementById("project-workspace").style.display = "none";
  document.getElementById("projects-list-view").style.display = "block";
}

async function refreshAllData() {
  const pid = ws.project.id;
  const [phases, wbs, boq, contracts, statements, changeOrders, progress, execution, costs, risks, quality, siteLogs, labor] = await Promise.all([
    api.get(`/api/projects/${pid}/phases`),
    api.get(`/api/projects/${pid}/wbs`),
    api.get(`/api/projects/${pid}/boq`),
    api.get(`/api/projects/${pid}/contracts`),
    api.get(`/api/projects/${pid}/statements`),
    api.get(`/api/projects/${pid}/change-orders`),
    api.get(`/api/projects/${pid}/progress`),
    api.get(`/api/projects/${pid}/execution`),
    api.get(`/api/projects/${pid}/costs`),
    api.get(`/api/projects/${pid}/risks`),
    api.get(`/api/projects/${pid}/quality`),
    api.get(`/api/projects/${pid}/site-logs`),
    api.get(`/api/projects/${pid}/labor`),
  ]);
  Object.assign(ws, { phases, wbs, boq, contracts, statements, changeOrders, progress, execution, costs, risks, quality, siteLogs, labor });

  // enrich join columns
  const wbsMap = {};
  wbs.forEach((w) => (wbsMap[w.id] = w));
  ws.wbs = wbs.map((w) => ({ ...w, parent_name: w.parent_id ? (wbsMap[w.parent_id]?.name || "") : "" }));

  const projMap = {};
  allProjects.forEach((p) => (projMap[p.id] = p));
  allEquipment = await api.get("/api/projects/equipment");
  ws.equipment = allEquipment.map((e) => ({ ...e, project_name: e.project_id ? (projMap[e.project_id]?.name || "") : "" }));
  ws.equipmentForProject = ws.equipment.filter((e) => e.project_id === pid);

  const boqMap = {};
  boq.forEach((b) => (boqMap[b.id] = b));
  ws.progress = progress.map((r) => ({ ...r, boq_desc: r.boq_id ? (boqMap[r.boq_id]?.description || "") : "" }));

  allSubcontractors = await api.get("/api/projects/subcontractors");
}

function buildTabs() {
  const bar = document.getElementById("ws-tabs");
  bar.innerHTML = TABS.map((tb) => `<button class="tab-btn" data-tab="${tb.key}" onclick="switchTab('${tb.key}')">${t(tb.label)}</button>`).join("");
}

function switchTab(key) {
  currentTab = key;
  document.querySelectorAll("#ws-tabs .tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === key));
  document.querySelectorAll("#tab-content .tab-panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + key));
  renderTab(key);
}

function renderTab(key) {
  if (key === "overview") { renderOverview(); return; }
  const cfg = ENTITIES[key];
  const el = document.getElementById("tab-" + key);
  el.innerHTML = renderTable(key, cfg);
}

function renderTable(key, cfg) {
  const ctx = { ...ws, subcontractors: allSubcontractors, equipment: allEquipment };
  const rows = key === "subcontractors" ? allSubcontractors : (key === "equipment" ? ws.equipment : ws[key]);
  const addBtn = canAction("projects", "create")
    ? `<button class="btn btn-primary btn-sm" onclick="openEntityModal('${key}')">${t(cfg.newBtn)}</button>`
    : "";
  if (!rows || !rows.length) {
    return `<div class="panel-toolbar"><span class="panel-title">${t(cfg.title)}</span>${addBtn}</div>
            <div class="card"><div class="empty-state" style="padding:28px;"><div class="empty-icon">📋</div>${t(cfg.empty)}</div></div>`;
  }
  const thead = `<tr>${cfg.columns.map((c) => `<th>${t(c.label)}</th>`).join("")}<th>${t("common.actions")}</th></tr>`;
  const tbody = rows.map((r) => {
    const cells = cfg.columns.map((c) => {
      let val = c.key ? r[c.key] : "";
      let html;
      if (c.render) html = c.render(r);
      else if (c.fmt === "status") html = pmBadge(val);
      else if (c.fmt === "enum") html = escapeHtml(pv(val));
      else if (c.fmt === "money") html = formatMoney(Number(val) || 0);
      else if (c.fmt === "date") html = fmtDate(val);
      else if (c.fmt === "progress") html = progressCell(val);
      else html = escapeHtml(val == null ? "" : val);
      return `<td>${html}</td>`;
    }).join("");
    const extra = cfg.extraActions ? cfg.extraActions(r) : "";
    const editBtn = canAction("projects", "edit") ? `<button class="btn btn-secondary btn-sm" onclick="openEntityModal('${key}', ${JSON.stringify(r)})">${t("common.edit")}</button>` : "";
    const delBtn = canAction("projects", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteEntity('${key}', ${r.id})">${t("common.delete")}</button>` : "";
    return `<tr>${cells}<td><div class="table-actions">${extra}${editBtn}${delBtn}</div></td></tr>`;
  }).join("");
  return `<div class="panel-toolbar"><span class="panel-title">${t(cfg.title)}</span>${addBtn}</div>
          <div class="card"><div class="table-wrapper"><table><thead>${thead}</thead><tbody>${tbody}</tbody></table></div></div>`;
}

// ===== Entity modal (generic) =====
function openEntityModal(key, record) {
  const cfg = ENTITIES[key];
  const ctx = { ...ws, subcontractors: allSubcontractors, equipment: allEquipment };
  const fieldsHtml = cfg.fields.map((f) => {
    const val = record ? (record[f.name] !== undefined && record[f.name] !== null ? record[f.name] : "") : (f.default !== undefined ? f.default : "");
    let inputHtml;
    if (f.type === "select") {
      const options = typeof f.options === "function" ? f.options(ctx) : f.options;
      const opts = (f.placeholder ? `<option value="">${escapeHtml(t(f.placeholder))}</option>` : "")
        + options.map((o) => `<option value="${o.value}" ${String(val) === String(o.value) ? "selected" : ""}>${escapeHtml(o.label)}</option>`).join("");
      inputHtml = `<select id="ef-${f.name}">${opts}</select>`;
    } else if (f.type === "textarea") {
      inputHtml = `<textarea id="ef-${f.name}" rows="${f.rows || 3}">${escapeHtml(val)}</textarea>`;
    } else {
      inputHtml = `<input type="${f.type}" id="ef-${f.name}" value="${escapeHtml(val)}" ${f.step ? `step="${f.step}"` : ""} ${f.max ? `max="${f.max}"` : ""} ${f.min ? `min="${f.min}"` : ""}>`;
    }
    const wide = f.wide ? " style=\"grid-column:1/-1;\"" : "";
    return `<div class="form-group"${wide}><label>${t(f.label)}${f.required ? " *" : ""}</label>${inputHtml}</div>`;
  }).join("");

  const title = record ? t("common.edit") : t(cfg.newBtn);
  const modal = document.getElementById("entity-modal");
  modal.innerHTML = `<div class="modal">
    <div class="modal-header">
      <h3>${title}</h3>
      <button class="modal-close" onclick="closeEntityModal()">✕</button>
    </div>
    <div class="modal-body">
      <input type="hidden" id="ef-id" value="${record ? record.id : ""}">
      <div class="entity-form-grid">${fieldsHtml}</div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-primary" onclick="saveEntity('${key}')">${t("common.save")}</button>
      <button class="btn btn-outline" onclick="closeEntityModal()">${t("common.cancel")}</button>
    </div>
  </div>`;
  modal.style.display = "flex";
}

function closeEntityModal() {
  document.getElementById("entity-modal").style.display = "none";
}

async function saveEntity(key) {
  const cfg = ENTITIES[key];
  const id = document.getElementById("ef-id").value;
  const body = {};
  for (const f of cfg.fields) {
    const el = document.getElementById("ef-" + f.name);
    if (!el) continue;
    const raw = el.value;
    if (f.type === "number") {
      body[f.name] = raw === "" ? "" : Number(raw);
    } else if (f.type === "date") {
      body[f.name] = raw === "" ? "" : raw;
    } else if (f.name === "parent_id" || f.name === "wbs_id" || f.name === "boq_id" || f.name === "contract_id" || f.name === "subcontractor_id" || f.name === "employee_id" || f.name === "project_id") {
      body[f.name] = raw === "" ? "" : Number(raw);
    } else {
      body[f.name] = raw;
    }
    if (f.required && (raw === "" || raw === undefined)) {
      showToast(t("common.required") + " : " + t(f.label), "warning");
      return;
    }
  }

  try {
    const pid = ws.project.id;
    let url, method;
    if (id) {
      url = cfg.itemApi ? cfg.itemApi(pid, id, body) : `${cfg.api(pid)}/${id}`;
      method = "PUT";
    } else {
      url = cfg.createApi ? cfg.createApi(pid, body) : cfg.api(pid);
      method = "POST";
    }
    await api.request(url, method, body);
    showToast(t("common.savedSuccess"));
    closeEntityModal();
    await refreshAllData();
    renderTab(currentTab);
    renderWorkspaceHeader();
    renderWorkspaceSummary();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteEntity(key, id) {
  const cfg = ENTITIES[key];
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    const pid = ws.project.id;
    const rec = (key === "equipment" ? ws.equipment : (key === "subcontractors" ? allSubcontractors : ws[key])).find((r) => r.id === id);
    let url = cfg.itemApi && rec ? cfg.itemApi(pid, id, rec) : `${cfg.api(pid)}/${id}`;
    await api.delete(url);
    showToast(t("common.deleted"));
    await refreshAllData();
    renderTab(currentTab);
    renderWorkspaceHeader();
    renderWorkspaceSummary();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ===== Price analysis modal =====
let currentBoq = null;

async function openAnalysisModal(boqId, label) {
  currentBoq = { id: boqId, label: label || "" };
  const items = await api.get(`/api/projects/boq/${boqId}/analysis`);
  const total = items.reduce((s, i) => s + (Number(i.amount) || 0), 0);
  const modal = document.getElementById("entity-modal");
  const rows = items.length
    ? items.map((i) => `<tr>
        <td>${escapeHtml(i.description)}</td>
        <td>${escapeHtml(i.unit || "—")}</td>
        <td>${Number(i.quantity) || 0}</td>
        <td>${formatMoney(Number(i.rate) || 0)}</td>
        <td>${formatMoney(Number(i.amount) || 0)}</td>
        <td>${escapeHtml(pv(i.cost_type))}</td>
        <td><button class="btn btn-danger btn-sm" onclick="deleteAnalysisItem(${i.id})">${t("common.delete")}</button></td>
      </tr>`).join("")
    : `<tr><td colspan="7"><div class="empty-state">${t("projects.noAnalysis")}</div></td></tr>`;
  modal.innerHTML = `<div class="modal" style="max-width:760px;">
    <div class="modal-header">
      <h3>${t("projects.analysisComponents")} — ${escapeHtml(currentBoq.label)}</h3>
      <button class="modal-close" onclick="closeEntityModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="panel-toolbar">
        <span style="color:var(--muted-foreground);">${t("projects.totalPrice")}: <strong style="color:var(--primary);">${formatMoney(total)}</strong></span>
        <button class="btn btn-primary btn-sm" onclick="openAnalysisForm()">${t("projects.addComponent")}</button>
      </div>
      <div class="table-wrapper"><table>
        <thead><tr><th>${t("projects.component")}</th><th>${t("common.unit")}</th><th>${t("projects.quantity")}</th><th>${t("projects.rate")}</th><th>${t("common.amount")}</th><th>${t("projects.costType")}</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
      <div id="analysis-form" style="display:none;margin-top:14px;"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeEntityModal()">${t("common.close")}</button>
    </div>
  </div>`;
  modal.style.display = "flex";
}

function openAnalysisForm() {
  const box = document.getElementById("analysis-form");
  box.innerHTML = `<div class="card" style="padding:16px;">
    <div class="form-row">
      <div class="form-group"><label>${t("projects.component")} *</label><input type="text" id="ai-desc"></div>
      <div class="form-group"><label>${t("common.unit")}</label><input type="text" id="ai-unit"></div>
      <div class="form-group"><label>${t("projects.quantity")}</label><input type="number" id="ai-qty" min="0" step="0.001" value="0"></div>
      <div class="form-group"><label>${t("projects.rate")}</label><input type="number" id="ai-rate" min="0" step="0.01" value="0"></div>
      <div class="form-group"><label>${t("projects.costType")}</label>
        <select id="ai-type">${COST_TYPES.map((s) => `<option value="${s}">${escapeHtml(pv(s))}</option>`).join("")}</select>
      </div>
    </div>
    <div class="form-actions" style="margin-top:10px;display:flex;gap:8px;">
      <button class="btn btn-primary btn-sm" onclick="saveAnalysisItem()">${t("common.save")}</button>
      <button class="btn btn-outline btn-sm" onclick="document.getElementById('analysis-form').innerHTML=''">${t("common.cancel")}</button>
    </div>
  </div>`;
  box.style.display = "block";
}

async function saveAnalysisItem() {
  const desc = document.getElementById("ai-desc").value;
  if (!desc) { showToast(t("common.required"), "warning"); return; }
  const body = {
    boq_id: currentBoq.id,
    description: desc,
    unit: document.getElementById("ai-unit").value,
    quantity: Number(document.getElementById("ai-qty").value) || 0,
    rate: Number(document.getElementById("ai-rate").value) || 0,
    cost_type: document.getElementById("ai-type").value,
  };
  try {
    await api.post(`/api/projects/boq/${currentBoq.id}/analysis`, body);
    showToast(t("common.savedSuccess"));
    await openAnalysisModal(currentBoq.id, currentBoq.label);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteAnalysisItem(id) {
  if (!confirm(t("projects.confirmDelete"))) return;
  try {
    await api.delete(`/api/projects/boq/${currentBoq.id}/analysis/${id}`);
    showToast(t("common.deleted"));
    await openAnalysisModal(currentBoq.id, currentBoq.label);
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ===== Overview tab =====
function renderOverview() {
  const s = ws.summary;
  const recentProgress = (ws.progress || []).slice(0, 8);
  const recentExec = (ws.execution || []).slice(0, 8);
  const recentCosts = (ws.costs || []).slice(0, 8);

  const progressRows = recentProgress.length
    ? recentProgress.map((r) => `<tr><td>${fmtDate(r.record_date)}</td><td>${escapeHtml(r.boq_desc || t("projects.overview"))}</td><td>${progressCell(r.percentage)}</td><td>${escapeHtml(r.note || "")}</td></tr>`).join("")
    : emptyState(t("projects.noProgress"));

  const execRows = recentExec.length
    ? recentExec.map((r) => `<tr><td>${fmtDate(r.log_date)}</td><td><strong>${escapeHtml(r.activity)}</strong></td><td>${pmBadge(r.status)}</td><td>${escapeHtml(r.responsible || "—")}</td></tr>`).join("")
    : emptyState(t("projects.noExecution"));

  const costRows = recentCosts.length
    ? recentCosts.map((r) => `<tr><td>${fmtDate(r.cost_date)}</td><td>${escapeHtml(pv(r.category))}</td><td>${escapeHtml(r.description)}</td><td>${formatMoney(Number(r.amount) || 0)}</td></tr>`).join("")
    : emptyState(t("projects.noCosts"));

  const el = document.getElementById("tab-overview");
  el.innerHTML = `
    <div class="stats-grid" style="margin-bottom:16px;">
      ${statCard("🎯", t("projects.totalBudget"), formatMoney(s.project.budget), t("projects.remaining") + ": " + formatMoney(Math.max(0, (s.project.budget || 0) - (s.project.spent || 0))))}
      ${statCard("💰", t("projects.totalCosts"), formatMoney(s.costs_total), t("projects.contractsValue") + ": " + formatMoney(s.contracts_total))}
      ${statCard("📋", t("projects.boqValue"), formatMoney(s.boq_total), s.boq_count + " " + t("projects.boqCount"))}
      ${statCard("🏗️", t("projects.execProgress"), (s.exec_total ? Math.round((s.exec_done / s.exec_total) * 100) : 0) + "%", s.exec_done + " / " + s.exec_total)}
      ${statCard("📅", t("projects.phases"), s.phase_count, t("projects.completionLabel") + ": " + s.phase_avg + "%")}
      ${statCard("⚠️", t("projects.risksOpen"), s.risks_open, "")}
      ${statCard("👷", t("projects.laborActive"), s.labor_active, "")}
      ${statCard("📍", t("projects.sitesCount"), s.sites_count, "")}
    </div>
    <div class="stats-grid" style="grid-template-columns:1fr 1fr;">
      <div class="card">
        <div class="panel-title" style="padding:14px 16px 0;">${t("projects.progress")}</div>
        <div class="table-wrapper" style="margin-top:6px;"><table>
          <thead><tr><th>${t("projects.recordDate")}</th><th>${t("projects.selectBoqItem")}</th><th>${t("projects.percentage")}</th><th>${t("projects.notes")}</th></tr></thead>
          <tbody>${progressRows}</tbody>
        </table></div>
      </div>
      <div class="card">
        <div class="panel-title" style="padding:14px 16px 0;">${t("projects.execution")}</div>
        <div class="table-wrapper" style="margin-top:6px;"><table>
          <thead><tr><th>${t("common.date")}</th><th>${t("projects.activity")}</th><th>${t("common.status")}</th><th>${t("projects.responsible")}</th></tr></thead>
          <tbody>${execRows}</tbody>
        </table></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="panel-title" style="padding:14px 16px 0;">${t("projects.costs")} — ${t("projects.totalCosts")}: ${formatMoney(s.costs_total)}</div>
      <div class="table-wrapper" style="margin-top:6px;"><table>
        <thead><tr><th>${t("common.date")}</th><th>${t("projects.costCategory")}</th><th>${t("common.description")}</th><th>${t("common.amount")}</th></tr></thead>
        <tbody>${costRows}</tbody>
      </table></div>
    </div>`;
}

function statCard(icon, label, value, sub) {
  return `<div class="stat-card">
    <div class="stat-icon" style="background:var(--primary-tint);color:var(--primary);">${icon}</div>
    <div class="stat-info">
      <div class="stat-label">${label}</div>
      <div class="stat-value">${value}</div>
      ${sub ? `<div class="stat-label" style="margin-top:2px;">${sub}</div>` : ""}
    </div>
  </div>`;
}

// ===== Workspace header + summary =====
function renderWorkspaceHeader() {
  const p = ws.project;
  const manager = allEmployees.find((e) => e.id === p.manager_id);
  document.getElementById("ws-project-name").textContent = p.name || "—";
  document.getElementById("ws-project-badges").innerHTML =
    `<span class="badge badge-info">${pmBadge(p.status)}</span>` +
    `<span class="badge badge-info">${t("common.priority")}: ${pv(p.priority)}</span>` +
    (p.location ? `<span class="badge badge-info">📍 ${escapeHtml(p.location)}</span>` : "");
  document.getElementById("ws-project-meta").textContent =
    (manager ? t("projects.managerLabel") + ": " + manager.full_name + " · " : "") +
    (p.start_date ? t("common.start") + ": " + p.start_date + " · " : "") +
    (p.deadline ? t("projects.deadlineLabel") + ": " + p.deadline : "");
}

function renderWorkspaceSummary() {
  const s = ws.summary;
  const p = s.project;
  const remaining = Math.max(0, (p.budget || 0) - (p.spent || 0));
  const box = document.getElementById("ws-summary");
  box.innerHTML = `
    ${wsKpi(t("common.budget"), formatMoney(p.budget), t("projects.remaining") + ": " + formatMoney(remaining))}
    ${wsKpi(t("projects.totalCosts"), formatMoney(s.costs_total), t("common.spent"))}
    ${wsKpi(t("projects.contractsValue"), formatMoney(s.contracts_total), t("projects.contracts") + ": " + s.contracts_count)}
    ${wsKpi(t("projects.boqValue"), formatMoney(s.boq_total), t("projects.boq") + ": " + s.boq_count)}
    ${wsKpi(t("common.completion"), p.completion + "%", t("projects.phases") + ": " + s.phase_avg + "%")}
  `;
}

function wsKpi(label, value, sub) {
  return `<div class="ws-kpi"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-sub">${sub}</div></div>`;
}

async function editWorkspaceProject() {
  editProject(ws.project);
}

// ===== Export project report =====
function exportProjectReport() {
  const p = ws.project;
  const rows = [];
  const push = (section, cells) => rows.push([section, ...cells]);

  push(t("projects.title"), [t("projects.nameLabel"), p.name]);
  push("", [t("common.status"), pv(p.status)]);
  push("", [t("common.budget"), p.budget]);
  push("", [t("common.spent"), p.spent]);
  push("", [t("common.completion"), p.completion + "%"]);
  push("", [t("projects.managerLabel"), (() => { const m = allEmployees.find((e) => e.id === p.manager_id); return m ? m.full_name : ""; })()]);

  ws.phases.forEach((r) => push(t("projects.phases"), [r.name, pv(r.status), r.completion + "%", r.budget]));
  ws.wbs.forEach((r) => push(t("projects.wbs"), [r.code, r.name, pv(r.type)]));
  ws.boq.forEach((r) => push(t("projects.boq"), [r.code, r.description, r.unit, r.quantity, r.unit_price, r.total, pv(r.category), pv(r.status)]));
  ws.contracts.forEach((r) => push(t("projects.contracts"), [r.contract_no, r.title, pv(r.contract_type), r.party_name, r.contract_value, pv(r.status)]));
  ws.statements.forEach((r) => push(t("projects.statements"), [r.statement_no, r.contract_no, r.statement_date, r.work_value, r.net_value, r.cumulative_total, pv(r.status)]));
  ws.changeOrders.forEach((r) => push(t("projects.changeOrders"), [r.change_no, r.description, pv(r.change_type), r.amount, r.change_date, pv(r.status)]));
  ws.costs.forEach((r) => push(t("projects.costs"), [r.cost_date, pv(r.category), r.description, r.amount]));
  ws.risks.forEach((r) => push(t("projects.risks"), [r.description, pv(r.probability), pv(r.impact), pv(r.level), pv(r.status)]));
  ws.quality.forEach((r) => push(t("projects.quality"), [r.check_date, pv(r.check_type), r.description, pv(r.result), pv(r.status)]));
  ws.labor.forEach((r) => push(t("projects.labor"), [r.name, r.trade, r.start_date, r.end_date, r.daily_rate, pv(r.status)]));

  exportCSV("project-" + (p.name || p.id) + ".csv", [t("projects.projectSummary")], rows);
}

// Expose
window.openProject = openProject;
window.closeWorkspace = closeWorkspace;
window.switchTab = switchTab;
window.openProjectModal = openProjectModal;
window.closeProjectModal = closeProjectModal;
window.editProject = editProject;
window.deleteProject = deleteProject;
window.saveProject = saveProject;
window.openEntityModal = openEntityModal;
window.closeEntityModal = closeEntityModal;
window.saveEntity = saveEntity;
window.deleteEntity = deleteEntity;
window.openAnalysisModal = openAnalysisModal;
window.openAnalysisForm = openAnalysisForm;
window.saveAnalysisItem = saveAnalysisItem;
window.deleteAnalysisItem = deleteAnalysisItem;
window.editWorkspaceProject = editWorkspaceProject;
window.exportProjectReport = exportProjectReport;
window.exportProjects = exportProjects;

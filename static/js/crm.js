/* ============================================================
   CRM Module JavaScript — Full Tabbed Interface
   ============================================================ */

const CRM_API = "/api/crm";

let allCustomers = [];
let allEmployees = [];
let allLeads = [];
let allStages = [];
let allOpportunities = [];
let allCalls = [];
let allMeetings = [];
let allTasks = [];
let allCampaigns = [];
let allCampaignLeads = [];
let allFollowUps = [];
let allQuotes = [];
let allContracts = [];
let allComplaints = [];
let allTickets = [];

const CRM_STATUS_KEYS = {
  new: "crm.leadStatus.new",
  contacted: "crm.leadStatus.contacted",
  qualified: "crm.leadStatus.qualified",
  unqualified: "crm.leadStatus.unqualified",
  won: "crm.won",
  lost: "crm.lost",
  open: "crm.open",
  closed: "crm.closed",
  scheduled: "crm.scheduled",
  done: "crm.done",
  cancelled: "crm.cancelled",
  pending: "crm.pending",
  in_progress: "crm.inProgress",
  resolved: "crm.resolved",
  planned: "crm.planned",
  active: "crm.active",
  completed: "crm.completed",
  draft: "crm.draft",
  sent: "crm.sent",
  accepted: "crm.accepted",
  rejected: "crm.rejected",
  expired: "crm.expired",
  terminated: "crm.terminated",
  overdue: "crm.overdue",
};

const CRM_STATUS_CLS = {
  new: "badge-primary", contacted: "badge-info", qualified: "badge-success",
  unqualified: "badge-neutral", won: "badge-success", lost: "badge-danger",
  open: "badge-warning", closed: "badge-neutral", scheduled: "badge-info",
  done: "badge-success", cancelled: "badge-danger", pending: "badge-warning",
  in_progress: "badge-info", resolved: "badge-success", planned: "badge-info",
  active: "badge-success", completed: "badge-primary", draft: "badge-neutral",
  sent: "badge-info", accepted: "badge-success", rejected: "badge-danger",
  expired: "badge-danger", terminated: "badge-danger", overdue: "badge-danger",
};

function crmStatusBadge(status) {
  return `<span class="badge ${CRM_STATUS_CLS[status] || "badge-neutral"}">${t(CRM_STATUS_KEYS[status] || status)}</span>`;
}

function priorityBadge(p) {
  const cls = { low: "badge-neutral", medium: "badge-warning", high: "badge-danger" }[p] || "badge-neutral";
  const key = p === "low" || p === "medium" || p === "high" ? `crm.priority.${p}` : p;
  return `<span class="badge ${cls}">${t(key)}</span>`;
}

function leadSourceBadge(src) {
  return `<span class="badge badge-neutral">${t(`crm.source.${src}`)}</span>`;
}

function closeModal(id) {
  document.getElementById(id).classList.remove("active");
}
window.closeModal = closeModal;

function modal(id) { document.getElementById(id).classList.add("active"); }

function empName(id) {
  const e = allEmployees.find((x) => x.id === Number(id));
  return e ? escapeHtml(e.full_name) : "—";
}
function custName(id) {
  const c = allCustomers.find((x) => x.id === Number(id));
  return c ? escapeHtml(c.full_name) : "—";
}
function leadName(id) {
  const l = allLeads.find((x) => x.id === Number(id));
  return l ? escapeHtml(l.full_name) : "—";
}
function stageName(id) {
  const s = allStages.find((x) => x.id === Number(id));
  return s ? escapeHtml(s.name) : "—";
}
function oppName(id) {
  const o = allOpportunities.find((x) => x.id === Number(id));
  return o ? escapeHtml(o.title) : "—";
}

function buildEmployeeOptions(selected) {
  return `<option value="">${t("common.choose")}</option>` +
    allEmployees.map((e) => `<option value="${e.id}" ${Number(selected) === e.id ? "selected" : ""}>${escapeHtml(e.full_name)}</option>`).join("");
}
function buildCustomerOptions(selected) {
  return `<option value="">${t("common.choose")}</option>` +
    allCustomers.map((c) => `<option value="${c.id}" ${Number(selected) === c.id ? "selected" : ""}>${escapeHtml(c.full_name)}</option>`).join("");
}
function buildLeadOptions(selected) {
  return `<option value="">${t("common.choose")}</option>` +
    allLeads.map((l) => `<option value="${l.id}" ${Number(selected) === l.id ? "selected" : ""}>${escapeHtml(l.full_name)}</option>`).join("");
}
function buildStageOptions(selected) {
  return `<option value="">${t("common.choose")}</option>` +
    allStages.map((s) => `<option value="${s.id}" ${Number(selected) === s.id ? "selected" : ""}>${escapeHtml(s.name)}</option>`).join("");
}
function buildOpportunityOptions(selected) {
  return `<option value="">${t("common.choose")}</option>` +
    allOpportunities.map((o) => `<option value="${o.id}" ${Number(selected) === o.id ? "selected" : ""}>${escapeHtml(o.title)}</option>`).join("");
}

function populateModalSelects() {
  const set = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };

  const empOpts = buildEmployeeOptions();
  ["lead-owner", "opportunity-owner", "call-employee", "meeting-employee", "task-employee", "campaign-owner", "followup-employee", "complaint-assigned", "ticket-assigned"].forEach((id) => set(id, empOpts));

  const custOpts = buildCustomerOptions();
  ["opportunity-customer", "call-customer", "meeting-customer", "task-customer", "followup-customer", "quote-customer", "contract-customer", "complaint-customer", "ticket-customer"].forEach((id) => set(id, custOpts));

  const leadOpts = buildLeadOptions();
  ["opportunity-lead", "call-lead", "meeting-lead", "task-lead", "followup-lead", "quote-lead", "campaign-leads-lead"].forEach((id) => set(id, leadOpts));

  set("opportunity-stage", buildStageOptions());
  set("task-opportunity", buildOpportunityOptions());
  set("followup-opportunity", buildOpportunityOptions());
  set("quote-opportunity", buildOpportunityOptions());

  set("campaign-leads-campaign", `<option value="">${t("common.choose")}</option>` + allCampaigns.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join(""));

  set("lead-source", `<option value="website">${t("crm.source.website")}</option>` +
    `<option value="facebook">${t("crm.source.facebook")}</option>` +
    `<option value="call">${t("crm.source.call")}</option>` +
    `<option value="walk_in">${t("crm.source.walk_in")}</option>` +
    `<option value="referral">${t("crm.source.referral")}</option>` +
    `<option value="other">${t("crm.source.other")}</option>`);

  set("lead-status", `<option value="new">${t("crm.leadStatus.new")}</option>` +
    `<option value="contacted">${t("crm.leadStatus.contacted")}</option>` +
    `<option value="qualified">${t("crm.leadStatus.qualified")}</option>` +
    `<option value="unqualified">${t("crm.leadStatus.unqualified")}</option>` +
    `<option value="won">${t("crm.leadStatus.won")}</option>` +
    `<option value="lost">${t("crm.leadStatus.lost")}</option>`);

  set("campaign-channel", `<option value="email">${t("crm.channel.email")}</option>` +
    `<option value="sms">${t("crm.channel.sms")}</option>` +
    `<option value="social">${t("crm.channel.social")}</option>` +
    `<option value="call">${t("crm.channel.call")}</option>` +
    `<option value="other">${t("crm.channel.other")}</option>`);

  set("followup-action", `<option value="call">${t("crm.action.call")}</option>` +
    `<option value="meeting">${t("crm.action.meeting")}</option>` +
    `<option value="email">${t("crm.action.email")}</option>` +
    `<option value="whatsapp">${t("crm.action.whatsapp")}</option>` +
    `<option value="visit">${t("crm.action.visit")}</option>`);
}

// ============ TAB SCROLL LINKS ============
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("#crm-tabs a.tab-btn").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const target = document.querySelector(link.getAttribute("href"));
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", link.getAttribute("href"));
      }
    });
  });
  loadAll();
});

async function loadAll() {
  try {
    const [customers, employees, leads, stages, opportunities, calls, meetings, tasks, campaigns, campaignLeads, followUps, quotes, contracts, complaints, tickets] = await Promise.all([
      api.get("/api/customers"),
      api.get("/api/employees"),
      api.get(`${CRM_API}/leads`),
      api.get(`${CRM_API}/stages`),
      api.get(`${CRM_API}/opportunities`),
      api.get(`${CRM_API}/calls`),
      api.get(`${CRM_API}/meetings`),
      api.get(`${CRM_API}/tasks`),
      api.get(`${CRM_API}/campaigns`),
      api.get(`${CRM_API}/campaign-leads`),
      api.get(`${CRM_API}/follow-ups`),
      api.get(`${CRM_API}/quotes`),
      api.get(`${CRM_API}/contracts`),
      api.get(`${CRM_API}/complaints`),
      api.get(`${CRM_API}/tickets`),
    ]);
    allCustomers = customers;
    allEmployees = employees;
    allLeads = leads;
    allStages = stages;
    allOpportunities = opportunities;
    allCalls = calls;
    allMeetings = meetings;
    allTasks = tasks;
    allCampaigns = campaigns;
    allCampaignLeads = campaignLeads;
    allFollowUps = followUps;
    allQuotes = quotes;
    allContracts = contracts;
    allComplaints = complaints;
    allTickets = tickets;
    populateModalSelects();
    renderAll();
    loadSummary();
  } catch (err) {
    console.error(err);
  }
}

function renderAll() {
  renderCustomers();
  renderLeads();
  renderOpportunities();
  renderPipeline();
  renderCalls();
  renderMeetings();
  renderTasks();
  renderCampaigns();
  renderFollowUps();
  renderQuotes();
  renderContracts();
  renderComplaints();
  renderTickets();
}

async function loadSummary() {
  try {
    const s = await api.get(`${CRM_API}/summary`);
    const fmt = (el, v, money) => {
      const node = document.getElementById(el);
      if (node) animateCount(node, v, money ? formatMoney : formatNumber);
    };
    fmt("kpi-customers", s.customers_count);
    fmt("kpi-leads", s.leads_open, false);
    fmt("kpi-opportunities", s.opportunities_open);
    fmt("kpi-pipeline", s.pipeline_total, true);
    fmt("kpi-won", s.won_total, true);
    fmt("kpi-followups", s.follow_ups_pending);
    fmt("kpi-quotes", s.quotes_count);
    fmt("kpi-contracts", s.contracts_count);
    fmt("kpi-complaints", s.complaints_open);
    fmt("kpi-tickets", s.tickets_open);
    fmt("kpi-meetings", s.meetings_today);
    fmt("kpi-overdue", s.follow_ups_overdue);
  } catch (err) {
    console.error(err);
  }
}

// ============ CUSTOMERS ============
function renderCustomers() {
  const tbody = document.getElementById("customers-table");
  if (!allCustomers.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">${t("crm.noCustomers") || t("common.noResults")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allCustomers.map((c) => `
    <tr>
      <td><strong>${escapeHtml(c.full_name)}</strong></td>
      <td>${escapeHtml(c.phone || "—")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(c.email || "—")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(c.company || "—")}</td>
      <td>${t(c.type === "company" ? "crm.companyType" : "crm.individual")}</td>
      <td>${c.is_active === false ? `<span class="badge badge-neutral">${t("crm.cancelled")}</span>` : `<span class="badge badge-success">${t("crm.active")}</span>`}</td>
      <td>
        <div class="table-actions">
          ${canAction("sales", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editCustomer(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
          ${canAction("sales", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteCustomer(${c.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function openCustomerModal() {
  document.getElementById("customer-modal-title").textContent = `${t("crm.new")} ${t("crm.tabCustomers")}`;
  document.getElementById("customer-id").value = "";
  ["customer-name", "customer-phone", "customer-email", "customer-company", "customer-address", "customer-notes"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("customer-type").value = "individual";
  modal("customer-modal");
}
function editCustomer(c) {
  document.getElementById("customer-modal-title").textContent = `${t("crm.tabCustomers")}`;
  document.getElementById("customer-id").value = c.id;
  document.getElementById("customer-name").value = c.full_name || "";
  document.getElementById("customer-type").value = c.type || "individual";
  document.getElementById("customer-phone").value = c.phone || "";
  document.getElementById("customer-email").value = c.email || "";
  document.getElementById("customer-company").value = c.company || "";
  document.getElementById("customer-address").value = c.address || "";
  document.getElementById("customer-notes").value = c.notes || "";
  modal("customer-modal");
}
async function saveCustomer() {
  const id = document.getElementById("customer-id").value;
  const body = {
    full_name: document.getElementById("customer-name").value.trim(),
    type: document.getElementById("customer-type").value,
    phone: document.getElementById("customer-phone").value.trim(),
    email: document.getElementById("customer-email").value.trim(),
    company: document.getElementById("customer-company").value.trim(),
    address: document.getElementById("customer-address").value.trim(),
    notes: document.getElementById("customer-notes").value,
    is_active: true,
  };
  if (!body.full_name) { showToast(t("crm.errorName"), "error"); return; }
  try {
    if (id) { await api.put(`/api/customers/${id}`, body); }
    else { await api.post("/api/customers", body); }
    closeModal("customer-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function deleteCustomer(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  try {
    await api.delete(`/api/customers/${id}`);
    showToast(t("crm.deleted"));
    await loadAll();
  } catch (e) {
    showToast(t("crm.customerDeleted"), "error");
  }
}

// ============ LEADS ============
function renderLeads() {
  const tbody = document.getElementById("leads-table");
  if (!allLeads.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${t("crm.noLeads")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allLeads.map((l) => `
    <tr>
      <td><strong>${escapeHtml(l.full_name)}</strong></td>
      <td>${escapeHtml(l.phone || "—")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(l.company || "—")}</td>
      <td>${leadSourceBadge(l.source)}</td>
      <td>${crmStatusBadge(l.status)}</td>
      <td style="color:var(--muted-foreground);">${l.owner_name || "—"}</td>
      <td><strong>${formatMoney(l.budget)}</strong></td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editLead(${JSON.stringify(l)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "create") && !["won", "lost"].includes(l.status) ? `<button class="btn btn-primary btn-sm" onclick="convertLead(${l.id})">${t("crm.convert")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteLead(${l.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function openLeadModal() {
  document.getElementById("lead-modal-title").textContent = t("crm.addLead");
  document.getElementById("lead-id").value = "";
  ["lead-name", "lead-phone", "lead-email", "lead-company", "lead-budget", "lead-city", "lead-notes"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("lead-source").value = "website";
  document.getElementById("lead-status").value = "new";
  document.getElementById("lead-owner").value = "";
  modal("lead-modal");
}
function editLead(l) {
  document.getElementById("lead-modal-title").textContent = t("crm.editLead");
  document.getElementById("lead-id").value = l.id;
  document.getElementById("lead-name").value = l.full_name || "";
  document.getElementById("lead-phone").value = l.phone || "";
  document.getElementById("lead-email").value = l.email || "";
  document.getElementById("lead-company").value = l.company || "";
  document.getElementById("lead-source").value = l.source || "website";
  document.getElementById("lead-status").value = l.status || "new";
  document.getElementById("lead-owner").value = l.owner_id || "";
  document.getElementById("lead-budget").value = l.budget || "";
  document.getElementById("lead-city").value = l.city || "";
  document.getElementById("lead-notes").value = l.notes || "";
  modal("lead-modal");
}
async function saveLead() {
  const id = document.getElementById("lead-id").value;
  const body = {
    full_name: document.getElementById("lead-name").value.trim(),
    phone: document.getElementById("lead-phone").value.trim(),
    email: document.getElementById("lead-email").value.trim(),
    company: document.getElementById("lead-company").value.trim(),
    source: document.getElementById("lead-source").value,
    status: document.getElementById("lead-status").value,
    owner_id: document.getElementById("lead-owner").value || null,
    budget: parseFloat(document.getElementById("lead-budget").value) || 0,
    city: document.getElementById("lead-city").value.trim(),
    notes: document.getElementById("lead-notes").value,
  };
  if (!body.full_name) { showToast(t("crm.errorName"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/leads/${id}`, body); }
    else { await api.post(`${CRM_API}/leads`, body); }
    closeModal("lead-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function convertLead(id) {
  const l = allLeads.find((x) => x.id === id);
  if (!confirm(`${t("crm.convertLead")}: ${l ? l.full_name : ""}?`)) return;
  try {
    await api.post(`${CRM_API}/leads/${id}/convert`, {});
    showToast(t("crm.converted"));
    await loadAll();
  } catch (e) { showToast(t("crm.convertError"), "error"); }
}
async function deleteLead(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  try {
    await api.delete(`${CRM_API}/leads/${id}`);
    showToast(t("crm.deleted"));
    await loadAll();
  } catch (e) { showToast(t("crm.cannotDelete"), "error"); }
}

// ============ OPPORTUNITIES ============
function renderOpportunities() {
  const tbody = document.getElementById("opportunities-table");
  if (!allOpportunities.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state">${t("crm.noOpportunities")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allOpportunities.map((o) => `
    <tr>
      <td><strong>${escapeHtml(o.title)}</strong></td>
      <td style="color:var(--muted-foreground);">${o.customer_name || "—"}</td>
      <td><strong>${formatMoney(o.amount)}</strong></td>
      <td>${stageName(o.stage_id)}</td>
      <td>${o.probability || 0}%</td>
      <td style="color:var(--muted-foreground);">${formatDate(o.expected_close_date)}</td>
      <td style="color:var(--muted-foreground);">${o.owner_name || "—"}</td>
      <td>${crmStatusBadge(o.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editOpportunity(${JSON.stringify(o)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "edit") && o.status === "open" ? `<button class="btn btn-success btn-sm" onclick="winOpportunity(${o.id})">${t("crm.win")}</button><button class="btn btn-danger btn-sm" onclick="loseOpportunity(${o.id})">${t("crm.lose")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteOpportunity(${o.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function openOpportunityModal() {
  document.getElementById("opportunity-modal-title").textContent = t("crm.addOpportunity");
  document.getElementById("opportunity-id").value = "";
  ["opportunity-title", "opportunity-amount", "opportunity-probability", "opportunity-close", "opportunity-notes"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("opportunity-stage").value = "";
  document.getElementById("opportunity-customer").value = "";
  document.getElementById("opportunity-lead").value = "";
  document.getElementById("opportunity-owner").value = "";
  modal("opportunity-modal");
}
function editOpportunity(o) {
  document.getElementById("opportunity-modal-title").textContent = t("crm.editOpportunity");
  document.getElementById("opportunity-id").value = o.id;
  document.getElementById("opportunity-title").value = o.title || "";
  document.getElementById("opportunity-amount").value = o.amount || "";
  document.getElementById("opportunity-stage").value = o.stage_id || "";
  document.getElementById("opportunity-probability").value = o.probability || "";
  document.getElementById("opportunity-customer").value = o.customer_id || "";
  document.getElementById("opportunity-lead").value = o.lead_id || "";
  document.getElementById("opportunity-owner").value = o.owner_id || "";
  document.getElementById("opportunity-close").value = o.expected_close_date || "";
  document.getElementById("opportunity-notes").value = o.notes || "";
  modal("opportunity-modal");
}
async function saveOpportunity() {
  const id = document.getElementById("opportunity-id").value;
  const stageId = document.getElementById("opportunity-stage").value;
  const body = {
    title: document.getElementById("opportunity-title").value.trim(),
    amount: parseFloat(document.getElementById("opportunity-amount").value) || 0,
    stage_id: stageId || null,
    probability: parseFloat(document.getElementById("opportunity-probability").value) || 0,
    customer_id: document.getElementById("opportunity-customer").value || null,
    lead_id: document.getElementById("opportunity-lead").value || null,
    owner_id: document.getElementById("opportunity-owner").value || null,
    expected_close_date: document.getElementById("opportunity-close").value || null,
    notes: document.getElementById("opportunity-notes").value,
    status: "open",
  };
  if (!body.title) { showToast(t("crm.errorTitle"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/opportunities/${id}`, body); }
    else { await api.post(`${CRM_API}/opportunities`, body); }
    closeModal("opportunity-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function winOpportunity(id) { await api.post(`${CRM_API}/opportunities/${id}/win`, {}); showToast(t("crm.saved")); await loadAll(); }
async function loseOpportunity(id) { await api.post(`${CRM_API}/opportunities/${id}/lose`, {}); showToast(t("crm.saved")); await loadAll(); }
async function deleteOpportunity(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  try { await api.delete(`${CRM_API}/opportunities/${id}`); showToast(t("crm.deleted")); await loadAll(); }
  catch (e) { showToast(t("crm.convertError"), "error"); }
}

// ============ PIPELINE ============
function renderPipeline() {
  const board = document.getElementById("pipeline-board");
  const openOpps = allOpportunities.filter((o) => o.status === "open");
  const sorted = allStages.slice().sort((a, b) => a.position - b.position);
  if (!sorted.length) {
    board.innerHTML = `<div class="card"><div class="empty-state">${t("crm.noStages")}</div></div>`;
    return;
  }
  board.innerHTML = sorted.map((st, idx) => {
    const cards = openOpps.filter((o) => o.stage_id === st.id);
    const total = cards.reduce((s, o) => s + (o.amount || 0), 0);
    return `
    <div class="pipeline-col">
      <div class="pipeline-col-header">
        <span>${escapeHtml(st.name)}</span>
        <span class="count">${cards.length} · ${formatMoney(total)}</span>
      </div>
      ${cards.map((o) => {
        const prob = o.probability || st.probability || 0;
        const prev = sorted[idx - 1];
        const next = sorted[idx + 1];
        return `
        <div class="pipeline-card">
          <div class="pc-title">${escapeHtml(o.title)}</div>
          <div class="pc-amount">${formatMoney(o.amount)}</div>
          <div class="pc-meta">${o.customer_name ? custName(o.customer_id) : (o.lead_name || "—")}</div>
          <div class="pc-meta">${o.owner_name || "—"} · ${formatDate(o.expected_close_date)}</div>
          <div class="prob-bar"><span style="width:${Math.min(100, prob)}%"></span></div>
          <div class="pc-meta">${prob}%</div>
          <div class="pc-actions">
            ${canAction("crm", "edit") && prev ? `<button class="btn btn-secondary btn-sm" onclick="moveStage(${o.id}, ${prev.id})">←</button>` : ""}
            ${canAction("crm", "edit") && next ? `<button class="btn btn-secondary btn-sm" onclick="moveStage(${o.id}, ${next.id})">→</button>` : ""}
            ${canAction("crm", "edit") ? `<button class="btn btn-success btn-sm" onclick="winOpportunity(${o.id})">${t("crm.win")}</button>` : ""}
            ${canAction("crm", "edit") ? `<button class="btn btn-danger btn-sm" onclick="loseOpportunity(${o.id})">${t("crm.lose")}</button>` : ""}
          </div>
        </div>`;
      }).join("") || `<div class="pc-meta" style="text-align:center;">—</div>`}
    </div>`;
  }).join("");
}

async function moveStage(oppId, stageId) {
  try {
    await api.post(`${CRM_API}/opportunities/${oppId}/stage`, { stage_id: stageId });
    await loadAll();
  } catch (e) { console.error(e); }
}

// ============ STAGES ============
function openStageModal() {
  document.getElementById("stage-modal-title").textContent = t("crm.addStage");
  document.getElementById("stage-id").value = "";
  document.getElementById("stage-name").value = "";
  document.getElementById("stage-position").value = allStages.length + 1;
  document.getElementById("stage-probability").value = 0;
  modal("stage-modal");
}
function editStage(s) {
  document.getElementById("stage-modal-title").textContent = t("crm.editStage");
  document.getElementById("stage-id").value = s.id;
  document.getElementById("stage-name").value = s.name || "";
  document.getElementById("stage-position").value = s.position || "";
  document.getElementById("stage-probability").value = s.probability || "";
  modal("stage-modal");
}
async function saveStage() {
  const id = document.getElementById("stage-id").value;
  const body = {
    name: document.getElementById("stage-name").value.trim(),
    position: parseInt(document.getElementById("stage-position").value) || 1,
    probability: parseFloat(document.getElementById("stage-probability").value) || 0,
    is_active: true,
  };
  if (!body.name) { showToast(t("crm.errorName"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/stages/${id}`, body); }
    else { await api.post(`${CRM_API}/stages`, body); }
    closeModal("stage-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}

// ============ CALLS ============
function renderCalls() {
  const tbody = document.getElementById("calls-table");
  if (!allCalls.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${t("crm.noCalls")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allCalls.map((c) => `
    <tr>
      <td>${t(c.direction === "in" ? "crm.incoming" : "crm.outgoing")}</td>
      <td>${c.customer_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${c.lead_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${c.employee_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${formatDate(c.call_date)}</td>
      <td>${c.duration || 0}</td>
      <td style="color:var(--muted-foreground);">${formatDate(c.follow_up_date)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editCall(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteCall(${c.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}
function openCallModal() {
  document.getElementById("call-modal-title").textContent = t("crm.addCall");
  document.getElementById("call-id").value = "";
  ["call-customer", "call-lead", "call-employee", "call-duration", "call-date", "call-followup", "call-notes"].forEach((id) => { const el = document.getElementById(id); if (el) el.value = ""; });
  document.getElementById("call-direction").value = "out";
  modal("call-modal");
}
function editCall(c) {
  document.getElementById("call-modal-title").textContent = t("crm.editCall");
  document.getElementById("call-id").value = c.id;
  document.getElementById("call-direction").value = c.direction || "out";
  document.getElementById("call-customer").value = c.customer_id || "";
  document.getElementById("call-lead").value = c.lead_id || "";
  document.getElementById("call-employee").value = c.employee_id || "";
  document.getElementById("call-date").value = c.call_date ? c.call_date.slice(0, 16) : "";
  document.getElementById("call-duration").value = c.duration || "";
  document.getElementById("call-followup").value = c.follow_up_date || "";
  document.getElementById("call-notes").value = c.notes || "";
  modal("call-modal");
}
async function saveCall() {
  const id = document.getElementById("call-id").value;
  const body = {
    direction: document.getElementById("call-direction").value,
    customer_id: document.getElementById("call-customer").value || null,
    lead_id: document.getElementById("call-lead").value || null,
    employee_id: document.getElementById("call-employee").value || null,
    call_date: document.getElementById("call-date").value || null,
    duration: parseInt(document.getElementById("call-duration").value) || 0,
    follow_up_date: document.getElementById("call-followup").value || null,
    notes: document.getElementById("call-notes").value,
  };
  if (!body.customer_id && !body.lead_id) { showToast(t("crm.errorParty"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/calls/${id}`, body); }
    else { await api.post(`${CRM_API}/calls`, body); }
    closeModal("call-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function deleteCall(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  await api.delete(`${CRM_API}/calls/${id}`);
  showToast(t("crm.deleted"));
  await loadAll();
}

// ============ MEETINGS ============
function renderMeetings() {
  const tbody = document.getElementById("meetings-table");
  if (!allMeetings.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${t("crm.noMeetings")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allMeetings.map((m) => `
    <tr>
      <td><strong>${escapeHtml(m.title)}</strong></td>
      <td>${m.customer_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${m.lead_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${m.employee_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${formatDate(m.meeting_date)}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(m.location || "—")}</td>
      <td>${crmStatusBadge(m.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editMeeting(${JSON.stringify(m)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteMeeting(${m.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}
function openMeetingModal() {
  document.getElementById("meeting-modal-title").textContent = t("crm.addMeeting");
  document.getElementById("meeting-id").value = "";
  ["meeting-title", "meeting-date", "meeting-location", "meeting-notes"].forEach((id) => document.getElementById(id).value = "");
  ["meeting-customer", "meeting-lead", "meeting-employee"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("meeting-status").value = "scheduled";
  modal("meeting-modal");
}
function editMeeting(m) {
  document.getElementById("meeting-modal-title").textContent = t("crm.editMeeting");
  document.getElementById("meeting-id").value = m.id;
  document.getElementById("meeting-title").value = m.title || "";
  document.getElementById("meeting-date").value = m.meeting_date ? m.meeting_date.slice(0, 16) : "";
  document.getElementById("meeting-customer").value = m.customer_id || "";
  document.getElementById("meeting-lead").value = m.lead_id || "";
  document.getElementById("meeting-employee").value = m.employee_id || "";
  document.getElementById("meeting-location").value = m.location || "";
  document.getElementById("meeting-status").value = m.status || "scheduled";
  document.getElementById("meeting-notes").value = m.notes || "";
  modal("meeting-modal");
}
async function saveMeeting() {
  const id = document.getElementById("meeting-id").value;
  const body = {
    title: document.getElementById("meeting-title").value.trim(),
    meeting_date: document.getElementById("meeting-date").value || null,
    customer_id: document.getElementById("meeting-customer").value || null,
    lead_id: document.getElementById("meeting-lead").value || null,
    employee_id: document.getElementById("meeting-employee").value || null,
    location: document.getElementById("meeting-location").value.trim(),
    status: document.getElementById("meeting-status").value,
    notes: document.getElementById("meeting-notes").value,
  };
  if (!body.title) { showToast(t("crm.errorTitle"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/meetings/${id}`, body); }
    else { await api.post(`${CRM_API}/meetings`, body); }
    closeModal("meeting-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function deleteMeeting(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  await api.delete(`${CRM_API}/meetings/${id}`);
  showToast(t("crm.deleted"));
  await loadAll();
}

// ============ TASKS ============
function renderTasks() {
  const tbody = document.getElementById("tasks-table");
  if (!allTasks.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${t("crm.noTasks")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allTasks.map((task) => `
    <tr>
      <td><strong>${escapeHtml(task.title)}</strong></td>
      <td>${task.customer_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${task.opportunity_title || "—"}</td>
      <td style="color:var(--muted-foreground);">${task.employee_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${formatDate(task.due_date)}</td>
      <td>${priorityBadge(task.priority)}</td>
      <td>${crmStatusBadge(task.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "edit") && task.status !== "done" ? `<button class="btn btn-success btn-sm" onclick="completeTask(${task.id})">${t("crm.markDone")}</button>` : ""}
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editTask(${JSON.stringify(task)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteTask(${task.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}
function openTaskModal() {
  document.getElementById("task-modal-title").textContent = t("crm.addTask");
  document.getElementById("task-id").value = "";
  ["task-title", "task-due", "task-desc"].forEach((id) => document.getElementById(id).value = "");
  ["task-customer", "task-lead", "task-opportunity", "task-employee"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("task-priority").value = "medium";
  document.getElementById("task-status").value = "pending";
  modal("task-modal");
}
function editTask(task) {
  document.getElementById("task-modal-title").textContent = t("crm.editTask");
  document.getElementById("task-id").value = task.id;
  document.getElementById("task-title").value = task.title || "";
  document.getElementById("task-due").value = task.due_date || "";
  document.getElementById("task-customer").value = task.customer_id || "";
  document.getElementById("task-lead").value = task.lead_id || "";
  document.getElementById("task-opportunity").value = task.opportunity_id || "";
  document.getElementById("task-employee").value = task.employee_id || "";
  document.getElementById("task-priority").value = task.priority || "medium";
  document.getElementById("task-status").value = task.status || "pending";
  document.getElementById("task-desc").value = task.description || "";
  modal("task-modal");
}
async function saveTask() {
  const id = document.getElementById("task-id").value;
  const body = {
    title: document.getElementById("task-title").value.trim(),
    description: document.getElementById("task-desc").value,
    due_date: document.getElementById("task-due").value || null,
    customer_id: document.getElementById("task-customer").value || null,
    lead_id: document.getElementById("task-lead").value || null,
    opportunity_id: document.getElementById("task-opportunity").value || null,
    employee_id: document.getElementById("task-employee").value || null,
    priority: document.getElementById("task-priority").value,
    status: document.getElementById("task-status").value,
  };
  if (!body.title) { showToast(t("crm.errorTitle"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/tasks/${id}`, body); }
    else { await api.post(`${CRM_API}/tasks`, body); }
    closeModal("task-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function completeTask(id) {
  const task = allTasks.find((x) => x.id === id);
  if (!task) return;
  task.status = "done";
  await api.put(`${CRM_API}/tasks/${id}`, task);
  showToast(t("crm.saved"));
  await loadAll();
}
async function deleteTask(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  await api.delete(`${CRM_API}/tasks/${id}`);
  showToast(t("crm.deleted"));
  await loadAll();
}

// ============ CAMPAIGNS ============
function renderCampaigns() {
  const tbody = document.getElementById("campaigns-table");
  if (!allCampaigns.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state">${t("crm.noCampaigns")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allCampaigns.map((c) => `
    <tr>
      <td><strong>${escapeHtml(c.name)}</strong></td>
      <td style="color:var(--muted-foreground);">${t(`crm.channel.${c.channel}`)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(c.start_date)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(c.end_date)}</td>
      <td><strong>${formatMoney(c.budget)}</strong></td>
      <td style="color:var(--muted-foreground);">${c.owner_name || "—"}</td>
      <td><span class="badge badge-info">${c.leads_count || 0}</span></td>
      <td>${crmStatusBadge(c.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "create") ? `<button class="btn btn-secondary btn-sm" onclick="openCampaignLeadsModal(${c.id})">${t("crm.addLeads")}</button>` : ""}
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editCampaign(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteCampaign(${c.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}
function openCampaignModal() {
  document.getElementById("campaign-modal-title").textContent = t("crm.addCampaign");
  document.getElementById("campaign-id").value = "";
  ["campaign-name", "campaign-start", "campaign-end", "campaign-budget", "campaign-notes"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("campaign-owner").value = "";
  document.getElementById("campaign-channel").value = "social";
  document.getElementById("campaign-status").value = "planned";
  modal("campaign-modal");
}
function editCampaign(c) {
  document.getElementById("campaign-modal-title").textContent = t("crm.editCampaign");
  document.getElementById("campaign-id").value = c.id;
  document.getElementById("campaign-name").value = c.name || "";
  document.getElementById("campaign-channel").value = c.channel || "social";
  document.getElementById("campaign-start").value = c.start_date || "";
  document.getElementById("campaign-end").value = c.end_date || "";
  document.getElementById("campaign-budget").value = c.budget || "";
  document.getElementById("campaign-owner").value = c.owner_id || "";
  document.getElementById("campaign-status").value = c.status || "planned";
  document.getElementById("campaign-notes").value = c.notes || "";
  modal("campaign-modal");
}
async function saveCampaign() {
  const id = document.getElementById("campaign-id").value;
  const body = {
    name: document.getElementById("campaign-name").value.trim(),
    channel: document.getElementById("campaign-channel").value,
    start_date: document.getElementById("campaign-start").value || null,
    end_date: document.getElementById("campaign-end").value || null,
    budget: parseFloat(document.getElementById("campaign-budget").value) || 0,
    owner_id: document.getElementById("campaign-owner").value || null,
    status: document.getElementById("campaign-status").value,
    notes: document.getElementById("campaign-notes").value,
  };
  if (!body.name) { showToast(t("crm.errorName"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/campaigns/${id}`, body); }
    else { await api.post(`${CRM_API}/campaigns`, body); }
    closeModal("campaign-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function deleteCampaign(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  await api.delete(`${CRM_API}/campaigns/${id}`);
  showToast(t("crm.deleted"));
  await loadAll();
}
function openCampaignLeadsModal(campaignId) {
  document.getElementById("campaign-leads-campaign").value = campaignId || "";
  document.getElementById("campaign-leads-lead").value = "";
  modal("campaign-leads-modal");
}
async function saveCampaignLead() {
  const body = {
    campaign_id: document.getElementById("campaign-leads-campaign").value,
    lead_id: document.getElementById("campaign-leads-lead").value,
  };
  if (!body.campaign_id || !body.lead_id) { showToast(t("crm.errorParty"), "error"); return; }
  try {
    await api.post(`${CRM_API}/campaign-leads`, body);
    closeModal("campaign-leads-modal");
    showToast(t("crm.leadLinked"));
    await loadAll();
  } catch (e) { console.error(e); }
}

// ============ FOLLOW-UPS ============
function renderFollowUps() {
  const tbody = document.getElementById("followups-table");
  if (!allFollowUps.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">${t("crm.noFollowUps")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allFollowUps.map((f) => {
    const overdue = f.status === "pending" && f.follow_up_date && f.follow_up_date < new Date().toISOString().slice(0, 10);
    return `
    <tr>
      <td>${f.customer_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${f.opportunity_title || "—"}</td>
      <td>${t(`crm.action.${f.action_type}`)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(f.follow_up_date)}</td>
      <td style="color:var(--muted-foreground);">${f.employee_name || "—"}</td>
      <td>${overdue ? `<span class="badge badge-danger">${t("crm.overdue")}</span>` : crmStatusBadge(f.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "edit") && f.status !== "done" ? `<button class="btn btn-success btn-sm" onclick="completeFollowUp(${f.id})">${t("crm.markDone")}</button>` : ""}
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editFollowUp(${JSON.stringify(f)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteFollowUp(${f.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}
function openFollowUpModal() {
  document.getElementById("followup-modal-title").textContent = t("crm.addFollowUp");
  document.getElementById("followup-id").value = "";
  ["followup-date", "followup-notes"].forEach((id) => document.getElementById(id).value = "");
  ["followup-customer", "followup-lead", "followup-opportunity", "followup-employee"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("followup-action").value = "call";
  modal("followup-modal");
}
function editFollowUp(f) {
  document.getElementById("followup-modal-title").textContent = t("crm.editFollowUp");
  document.getElementById("followup-id").value = f.id;
  document.getElementById("followup-customer").value = f.customer_id || "";
  document.getElementById("followup-lead").value = f.lead_id || "";
  document.getElementById("followup-opportunity").value = f.opportunity_id || "";
  document.getElementById("followup-employee").value = f.employee_id || "";
  document.getElementById("followup-date").value = f.follow_up_date || "";
  document.getElementById("followup-action").value = f.action_type || "call";
  document.getElementById("followup-notes").value = f.notes || "";
  modal("followup-modal");
}
async function saveFollowUp() {
  const id = document.getElementById("followup-id").value;
  const body = {
    customer_id: document.getElementById("followup-customer").value || null,
    lead_id: document.getElementById("followup-lead").value || null,
    opportunity_id: document.getElementById("followup-opportunity").value || null,
    employee_id: document.getElementById("followup-employee").value || null,
    follow_up_date: document.getElementById("followup-date").value || null,
    action_type: document.getElementById("followup-action").value,
    notes: document.getElementById("followup-notes").value,
  };
  if (!body.follow_up_date) { showToast(t("crm.errorDate"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/follow-ups/${id}`, body); }
    else { await api.post(`${CRM_API}/follow-ups`, body); }
    closeModal("followup-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function completeFollowUp(id) {
  await api.post(`${CRM_API}/follow-ups/${id}/done`, {});
  showToast(t("crm.saved"));
  await loadAll();
}
async function deleteFollowUp(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  await api.delete(`${CRM_API}/follow-ups/${id}`);
  showToast(t("crm.deleted"));
  await loadAll();
}

// ============ QUOTES ============
function renderQuotes() {
  const tbody = document.getElementById("quotes-table");
  if (!allQuotes.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">${t("crm.noQuotes")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allQuotes.map((q) => `
    <tr>
      <td><strong>${escapeHtml(q.quote_number)}</strong></td>
      <td>${q.customer_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(q.title || "—")}</td>
      <td style="color:var(--muted-foreground);">${formatDate(q.valid_until)}</td>
      <td><strong>${formatMoney(q.total)}</strong></td>
      <td>${crmStatusBadge(q.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "view") ? `<button class="btn btn-outline btn-sm" onclick="printQuote(${q.id})" title="${t("doc.print")}">${t("doc.print")}</button>` : ""}
          ${canAction("crm", "view") ? `<button class="btn btn-outline btn-sm" onclick="downloadQuotePdf(${q.id})" title="${t("common.download")}">PDF</button>` : ""}
          ${canAction("crm", "edit") && ["draft", "sent"].includes(q.status) ? `<button class="btn btn-success btn-sm" onclick="acceptQuote(${q.id})">${t("crm.accept")}</button>` : ""}
          ${canAction("crm", "edit") && ["draft", "sent"].includes(q.status) ? `<button class="btn btn-danger btn-sm" onclick="rejectQuote(${q.id})">${t("crm.reject")}</button>` : ""}
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editQuote(${JSON.stringify(q)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteQuote(${q.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}
function addQuoteItem(desc, qty, price) {
  const body = document.getElementById("quote-items-body");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="qi-desc" value="${escapeHtml(desc || "")}"></td>
    <td><input type="number" class="qi-qty" min="0" step="0.01" value="${qty != null ? qty : 1}"></td>
    <td><input type="number" class="qi-price" min="0" step="0.01" value="${price != null ? price : 0}"></td>
    <td class="qi-total">0</td>
    <td><button type="button" class="btn btn-danger btn-sm" onclick="removeQuoteItem(this)">${t("crm.removeItem")}</button></td>`;
  body.appendChild(tr);
  tr.querySelectorAll(".qi-desc, .qi-qty, .qi-price").forEach((el) => {
    el.addEventListener(el.tagName === "INPUT" && el.type === "number" ? "input" : "input", recalcQuote);
  });
}
function removeQuoteItem(btn) {
  btn.closest("tr").remove();
  recalcQuote();
}
function collectQuoteItems() {
  return Array.from(document.querySelectorAll("#quote-items-body tr")).map((tr) => ({
    description: tr.querySelector(".qi-desc").value.trim(),
    qty: parseFloat(tr.querySelector(".qi-qty").value) || 1,
    unit_price: parseFloat(tr.querySelector(".qi-price").value) || 0,
  })).filter((i) => i.description);
}
function recalcQuote() {
  const items = collectQuoteItems();
  const subtotal = items.reduce((s, i) => s + i.qty * i.unit_price, 0);
  const discount = parseFloat(document.getElementById("quote-discount").value) || 0;
  const tax = parseFloat(document.getElementById("quote-tax").value) || 0;
  document.getElementById("quote-subtotal").value = subtotal.toFixed(2);
  const total = subtotal - discount + (subtotal * tax / 100);
  document.getElementById("quote-total").value = total.toFixed(2);
  document.querySelectorAll("#quote-items-body tr").forEach((tr) => {
    const q = parseFloat(tr.querySelector(".qi-qty").value) || 1;
    const p = parseFloat(tr.querySelector(".qi-price").value) || 0;
    tr.querySelector(".qi-total").textContent = formatMoney(q * p);
  });
}
function openQuoteModal() {
  document.getElementById("quote-modal-title").textContent = t("crm.addQuote");
  document.getElementById("quote-id").value = "";
  ["quote-title", "quote-valid", "quote-notes"].forEach((id) => document.getElementById(id).value = "");
  ["quote-customer", "quote-lead", "quote-opportunity"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("quote-status").value = "draft";
  document.getElementById("quote-discount").value = "0";
  document.getElementById("quote-tax").value = "0";
  document.getElementById("quote-subtotal").value = "0";
  document.getElementById("quote-total").value = "0";
  document.getElementById("quote-items-body").innerHTML = "";
  addQuoteItem("", 1, 0);
  modal("quote-modal");
}
function editQuote(q) {
  document.getElementById("quote-modal-title").textContent = t("crm.editQuote");
  document.getElementById("quote-id").value = q.id;
  document.getElementById("quote-title").value = q.title || "";
  document.getElementById("quote-valid").value = q.valid_until || "";
  document.getElementById("quote-notes").value = q.notes || "";
  document.getElementById("quote-customer").value = q.customer_id || "";
  document.getElementById("quote-lead").value = q.lead_id || "";
  document.getElementById("quote-opportunity").value = q.opportunity_id || "";
  document.getElementById("quote-status").value = q.status || "draft";
  document.getElementById("quote-discount").value = q.discount || 0;
  document.getElementById("quote-tax").value = q.tax_rate || 0;
  document.getElementById("quote-items-body").innerHTML = "";
  (q.items && q.items.length ? q.items : [{ description: "", qty: 1, unit_price: 0 }]).forEach((i) => addQuoteItem(i.description, i.qty, i.unit_price));
  recalcQuote();
  modal("quote-modal");
}
async function saveQuote() {
  const id = document.getElementById("quote-id").value;
  const body = {
    title: document.getElementById("quote-title").value.trim(),
    valid_until: document.getElementById("quote-valid").value || null,
    customer_id: document.getElementById("quote-customer").value || null,
    lead_id: document.getElementById("quote-lead").value || null,
    opportunity_id: document.getElementById("quote-opportunity").value || null,
    status: document.getElementById("quote-status").value,
    discount: parseFloat(document.getElementById("quote-discount").value) || 0,
    tax_rate: parseFloat(document.getElementById("quote-tax").value) || 0,
    notes: document.getElementById("quote-notes").value,
    items: collectQuoteItems(),
  };
  if (!body.items.length) { showToast(t("crm.errorTitle"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/quotes/${id}`, body); }
    else { await api.post(`${CRM_API}/quotes`, body); }
    closeModal("quote-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function acceptQuote(id) {
  if (!confirm(t("crm.accept"))) return;
  try {
    await api.post(`${CRM_API}/quotes/${id}/accept`, {});
    showToast(t("crm.quoteAccepted"));
    await loadAll();
  } catch (e) { showToast(t("crm.quoteNeedsCustomer"), "error"); }
}
async function rejectQuote(id) {
  if (!confirm(t("crm.reject"))) return;
  await api.post(`${CRM_API}/quotes/${id}/reject`, {});
  showToast(t("crm.saved"));
  await loadAll();
}
async function deleteQuote(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  try { await api.delete(`${CRM_API}/quotes/${id}`); showToast(t("crm.deleted")); await loadAll(); }
  catch (e) { showToast(t("crm.convertError"), "error"); }
}
function printQuote(id) { window.open(`/documents/crm-quote/${id}`, "_blank"); }
function downloadQuotePdf(id) { window.open(`/documents/crm-quote/${id}/pdf`, "_blank"); }

// ============ CONTRACTS ============
function renderContracts() {
  const tbody = document.getElementById("contracts-table");
  if (!allContracts.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${t("crm.noContracts")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allContracts.map((c) => `
    <tr>
      <td><strong>${escapeHtml(c.contract_number)}</strong></td>
      <td>${c.customer_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(c.title)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(c.start_date)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(c.end_date)}</td>
      <td><strong>${formatMoney(c.value)}</strong></td>
      <td>${crmStatusBadge(c.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "view") ? `<button class="btn btn-outline btn-sm" onclick="printContract(${c.id})" title="${t("doc.print")}">${t("doc.print")}</button>` : ""}
          ${canAction("crm", "view") ? `<button class="btn btn-outline btn-sm" onclick="downloadContractPdf(${c.id})" title="${t("common.download")}">PDF</button>` : ""}
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editContract(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteContract(${c.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}
function openContractModal() {
  document.getElementById("contract-modal-title").textContent = t("crm.addContract");
  document.getElementById("contract-id").value = "";
  ["contract-title", "contract-start", "contract-end", "contract-value", "contract-notes"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("contract-customer").value = "";
  document.getElementById("contract-status").value = "draft";
  modal("contract-modal");
}
function editContract(c) {
  document.getElementById("contract-modal-title").textContent = t("crm.editContract");
  document.getElementById("contract-id").value = c.id;
  document.getElementById("contract-title").value = c.title || "";
  document.getElementById("contract-customer").value = c.customer_id || "";
  document.getElementById("contract-start").value = c.start_date || "";
  document.getElementById("contract-end").value = c.end_date || "";
  document.getElementById("contract-value").value = c.value || "";
  document.getElementById("contract-status").value = c.status || "draft";
  document.getElementById("contract-notes").value = c.notes || "";
  modal("contract-modal");
}
async function saveContract() {
  const id = document.getElementById("contract-id").value;
  const body = {
    title: document.getElementById("contract-title").value.trim(),
    customer_id: document.getElementById("contract-customer").value || null,
    start_date: document.getElementById("contract-start").value || null,
    end_date: document.getElementById("contract-end").value || null,
    value: parseFloat(document.getElementById("contract-value").value) || 0,
    status: document.getElementById("contract-status").value,
    notes: document.getElementById("contract-notes").value,
  };
  if (!body.title) { showToast(t("crm.errorTitle"), "error"); return; }
  if (!body.customer_id) { showToast(t("crm.errorParty"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/contracts/${id}`, body); }
    else { await api.post(`${CRM_API}/contracts`, body); }
    closeModal("contract-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function deleteContract(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  await api.delete(`${CRM_API}/contracts/${id}`);
  showToast(t("crm.deleted"));
  await loadAll();
}
function printContract(id) { window.open(`/documents/crm-contract/${id}`, "_blank"); }
function downloadContractPdf(id) { window.open(`/documents/crm-contract/${id}/pdf`, "_blank"); }

// ============ COMPLAINTS ============
function renderComplaints() {
  const tbody = document.getElementById("complaints-table");
  if (!allComplaints.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state">${t("crm.noComplaints")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allComplaints.map((c) => `
    <tr>
      <td><strong>${escapeHtml(c.complaint_number)}</strong></td>
      <td>${c.customer_name || "—"}</td>
      <td>${escapeHtml(c.subject)}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(c.category || "—")}</td>
      <td>${priorityBadge(c.priority)}</td>
      <td>${crmStatusBadge(c.status)}</td>
      <td style="color:var(--muted-foreground);">${c.assignee_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${formatDate(c.resolved_date)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editComplaint(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteComplaint(${c.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}
function openComplaintModal() {
  document.getElementById("complaint-modal-title").textContent = t("crm.addComplaint");
  document.getElementById("complaint-id").value = "";
  ["complaint-subject", "complaint-category", "complaint-rating", "complaint-notes"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("complaint-customer").value = "";
  document.getElementById("complaint-priority").value = "medium";
  document.getElementById("complaint-status").value = "open";
  document.getElementById("complaint-assigned").value = "";
  modal("complaint-modal");
}
function editComplaint(c) {
  document.getElementById("complaint-modal-title").textContent = t("crm.editComplaint");
  document.getElementById("complaint-id").value = c.id;
  document.getElementById("complaint-customer").value = c.customer_id || "";
  document.getElementById("complaint-subject").value = c.subject || "";
  document.getElementById("complaint-category").value = c.category || "";
  document.getElementById("complaint-priority").value = c.priority || "medium";
  document.getElementById("complaint-status").value = c.status || "open";
  document.getElementById("complaint-assigned").value = c.assigned_to || "";
  document.getElementById("complaint-rating").value = c.rating || "";
  document.getElementById("complaint-notes").value = c.description || "";
  modal("complaint-modal");
}
async function saveComplaint() {
  const id = document.getElementById("complaint-id").value;
  const body = {
    customer_id: document.getElementById("complaint-customer").value || null,
    subject: document.getElementById("complaint-subject").value.trim(),
    category: document.getElementById("complaint-category").value.trim(),
    priority: document.getElementById("complaint-priority").value,
    status: document.getElementById("complaint-status").value,
    assigned_to: document.getElementById("complaint-assigned").value || null,
    rating: parseInt(document.getElementById("complaint-rating").value) || 0,
    description: document.getElementById("complaint-notes").value,
  };
  if (!body.customer_id) { showToast(t("crm.errorParty"), "error"); return; }
  if (!body.subject) { showToast(t("crm.errorSubject"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/complaints/${id}`, body); }
    else { await api.post(`${CRM_API}/complaints`, body); }
    closeModal("complaint-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function deleteComplaint(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  await api.delete(`${CRM_API}/complaints/${id}`);
  showToast(t("crm.deleted"));
  await loadAll();
}

// ============ TICKETS ============
function renderTickets() {
  const tbody = document.getElementById("tickets-table");
  if (!allTickets.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state">${t("crm.noTickets")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allTickets.map((tk) => `
    <tr>
      <td><strong>${escapeHtml(tk.ticket_number)}</strong></td>
      <td>${tk.customer_name || "—"}</td>
      <td>${escapeHtml(tk.subject)}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(tk.category || "—")}</td>
      <td>${priorityBadge(tk.priority)}</td>
      <td>${crmStatusBadge(tk.status)}</td>
      <td style="color:var(--muted-foreground);">${tk.assignee_name || "—"}</td>
      <td style="color:var(--muted-foreground);">${formatDate(tk.resolved_date)}</td>
      <td>
        <div class="table-actions">
          ${canAction("crm", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editTicket(${JSON.stringify(tk)})'>${t("common.edit")}</button>` : ""}
          ${canAction("crm", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteTicket(${tk.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}
function openTicketModal() {
  document.getElementById("ticket-modal-title").textContent = t("crm.addTicket");
  document.getElementById("ticket-id").value = "";
  ["ticket-subject", "ticket-category", "ticket-notes"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("ticket-customer").value = "";
  document.getElementById("ticket-priority").value = "medium";
  document.getElementById("ticket-status").value = "new";
  document.getElementById("ticket-assigned").value = "";
  modal("ticket-modal");
}
function editTicket(tk) {
  document.getElementById("ticket-modal-title").textContent = t("crm.editTicket");
  document.getElementById("ticket-id").value = tk.id;
  document.getElementById("ticket-customer").value = tk.customer_id || "";
  document.getElementById("ticket-subject").value = tk.subject || "";
  document.getElementById("ticket-category").value = tk.category || "";
  document.getElementById("ticket-priority").value = tk.priority || "medium";
  document.getElementById("ticket-status").value = tk.status || "new";
  document.getElementById("ticket-assigned").value = tk.assigned_to || "";
  document.getElementById("ticket-notes").value = tk.description || "";
  modal("ticket-modal");
}
async function saveTicket() {
  const id = document.getElementById("ticket-id").value;
  const body = {
    customer_id: document.getElementById("ticket-customer").value || null,
    subject: document.getElementById("ticket-subject").value.trim(),
    category: document.getElementById("ticket-category").value.trim(),
    priority: document.getElementById("ticket-priority").value,
    status: document.getElementById("ticket-status").value,
    assigned_to: document.getElementById("ticket-assigned").value || null,
    description: document.getElementById("ticket-notes").value,
  };
  if (!body.customer_id) { showToast(t("crm.errorParty"), "error"); return; }
  if (!body.subject) { showToast(t("crm.errorSubject"), "error"); return; }
  try {
    if (id) { await api.put(`${CRM_API}/tickets/${id}`, body); }
    else { await api.post(`${CRM_API}/tickets`, body); }
    closeModal("ticket-modal");
    showToast(t("crm.saved"));
    await loadAll();
  } catch (e) { console.error(e); }
}
async function deleteTicket(id) {
  if (!confirm(t("crm.confirmDelete"))) return;
  await api.delete(`${CRM_API}/tickets/${id}`);
  showToast(t("crm.deleted"));
  await loadAll();
}

/* ============================================================
   Dashboard JavaScript (interactive)
   ============================================================ */

let trendData = [];
let period = 12;
let revenueChart = null;
let unitsChart = null;
let projectsChart = null;
let __stats = null;

const AUDIT_ACTION_LABELS = {
  create: "audit.create", update: "audit.update", delete: "audit.delete",
  payment: "audit.payment", login: "audit.login", logout: "audit.logout",
  submit: "audit.submit", approve: "audit.approve", reject: "audit.reject",
};
const AUDIT_ACTION_CLS = {
  create: "badge-success", update: "badge-info", delete: "badge-danger",
  payment: "badge-warning", login: "badge-success", logout: "badge-neutral",
  submit: "badge-info", approve: "badge-success", reject: "badge-danger",
};
const AUDIT_ENTITY_LABELS = {
  unit: "audit.unit", project: "audit.project", employee: "audit.employee",
  customer: "audit.customer", supplier: "audit.supplier", invoice: "audit.invoice",
  order: "audit.order", rental: "audit.rental", plan: "audit.plan",
  installment: "audit.installment", user: "audit.user",
  company: "audit.company", branch: "audit.branch", financial_year: "audit.financialYear",
  workflow: "audit.workflow", approval: "audit.approval",
};
const ACTIVITY_ICONS = {
  unit: ["🏠", "kpi-brown"], project: ["👷", "kpi-olive"],
  employee: ["👥", "kpi-terracotta"], customer: ["🤝", "kpi-sage"],
  supplier: ["🚚", "kpi-moss"], invoice: ["🧾", "kpi-clay"],
  order: ["📦", "kpi-sand"], rental: ["🔑", "kpi-terra"],
  plan: ["📅", "kpi-sage"], installment: ["💳", "kpi-brown"],
  user: ["👤", "kpi-clay"],
  company: ["🏢", "kpi-clay"], branch: ["📍", "kpi-sand"],
  financial_year: ["📅", "kpi-olive"],
};

function timeAgo(iso) {
  if (!iso) return "";
  try {
    const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
    const diff = new Date(iso).getTime() - Date.now();
    const sec = Math.round(diff / 1000);
    const min = Math.round(sec / 60);
    const hr = Math.round(min / 60);
    const day = Math.round(hr / 24);
    if (Math.abs(sec) < 60) return rtf.format(0, "second");
    if (Math.abs(min) < 60) return rtf.format(min, "minute");
    if (Math.abs(hr) < 24) return rtf.format(hr, "hour");
    if (Math.abs(day) < 30) return rtf.format(day, "day");
    return formatDate(iso);
  } catch (e) {
    return formatDate(iso);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    // ===== Load stats =====
    const stats = await api.get("/api/dashboard/stats");
    __stats = stats;
    renderKpis(stats);

    // ===== Load revenue trend =====
    trendData = stats.revenue_trend || [];
    renderTrend();

    // ===== Load projects =====
    const projects = await api.get("/api/projects");
    renderProjects(projects);
    renderProjectsChart(stats.project_statuses);

    // ===== Load units =====
    const units = await api.get("/api/units");
    renderUnitsChart(units);

    // ===== Load activity =====
    renderActivity(stats.recent_activity);
  } catch (err) {
    console.error(err);
  }
});

// ===== KPI cards =====
function renderKpis(s) {
  const kpis = [
    { id: "kpi-projects", val: s.projects_count, fmt: formatNumber, sub: `${s.active_projects} ${t("dashboard.activeProjects")}` },
    { id: "kpi-revenue", val: s.total_revenue, fmt: formatMoney, sub: t("dashboard.totalSales") },
    { id: "kpi-units", val: s.units_count, fmt: formatNumber, sub: `${s.units_available} ${t("dashboard.availableUnits")}` },
    { id: "kpi-employees", val: s.employees_count, fmt: formatNumber, sub: t("dashboard.activeEmployees") },
    { id: "kpi-customers", val: s.customers_count, fmt: formatNumber, sub: t("dashboard.totalCustomers") },
    { id: "kpi-suppliers", val: s.suppliers_count, fmt: formatNumber, sub: t("dashboard.totalSuppliers") },
    { id: "kpi-rentals", val: s.active_rentals_count, fmt: formatNumber, sub: `${formatMoney(s.active_rentals_revenue)} ${t("dashboard.activeRentalsSub")}` },
    { id: "kpi-pending", val: s.pending_revenue + s.pending_expenses + s.pending_installments_amount, fmt: formatMoney, sub: t("dashboard.pendingSub") },
  ];
  if (document.getElementById("kpi-approvals")) {
    kpis.push({ id: "kpi-approvals", val: s.pending_approvals_count || 0, fmt: formatNumber, sub: t("workflow.notifTitle") });
  }
  kpis.forEach((k) => {
    animateCount(document.getElementById(k.id), k.val, k.fmt);
    const sub = document.getElementById(k.id + "-sub");
    if (sub) sub.textContent = k.sub;
  });
}

// ===== Revenue vs expenses trend (interactive period) =====
function renderTrend() {
  const slice = trendData.slice(-period);
  const AR_SHORT = ["ينا","فبر","مارس","أبر","مايو","يون","يول","أغس","سبت","أكت","نوف","ديس"];
  const EN_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const labels = slice.map((d) => {
    const [y, m] = d.month.split("-");
    const short = LANG === "ar" ? AR_SHORT[+m - 1] : EN_SHORT[+m - 1];
    return short + " " + String(+y).slice(-2);
  });

  const ctx = document.getElementById("revenueChart");
  if (!ctx) return;
  if (revenueChart) revenueChart.destroy();
  revenueChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: t("dashboard.revenueLabel"), data: slice.map((d) => d.revenue), backgroundColor: chartColors.olive, borderRadius: 6, barThickness: 16 },
        { label: t("dashboard.expensesLabel"), data: slice.map((d) => d.expenses), backgroundColor: chartColors.terracotta, borderRadius: 6, barThickness: 16 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 11 }, padding: 12, usePointStyle: true } },
        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${formatMoney(c.raw)} ${t("common.currency")}` } },
      },
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { callback: (v) => formatMoney(v) } },
      },
    },
  });
}

function setPeriod(p) {
  period = p;
  document.querySelectorAll("#trend-period .seg-btn").forEach((b) => {
    b.classList.toggle("active", +b.dataset.p === p);
  });
  renderTrend();
}

// ===== Projects list =====
function renderProjects(projects) {
  const list = document.getElementById("projects-list");
  if (!projects.length) {
    list.innerHTML = `<div class="empty-state"><div class="empty-icon">🗂️</div>${t("dashboard.noProjectsYet")}</div>`;
    return;
  }
  list.innerHTML = projects.slice(0, 5).map((p) => {
    const fillClass = p.completion < 40 ? "danger" : p.completion < 70 ? "warning" : "";
    return `
      <div class="list-item">
        <div class="list-icon kpi-olive" style="color:#fff;">👷</div>
        <div class="list-body">
          <div class="list-title">${p.name}</div>
          <div class="list-meta">${statusBadge(p.status)} &nbsp; ${t("dashboard.budgetLabel")}: ${formatMoney(p.budget)}</div>
          <div class="progress-bar" style="margin-top:6px;"><div class="progress-fill ${fillClass}" style="width:${p.completion}%"></div></div>
        </div>
        <div class="list-side"><strong style="color:var(--foreground);">${p.completion}%</strong></div>
      </div>`;
  }).join("");
}

// ===== Units doughnut =====
function renderUnitsChart(units) {
  const statuses = { available: 0, reserved: 0, sold: 0, rented: 0 };
  units.forEach((u) => { if (statuses[u.status] !== undefined) statuses[u.status]++; });

  const ctx = document.getElementById("unitsChart");
  if (!ctx) return;
  if (unitsChart) unitsChart.destroy();
  unitsChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: [t("status.available"), t("status.reserved"), t("status.sold"), t("status.rented")],
      datasets: [{
        data: [statuses.available, statuses.reserved, statuses.sold, statuses.rented],
        backgroundColor: [chartColors.olive, chartColors.sand, chartColors.sage, chartColors.brown],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "60%",
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 11 }, padding: 12 } },
      },
    },
  });
}

// ===== Projects status doughnut =====
function renderProjectsChart(statuses) {
  const ctx = document.getElementById("projectsChart");
  if (!ctx) return;
  const keys = ["active", "finishing", "completed", "suspended"];
  const labels = keys.map((k) => STATUS_LABELS[k] || k);
  const data = keys.map((k) => statuses[k] || 0);
  if (projectsChart) projectsChart.destroy();
  projectsChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: [chartColors.olive, chartColors.sand, chartColors.sage, chartColors.terracotta],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "60%",
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 11 }, padding: 12 } },
      },
    },
  });
}

// ===== Recent activity (from audit log) =====
function renderActivity(logs) {
  const el = document.getElementById("recent-activity");
  if (!logs || !logs.length) {
    el.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div>${t("dashboard.noActivity")}</div>`;
    return;
  }
  el.innerHTML = logs.map((l) => {
    const [icon, color] = ACTIVITY_ICONS[l.entity] || ["⚡", "kpi-clay"];
    const aKey = AUDIT_ACTION_LABELS[l.action];
    const aCls = AUDIT_ACTION_CLS[l.action] || "badge-neutral";
    const eKey = AUDIT_ENTITY_LABELS[l.entity];
    const desc = l.description ? `<div class="act-desc">${escapeHtml(l.description)}</div>` : "";
    return `
      <div class="act-item">
        <div class="act-rail">
          <div class="act-node ${color}">${icon}</div>
          <div class="act-line"></div>
        </div>
        <div class="act-body">
          <div class="act-head">
            <span class="badge ${aCls}">${aKey ? t(aKey) : l.action}</span>
            <span class="badge badge-neutral">${eKey ? t(eKey) : l.entity}</span>
            <span class="act-user">${escapeHtml(l.username || "—")}</span>
          </div>
          ${desc}
        </div>
        <div class="act-time">${timeAgo(l.created_at)}</div>
      </div>`;
  }).join("");
}

// ===== Export dashboard summary =====
function exportDashboard() {
  if (!__stats) { showToast(t("common.loading"), "info"); return; }
  const s = __stats;
  const headers = [
    t("dashboard.kpiProjects"), t("dashboard.kpiRevenue"), t("dashboard.kpiUnits"),
    t("dashboard.kpiEmployees"), t("dashboard.kpiCustomers"), t("dashboard.kpiSuppliers"),
    t("dashboard.kpiRentals"), t("dashboard.kpiPending"),
  ];
  const row = [
    s.projects_count, s.total_revenue, s.units_count, s.employees_count,
    s.customers_count, s.suppliers_count, s.active_rentals_count,
    +(s.pending_revenue + s.pending_expenses + s.pending_installments_amount).toFixed(2),
  ];
  exportCSV("dashboard_overview.csv", headers, [row]);

  const trendHeaders = [t("dashboard.trendTitle"), t("dashboard.revenueLabel"), t("dashboard.expensesLabel")];
  const trendRows = (s.revenue_trend || []).map((d) => [d.month, d.revenue, d.expenses]);
  exportCSV("dashboard_revenue_trend.csv", trendHeaders, trendRows);
  showToast(t("common.exportDone"));
}

window.setPeriod = setPeriod;
window.exportDashboard = exportDashboard;

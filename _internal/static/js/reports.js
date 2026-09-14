/* ============================================================
   Reports Module JavaScript
   ============================================================ */

let repProjects = [];
let repEmployees = [];
let repInvoices = [];
let repUnits = [];
let reportYear = "";

const reportCharts = {};

function destroyChart(name) {
  if (reportCharts[name]) {
    reportCharts[name].destroy();
    reportCharts[name] = null;
  }
}

function invoicesUrl() {
  return reportYear ? "/api/invoices?financial_year_id=" + encodeURIComponent(reportYear) : "/api/invoices";
}

async function loadYearOptions() {
  try {
    const res = await api.get("/api/financial-years");
    const select = document.getElementById("yearFilter");
    if (!select) return;
    select.innerHTML = '<option value="">' + t("reports.allYears") + "</option>";
    (res.years || []).forEach((y) => {
      const opt = document.createElement("option");
      opt.value = y.id;
      opt.textContent = y.name;
      select.appendChild(opt);
    });
    select.addEventListener("change", applyYearFilter);
  } catch (err) {
    console.error("Failed to load financial years", err);
  }
}

async function loadData() {
  try {
    [repProjects, repEmployees, repInvoices, repUnits] = await Promise.all([
      api.get("/api/projects"),
      api.get("/api/employees"),
      api.get(invoicesUrl()),
      api.get("/api/units"),
    ]);

    renderProjectsChart(repProjects);
    renderDepartmentsChart(repEmployees);
    renderInvoicesChart(repInvoices);
    renderSummary(repProjects, repInvoices, repUnits, repEmployees);
  } catch (err) {
    console.error(err);
  }
}

function applyYearFilter() {
  const select = document.getElementById("yearFilter");
  reportYear = select ? select.value : "";
  loadData();
}

document.addEventListener("DOMContentLoaded", () => {
  loadYearOptions();
  loadData();
});

function printReport() {
  window.print();
}

function exportReport() {  const totalBudget = repProjects.reduce((a, p) => a + (p.budget || 0), 0);
  const totalSpent = repProjects.reduce((a, p) => a + (p.spent || 0), 0);
  const totalSales = repInvoices.filter((i) => i.invoice_type === "sales").reduce((a, i) => a + (i.amount || 0), 0);
  const totalUnitsValue = repUnits.reduce((a, u) => a + (u.price || 0), 0);
  const avgCompletion = repProjects.length ? Math.round(repProjects.reduce((a, p) => a + (p.completion || 0), 0) / repProjects.length) : 0;
  const pendingDues = repInvoices.reduce((a, i) => a + (i.balance || 0), 0);

  const projectRows = repProjects.map((p) => [
    p.name, tv(p.status), tv(p.priority), p.budget || 0, p.spent || 0,
    (p.completion || 0) + "%", p.location || "",
  ]);

  const invoiceRows = repInvoices.map((i) => [
    i.invoice_number,
    i.invoice_type === "sales" ? t("finance.salesLabel") : t("finance.expensesLabel"),
    i.amount || 0, i.paid_amount || 0, i.balance || 0,
    STATUS_LABELS[i.status] || i.status,
  ]);

  const unitRows = repUnits.map((u) => [u.unit_code, tv(u.unit_type), u.area || 0, u.price || 0]);

  const employeeRows = repEmployees.map((e) => [
    e.full_name, tv(e.department), e.position || "", e.salary || 0,
  ]);

  const out = [];
  out.push(["=SUMMARY=", ""]);
  out.push([t("reports.totalBudgets"), totalBudget]);
  out.push([t("reports.totalExpenses"), totalSpent]);
  out.push([t("reports.totalSales"), totalSales]);
  out.push([t("reports.pendingDues"), pendingDues]);
  out.push([t("reports.unitsValue"), totalUnitsValue]);
  out.push([t("reports.avgCompletion"), avgCompletion + "%"]);
  out.push([t("reports.employeeCount"), repEmployees.length]);
  out.push([""]);
  out.push([t("reports.projectsTitle")]);
  out.push([t("projects.colName"), t("common.status"), t("common.priority"), t("common.budget"), t("common.spent"), t("common.completion"), t("common.location")]);
  projectRows.forEach((r) => out.push(r));
  out.push([""]);
  out.push([t("reports.invoicesTitle")]);
  out.push([t("finance.colNumber"), t("common.type"), t("common.amount"), t("common.paid"), t("common.balance"), t("common.status")]);
  invoiceRows.forEach((r) => out.push(r));
  out.push([""]);
  out.push([t("realestate.title")]);
  out.push([t("realestate.colCode"), t("common.type"), t("common.area"), t("common.price")]);
  unitRows.forEach((r) => out.push(r));
  out.push([""]);
  out.push([t("hr.title")]);
  out.push([t("common.fullName"), t("common.department"), t("common.position"), t("common.salary")]);
  employeeRows.forEach((r) => out.push(r));

  exportCSV("report.csv", [t("reports.title")], out);
}

function renderProjectsChart(projects) {
  const counts = {};
  projects.forEach((p) => {
    counts[p.status] = (counts[p.status] || 0) + 1;
  });

  const statusLabels = {
    active: t("status.active"),
    finishing: t("status.finishing"),
    completed: t("status.completed"),
    suspended: t("status.suspended"),
  };

  destroyChart("projects");
  reportCharts.projects = new Chart(document.getElementById("reportsProjects"), {
    type: "doughnut",
    data: {
      labels: Object.keys(counts).map((s) => statusLabels[s] || s),
      datasets: [{
        data: Object.values(counts),
        backgroundColor: [chartColors.olive, chartColors.sand, chartColors.sage, chartColors.clay],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "60%",
      plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } },
    },
  });
}

function renderDepartmentsChart(employees) {
  const counts = {};
  employees.forEach((e) => {
    counts[e.department] = (counts[e.department] || 0) + 1;
  });

  destroyChart("departments");
  reportCharts.departments = new Chart(document.getElementById("reportsDepartments"), {
    type: "bar",
    data: {
      labels: Object.keys(counts).map((d) => tv(d)),
      datasets: [{
        label: t("reports.employeeCount"),
        data: Object.values(counts),
        backgroundColor: chartColors.olive,
        borderRadius: 8,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.05)" } },
      },
    },
  });
}

function renderInvoicesChart(invoices) {
  const counts = { pending: 0, paid: 0, partial: 0, overdue: 0 };
  invoices.forEach((i) => { if (counts[i.status] !== undefined) counts[i.status]++; });

  const labels = {
    pending: t("status.pending"),
    paid: t("status.paid"),
    partial: t("status.partial"),
    overdue: t("status.overdue"),
  };

  destroyChart("invoices");
  reportCharts.invoices = new Chart(document.getElementById("reportsInvoices"), {
    type: "pie",
    data: {
      labels: Object.keys(counts).map((s) => labels[s]),
      datasets: [{
        data: Object.values(counts),
        backgroundColor: [chartColors.sand, chartColors.sage, chartColors.olive, chartColors.clay],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } },
    },
  });
}

function renderSummary(projects, invoices, units, employees) {
  const totalBudget = projects.reduce((a, p) => a + (p.budget || 0), 0);
  const totalSpent = projects.reduce((a, p) => a + (p.spent || 0), 0);
  const totalSales = invoices.filter((i) => i.invoice_type === "sales").reduce((a, i) => a + (i.amount || 0), 0);
  const totalUnitsValue = units.reduce((a, u) => a + (u.price || 0), 0);
  const avgCompletion = projects.length ? Math.round(projects.reduce((a, p) => a + (p.completion || 0), 0) / projects.length) : 0;

  document.getElementById("reports-summary").innerHTML = `
    <div class="list-item"><div class="list-icon kpi-olive" style="color:#fff;">💼</div>
      <div class="list-body"><div class="list-title">${t("reports.totalBudgets")}</div></div>
      <div class="list-side"><strong>${formatMoney(totalBudget)}</strong></div></div>
    <div class="list-item"><div class="list-icon kpi-terracotta" style="color:#fff;">💸</div>
      <div class="list-body"><div class="list-title">${t("reports.totalExpenses")}</div></div>
      <div class="list-side"><strong>${formatMoney(totalSpent)}</strong></div></div>
    <div class="list-item"><div class="list-icon kpi-sage" style="color:#fff;">📈</div>
      <div class="list-body"><div class="list-title">${t("reports.totalSales")}</div></div>
      <div class="list-side"><strong>${formatMoney(totalSales)}</strong></div></div>
    <div class="list-item"><div class="list-icon kpi-brown" style="color:#fff;">🏠</div>
      <div class="list-body"><div class="list-title">${t("reports.unitsValue")}</div></div>
      <div class="list-side"><strong>${formatMoney(totalUnitsValue)}</strong></div></div>
    <div class="list-item"><div class="list-icon kpi-sand" style="color:#fff;">🎯</div>
      <div class="list-body"><div class="list-title">${t("reports.avgCompletion")}</div></div>
      <div class="list-side"><strong>${avgCompletion}%</strong></div></div>
    <div class="list-item"><div class="list-icon kpi-moss" style="color:#fff;">👥</div>
      <div class="list-body"><div class="list-title">${t("reports.employeeCount")}</div></div>
      <div class="list-side"><strong>${formatNumber(employees.length)}</strong></div></div>`;
}

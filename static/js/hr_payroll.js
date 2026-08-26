/* Payroll - Runs & Payslips */
let runsData = [];

async function loadRuns() {
  try {
    runsData = await api.get("/api/payroll/runs");
    renderRuns();
    updateKpis();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function updateKpis() {
  const latest = runsData[0];
  const gross = latest ? latest.total_gross : 0;
  const deductions = latest ? latest.total_deductions : 0;
  const net = latest ? latest.total_net : 0;
  const emps = latest ? latest.employees_count : 0;
  document.getElementById("kpi-gross").textContent = prMoney(gross);
  document.getElementById("kpi-deductions").textContent = prMoney(deductions);
  document.getElementById("kpi-net").textContent = prMoney(net);
  document.getElementById("kpi-emps").textContent = emps;
}

function renderRuns() {
  document.getElementById("runs-count").textContent = `(${runsData.length})`;
  document.getElementById("runs-empty").style.display = runsData.length ? "none" : "";
  document.getElementById("runs-table").innerHTML = runsData.map((r) => {
    const actions = [];
    actions.push(`<button class="icon-btn" title="${t("payroll.viewPayslip")}" onclick="openLinesModal(${r.id}, '${escapeHtml(r.name).replace(/'/g, "\\'")}')">📄</button>`);
    if (prCan("edit")) {
      if (r.status === "draft") actions.push(`<button class="icon-btn" title="${t("payroll.markFinalized")}" onclick="updateRunStatus(${r.id}, 'finalized')">✅</button>`);
      if (r.status === "finalized") actions.push(`<button class="icon-btn" title="${t("payroll.markPaid")}" onclick="updateRunStatus(${r.id}, 'paid')">💰</button>`);
      actions.push(`<button class="icon-btn" title="${t("payroll.recalculate")}" onclick="recalculateRun(${r.id})">🔄</button>`);
    }
    if (prCan("delete")) actions.push(`<button class="icon-btn" title="${t("common.delete")}" onclick="deleteRun(${r.id})">🗑️</button>`);
    return `
    <tr>
      <td><b>${escapeHtml(r.name)}</b></td>
      <td>${escapeHtml(r.month || "—")}</td>
      <td>${formatDate(r.from_date)} → ${formatDate(r.to_date)}</td>
      <td>${r.employees_count}</td>
      <td>${prMoney(r.total_gross)}</td>
      <td>${prMoney(r.total_deductions)}</td>
      <td><b>${prMoney(r.total_net)}</b></td>
      <td>${prStatusBadge(r.status)}</td>
      <td><div class="table-actions">${actions.join("")}</div></td>
    </tr>`;
  }).join("");
}

function openRunModal() {
  const now = new Date();
  document.getElementById("run-name").value = "";
  document.getElementById("run-month").value = now.toISOString().slice(0, 7);
  const from = new Date(now.getFullYear(), now.getMonth(), 1);
  const to = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  document.getElementById("run-from").value = from.toISOString().slice(0, 10);
  document.getElementById("run-to").value = to.toISOString().slice(0, 10);
  document.getElementById("run-modal").classList.add("active");
}

function closeRunModal() {
  document.getElementById("run-modal").classList.remove("active");
}

async function createRun() {
  const body = {
    name: document.getElementById("run-name").value.trim(),
    month: document.getElementById("run-month").value || null,
    from_date: document.getElementById("run-from").value || null,
    to_date: document.getElementById("run-to").value || null,
  };
  if (!body.name) { showToast(t("payroll.nameRequired"), "warning"); return; }
  try {
    await api.post("/api/payroll/runs", body);
    showToast(t("payroll.runCreated"));
    closeRunModal();
    loadRuns();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function updateRunStatus(runId, status) {
  try {
    await api.put(`/api/payroll/runs/${runId}`, { status });
    showToast(t("payroll.saved"));
    loadRuns();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function recalculateRun(runId) {
  if (!confirm(t("payroll.recalculate"))) return;
  try {
    await api.post(`/api/payroll/runs/${runId}/recalculate`);
    showToast(t("payroll.recalculated"));
    loadRuns();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteRun(runId) {
  if (!confirm(t("payroll.confirmDelete"))) return;
  try {
    await api.delete(`/api/payroll/runs/${runId}`);
    showToast(t("payroll.deleted"));
    loadRuns();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

/* ===== Run lines ===== */
let currentRunName = "";

async function openLinesModal(runId, runName) {
  currentRunName = runName;
  document.getElementById("lines-modal-title").textContent = `${t("payroll.payroll")}: ${runName}`;
  try {
    const run = await api.get(`/api/payroll/runs/${runId}`);
    const lines = run.lines || [];
    document.getElementById("lines-table").innerHTML = lines.map((l) => `
      <tr>
        <td><b>${escapeHtml(l.employee_name || "—")}</b></td>
        <td>${prMoney(l.base_salary)}</td>
        <td>${prMoney(l.allowance_total)}</td>
        <td>${prMoney(l.total_deductions)}</td>
        <td>${prMoney(l.gross)}</td>
        <td><b>${prMoney(l.net)}</b></td>
        <td><button class="btn btn-sm btn-outline" onclick="openPayslip(${JSON.stringify(l)})">${t("payroll.payslip")}</button></td>
      </tr>`).join("");
    document.getElementById("lines-modal").classList.add("active");
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function closeLinesModal() {
  document.getElementById("lines-modal").classList.remove("active");
}

/* ===== Payslip ===== */
function breakdownRows(items) {
  if (!items || !items.length) return `<tr><td colspan="2" class="muted">${t("common.none")}</td></tr>`;
  return items.map((it) => `<tr><td>${escapeHtml(it.name || "—")}</td><td style="text-align:end;">${prMoney(it.amount)}</td></tr>`).join("");
}

function openPayslip(line) {
  document.getElementById("payslip-title").textContent = `${t("payroll.payslip")} — ${line.employee_name || ""}`;
  document.getElementById("payslip-body").innerHTML = `
    <div class="payslip">
      <div style="display:flex;justify-content:space-between;margin-bottom:12px;">
        <div>
          <div class="payslip-name"><b>${escapeHtml(line.employee_name || "—")}</b></div>
          <div class="muted">${escapeHtml(line.department_name || "")}${line.position_name ? " — " + escapeHtml(line.position_name) : ""}</div>
        </div>
        <div style="text-align:end;">
          <div><b>${currentRunName}</b></div>
          <div class="muted">${line.run_id ? `#${line.run_id}` : ""}</div>
        </div>
      </div>
      <table class="table payslip-table">
        <thead><tr><th>${t("payroll.gross")}</th><th></th></tr></thead>
        <tbody>
          <tr><td>${t("payroll.baseSalary")}</td><td style="text-align:end;">${prMoney(line.base_salary)}</td></tr>
          <tr><td>${t("payroll.allowances")}</td><td style="text-align:end;">${prMoney(line.allowance_total)}</td></tr>
          ${breakdownRows(line.allowances)}
          <tr><td>${t("payroll.bonuses")}</td><td style="text-align:end;">${prMoney(line.bonus_total)}</td></tr>
          ${breakdownRows(line.bonuses)}
          <tr class="payslip-total-row"><td><b>${t("payroll.gross")}</b></td><td style="text-align:end;"><b>${prMoney(line.gross)}</b></td></tr>
        </tbody>
      </table>
      <table class="table payslip-table">
        <thead><tr><th>${t("payroll.totalDeductions")}</th><th></th></tr></thead>
        <tbody>
          <tr><td>${t("payroll.deductions")}</td><td style="text-align:end;">${prMoney(line.deduction_total)}</td></tr>
          ${breakdownRows(line.deductions)}
          <tr><td>${t("payroll.penalties")}</td><td style="text-align:end;">${prMoney(line.penalties_total)}</td></tr>
          <tr><td>${t("payroll.loanInstallment")}</td><td style="text-align:end;">${prMoney(line.loan_installment)}</td></tr>
          <tr><td>${t("payroll.insuranceAmount")}</td><td style="text-align:end;">${prMoney(line.insurance)}</td></tr>
          <tr><td>${t("payroll.taxAmount")}</td><td style="text-align:end;">${prMoney(line.tax)}</td></tr>
          <tr class="payslip-total-row"><td><b>${t("payroll.totalDeductions")}</b></td><td style="text-align:end;"><b>${prMoney(line.total_deductions)}</b></td></tr>
        </tbody>
      </table>
      <div class="payslip-net">
        ${t("payroll.net")}: <b>${prMoney(line.net)}</b>
      </div>
    </div>`;
  document.getElementById("payslip-modal").classList.add("active");
}

function closePayslipModal() {
  document.getElementById("payslip-modal").classList.remove("active");
}

function printPayslip() {
  const body = document.getElementById("payslip-body").innerHTML;
  const title = document.getElementById("payslip-title").textContent;
  const w = window.open("", "_blank", "width=600,height=800");
  w.document.write(`<!doctype html><html lang="ar"><head><meta charset="utf-8"><title>${title}</title>
    <style>
      body{font-family:Arial,sans-serif;padding:24px;color:#111;}
      .table{width:100%;border-collapse:collapse;margin:8px 0;}
      .table th{background:#f4f4f4;text-align:right;padding:8px;border:1px solid #ddd;}
      .table td{padding:8px;border:1px solid #ddd;text-align:right;}
      .payslip-name{font-size:18px;}
      .payslip-total-row td{background:#fbfbfb;font-weight:bold;}
      .payslip-net{margin-top:16px;font-size:16px;text-align:center;padding:12px;border:2px solid #222;border-radius:8px;}
      .muted{color:#888;font-size:13px;}
    </style></head><body>${body}</body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => { w.print(); }, 300);
}

window.openRunModal = openRunModal;
window.closeRunModal = closeRunModal;
window.createRun = createRun;
window.updateRunStatus = updateRunStatus;
window.recalculateRun = recalculateRun;
window.deleteRun = deleteRun;
window.openLinesModal = openLinesModal;
window.closeLinesModal = closeLinesModal;
window.openPayslip = openPayslip;
window.closePayslipModal = closePayslipModal;
window.printPayslip = printPayslip;

loadRuns();

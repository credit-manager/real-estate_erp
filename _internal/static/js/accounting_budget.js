/* Budget planning */
let budgetMeta = null;

async function loadBudget() {
  const yearId = document.getElementById("budget-year").value;
  const tbody = document.getElementById("budget-table");
  try {
    const data = await api.get("/accounting/api/budget?year_id=" + yearId);
    const existing = {};
    data.rows.forEach((r) => existing[r.account_id] = r);
    const accounts = budgetMeta.accounts.filter((a) => a.type === "expense" || a.type === "revenue");
    tbody.innerHTML = accounts.map((a) => {
      const row = existing[a.id] || {};
      return `
      <tr>
        <td><strong>${escapeHtml(a.code)}</strong></td>
        <td>${escapeHtml(a.name)}</td>
        <td>${acctTypeBadge(a.type)}</td>
        <td><input type="number" class="budget-input" data-account="${a.id}" min="0" step="0.01" value="${row.amount ?? ""}" ${canAction("accounting", "create") ? "" : "disabled"}></td>
        <td class="${moneyClass(row.actual)}">${fmtMoney(row.actual)}</td>
        <td class="${moneyClass(row.variance)}">${fmtMoney(row.variance)}</td>
      </tr>`;
    }).join("") || `<tr><td colspan="6"><div class="empty-state">${t("accounting.noAccounts")}</div></td></tr>`;
    document.getElementById("budget-total").textContent = fmtMoney(data.total_budget);
    document.getElementById("budget-actual").textContent = fmtMoney(data.total_actual);
    document.getElementById("budget-variance").textContent = fmtMoney(data.total_budget - data.total_actual);
  } catch (e) { toastError(e); }
}

async function saveBudget() {
  const yearId = document.getElementById("budget-year").value;
  if (!yearId) { showToast(t("accounting.yearRequired"), "warning"); return; }
  const lines = [];
  document.querySelectorAll(".budget-input").forEach((inp) => {
    lines.push({
      account_id: parseInt(inp.dataset.account),
      amount: parseFloat(inp.value) || 0,
    });
  });
  try {
    await api.post("/accounting/api/budget", { financial_year_id: parseInt(yearId), lines });
    showToast(t("common.savedSuccess"));
    loadBudget();
  } catch (e) { toastError(e); }
}

window.loadBudget = loadBudget;
window.saveBudget = saveBudget;

document.addEventListener("DOMContentLoaded", async () => {
  try {
    budgetMeta = await api.get("/accounting/api/meta");
    const sel = document.getElementById("budget-year");
    sel.innerHTML = `<option value="">${t("accounting.allYears")}</option>` +
      budgetMeta.years.map((y) => `<option value="${y.id}">${escapeHtml(y.name)}</option>`).join("");
    loadBudget();
  } catch (e) { toastError(e); }
});

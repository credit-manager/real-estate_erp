/* Accounting landing page */

function goTo(section) {
  const urls = {
    journal: "/accounting/journal",
    reports: "/accounting/reports",
  };
  window.location.href = urls[section] || "/accounting";
}

async function loadSummary() {
  try {
    const meta = await api.get("/accounting/api/meta");
    const cash = meta.cash_accounts.reduce((s, a) => s + a.balance, 0);
    const banks = meta.bank_accounts.reduce((s, a) => s + a.balance, 0);
    const el = (id, v, cls) => {
      const node = document.getElementById(id);
      if (node) { node.textContent = fmtMoney(v); if (cls) node.className = "stat-value " + cls; }
    };
    el("acc-cash", cash);
    el("acc-banks", banks);
    const [ar, ap, pl] = await Promise.all([
      api.get("/accounting/api/receivables"),
      api.get("/accounting/api/payables"),
      api.get("/accounting/api/reports/pl"),
    ]);
    el("acc-ar", ar.total);
    el("acc-ap", ap.total);
    el("acc-net", pl.net_income, pl.net_income < 0 ? "stat-value text-danger" : "stat-value text-success");
  } catch (e) { /* meta already fetched */ }
}

window.goTo = goTo;
document.addEventListener("DOMContentLoaded", loadSummary);

/* Receivables (AR) / Payables (AP) */
let currentTab = "ar";

async function loadAR(tab) {
  currentTab = tab || currentTab;
  const url = currentTab === "ar" ? "/accounting/api/receivables" : "/accounting/api/payables";
  try {
    const data = await api.get(url);
    const aging = data.aging || {};
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = fmtMoney(v); };
    set("aging-0", aging["0-30"] || 0);
    set("aging-1", aging["31-60"] || 0);
    set("aging-2", aging["61-90"] || 0);
    set("aging-3", aging["90+"] || 0);
    set("aging-total", data.total);
    const tbody = document.getElementById("ar-table");
    tbody.innerHTML = data.rows.length ? data.rows.map((r) => `
      <tr>
        <td><strong>${escapeHtml(r.party)}</strong>
          <div class="table-sub">${escapeHtml(r.invoice_number)}</div>
        </td>
        <td>${escapeHtml(r.invoice_number)}</td>
        <td>${formatDate(r.date)}</td>
        <td>${formatDate(r.due_date)}</td>
        <td>${fmtMoney(r.amount)}</td>
        <td class="text-success">${fmtMoney(r.paid)}</td>
        <td class="${moneyClass(r.balance)}"><strong>${fmtMoney(r.balance)}</strong></td>
      </tr>`).join("") : `<tr><td colspan="7"><div class="empty-state">${t("accounting.noBalances")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get("tab") === "ap" ? "ap" : "ar";
  initTabs("ar-tabs", (tab) => loadAR(tab));
  const tabBtns = document.querySelectorAll("#ar-tabs .tab-btn");
  tabBtns.forEach((b) => { b.classList.toggle("active", b.dataset.tab === initialTab); });
  loadAR(initialTab);
});

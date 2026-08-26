/* Expenses / Revenues */
let inexpMeta = null;
let inexpTab = "expense";

async function loadIncExp() {
  const start = document.getElementById("inexp-start").value;
  const end = document.getElementById("inexp-end").value;
  const params = new URLSearchParams({ type: inexpTab });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  try {
    const data = await api.get("/accounting/api/entries/by-type?" + params.toString());
    const tbody = document.getElementById("inexp-table");
    tbody.innerHTML = data.rows.length ? data.rows.map((r) => `
      <tr>
        <td>${formatDate(r.date)}</td>
        <td>${escapeHtml(r.entry_number || "")}</td>
        <td>${escapeHtml(r.account_code || "")} - ${escapeHtml(r.account_name || "")}</td>
        <td>${escapeHtml(r.cost_center || "—")}</td>
        <td>${escapeHtml(r.description || "")}</td>
        <td class="${moneyClass(r.amount)}"><strong>${fmtMoney(r.amount)}</strong></td>
      </tr>`).join("") : `<tr><td colspan="6"><div class="empty-state">${t("accounting.noEntries")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

async function loadIncExpMeta() {
  try {
    inexpMeta = await api.get("/accounting/api/meta");
    const accSel = document.getElementById("inexp-account");
    accSel.innerHTML = `<option value="">${t("common.select")}</option>` + inexpMeta.accounts
      .filter((a) => a.type === inexpTab)
      .map((a) => `<option value="${a.id}">${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
    const cashSel = document.getElementById("inexp-cashaccount");
    cashSel.innerHTML = `<option value="">${t("common.select")}</option>` +
      [...inexpMeta.cash_accounts, ...inexpMeta.bank_accounts]
        .map((a) => `<option value="${a.id}">${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
    document.getElementById("inexp-cc").innerHTML = costCenterOptions(inexpMeta.cost_centers);
    const yr = document.getElementById("inexp-year");
    yr.innerHTML = `<option value="">${t("common.select")}</option>` +
      inexpMeta.years.map((y) => `<option value="${y.id}">${escapeHtml(y.name)}</option>`).join("");
  } catch (e) { toastError(e); }
}

function openIncExpModal() {
  document.getElementById("inexp-modal-title").textContent = inexpTab === "expense" ? t("accounting.newExpense") : t("accounting.newRevenue");
  document.getElementById("inexp-amount").value = "";
  document.getElementById("inexp-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("inexp-desc").value = "";
  loadIncExpMeta();
  document.getElementById("inexp-modal").classList.add("active");
}

function closeIncExpModal() { document.getElementById("inexp-modal").classList.remove("active"); }

async function saveIncExp() {
  const account_id = parseInt(document.getElementById("inexp-account").value) || null;
  const amount = parseFloat(document.getElementById("inexp-amount").value) || 0;
  if (!account_id) { showToast(t("accounting.accountRequired"), "warning"); return; }
  if (amount <= 0) { showToast(t("accounting.amountPositive"), "warning"); return; }
  const body = {
    account_id,
    amount,
    date: document.getElementById("inexp-date").value,
    funding: document.getElementById("inexp-funding").value,
    cash_account_id: parseInt(document.getElementById("inexp-cashaccount").value) || null,
    cost_center_id: parseInt(document.getElementById("inexp-cc").value) || null,
    financial_year_id: parseInt(document.getElementById("inexp-year").value) || null,
    description: document.getElementById("inexp-desc").value.trim(),
  };
  try {
    const url = inexpTab === "expense" ? "/accounting/api/expense" : "/accounting/api/revenue";
    await api.post(url, body);
    showToast(t("common.savedSuccess"));
    closeIncExpModal();
    loadIncExp();
  } catch (e) { toastError(e); }
}

function onTabSwitch(tab) {
  inexpTab = tab;
  const btn = document.getElementById("add-inexp-btn");
  if (btn) btn.textContent = tab === "expense" ? t("accounting.newExpense") : t("accounting.newRevenue");
  loadIncExp();
}

window.openIncExpModal = openIncExpModal;
window.closeIncExpModal = closeIncExpModal;
window.saveIncExp = saveIncExp;
window.loadIncExp = loadIncExp;

document.addEventListener("DOMContentLoaded", () => {
  initTabs("inexp-tabs", onTabSwitch);
  loadIncExpMeta();
  loadIncExp();
});

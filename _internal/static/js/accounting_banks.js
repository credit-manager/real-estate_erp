/* Bank accounts + operations */
let banksMeta = null;
let editingBankId = null;

async function loadBanks() {
  try {
    const data = await api.get("/accounting/api/banks");
    const tbody = document.getElementById("banks-table");
    tbody.innerHTML = data.accounts.length ? data.accounts.map((a) => `
      <tr>
        <td><strong>${escapeHtml(a.code)}</strong></td>
        <td>${escapeHtml(a.name)}</td>
        <td>${escapeHtml(a.bank_name || "—")}</td>
        <td>${escapeHtml(a.account_number || "—")}</td>
        <td class="${moneyClass(a.balance)}"><strong>${fmtMoney(a.balance)}</strong></td>
        <td>
          <div class="table-actions">
            ${canAction("accounting", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editBank(${JSON.stringify(a)})'>${t("common.edit")}</button>` : ""}
            ${canAction("accounting", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteBank(${a.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="6"><div class="empty-state">${t("accounting.noBankAccounts")}</div></td></tr>`;

    const sel = document.getElementById("bank-account");
    sel.innerHTML = `<option value="">${t("common.select")}</option>` + data.accounts.map((a) =>
      `<option value="${a.id}" ${a.id == data.defaults.bank ? "selected" : ""}>${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
    loadBankLedger();
  } catch (e) { toastError(e); }
}

async function loadBankLedger() {
  const accountId = document.getElementById("bank-account").value;
  const tbody = document.getElementById("bank-ledger-table");
  if (!accountId) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state">${t("accounting.selectAccount")}</div></td></tr>`;
    document.getElementById("bank-balance").innerHTML = "";
    return;
  }
  try {
    const data = await api.get(`/accounting/api/bank/ledger?account_id=${accountId}`);
    document.getElementById("bank-balance").innerHTML = `<strong>${t("accounting.balance")}: ${fmtMoney(data.balance)}</strong>`;
    tbody.innerHTML = data.rows.length ? data.rows.map((r) => `
      <tr>
        <td>${formatDate(r.date)}</td>
        <td>${escapeHtml(r.entry_number || "")}</td>
        <td>${escapeHtml(r.description || "")}</td>
        <td class="text-success">${r.debit ? fmtMoney(r.debit) : "—"}</td>
        <td class="text-danger">${r.credit ? fmtMoney(r.credit) : "—"}</td>
        <td><strong>${fmtMoney(r.balance)}</strong></td>
      </tr>`).join("") : `<tr><td colspan="6"><div class="empty-state">${t("accounting.noEntries")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

function openBankModal(bk) {
  editingBankId = bk ? bk.id : null;
  document.getElementById("bk-code").value = bk ? bk.code : "";
  document.getElementById("bk-name").value = bk ? bk.name : "";
  document.getElementById("bk-bankname").value = bk ? bk.bank_name || "" : "";
  document.getElementById("bk-acctnum").value = bk ? bk.account_number || "" : "";
  document.getElementById("bk-opening").value = bk ? bk.opening_balance || 0 : 0;
  document.getElementById("bk-currency").value = bk ? bk.currency_code || "" : "";
  document.getElementById("bank-modal").classList.add("active");
}

function editBank(bk) { openBankModal(bk); }
function closeBankModal() { document.getElementById("bank-modal").classList.remove("active"); }

async function saveBank() {
  const code = document.getElementById("bk-code").value.trim();
  const name = document.getElementById("bk-name").value.trim();
  if (!code || !name) { showToast(t("common.required"), "warning"); return; }
  const body = {
    code, name,
    type: "asset",
    is_bank: true,
    bank_name: document.getElementById("bk-bankname").value.trim() || null,
    account_number: document.getElementById("bk-acctnum").value.trim() || null,
    opening_balance: parseFloat(document.getElementById("bk-opening").value) || 0,
    currency_code: document.getElementById("bk-currency").value.trim() || null,
  };
  try {
    if (editingBankId) await api.put(`/accounting/api/accounts/${editingBankId}`, body);
    else await api.post("/accounting/api/accounts", body);
    showToast(t("common.savedSuccess"));
    closeBankModal();
    loadBanks();
  } catch (e) { toastError(e); }
}

async function deleteBank(id) {
  if (!confirm(t("accounting.confirmDeleteAccount"))) return;
  try {
    await api.delete(`/accounting/api/accounts/${id}`);
    showToast(t("common.deleted"));
    loadBanks();
  } catch (e) { toastError(e); }
}

let bankOpDirection = "receive";
function openOpModal(direction) {
  bankOpDirection = direction;
  document.getElementById("op-modal-title").textContent = direction === "receive" ? t("accounting.receive") : t("accounting.pay");
  document.getElementById("op-amount").value = "";
  document.getElementById("op-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("op-desc").value = "";
  document.getElementById("op-modal").classList.add("active");
}

async function saveOp() {
  const amount = parseFloat(document.getElementById("op-amount").value) || 0;
  const accountId = document.getElementById("bank-account").value;
  if (!accountId) { showToast(t("accounting.accountRequired"), "warning"); return; }
  if (amount <= 0) { showToast(t("accounting.amountPositive"), "warning"); return; }
  const body = {
    account_id: accountId,
    amount,
    direction: bankOpDirection,
    date: document.getElementById("op-date").value,
    counterpart_account_id: parseInt(document.getElementById("op-counterpart").value) || null,
    cost_center_id: parseInt(document.getElementById("op-cc").value) || null,
    financial_year_id: parseInt(document.getElementById("op-year").value) || null,
    description: document.getElementById("op-desc").value.trim(),
  };
  try {
    await api.post("/accounting/api/bank/op", body);
    showToast(t("common.savedSuccess"));
    closeOpModal();
    loadBankLedger();
  } catch (e) { toastError(e); }
}

function closeOpModal() { document.getElementById("op-modal").classList.remove("active"); }

async function initBankSelects() {
  try {
    banksMeta = await api.get("/accounting/api/meta");
    const counter = document.getElementById("op-counterpart");
    if (!counter) return;
    counter.innerHTML = `<option value="">${t("common.select")}</option>` + banksMeta.accounts.map((a) =>
      `<option value="${a.id}">${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
    const cc = document.getElementById("op-cc");
    if (cc) cc.innerHTML = costCenterOptions(banksMeta.cost_centers);
    const yr = document.getElementById("op-year");
    if (yr) yr.innerHTML = `<option value="">${t("common.select")}</option>` +
      banksMeta.years.map((y) => `<option value="${y.id}">${escapeHtml(y.name)}</option>`).join("");
  } catch (e) { toastError(e); }
}

window.openBankModal = openBankModal;
window.editBank = editBank;
window.closeBankModal = closeBankModal;
window.saveBank = saveBank;
window.deleteBank = deleteBank;
window.openOpModal = openOpModal;
window.closeOpModal = closeOpModal;
window.saveOp = saveOp;
window.loadBanks = loadBanks;
window.loadBankLedger = loadBankLedger;

document.addEventListener("DOMContentLoaded", () => {
  initBankSelects();
  loadBanks();
});

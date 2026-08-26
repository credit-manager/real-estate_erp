/* Cash operations */
let cashMeta = null;
let opDirection = "receive";
let currentKind = "cash";

async function loadCash() {
  const accountId = document.getElementById("cash-account").value;
  if (!accountId) {
    document.getElementById("cash-table").innerHTML =
      `<tr><td colspan="6"><div class="empty-state">${t("accounting.selectAccount")}</div></td></tr>`;
    return;
  }
  try {
    const data = await api.get(`/accounting/api/${currentKind}/ledger?account_id=${accountId}`);
    document.getElementById("cash-balance").innerHTML =
      `<strong>${t("accounting.balance")}: ${fmtMoney(data.balance)}</strong>`;
    const tbody = document.getElementById("cash-table");
    let running = parseFloat(data.account.opening_balance || 0);
    tbody.innerHTML = data.rows.length ? data.rows.map((r) => {
      running = r.balance;
      return `
      <tr>
        <td>${formatDate(r.date)}</td>
        <td>${escapeHtml(r.entry_number || "")}</td>
        <td>${escapeHtml(r.description || "")}</td>
        <td class="text-success">${r.debit ? fmtMoney(r.debit) : "—"}</td>
        <td class="text-danger">${r.credit ? fmtMoney(r.credit) : "—"}</td>
        <td><strong>${fmtMoney(r.balance)}</strong></td>
      </tr>`;
    }).join("") : `<tr><td colspan="6"><div class="empty-state">${t("accounting.noEntries")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

async function loadCashMeta() {
  try {
    const url = currentKind === "cash" ? "/accounting/api/cash" : "/accounting/api/banks";
    const data = await api.get(url);
    const accounts = data.accounts;
    const sel = document.getElementById("cash-account");
    sel.innerHTML = `<option value="">${t("common.select")}</option>` + accounts.map((a) =>
      `<option value="${a.id}" ${a.id == data.defaults[currentKind] ? "selected" : ""}>${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
    const meta = await api.get("/accounting/api/meta");
    cashMeta = { ...data, accounts: meta.accounts, cost_centers: meta.cost_centers, years: meta.years };
    fillOpSelects();
    loadCash();
  } catch (e) { toastError(e); }
}

function fillOpSelects() {
  if (!cashMeta) return;
  const counter = document.getElementById("op-counterpart");
  counter.innerHTML = `<option value="">${t("common.select")}</option>` + cashMeta.accounts.map((a) =>
    `<option value="${a.id}">${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
  const cc = document.getElementById("op-cc");
  cc.innerHTML = costCenterOptions(cashMeta.cost_centers);
  const yr = document.getElementById("op-year");
  yr.innerHTML = `<option value="">${t("common.select")}</option>` +
    cashMeta.years.map((y) => `<option value="${y.id}">${escapeHtml(y.name)}</option>`).join("");
}

function openOpModal(direction) {
  opDirection = direction;
  document.getElementById("op-modal-title").textContent = direction === "receive" ? t("accounting.receive") : t("accounting.pay");
  document.getElementById("op-amount").value = "";
  document.getElementById("op-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("op-desc").value = "";
  document.getElementById("op-modal").classList.add("active");
}

function closeOpModal() { document.getElementById("op-modal").classList.remove("active"); }

async function saveOp() {
  const amount = parseFloat(document.getElementById("op-amount").value) || 0;
  const accountId = document.getElementById("cash-account").value;
  if (!accountId) { showToast(t("accounting.accountRequired"), "warning"); return; }
  if (amount <= 0) { showToast(t("accounting.amountPositive"), "warning"); return; }
  const body = {
    account_id: accountId,
    amount,
    direction: opDirection,
    date: document.getElementById("op-date").value,
    counterpart_account_id: parseInt(document.getElementById("op-counterpart").value) || null,
    cost_center_id: parseInt(document.getElementById("op-cc").value) || null,
    financial_year_id: parseInt(document.getElementById("op-year").value) || null,
    description: document.getElementById("op-desc").value.trim(),
  };
  try {
    await api.post(`/accounting/api/${currentKind}/op`, body);
    showToast(t("common.savedSuccess"));
    closeOpModal();
    loadCash();
  } catch (e) { toastError(e); }
}

window.openOpModal = openOpModal;
window.closeOpModal = closeOpModal;
window.saveOp = saveOp;
window.loadCash = loadCash;

document.addEventListener("DOMContentLoaded", loadCashMeta);

/* Chart of Accounts */
let allAccounts = [];
let accountMeta = null;
let editingAccountId = null;

const DEFAULT_FIELD_LABELS = {
  acc_default_cash: "accounting.defCash",
  acc_default_bank: "accounting.defBank",
  acc_default_receivable: "accounting.defReceivable",
  acc_default_payable: "accounting.defPayable",
  acc_default_revenue: "accounting.defRevenue",
  acc_default_expense: "accounting.defExpense",
  acc_default_asset: "accounting.defAsset",
  acc_default_accumulated: "accounting.defAccumulated",
  acc_default_depreciation: "accounting.defDepreciation",
  acc_default_tax_in: "accounting.defTaxIn",
  acc_default_tax_out: "accounting.defTaxOut",
};

async function loadAccounts() {
  const end = document.getElementById("chart-end").value || "";
  try {
    allAccounts = await api.get("/accounting/api/accounts" + (end ? `?end_date=${end}` : ""));
    renderTree();
  } catch (e) { toastError(e); }
}

// مقارنة رقمية صحيحة لأكواد الحسابات (بدلاً من المقارنة النصية)
function compareCodes(x, y) {
  const nx = parseFloat(x.code) || 0;
  const ny = parseFloat(y.code) || 0;
  if (nx !== ny) return nx - ny;
  return String(x.code).localeCompare(String(y.code));
}

function renderTree() {
  const tbody = document.getElementById("accounts-table");
  const byParent = {};
  const roots = [];
  for (const a of allAccounts) {
    if (a.parent_id) (byParent[a.parent_id] = byParent[a.parent_id] || []).push(a);
    else roots.push(a);
  }
  const rows = [];
  const walk = (list, depth) => {
    for (const a of list) {
      const kids = byParent[a.id] || [];
      rows.push(`
        <tr>
          <td style="padding-inline-start:${12 + depth * 20}px;"><strong>${escapeHtml(a.code)}</strong></td>
          <td>${escapeHtml(a.name)}</td>
          <td>${acctTypeBadge(a.type)}</td>
          <td>
            ${a.is_cash ? `<span class="badge badge-success">${t("accounting.cashBox")}</span>` : ""}
            ${a.is_bank ? `<span class="badge badge-info">${t("accounting.bank")}</span>` : ""}
            ${a.is_contra ? `<span class="badge badge-warning">${t("accounting.contra")}</span>` : ""}
            ${!a.is_active ? `<span class="badge badge-danger">${t("accounting.inactive")}</span>` : ""}
          </td>
          <td class="${moneyClass(a.balance)}">${fmtMoney(a.balance)}</td>
          <td>
            <div class="table-actions">
              ${canAction("accounting", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editAccount(${JSON.stringify(a)})'>${t("common.edit")}</button>` : ""}
              ${canAction("accounting", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteAccount(${a.id})">${t("common.delete")}</button>` : ""}
            </div>
          </td>
        </tr>`);
      if (kids.length) walk(kids.sort(compareCodes), depth + 1);
    }
  };
  roots.sort(compareCodes);
  walk(roots, 0);
  tbody.innerHTML = rows.length ? rows.join("") :
    `<tr><td colspan="6"><div class="empty-state">${t("accounting.noAccounts")}</div></td></tr>`;
}

async function loadMeta() {
  try {
    accountMeta = await api.get("/accounting/api/meta");
    // ترتيب الحسابات رقمياً في القوائم المنسدلة
    const sorted = [...accountMeta.accounts].sort(compareCodes);
    const sel = document.getElementById("acc-parent");
    sel.innerHTML = `<option value="">—</option>` + sorted
      .map((a) => `<option value="${a.id}">${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
    renderDefaultsFields();
  } catch (e) { toastError(e); }
}

function renderDefaultsFields() {
  const container = document.getElementById("defaults-fields");
  if (!container || !accountMeta) return;
  const fields = [];
  const sorted = [...accountMeta.accounts].sort(compareCodes);
  for (const key of Object.keys(DEFAULT_FIELD_LABELS)) {
    fields.push(`
      <div class="form-group">
        <label>${t(DEFAULT_FIELD_LABELS[key])}</label>
        <select class="def-select" data-key="${key}">
          <option value="">—</option>
          ${sorted.map((a) => `<option value="${a.id}" ${a.id == accountMeta.defaults[key] ? "selected" : ""}>${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("")}
        </select>
      </div>`);
  }
  container.innerHTML = fields.join("");
}

function openAccountModal(acc) {
  editingAccountId = acc ? acc.id : null;
  document.getElementById("account-modal-title").textContent = acc ? t("accounting.editAccount") : t("accounting.newAccount");
  document.getElementById("acc-code").value = acc ? acc.code : "";
  document.getElementById("acc-name").value = acc ? acc.name : "";
  document.getElementById("acc-type").value = acc ? acc.type : "asset";
  document.getElementById("acc-parent").value = acc && acc.parent_id ? acc.parent_id : "";
  document.getElementById("acc-opening").value = acc ? acc.opening_balance || 0 : 0;
  document.getElementById("acc-currency").value = acc ? acc.currency_code || "" : "";
  document.getElementById("acc-active").checked = acc ? acc.is_active !== false : true;
  document.getElementById("acc-cash").checked = acc ? !!acc.is_cash : false;
  document.getElementById("acc-bank").checked = acc ? !!acc.is_bank : false;
  document.getElementById("acc-contra").checked = acc ? !!acc.is_contra : false;
  document.getElementById("acc-bankname").value = acc ? acc.bank_name || "" : "";
  document.getElementById("acc-acctnum").value = acc ? acc.account_number || "" : "";
  document.getElementById("acc-desc").value = acc ? acc.description || "" : "";
  toggleBankFields();
  document.getElementById("account-modal").classList.add("active");
}

function editAccount(acc) { openAccountModal(acc); }

function closeAccountModal() { document.getElementById("account-modal").classList.remove("active"); }

function toggleBankFields() {
  const bank = document.getElementById("acc-bank").checked;
  document.getElementById("bank-fields").style.display = bank ? "flex" : "none";
}

async function saveAccount() {
  const code = document.getElementById("acc-code").value.trim();
  const name = document.getElementById("acc-name").value.trim();
  if (!code || !name) { showToast(t("common.required"), "warning"); return; }
  const body = {
    code, name,
    type: document.getElementById("acc-type").value,
    parent_id: parseInt(document.getElementById("acc-parent").value) || null,
    opening_balance: parseFloat(document.getElementById("acc-opening").value) || 0,
    currency_code: document.getElementById("acc-currency").value.trim() || null,
    is_active: document.getElementById("acc-active").checked,
    is_cash: document.getElementById("acc-cash").checked,
    is_bank: document.getElementById("acc-bank").checked,
    is_contra: document.getElementById("acc-contra").checked,
    bank_name: document.getElementById("acc-bankname").value.trim() || null,
    account_number: document.getElementById("acc-acctnum").value.trim() || null,
    description: document.getElementById("acc-desc").value.trim() || null,
  };
  try {
    if (editingAccountId) await api.put(`/accounting/api/accounts/${editingAccountId}`, body);
    else await api.post("/accounting/api/accounts", body);
    showToast(t("common.savedSuccess"));
    closeAccountModal();
    await loadMeta();
    await loadAccounts();
  } catch (e) { toastError(e); }
}

async function deleteAccount(id) {
  if (!confirm(t("accounting.confirmDeleteAccount"))) return;
  try {
    await api.delete(`/accounting/api/accounts/${id}`);
    showToast(t("common.deleted"));
    await loadMeta();
    await loadAccounts();
  } catch (e) { toastError(e); }
}

function openDefaultsModal() {
  renderDefaultsFields();
  document.getElementById("defaults-modal").classList.add("active");
}

function closeDefaultsModal() { document.getElementById("defaults-modal").classList.remove("active"); }

async function saveDefaults() {
  const body = {};
  document.querySelectorAll(".def-select").forEach((sel) => {
    body[sel.dataset.key] = sel.value ? parseInt(sel.value) : null;
  });
  try {
    await api.post("/accounting/api/accounts/defaults", body);
    showToast(t("common.savedSuccess"));
    closeDefaultsModal();
  } catch (e) { toastError(e); }
}

window.openAccountModal = openAccountModal;
window.editAccount = editAccount;
window.closeAccountModal = closeAccountModal;
window.saveAccount = saveAccount;
window.deleteAccount = deleteAccount;
window.openDefaultsModal = openDefaultsModal;
window.closeDefaultsModal = closeDefaultsModal;
window.saveDefaults = saveDefaults;
window.loadAccounts = loadAccounts;

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("acc-bank").addEventListener("change", toggleBankFields);
  loadMeta();
  loadAccounts();
});

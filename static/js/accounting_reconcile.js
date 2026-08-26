/* Reconciliations */
let recAccounts = [];

async function loadRecAccounts() {
  try {
    const meta = await api.get("/accounting/api/meta");
    recAccounts = [...meta.cash_accounts, ...meta.bank_accounts];
    const sel = document.getElementById("rec-account");
    sel.innerHTML = `<option value="">${t("common.select")}</option>` +
      recAccounts.map((a) => `<option value="${a.id}">${escapeHtml(a.code)} - ${escapeHtml(a.name)}</option>`).join("");
    loadRec();
  } catch (e) { toastError(e); }
}

async function loadRec() {
  const accountId = document.getElementById("rec-account").value;
  const tbody = document.getElementById("rec-table");
  if (!accountId) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state">${t("accounting.selectAccount")}</div></td></tr>`;
    document.getElementById("rec-balance").innerHTML = "";
    return;
  }
  try {
    const data = await api.get(`/accounting/api/reconciliations?account_id=${accountId}`);
    document.getElementById("rec-balance").innerHTML =
      `<strong>${t("accounting.balance")}: ${fmtMoney(data.balance)}</strong>`;
    tbody.innerHTML = data.rows.length ? data.rows.map((r) => `
      <tr>
        <td><input type="checkbox" class="rec-check" value="${r.line_id}"></td>
        <td>${formatDate(r.date)}</td>
        <td>${escapeHtml(r.entry_number || "")}</td>
        <td>${escapeHtml(r.description || "")}</td>
        <td class="text-success">${r.debit ? fmtMoney(r.debit) : "—"}</td>
        <td class="text-danger">${r.credit ? fmtMoney(r.credit) : "—"}</td>
      </tr>`).join("") : `<tr><td colspan="6"><div class="empty-state">${t("accounting.allReconciled")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

function toggleSelectAll(el) {
  document.querySelectorAll(".rec-check").forEach((c) => c.checked = el.checked);
}

async function doReconcile() {
  const ids = Array.from(document.querySelectorAll(".rec-check:checked")).map((c) => parseInt(c.value));
  if (!ids.length) { showToast(t("accounting.selectRows"), "warning"); return; }
  try {
    await api.post("/accounting/api/reconciliations/reconcile", { line_ids: ids });
    showToast(t("common.savedSuccess"));
    loadRec();
  } catch (e) { toastError(e); }
}

window.loadRec = loadRec;
window.doReconcile = doReconcile;
window.toggleSelectAll = toggleSelectAll;

document.addEventListener("DOMContentLoaded", loadRecAccounts);

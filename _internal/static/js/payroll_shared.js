/* ============================================================
   Payroll Module - Shared Helpers
   ============================================================ */

function prT(key) {
  return hrT(key);
}

function prCan(action) {
  const perms = window.PERMS || {};
  const acts = perms["payroll"] || [];
  return acts.indexOf(action) !== -1;
}

function prMoney(num) {
  const n = Number(num || 0);
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

function prBadge(key, cls) {
  return `<span class="badge ${cls}">${prT(key)}</span>`;
}

function prStatusBadge(status) {
  const map = {
    draft: ["badge-warning", "payroll.statusDraft"],
    finalized: ["badge-info", "payroll.statusFinalized"],
    paid: ["badge-success", "payroll.statusPaid"],
    approved: ["badge-success", "payroll.statusApproved"],
    pending: ["badge-warning", "payroll.statusPending"],
  };
  const m = map[status];
  if (!m) return `<span class="badge badge-neutral">${escapeHtml(status)}</span>`;
  return `<span class="badge ${m[0]}">${prT(m[1])}</span>`;
}

function prActionButtons(entity, obj, editFn, delFn, extra) {
  const btns = [];
  if (extra) btns.push(extra(obj));
  if (prCan("edit")) {
    btns.push(`<button class="icon-btn" title="${prT("common.edit")}" onclick='${editFn}(${JSON.stringify(obj)})'>✏️</button>`);
  }
  if (prCan("delete")) {
    btns.push(`<button class="icon-btn" title="${prT("common.delete")}" onclick="${delFn}(${obj.id})">🗑️</button>`);
  }
  return `<div class="table-actions">${btns.join("")}</div>`;
}

function prEmployeesOptions(employees, selected) {
  return employees.map((e) =>
    `<option value="${e.id}" ${e.id === selected ? "selected" : ""}>${escapeHtml(e.full_name)}</option>`
  ).join("");
}

function prAmountCell(value) {
  return `<b>${prMoney(value)}</b>`;
}

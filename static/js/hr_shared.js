/* ============================================================
   HR Module - Shared Helpers
   ============================================================ */

function hrT(key) {
  return (window.T && window.T[key] !== undefined && window.T[key] !== null) ? window.T[key] : key;
}

function hrCan(action) {
  const perms = window.PERMS || {};
  const acts = perms["hr"] || [];
  return acts.indexOf(action) !== -1;
}

function hrEmpTypeLabel(v) {
  const map = { full_time: "hr.empFullTime", part_time: "hr.empPartTime", fixed_term: "hr.empFixedTerm" };
  return map[v] ? hrT(map[v]) : v;
}

function hrBadge(key, cls) {
  return `<span class="badge ${cls}">${hrT(key)}</span>`;
}

function hrStatusBadge(status) {
  const map = {
    active: ["badge-success", "status.active"],
    present: ["badge-success", "hr.attPresent"],
    approved: ["badge-success", "hr.statusApproved"],
    completed: ["badge-success", "hr.trainingCompleted"],
    enrolled: ["badge-success", "hr.enrEnrolled"],
    hired: ["badge-success", "hr.recHired"],
    settled: ["badge-success", "hr.advSettled"],
    open: ["badge-warning", "hr.advOpen"],
    partial: ["badge-warning", "hr.advPartial"],
    pending: ["badge-warning", "hr.statusPending"],
    interview: ["badge-warning", "hr.recInterview"],
    offered: ["badge-info", "hr.recOffered"],
    on_leave: ["badge-warning", "status.on_leave"],
    late: ["badge-warning", "hr.attLate"],
    terminated: ["badge-danger", "status.terminated"],
    expired: ["badge-danger", "hr.contractExpired"],
    cancelled: ["badge-danger", "hr.statusCancelled"],
    rejected: ["badge-danger", "hr.statusRejected"],
    absent: ["badge-danger", "hr.attAbsent"],
    dropped: ["badge-danger", "hr.enrDropped"],
  };
  const m = map[status];
  if (!m) return `<span class="badge badge-neutral">${escapeHtml(status)}</span>`;
  return `<span class="badge ${m[0]}">${hrT(m[1])}</span>`;
}

function hrActiveBadge(isActive) {
  if (isActive === true || isActive === "true" || isActive === 1 || isActive === "1") {
    return hrBadge("common.active", "badge-success");
  }
  return hrBadge("common.inactive", "badge-secondary");
}

function hrActionButtons(entity, obj, editFn, delFn) {
  const btns = [];
  if (hrCan("edit")) {
    btns.push(`<button class="icon-btn" title="${hrT("common.edit")}" onclick='${editFn}(${JSON.stringify(obj)})'>✏️</button>`);
  }
  if (hrCan("delete")) {
    btns.push(`<button class="icon-btn" title="${hrT("common.delete")}" onclick="${delFn}(${obj.id})">🗑️</button>`);
  }
  return `<div class="table-actions">${btns.join("")}</div>`;
}

function hrEmployeesOptions(employees, selected) {
  return employees.map((e) =>
    `<option value="${e.id}" ${e.id === selected ? "selected" : ""}>${escapeHtml(e.full_name)}</option>`
  ).join("");
}

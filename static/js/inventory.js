function invT(key) {
  return (window.T && window.T[key] !== undefined && window.T[key] !== null) ? window.T[key] : key;
}

function invCan(action) {
  const perms = window.PERMS || {};
  const acts = perms["inventory"] || [];
  return acts.indexOf(action) !== -1;
}

function invBadge(status, isExpired) {
  if (status === "completed" || status === "posted" || status === "active" || status === "in_stock") {
    return `<span class="badge badge-success">${invT("inventory.statusInStock")}</span>`;
  }
  if (status === "draft") {
    return `<span class="badge badge-secondary">${invT("inventory.statusScrapped")}</span>`;
  }
  if (status === "sold") {
    return `<span class="badge badge-info">${invT("inventory.statusSold")}</span>`;
  }
  if (status === "scrapped") {
    return `<span class="badge badge-danger">${invT("inventory.statusScrapped")}</span>`;
  }
  if (isExpired) {
    return `<span class="badge badge-danger">${invT("inventory.expired")}</span>`;
  }
  return `<span class="badge badge-secondary">${status}</span>`;
}

function invStatusBadge(status) {
  if (status === true || status === "true" || status === 1 || status === "1") {
    return `<span class="badge badge-success">${invT("common.active")}</span>`;
  }
  return `<span class="badge badge-secondary">${invT("common.inactive")}</span>`;
}

function invActionButtons(entity, obj, perms) {
  const btns = [];
  if (invCan("edit")) {
    btns.push(`<button class="icon-btn" title="${invT("common.edit")}" onclick="edit${entity}(${JSON.stringify(obj)})">✏️</button>`);
  }
  if (invCan("delete")) {
    btns.push(`<button class="icon-btn" title="${invT("common.delete")}" onclick="del${entity}(${obj.id})">🗑️</button>`);
  }
  return `<div class="row-actions">${btns.join("")}</div>`;
}

function invEmptyState(el, msg) {
  const target = document.getElementById(el);
  if (!target) return;
  target.innerHTML = `<div class="empty-icon">📦</div><div>${msg}</div>`;
}

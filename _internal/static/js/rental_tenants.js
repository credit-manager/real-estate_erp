/* ============================================================
   Rental Tenants JavaScript
   ============================================================ */

let allTenants = [];

document.addEventListener("DOMContentLoaded", async () => {
  try {
    allTenants = await api.get("/api/rentals/tenants");
    renderTenants();
    renderTenantSummary();
  } catch (err) {
    console.error(err);
  }
});

function tenantBadge(tn) {
  if (!tn.is_active) return `<span class="badge badge-danger">${t("common.inactive")}</span>`;
  if (tn.active_contracts > 0) return `<span class="badge badge-success">${t("rentals.tenantActive")}</span>`;
  return `<span class="badge badge-muted">${t("rentals.tenantNoContract")}</span>`;
}

function renderTenants() {
  const tbody = document.getElementById("tenants-table");
  if (!allTenants.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">👤</div>${t("rentals.noTenants")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allTenants.map((tn) => {
    const units = (tn.units || []).filter(Boolean).join(", ") || "—";
    return `
      <tr>
        <td><strong>${escapeHtml(tn.full_name)}</strong>
          ${tn.company ? `<div class="table-sub">${escapeHtml(tn.company)}</div>` : ""}
        </td>
        <td style="color:var(--muted-foreground);">
          ${tn.phone ? `<div>${escapeHtml(tn.phone)}</div>` : ""}
          ${tn.email ? `<div class="table-sub">${escapeHtml(tn.email)}</div>` : ""}
        </td>
        <td><span class="badge badge-muted">${tn.type === "company" ? t("rentals.typeCompany") : t("rentals.typeIndividual")}</span></td>
        <td><strong>${tn.active_contracts}</strong><div class="table-sub">${t("rentals.activeContracts")}: ${tn.contracts_count}</div></td>
        <td><strong>${formatMoney(tn.monthly_total)}</strong></td>
        <td style="color:var(--muted-foreground);">${escapeHtml(units)}</td>
        <td>${tenantBadge(tn)}</td>
        <td>
          <div class="table-actions">
            ${canAction("rentals", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editTenant(${JSON.stringify(tn)})'>${t("common.edit")}</button>` : ""}
            ${canAction("rentals", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteTenant(${tn.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`;
  }).join("");
}

function renderTenantSummary() {
  animateCount(document.getElementById("tenant-total"), allTenants.length, formatNumber);
  animateCount(document.getElementById("tenant-active"), allTenants.filter((x) => x.active_contracts > 0).length, formatNumber);
  const monthly = allTenants.reduce((acc, x) => acc + (x.monthly_total || 0), 0);
  animateCount(document.getElementById("tenant-monthly"), monthly, formatMoney);
}

// ===== Modal =====
function openTenantModal() {
  document.getElementById("tenant-modal-title").textContent = t("rentals.newTenant");
  document.getElementById("tenant-id").value = "";
  document.getElementById("tenant-full-name").value = "";
  document.getElementById("tenant-phone").value = "";
  document.getElementById("tenant-email").value = "";
  document.getElementById("tenant-company").value = "";
  document.getElementById("tenant-address").value = "";
  document.getElementById("tenant-notes").value = "";
  document.getElementById("tenant-type").value = "individual";
  document.getElementById("tenant-modal").classList.add("active");
}

function editTenant(tn) {
  document.getElementById("tenant-modal-title").textContent = t("rentals.editTenant");
  document.getElementById("tenant-id").value = tn.id;
  document.getElementById("tenant-full-name").value = tn.full_name || "";
  document.getElementById("tenant-phone").value = tn.phone || "";
  document.getElementById("tenant-email").value = tn.email || "";
  document.getElementById("tenant-company").value = tn.company || "";
  document.getElementById("tenant-address").value = tn.address || "";
  document.getElementById("tenant-notes").value = "";
  document.getElementById("tenant-type").value = tn.type || "individual";
  document.getElementById("tenant-modal").classList.add("active");
}

function closeTenantModal() {
  document.getElementById("tenant-modal").classList.remove("active");
}

async function saveTenant() {
  const id = document.getElementById("tenant-id").value;
  const body = {
    full_name: document.getElementById("tenant-full-name").value,
    phone: document.getElementById("tenant-phone").value,
    email: document.getElementById("tenant-email").value,
    company: document.getElementById("tenant-company").value,
    address: document.getElementById("tenant-address").value,
    notes: document.getElementById("tenant-notes").value,
    type: document.getElementById("tenant-type").value,
  };
  if (!body.full_name) { showToast(t("rentals.nameRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/rentals/tenants/${id}`, body);
    else await api.post("/api/rentals/tenants", body);
    showToast(t("common.saved"));
    closeTenantModal();
    allTenants = await api.get("/api/rentals/tenants");
    renderTenants();
    renderTenantSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteTenant(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/rentals/tenants/${id}`);
    showToast(t("common.deleted"));
    allTenants = await api.get("/api/rentals/tenants");
    renderTenants();
    renderTenantSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openTenantModal = openTenantModal;
window.closeTenantModal = closeTenantModal;
window.editTenant = editTenant;
window.deleteTenant = deleteTenant;
window.saveTenant = saveTenant;

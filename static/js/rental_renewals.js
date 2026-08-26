/* ============================================================
   Rental Renewals JavaScript
   ============================================================ */

let allRenewals = [];
let allRentals = [];
let allCustomers = [];
let availableUnits = [];

document.addEventListener("DOMContentLoaded", async () => {
  try {
    [allRenewals, allRentals, allCustomers, availableUnits] = await Promise.all([
      api.get("/api/rentals/renewals"),
      api.get("/api/rental-contracts"),
      api.get("/api/customers"),
      api.get("/api/units"),
    ]);
    renderRenewals();
    renderRenewalSummary();
    populateRenewalContractSelect();
    const prefillId = new URLSearchParams(location.search).get("contract");
    if (prefillId) {
      const sel = document.getElementById("renewal-contract");
      sel.value = prefillId;
      sel.dispatchEvent(new Event("change"));
      document.getElementById("renewal-modal").classList.add("active");
    }
  } catch (err) {
    console.error(err);
  }
});

function populateRenewalContractSelect() {
  const select = document.getElementById("renewal-contract");
  const opts = allRentals
    .filter((r) => r.status === "active")
    .map((r) => {
      const customer = allCustomers.find((c) => c.id === r.customer_id);
      return `<option value="${r.id}">${escapeHtml(r.contract_number)} — ${customer ? escapeHtml(customer.full_name) : "—"}</option>`;
    });
  select.innerHTML = `<option value="">${t("rentals.selectContract")}</option>` + opts.join("");
}

document.getElementById("renewal-contract").addEventListener("change", (e) => {
  const id = parseInt(e.target.value, 10);
  const r = allRentals.find((x) => x.id === id);
  if (r) {
    document.getElementById("renewal-prev-end").value = r.end_date || "";
    document.getElementById("renewal-new-end").value = "";
    document.getElementById("renewal-prev-rent").value = r.monthly_rent || 0;
    document.getElementById("renewal-new-rent").value = r.monthly_rent || "";
  } else {
    document.getElementById("renewal-prev-end").value = "";
    document.getElementById("renewal-new-end").value = "";
    document.getElementById("renewal-prev-rent").value = "";
    document.getElementById("renewal-new-rent").value = "";
  }
});

function renewalStatusLabel(r) {
  const today = new Date();
  if (r.new_end_date) {
    const end = new Date(r.new_end_date);
    if (end < today) return `<span class="badge badge-danger">${t("rentals.statusExpired")}</span>`;
    const diff = Math.ceil((end - today) / (1000 * 60 * 60 * 24));
    if (diff <= 30) return `<span class="badge badge-warning">${t("rentals.statusEndingSoon")}</span>`;
  }
  return `<span class="badge badge-success">${t("rentals.statusActive")}</span>`;
}

function renderRenewals() {
  const tbody = document.getElementById("renewals-table");
  if (!allRenewals.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">🔄</div>${t("rentals.noRenewals")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allRenewals.map((r) => {
    const rentChange = r.new_monthly_rent !== r.previous_monthly_rent
      ? `<div class="table-sub" style="color:var(--amber);">${formatMoney(r.previous_monthly_rent)} → ${formatMoney(r.new_monthly_rent)}</div>`
      : "";
    return `
      <tr>
        <td><strong>${escapeHtml(r.renewal_number)}</strong></td>
        <td><strong>${escapeHtml(r.contract_number || "—")}</strong></td>
        <td style="color:var(--muted-foreground);">${escapeHtml(r.customer_name || "—")}</td>
        <td style="color:var(--muted-foreground);">${escapeHtml(r.unit_code || "—")}</td>
        <td style="color:var(--muted-foreground);">${formatDate(r.previous_end_date)}</td>
        <td><strong>${formatDate(r.new_end_date)}</strong>${renewalStatusLabel(r)}</td>
        <td style="color:var(--muted-foreground);">${formatMoney(r.previous_monthly_rent)}</td>
        <td><strong>${formatMoney(r.new_monthly_rent)}</strong>${rentChange}</td>
        <td>
          <div class="table-actions">
            ${canAction("rentals", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteRenewal(${r.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`;
  }).join("");
}

function renderRenewalSummary() {
  animateCount(document.getElementById("renewal-total"), allRenewals.length, formatNumber);
  const today = new Date();
  const active = allRenewals.filter((r) => r.new_end_date && new Date(r.new_end_date) >= today).length;
  animateCount(document.getElementById("renewal-active"), active, formatNumber);
  const upcoming = allRenewals.filter((r) => {
    if (!r.new_end_date) return false;
    const diff = (new Date(r.new_end_date) - today) / (1000 * 60 * 60 * 24);
    return diff >= 0 && diff <= 90;
  }).length;
  animateCount(document.getElementById("renewal-upcoming"), upcoming, formatNumber);
}

function exportRenewals() {
  const headers = [
    t("rentals.colNumber"), t("rentals.renewalContract"), t("common.customer"), t("common.unit"),
    t("rentals.previousEnd"), t("rentals.newEnd"), t("rentals.previousRent"), t("rentals.newRent"),
  ];
  const rows = allRenewals.map((r) => [
    r.renewal_number, r.contract_number || "", r.customer_name || "", r.unit_code || "",
    formatDate(r.previous_end_date), formatDate(r.new_end_date),
    r.previous_monthly_rent || 0, r.new_monthly_rent || 0,
  ]);
  exportCSV("rental-renewals.csv", headers, rows);
}

// ===== Modal =====
async function showEscalationHint() {
  const hint = document.getElementById("renewal-escalation-hint");
  if (!hint) return;
  try {
    const cfg = await api.get("/api/rentals/escalation-config");
    if (cfg && cfg.enabled && cfg.percent > 0) {
      hint.textContent = t("rentals.escalationHint").replace("{pct}", cfg.percent);
      hint.style.display = "block";
    } else {
      hint.style.display = "none";
    }
  } catch (e) { hint.style.display = "none"; }
}

function openRenewalModal() {
  document.getElementById("renewal-contract").value = "";
  document.getElementById("renewal-prev-end").value = "";
  document.getElementById("renewal-new-end").value = "";
  document.getElementById("renewal-prev-rent").value = "";
  document.getElementById("renewal-new-rent").value = "";
  document.getElementById("renewal-notes").value = "";
  populateRenewalContractSelect();
  showEscalationHint();
  document.getElementById("renewal-modal").classList.add("active");
}

function closeRenewalModal() {
  document.getElementById("renewal-modal").classList.remove("active");
}

async function saveRenewal() {
  const contract_id = parseInt(document.getElementById("renewal-contract").value, 10) || null;
  const body = {
    contract_id,
    new_end_date: document.getElementById("renewal-new-end").value,
    new_monthly_rent: parseFloat(document.getElementById("renewal-new-rent").value) || 0,
    notes: document.getElementById("renewal-notes").value,
  };
  if (!contract_id) { showToast(t("rentals.selectContract"), "warning"); return; }
  if (!body.new_end_date) { showToast(t("rentals.endDateRequired"), "warning"); return; }

  try {
    await api.post("/api/rentals/renewals", body);
    showToast(t("common.saved"));
    closeRenewalModal();
    [allRenewals, allRentals] = await Promise.all([
      api.get("/api/rentals/renewals"),
      api.get("/api/rental-contracts"),
    ]);
    renderRenewals();
    renderRenewalSummary();
    populateRenewalContractSelect();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteRenewal(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/rentals/renewals/${id}`);
    showToast(t("common.deleted"));
    allRenewals = await api.get("/api/rentals/renewals");
    renderRenewals();
    renderRenewalSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openRenewalModal = openRenewalModal;
window.closeRenewalModal = closeRenewalModal;
window.saveRenewal = saveRenewal;
window.deleteRenewal = deleteRenewal;
window.exportRenewals = exportRenewals;

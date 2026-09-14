/* ============================================================
   Rentals Module JavaScript
   ============================================================ */

let allRentals = [];
let availableUnits = [];
let allCustomers = [];

document.addEventListener("DOMContentLoaded", async () => {
  try {
    [allRentals, availableUnits, allCustomers] = await Promise.all([
      api.get("/api/rental-contracts"),
      api.get("/api/units"),
      api.get("/api/customers"),
    ]);
    await loadFinancialYearOptions();
    buildFinancialYearFilter("filter-year");
    renderRentals();
    renderSummary();
    populateUnitSelect();
    populateCustomerSelect();

    document.getElementById("filter-year").addEventListener("change", renderRentals);
  } catch (err) {
    console.error(err);
  }
});

function populateCustomerSelect() {
  const select = document.getElementById("rental-customer");
  const options = allCustomers.map((c) => `<option value="${c.id}">${escapeHtml(c.full_name)}</option>`);
  select.innerHTML = `<option value="">${t("rentals.selectCustomer")}</option>` + options.join("");
}

function populateUnitSelect() {
  const select = document.getElementById("rental-unit");
  const options = availableUnits
    .filter((u) => u.status !== "rented")
    .map((u) => `<option value="${u.id}">${u.unit_code}</option>`);
  select.innerHTML = `<option value="">${t("rentals.selectUnit")}</option>` + options.join("");
}

function renderRentals() {
  const year = selectedFinancialYear("filter-year");
  const rows = year ? allRentals.filter((r) => r.financial_year_id === year) : allRentals;
  const tbody = document.getElementById("rentals-table");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">🏢</div>${t("rentals.noContracts")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((r) => {
    const unit = availableUnits.find((u) => u.id === r.unit_id);
    const customer = allCustomers.find((c) => c.id === r.customer_id);
    return `
      <tr>
        <td><strong>${r.contract_number}</strong>
          ${r.financial_year_name ? `<div class="table-sub">${t("financialYears.year")}: ${escapeHtml(r.financial_year_name)}</div>` : ""}
        </td>
        <td style="color:var(--muted-foreground);">${customer ? escapeHtml(customer.full_name) : "—"}</td>
        <td style="color:var(--muted-foreground);">${unit ? unit.unit_code : "—"}</td>
        <td><strong>${moneyWithCurrency(r.monthly_rent, r)}</strong></td>
        <td style="color:var(--muted-foreground);">${formatDate(r.start_date)}</td>
        <td style="color:var(--muted-foreground);">${formatDate(r.end_date)}</td>
        <td>${statusBadge(r.status)}</td>
        <td>${approvalBadge(r.approval_status)}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-info btn-sm" onclick="window.open('/documents/contract/${r.id}', '_blank')">${t("common.print")}</button>
            <button class="btn btn-outline btn-sm" onclick="downloadPDF('/documents/contract/${r.id}/pdf')">${t("common.download")} PDF</button>
            ${r.status === "active" ? `<button class="btn btn-primary btn-sm" onclick="quickCollect(${r.id})">${t("rentals.quickCollect")}</button><button class="btn btn-secondary btn-sm" onclick="quickRenew(${r.id})">${t("rentals.quickRenew")}</button>` : ""}
            ${canAction("rentals", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editRental(${JSON.stringify(r)})'>${t("common.edit")}</button>` : ""}
            ${canAction("rentals", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteRental(${r.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`;
  }).join("");
}

function renderSummary() {
  animateCount(document.getElementById("rental-total"), allRentals.length, formatNumber);
  animateCount(document.getElementById("rental-active"), allRentals.filter((r) => r.status === "active").length, formatNumber);
  const monthly = allRentals.filter((r) => r.status === "active").reduce((acc, r) => acc + (r.monthly_rent || 0), 0);
  animateCount(document.getElementById("rental-monthly"), monthly, formatMoney);
}

function exportRentals() {
  const headers = [
    t("rentals.colNumber"), t("common.customer"), t("common.unit"),
    t("rentals.monthlyRent"), t("common.start"), t("common.end"), t("common.status"),
  ];
  const rows = allRentals.map((r) => {
    const unit = availableUnits.find((u) => u.id === r.unit_id);
    const customer = allCustomers.find((c) => c.id === r.customer_id);
    return [
      r.contract_number,
      customer ? customer.full_name : "",
      unit ? unit.unit_code : "",
      r.monthly_rent || 0,
      formatDate(r.start_date),
      formatDate(r.end_date),
      STATUS_LABELS[r.status] || r.status,
    ];
  });
  exportCSV("rental-contracts.csv", headers, rows);
}

// ===== Modal =====
function openRentalModal() {
  document.getElementById("rental-modal-title").textContent = t("rentals.newContractTitle");
  document.getElementById("rental-id").value = "";
  const numEl = document.getElementById("rental-number");
  numEl.value = "";
  prefillDocNumber(numEl, "contract", "RC-");
  document.getElementById("rental-monthly-input").value = "";
  document.getElementById("rental-start").value = "";
  document.getElementById("rental-end").value = "";
  document.getElementById("rental-unit").value = "";
  document.getElementById("rental-customer").value = "";
  populateUnitSelect();
  populateCustomerSelect();
  fillFinancialYearSelect("rental-year");
  document.getElementById("rental-modal").classList.add("active");
}

function editRental(r) {
  document.getElementById("rental-modal-title").textContent = t("rentals.editContract");
  document.getElementById("rental-id").value = r.id;
  document.getElementById("rental-number").value = r.contract_number || "";
  document.getElementById("rental-unit").value = r.unit_id || "";
  document.getElementById("rental-customer").value = r.customer_id || "";
  document.getElementById("rental-monthly-input").value = r.monthly_rent || "";
  document.getElementById("rental-start").value = r.start_date || "";
  document.getElementById("rental-end").value = r.end_date || "";
  populateUnitSelect();
  populateCustomerSelect();
  fillFinancialYearSelect("rental-year", r.financial_year_id);
  document.getElementById("rental-modal").classList.add("active");
}

function closeRentalModal() {
  document.getElementById("rental-modal").classList.remove("active");
}

async function saveRental() {
  const id = document.getElementById("rental-id").value;
  const body = {
    contract_number: document.getElementById("rental-number").value,
    unit_id: parseInt(document.getElementById("rental-unit").value) || null,
    customer_id: parseInt(document.getElementById("rental-customer").value) || null,
    monthly_rent: parseFloat(document.getElementById("rental-monthly-input").value) || 0,
    financial_year_id: financialYearValue("rental-year"),
    start_date: document.getElementById("rental-start").value,
    end_date: document.getElementById("rental-end").value,
  };
  if (!body.contract_number) { showToast(t("rentals.numberRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/rental-contracts/${id}`, body);
    else await api.post("/api/rental-contracts", body);
    showToast(t("common.saved"));
    closeRentalModal();
    [allRentals, availableUnits] = await Promise.all([
      api.get("/api/rental-contracts"),
      api.get("/api/units"),
    ]);
    renderRentals();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteRental(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/rental-contracts/${id}`);
    showToast(t("common.deleted"));
    [allRentals, availableUnits] = await Promise.all([
      api.get("/api/rental-contracts"),
      api.get("/api/units"),
    ]);
    renderRentals();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openRentalModal = openRentalModal;
window.closeRentalModal = closeRentalModal;
window.editRental = editRental;
window.deleteRental = deleteRental;
window.saveRental = saveRental;

function quickCollect(contractId) {
  const r = allRentals.find((x) => x.id === contractId);
  if (!r) return;
  const amount = prompt(`${t("rentals.quickCollectPrompt")} (${r.contract_number})`, r.monthly_rent || 0);
  if (amount === null || amount === "") return;
  const value = parseFloat(amount);
  if (isNaN(value) || value <= 0) { showToast(t("rentals.amountRequired"), "warning"); return; }
  collectPayment(r, value);
}

function collectPayment(r, amount) {
  const method = prompt(`${t("rentals.quickMethodPrompt")}: 1) ${t("rentals.methodCash")} 2) ${t("rentals.methodBank")} 3) ${t("rentals.methodTransfer")}`, "1");
  if (method === null) return;
  const methods = { "1": "cash", "2": "bank", "3": "transfer" };
  const selected = methods[(method || "").trim()] || "cash";
  api.post("/api/rentals/payments", {
    contract_id: r.id,
    amount,
    payment_date: new Date().toISOString().slice(0, 10),
    method: selected,
    reference: r.contract_number,
    notes: "",
  }).then(() => {
    showToast(t("common.saved"));
  }).catch((err) => {
    showToast(err.message, "error");
  });
}

function quickRenew(contractId) {
  location.href = `/rentals/renewals?contract=${contractId}`;
}

window.quickCollect = quickCollect;
window.quickRenew = quickRenew;

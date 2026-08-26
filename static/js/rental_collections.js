/* ============================================================
   Rental Collections JavaScript
   ============================================================ */

let allPayments = [];
let allRentals = [];
let allCustomers = [];
let availableUnits = [];

document.addEventListener("DOMContentLoaded", async () => {
  try {
    [allPayments, allRentals, allCustomers, availableUnits] = await Promise.all([
      api.get("/api/rentals/payments"),
      api.get("/api/rental-contracts"),
      api.get("/api/customers"),
      api.get("/api/units"),
    ]);
    renderPayments();
    renderCollectionSummary();
    populateContractFilter();
    populatePaymentContractSelect();
    document.getElementById("filter-contract").addEventListener("change", renderPayments);
  } catch (err) {
    console.error(err);
  }
});

function populateContractFilter() {
  const select = document.getElementById("filter-contract");
  const opts = allRentals.map((r) => {
    const customer = allCustomers.find((c) => c.id === r.customer_id);
    return `<option value="${r.id}">${escapeHtml(r.contract_number)} — ${customer ? escapeHtml(customer.full_name) : "—"}</option>`;
  });
  select.innerHTML = `<option value="">${t("rentals.allContracts")}</option>` + opts.join("");
}

function populatePaymentContractSelect() {
  const select = document.getElementById("payment-contract");
  const opts = allRentals.map((r) => {
    const customer = allCustomers.find((c) => c.id === r.customer_id);
    return `<option value="${r.id}">${escapeHtml(r.contract_number)} — ${customer ? escapeHtml(customer.full_name) : "—"}</option>`;
  });
  select.innerHTML = `<option value="">${t("rentals.selectContract")}</option>` + opts.join("");
}

function methodLabel(m) {
  const key = m === "bank" ? "rentals.methodBank" : m === "transfer" ? "rentals.methodTransfer" : "rentals.methodCash";
  return t(key);
}

function renderPayments() {
  const contractFilter = document.getElementById("filter-contract").value;
  let rows = allPayments;
  if (contractFilter) rows = allPayments.filter((p) => String(p.contract_id) === contractFilter);
  const tbody = document.getElementById("payments-table");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">💰</div>${t("rentals.noPayments")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((p) => {
    const unit = availableUnits.find((u) => u.id === (allRentals.find((r) => r.id === p.contract_id) || {}).unit_id);
    return `
      <tr>
        <td><strong>${escapeHtml(p.payment_number)}</strong></td>
        <td><strong>${escapeHtml(p.contract_number || "—")}</strong></td>
        <td style="color:var(--muted-foreground);">${escapeHtml(p.customer_name || "—")}</td>
        <td style="color:var(--muted-foreground);">${unit ? unit.unit_code : "—"}</td>
        <td style="color:var(--muted-foreground);">${formatDate(p.payment_date)}</td>
        <td><strong style="color:var(--primary);">${formatMoney(p.amount)}</strong></td>
        <td><span class="badge badge-muted">${methodLabel(p.method)}</span></td>
        <td style="color:var(--muted-foreground);">${escapeHtml(p.reference || "—")}</td>
        <td>
          <div class="table-actions">
            ${canAction("rentals", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editPayment(${JSON.stringify(p)})'>${t("common.edit")}</button>` : ""}
            ${canAction("rentals", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deletePayment(${p.id})">${t("common.delete")}</button>` : ""}
          </div>
        </td>
      </tr>`;
  }).join("");
}

function renderCollectionSummary() {
  const total = allPayments.reduce((acc, p) => acc + (p.amount || 0), 0);
  animateCount(document.getElementById("collected-total"), total, formatMoney);
  animateCount(document.getElementById("payments-count"), allPayments.length, formatNumber);
  const balance = allRentals.reduce((acc, r) => {
    if (r.status !== "active") return acc;
    const paid = allPayments.filter((p) => p.contract_id === r.id).reduce((s, p) => s + (p.amount || 0), 0);
    return acc + Math.max(0, (r.monthly_rent || 0) - paid);
  }, 0);
  animateCount(document.getElementById("balance-total"), balance, formatMoney);
}

function exportCollections() {
  const headers = [
    t("rentals.colPaymentNumber"), t("rentals.renewalContract"), t("common.customer"), t("common.unit"),
    t("rentals.paymentDate"), t("rentals.amount"), t("rentals.method"), t("rentals.reference"),
  ];
  const rows = allPayments.map((p) => [
    p.payment_number, p.contract_number || "", p.customer_name || "", p.unit_code || "",
    formatDate(p.payment_date), p.amount || 0, methodLabel(p.method), p.reference || "",
  ]);
  exportCSV("rental-collections.csv", headers, rows);
}

// ===== Modal =====
function openPaymentModal() {
  document.getElementById("payment-id").value = "";
  document.getElementById("payment-contract").value = "";
  document.getElementById("payment-amount").value = "";
  document.getElementById("payment-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("payment-method").value = "cash";
  document.getElementById("payment-reference").value = "";
  document.getElementById("payment-notes").value = "";
  populatePaymentContractSelect();
  document.getElementById("payment-modal").classList.add("active");
}

function editPayment(p) {
  document.getElementById("payment-id").value = p.id;
  document.getElementById("payment-contract").value = p.contract_id || "";
  document.getElementById("payment-amount").value = p.amount || "";
  document.getElementById("payment-date").value = p.payment_date || "";
  document.getElementById("payment-method").value = p.method || "cash";
  document.getElementById("payment-reference").value = p.reference || "";
  document.getElementById("payment-notes").value = p.notes || "";
  populatePaymentContractSelect();
  document.getElementById("payment-modal").classList.add("active");
}

function closePaymentModal() {
  document.getElementById("payment-modal").classList.remove("active");
}

async function savePayment() {
  const id = document.getElementById("payment-id").value;
  const body = {
    contract_id: parseInt(document.getElementById("payment-contract").value, 10) || null,
    amount: parseFloat(document.getElementById("payment-amount").value) || 0,
    payment_date: document.getElementById("payment-date").value,
    method: document.getElementById("payment-method").value,
    reference: document.getElementById("payment-reference").value,
    notes: document.getElementById("payment-notes").value,
  };
  if (!body.contract_id) { showToast(t("rentals.selectContract"), "warning"); return; }
  if (body.amount <= 0) { showToast(t("rentals.amountRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/rentals/payments/${id}`, body);
    else await api.post("/api/rentals/payments", body);
    showToast(t("common.saved"));
    closePaymentModal();
    allPayments = await api.get("/api/rentals/payments");
    renderPayments();
    renderCollectionSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deletePayment(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/rentals/payments/${id}`);
    showToast(t("common.deleted"));
    allPayments = await api.get("/api/rentals/payments");
    renderPayments();
    renderCollectionSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openPaymentModal = openPaymentModal;
window.closePaymentModal = closePaymentModal;
window.editPayment = editPayment;
window.deletePayment = deletePayment;
window.savePayment = savePayment;
window.exportCollections = exportCollections;

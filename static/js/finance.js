/* ============================================================
   Finance Module JavaScript
   ============================================================ */

let allInvoices = [];
let allCustomers = [];
let allSuppliers = [];
let defaultTaxRate = 0;

document.addEventListener("DOMContentLoaded", async () => {
  try {
    [allInvoices, allCustomers, allSuppliers] = await Promise.all([
      api.get("/api/invoices"),
      api.get("/api/customers"),
      api.get("/api/suppliers"),
    ]);
    await loadFinancialYearOptions();
    buildFinancialYearFilter("filter-year");
    renderInvoices();
    renderSummary();

    document.getElementById("filter-type").addEventListener("change", renderInvoices);
    document.getElementById("filter-status").addEventListener("change", renderInvoices);
    document.getElementById("filter-year").addEventListener("change", renderInvoices);
  } catch (err) {
    console.error(err);
  }
  api.get("/api/taxes/defaults").then((res) => {
    if (res && typeof res.default_rate === "number") defaultTaxRate = res.default_rate;
  }).catch(() => {});
});

function partyName(i) {
  if (i.invoice_type === "sales") {
    const c = allCustomers.find((c) => c.id === i.customer_id);
    return c ? escapeHtml(c.full_name) : null;
  }
  const s = allSuppliers.find((s) => s.id === i.supplier_id);
  return s ? escapeHtml(s.company_name) : null;
}

function renderInvoices() {
  const type = document.getElementById("filter-type").value;
  const status = document.getElementById("filter-status").value;
  const year = selectedFinancialYear("filter-year");

  const filtered = allInvoices.filter((i) => {
    const tOk = !type || i.invoice_type === type;
    const sOk = !status || i.status === status;
    const yOk = !year || i.financial_year_id === year;
    return tOk && sOk && yOk;
  });

  const tbody = document.getElementById("invoices-table");
  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">🧾</div>${t("finance.noInvoices")}</div></td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((i) => {
    const party = partyName(i);
    return `
    <tr>
      <td><strong>${i.invoice_number}</strong></td>
      <td>${statusBadge(i.invoice_type === "sales" ? "active" : "finishing")}</td>
      <td style="color:var(--muted-foreground);">
        ${party || "—"}
        ${i.description ? `<div class="table-sub">${escapeHtml(i.description)}</div>` : ""}
        ${i.financial_year_name ? `<div class="table-sub">${t("financialYears.year")}: ${escapeHtml(i.financial_year_name)}</div>` : ""}
      </td>
      <td><strong>${moneyWithCurrency(i.amount, i)}</strong></td>
      <td style="color:var(--success);">${moneyWithCurrency(i.paid_amount, i)}</td>
      <td style="color:var(--red);">${moneyWithCurrency(i.balance, i)}</td>
      <td>${statusBadge(i.status)}</td>
      <td>${approvalBadge(i.approval_status)}</td>
      <td>
        <div class="table-actions">
          <button class="btn btn-info btn-sm" onclick="window.open('/documents/invoice/${i.id}', '_blank')">${t("common.print")}</button>
          <button class="btn btn-outline btn-sm" onclick="downloadPDF('/documents/invoice/${i.id}/pdf')">${t("common.download")} PDF</button>
          ${canAction("finance", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editInvoice(${JSON.stringify(i)})'>${t("common.edit")}</button>` : ""}
          ${canAction("finance", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteInvoice(${i.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}

function renderSummary() {
  const sales = allInvoices.filter((i) => i.invoice_type === "sales");
  const purchases = allInvoices.filter((i) => i.invoice_type === "purchase");
  const sum = (arr, f) => arr.reduce((acc, i) => acc + f(i), 0);

  animateCount(document.getElementById("fin-total"), sum(allInvoices, (i) => i.amount), formatMoney);
  animateCount(document.getElementById("fin-sales"), sum(sales, (i) => i.amount), formatMoney);
  animateCount(document.getElementById("fin-purchases"), sum(purchases, (i) => i.amount), formatMoney);
  animateCount(document.getElementById("fin-pending"), sum(allInvoices, (i) => i.balance), formatMoney);
}

function exportInvoices() {
  const headers = [
    t("finance.colNumber"), t("common.type"), t("common.customer"),
    t("common.description"), t("common.amount"), t("common.paid"),
    t("common.balance"), t("common.status"), t("finance.issueDate"), t("finance.dueDate"),
  ];
  const rows = allInvoices.map((i) => [
    i.invoice_number,
    i.invoice_type === "sales" ? t("finance.salesLabel") : t("finance.expensesLabel"),
    partyName(i) || "",
    i.description || "",
    i.amount || 0,
    i.paid_amount || 0,
    i.balance || 0,
    STATUS_LABELS[i.status] || i.status,
    formatDate(i.issue_date),
    formatDate(i.due_date),
  ]);
  exportCSV("invoices.csv", headers, rows);
}

function populatePartySelect() {
  const type = document.getElementById("invoice-type").value;
  const select = document.getElementById("invoice-party");
  document.getElementById("invoice-party-label").textContent = type === "sales" ? t("common.customer") : t("common.supplier");
  const data = type === "sales"
    ? allCustomers.map((c) => ({ id: c.id, name: c.full_name }))
    : allSuppliers.map((s) => ({ id: s.id, name: s.company_name }));
  select.innerHTML = `<option value="">${t("common.select")}</option>`
    + data.map((x) => `<option value="${x.id}">${escapeHtml(x.name)}</option>`).join("");
  return select;
}

// ===== Invoice items =====
const itemsEditor = document.getElementById("invoice-items");
if (itemsEditor) {
  itemsEditor.addEventListener("input", () => recalcItems());
}

function itemRowHTML() {
  return `
    <div class="item-row">
      <input type="text" class="item-desc" placeholder="${t("invoice.descPlaceholder")}">
      <input type="number" class="item-qty" min="0" step="0.01" value="1" title="${t("invoice.qtyCol")}">
      <input type="number" class="item-price" min="0" step="0.01" placeholder="0.00" title="${t("invoice.priceCol")}">
      <input type="number" class="item-tax" min="0" step="0.01" value="${defaultTaxRate}" title="${t("invoice.taxCol")}">
      <span class="item-line-total" title="${t("invoice.totalCol")}">0.00</span>
      <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removeInvoiceItem(this)" title="${t("invoice.removeItem")}">✕</button>
    </div>`;
}

function addInvoiceItem() {
  const container = document.getElementById("invoice-items");
  if (container) container.insertAdjacentHTML("beforeend", itemRowHTML());
}

function removeInvoiceItem(btn) {
  const row = btn.closest(".item-row");
  if (row) row.remove();
  recalcItems();
}

function collectItems() {
  return Array.from(document.querySelectorAll("#invoice-items .item-row"))
    .map((row) => ({
      description: (row.querySelector(".item-desc").value || "").trim(),
      quantity: parseFloat(row.querySelector(".item-qty").value) || 0,
      unit_price: parseFloat(row.querySelector(".item-price").value) || 0,
      tax_rate: parseFloat(row.querySelector(".item-tax").value) || 0,
    }))
    .filter((it) => it.description);
}

function recalcItems() {
  const amountEl = document.getElementById("invoice-amount");
  const rows = Array.from(document.querySelectorAll("#invoice-items .item-row"));
  let total = 0;
  let hasItems = false;
  rows.forEach((row) => {
    const qty = parseFloat(row.querySelector(".item-qty").value) || 0;
    const price = parseFloat(row.querySelector(".item-price").value) || 0;
    const tax = parseFloat(row.querySelector(".item-tax").value) || 0;
    const desc = (row.querySelector(".item-desc").value || "").trim();
    const lineTotal = qty * price * (1 + tax / 100);
    row.querySelector(".item-line-total").textContent = formatMoney(lineTotal);
    if (desc && lineTotal > 0) { total += lineTotal; hasItems = true; }
  });
  if (hasItems && amountEl) {
    amountEl.value = total.toFixed(2);
    amountEl.disabled = true;
  } else if (amountEl) {
    amountEl.disabled = false;
  }
}

// ===== Modal =====
function openInvoiceModal() {
  document.getElementById("invoice-modal-title").textContent = t("finance.newInvoice");
  document.getElementById("invoice-id").value = "";
  const numEl = document.getElementById("invoice-number");
  numEl.value = "";
  prefillDocNumber(numEl, "invoice", "INV-");
  document.getElementById("invoice-description").value = "";
  document.getElementById("invoice-amount").value = "";
  document.getElementById("invoice-amount").disabled = false;
  document.getElementById("invoice-paid").value = "";
  document.getElementById("invoice-type").value = "sales";
  document.getElementById("invoice-status").value = "pending";
  document.getElementById("invoice-issue-date").value = "";
  document.getElementById("invoice-due-date").value = "";
  const container = document.getElementById("invoice-items");
  if (container) container.innerHTML = itemRowHTML();
  populatePartySelect();
  fillFinancialYearSelect("invoice-year");
  document.getElementById("invoice-modal").classList.add("active");
}

function editInvoice(i) {
  document.getElementById("invoice-modal-title").textContent = t("finance.editInvoice");
  document.getElementById("invoice-id").value = i.id;
  document.getElementById("invoice-number").value = i.invoice_number || "";
  document.getElementById("invoice-description").value = i.description || "";
  document.getElementById("invoice-amount").value = i.amount || "";
  document.getElementById("invoice-amount").disabled = false;
  document.getElementById("invoice-paid").value = i.paid_amount || "";
  document.getElementById("invoice-type").value = i.invoice_type || "sales";
  document.getElementById("invoice-status").value = i.status || "pending";
  document.getElementById("invoice-issue-date").value = i.issue_date || "";
  document.getElementById("invoice-due-date").value = i.due_date || "";
  const container = document.getElementById("invoice-items");
  if (container) {
    container.innerHTML = (i.items && i.items.length ? i.items : [{}]).map(itemRowHTML).join("");
    const rows = container.querySelectorAll(".item-row");
    (i.items || []).forEach((it, idx) => {
      if (!rows[idx]) return;
      rows[idx].querySelector(".item-desc").value = it.description || "";
      rows[idx].querySelector(".item-qty").value = it.quantity || 1;
      rows[idx].querySelector(".item-price").value = it.unit_price || 0;
      rows[idx].querySelector(".item-tax").value = it.tax_rate || 0;
    });
  }
  populatePartySelect();
  document.getElementById("invoice-party").value = (i.invoice_type === "sales" ? i.customer_id : i.supplier_id) || "";
  fillFinancialYearSelect("invoice-year", i.financial_year_id);
  document.getElementById("invoice-modal").classList.add("active");
  recalcItems();
}

function closeInvoiceModal() {
  document.getElementById("invoice-modal").classList.remove("active");
}

async function saveInvoice() {
  const id = document.getElementById("invoice-id").value;
  const items = collectItems();
  const body = {
    invoice_number: document.getElementById("invoice-number").value,
    invoice_type: document.getElementById("invoice-type").value,
    description: document.getElementById("invoice-description").value,
    amount: parseFloat(document.getElementById("invoice-amount").value) || 0,
    paid_amount: parseFloat(document.getElementById("invoice-paid").value) || 0,
    status: document.getElementById("invoice-status").value,
    financial_year_id: financialYearValue("invoice-year"),
    issue_date: document.getElementById("invoice-issue-date").value,
    due_date: document.getElementById("invoice-due-date").value,
    items,
  };
  const partyVal = parseInt(document.getElementById("invoice-party").value) || null;
  if (body.invoice_type === "sales") body.customer_id = partyVal;
  else body.supplier_id = partyVal;

  if (!body.invoice_number) { showToast(t("finance.numberRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/invoices/${id}`, body);
    else await api.post("/api/invoices", body);
    showToast(t("common.savedSuccess"));
    closeInvoiceModal();
    allInvoices = await api.get("/api/invoices");
    renderInvoices();
    renderSummary();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteInvoice(id) {
  if (!confirm(t("finance.confirmDelete"))) return;
  try {
    await api.delete(`/api/invoices/${id}`);
    showToast(t("common.deleted"));
    allInvoices = await api.get("/api/invoices");
    renderInvoices();
    renderSummary();
  } catch (err) {
    showToast(err.message, "error");
  }
}

window.openInvoiceModal = openInvoiceModal;
window.closeInvoiceModal = closeInvoiceModal;
window.editInvoice = editInvoice;
window.deleteInvoice = deleteInvoice;
window.saveInvoice = saveInvoice;
window.populatePartySelect = populatePartySelect;
window.addInvoiceItem = addInvoiceItem;
window.removeInvoiceItem = removeInvoiceItem;

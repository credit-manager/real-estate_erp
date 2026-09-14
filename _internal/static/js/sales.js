/* ============================================================
   Sales Module JavaScript
   Quotes · Sales Orders · Invoices · Returns · Commissions · Team
   ============================================================ */

const SALES_API = "/api/sales";

let allCustomers = [];
let allEmployees = [];
let allQuotes = [];
let allOrders = [];
let allInvoices = [];
let allReturns = [];
let allCommissions = [];
let allTeam = [];

document.addEventListener("DOMContentLoaded", async () => {
  await loadAll();
});

async function loadAll() {
  const [customers, employees, quotes, orders, invoices, returns, commissions, team, summary] = await Promise.all([
    api.get("/api/customers").catch(() => []),
    api.get("/api/employees").catch(() => []),
    api.get(`${SALES_API}/quotes`).catch(() => []),
    api.get(`${SALES_API}/orders`).catch(() => []),
    api.get(`${SALES_API}/invoices`).catch(() => []),
    api.get(`${SALES_API}/returns`).catch(() => []),
    api.get(`${SALES_API}/commissions`).catch(() => []),
    api.get(`${SALES_API}/team`).catch(() => []),
    api.get(`${SALES_API}/summary`).catch(() => ({})),
  ]);
  allCustomers = customers;
  allEmployees = employees;
  allQuotes = quotes;
  allOrders = orders;
  allInvoices = invoices;
  allReturns = returns;
  allCommissions = commissions;
  allTeam = team;
  populateSelects();
  renderSummary(summary);
  renderQuotes();
  renderOrders();
  renderInvoices();
  renderReturns();
  renderCommissions();
  renderTeam();
}

function populateSelects() {
  const custOpts = allCustomers.map((c) => `<option value="${c.id}">${escapeHtml(c.full_name)}</option>`).join("");
  const empOpts = allEmployees.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
  const orderOpts = allOrders.map((o) => `<option value="${o.id}">${escapeHtml(o.order_number)} — ${escapeHtml(o.customer_name || "")}</option>`).join("");
  const invOpts = allInvoices.map((i) => `<option value="${i.id}">${escapeHtml(i.invoice_number)} — ${escapeHtml(i.customer_name || "")}</option>`).join("");

  ["quote-customer", "order-customer", "invoice-customer", "return-customer"].forEach((id) => {
    document.getElementById(id).innerHTML = `<option value="">${t("sales.selectCustomer")}</option>` + custOpts;
  });
  ["order-salesperson", "commission-salesperson"].forEach((id) => {
    document.getElementById(id).innerHTML = `<option value="">${t("sales.selectSalesperson")}</option>` + empOpts;
  });
  document.getElementById("return-invoice").innerHTML = `<option value="">${t("sales.selectInvoice")}</option>` + invOpts;
  document.getElementById("commission-order").innerHTML = `<option value="">${t("sales.selectQuote")} / ${t("sales.orderNumber")}</option>` + orderOpts;
  document.getElementById("commission-invoice").innerHTML = `<option value="">${t("sales.selectInvoice")}</option>` + invOpts;
}

// ===== Modal helpers =====
function modal(id) { document.getElementById(id).classList.add("active"); }
function closeModal(id) { document.getElementById(id).classList.remove("active"); }
window.modal = modal;
window.closeModal = closeModal;

// ===== Status badge =====
function salesStatusBadge(status) {
  const cls = {
    draft: "badge-neutral", sent: "badge-info", accepted: "badge-success",
    confirmed: "badge-info", delivered: "badge-warning", completed: "badge-success",
    cancelled: "badge-danger", pending: "badge-warning", partial: "badge-warning",
    paid: "badge-success", overdue: "badge-danger", processed: "badge-info",
    rejected: "badge-danger", approved: "badge-success",
  }[status] || "badge-neutral";
  return `<span class="badge ${cls}">${t(`status.${status}`)}</span>`;
}

function customerName(id) {
  const c = allCustomers.find((x) => x.id === Number(id));
  return c ? escapeHtml(c.full_name) : "—";
}

// ===== Summary =====
function renderSummary(s) {
  animateCount(document.getElementById("kpi-customers"), s.customers_count || 0, formatNumber);
  animateCount(document.getElementById("kpi-quotes"), s.quotes_count || 0, formatNumber);
  animateCount(document.getElementById("kpi-orders"), s.orders_count || 0, formatNumber);
  animateCount(document.getElementById("kpi-orders-value"), s.orders_value || 0, formatMoney);
  animateCount(document.getElementById("kpi-invoices"), s.invoices_count || 0, formatNumber);
  animateCount(document.getElementById("kpi-revenue"), s.total_revenue || 0, formatMoney);
  animateCount(document.getElementById("kpi-collected"), s.paid_revenue || 0, formatMoney);
  animateCount(document.getElementById("kpi-pending"), s.pending_revenue || 0, formatMoney);
  animateCount(document.getElementById("kpi-returns"), s.returns_count || 0, formatNumber);
  animateCount(document.getElementById("kpi-commissions"), s.commissions_total || 0, formatMoney);
  animateCount(document.getElementById("kpi-commissions-pending"), s.commissions_pending || 0, formatNumber);
  animateCount(document.getElementById("kpi-overdue"), s.overdue_orders || 0, formatNumber);
}

// ==================== QUOTES ====================
function renderQuotes() {
  const tbody = document.getElementById("quotes-table");
  if (!allQuotes.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">📄</div>${t("sales.noQuotes")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allQuotes.map((q) => `
    <tr>
      <td><strong>${escapeHtml(q.quote_number)}</strong></td>
      <td>${escapeHtml(q.customer_name || "—")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(q.title || "—")}</td>
      <td style="color:var(--muted-foreground);">${formatDate(q.valid_until)}</td>
      <td><strong>${formatMoney(q.total)}</strong></td>
      <td>${salesStatusBadge(q.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("sales", "view") ? `<button class="btn btn-outline btn-sm" onclick="printQuote(${q.id})" title="${t("doc.print")}">${t("doc.print")}</button>` : ""}
          ${canAction("sales", "view") ? `<button class="btn btn-outline btn-sm" onclick="downloadQuotePdf(${q.id})" title="${t("common.download")}">PDF</button>` : ""}
          ${canAction("sales", "create") && q.customer_id ? `<button class="btn btn-success btn-sm" onclick="convertQuote(${q.id})">${t("sales.convertOrder")}</button>` : ""}
          ${canAction("sales", "edit") && ["draft", "sent"].includes(q.status) ? `<button class="btn btn-secondary btn-sm" onclick='editQuote(${JSON.stringify(q)})'>${t("common.edit")}</button>` : ""}
          ${canAction("sales", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteQuote(${q.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function addQuoteItem(desc = "", qty = 1, price = 0) {
  const body = document.getElementById("quote-items-body");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="item-desc" value="${escapeHtml(desc)}" placeholder="${t("sales.itemDescription")}"></td>
    <td><input type="number" class="item-qty" min="0" step="0.01" value="${qty}" oninput="recalcQuote()"></td>
    <td><input type="number" class="item-price" min="0" step="0.01" value="${price}" oninput="recalcQuote()"></td>
    <td class="item-total">0</td>
    <td><button class="btn btn-danger btn-sm" type="button" onclick="this.closest('tr').remove(); recalcQuote();">×</button></td>`;
  body.appendChild(tr);
  recalcQuote();
}

function recalcQuote() {
  let subtotal = 0;
  document.querySelectorAll("#quote-items-body tr").forEach((tr) => {
    const qty = parseFloat(tr.querySelector(".item-qty").value) || 0;
    const price = parseFloat(tr.querySelector(".item-price").value) || 0;
    const total = qty * price;
    subtotal += total;
    tr.querySelector(".item-total").textContent = formatMoney(total);
  });
  document.getElementById("quote-subtotal").value = subtotal.toFixed(2);
  const discount = parseFloat(document.getElementById("quote-discount").value) || 0;
  const tax = parseFloat(document.getElementById("quote-tax").value) || 0;
  const total = subtotal - discount + subtotal * tax / 100;
  document.getElementById("quote-total").value = total.toFixed(2);
}

function openQuoteModal() {
  document.getElementById("quote-modal-title").textContent = t("sales.newQuote");
  document.getElementById("quote-id").value = "";
  document.getElementById("quote-title").value = "";
  document.getElementById("quote-customer").value = "";
  document.getElementById("quote-valid").value = "";
  document.getElementById("quote-status").value = "draft";
  document.getElementById("quote-discount").value = "0";
  document.getElementById("quote-tax").value = "0";
  document.getElementById("quote-notes").value = "";
  document.getElementById("quote-items-body").innerHTML = "";
  addQuoteItem("", 1, 0);
  modal("quote-modal");
}

function editQuote(q) {
  document.getElementById("quote-modal-title").textContent = t("common.edit");
  document.getElementById("quote-id").value = q.id;
  document.getElementById("quote-title").value = q.title || "";
  document.getElementById("quote-customer").value = q.customer_id || "";
  document.getElementById("quote-valid").value = q.valid_until || "";
  document.getElementById("quote-status").value = q.status || "draft";
  document.getElementById("quote-discount").value = q.discount || 0;
  document.getElementById("quote-tax").value = q.tax_rate || 0;
  document.getElementById("quote-notes").value = q.notes || "";
  document.getElementById("quote-items-body").innerHTML = "";
  (q.items && q.items.length ? q.items : [{}]).forEach((it) => addQuoteItem(it.description, it.qty, it.unit_price));
  modal("quote-modal");
}

async function saveQuote() {
  const id = document.getElementById("quote-id").value;
  const items = Array.from(document.querySelectorAll("#quote-items-body tr")).map((tr) => ({
    description: tr.querySelector(".item-desc").value,
    qty: parseFloat(tr.querySelector(".item-qty").value) || 1,
    unit_price: parseFloat(tr.querySelector(".item-price").value) || 0,
  })).filter((it) => it.description);
  if (!items.length) { showToast(t("sales.itemsRequired"), "warning"); return; }
  const body = {
    customer_id: document.getElementById("quote-customer").value || null,
    title: document.getElementById("quote-title").value,
    valid_until: document.getElementById("quote-valid").value,
    status: document.getElementById("quote-status").value,
    discount: parseFloat(document.getElementById("quote-discount").value) || 0,
    tax_rate: parseFloat(document.getElementById("quote-tax").value) || 0,
    notes: document.getElementById("quote-notes").value,
    items,
  };
  try {
    if (id) await api.put(`/api/crm/quotes/${id}`, body);
    else await api.post("/api/crm/quotes", body);
    showToast(t("common.saved"));
    closeModal("quote-modal");
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteQuote(id) {
  if (!confirm(t("sales.confirmDelete"))) return;
  try {
    await api.delete(`/api/crm/quotes/${id}`);
    showToast(t("common.deleted"));
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function convertQuote(id) {
  if (!confirm(t("sales.convertOrderConfirm"))) return;
  try {
    const order = await api.post(`${SALES_API}/quotes/${id}/convert`, {});
    showToast(t("common.saved"));
    await loadAll();
    editOrder(order);
  } catch (err) { showToast(err.message, "error"); }
}

function printQuote(id) { window.open(`/documents/crm-quote/${id}`, "_blank"); }
function downloadQuotePdf(id) { window.open(`/documents/crm-quote/${id}/pdf`, "_blank"); }

// ==================== SALES ORDERS ====================
function renderOrders() {
  const tbody = document.getElementById("orders-table");
  if (!allOrders.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">📦</div>${t("sales.noOrders")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allOrders.map((o) => `
    <tr>
      <td><strong>${escapeHtml(o.order_number)}</strong></td>
      <td>${escapeHtml(o.customer_name || "—")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(o.salesperson_name || "—")}</td>
      <td style="color:var(--muted-foreground);">${formatDate(o.order_date)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(o.due_date)}</td>
      <td><strong>${formatMoney(o.amount)}</strong></td>
      <td>${salesStatusBadge(o.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("sales", "view") ? `<button class="btn btn-outline btn-sm" onclick="printOrder(${o.id})" title="${t("doc.print")}">${t("doc.print")}</button>` : ""}
          ${canAction("sales", "view") ? `<button class="btn btn-outline btn-sm" onclick="downloadOrderPdf(${o.id})" title="${t("common.download")}">PDF</button>` : ""}
          ${canAction("sales", "create") && o.status !== "cancelled" && o.status !== "completed" ? `<button class="btn btn-success btn-sm" onclick="orderToInvoice(${o.id})">${t("sales.toInvoice")}</button>` : ""}
          ${canAction("sales", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editOrder(${JSON.stringify(o)})'>${t("common.edit")}</button>` : ""}
          ${canAction("sales", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteOrder(${o.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function addOrderItem(desc = "", qty = 1, price = 0, tax = 0) {
  const body = document.getElementById("order-items-body");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="item-desc" value="${escapeHtml(desc)}" placeholder="${t("sales.itemDescription")}"></td>
    <td><input type="number" class="item-qty" min="0" step="0.01" value="${qty}" oninput="recalcOrderRow(this)"></td>
    <td><input type="number" class="item-price" min="0" step="0.01" value="${price}" oninput="recalcOrderRow(this)"></td>
    <td><input type="number" class="item-tax" min="0" step="0.01" value="${tax}"></td>
    <td class="item-total">0</td>
    <td><button class="btn btn-danger btn-sm" type="button" onclick="this.closest('tr').remove();">×</button></td>`;
  body.appendChild(tr);
  recalcOrderRow(tr.querySelector(".item-price"));
}

function recalcOrderRow(el) {
  const tr = el.closest("tr");
  const qty = parseFloat(tr.querySelector(".item-qty").value) || 0;
  const price = parseFloat(tr.querySelector(".item-price").value) || 0;
  const tax = parseFloat(tr.querySelector(".item-tax").value) || 0;
  tr.querySelector(".item-total").textContent = formatMoney(qty * price * (1 + tax / 100));
}

function openOrderModal() {
  document.getElementById("order-modal-title").textContent = t("sales.newOrder");
  document.getElementById("order-id").value = "";
  document.getElementById("order-quote-id").value = "";
  document.getElementById("order-customer").value = "";
  document.getElementById("order-salesperson").value = "";
  document.getElementById("order-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("order-due").value = "";
  document.getElementById("order-status").value = "draft";
  document.getElementById("order-paid").value = "0";
  document.getElementById("order-notes").value = "";
  document.getElementById("order-items-body").innerHTML = "";
  addOrderItem("", 1, 0, 0);
  modal("order-modal");
}

function editOrder(o) {
  document.getElementById("order-modal-title").textContent = t("sales.editOrder");
  document.getElementById("order-id").value = o.id;
  document.getElementById("order-quote-id").value = o.quote_id || "";
  document.getElementById("order-customer").value = o.customer_id || "";
  document.getElementById("order-salesperson").value = o.salesperson_id || "";
  document.getElementById("order-date").value = o.order_date || new Date().toISOString().slice(0, 10);
  document.getElementById("order-due").value = o.due_date || "";
  document.getElementById("order-status").value = o.status || "draft";
  document.getElementById("order-paid").value = o.paid_amount || 0;
  document.getElementById("order-notes").value = o.notes || "";
  document.getElementById("order-items-body").innerHTML = "";
  (o.items && o.items.length ? o.items : [{}]).forEach((it) => addOrderItem(it.description, it.quantity, it.unit_price, it.tax_rate));
  modal("order-modal");
}

function collectItems(bodyId) {
  return Array.from(document.querySelectorAll(`#${bodyId} tr`)).map((tr) => ({
    description: tr.querySelector(".item-desc").value,
    quantity: parseFloat(tr.querySelector(".item-qty").value) || 1,
    unit_price: parseFloat(tr.querySelector(".item-price").value) || 0,
    tax_rate: parseFloat(tr.querySelector(".item-tax").value) || 0,
  })).filter((it) => it.description);
}

async function saveOrder() {
  const id = document.getElementById("order-id").value;
  const items = collectItems("order-items-body");
  if (!items.length) { showToast(t("sales.itemsRequired"), "warning"); return; }
  if (!document.getElementById("order-customer").value) { showToast(t("sales.customerRequired"), "warning"); return; }
  const body = {
    customer_id: document.getElementById("order-customer").value || null,
    salesperson_id: document.getElementById("order-salesperson").value || null,
    quote_id: document.getElementById("order-quote-id").value || null,
    order_date: document.getElementById("order-date").value,
    due_date: document.getElementById("order-due").value,
    status: document.getElementById("order-status").value,
    paid_amount: parseFloat(document.getElementById("order-paid").value) || 0,
    notes: document.getElementById("order-notes").value,
    items,
  };
  try {
    if (id) await api.put(`${SALES_API}/orders/${id}`, body);
    else await api.post(`${SALES_API}/orders`, body);
    showToast(t("common.saved"));
    closeModal("order-modal");
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteOrder(id) {
  if (!confirm(t("sales.confirmDelete"))) return;
  try {
    await api.delete(`${SALES_API}/orders/${id}`);
    showToast(t("common.deleted"));
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function orderToInvoice(id) {
  if (!confirm(t("sales.toInvoiceConfirm"))) return;
  try {
    await api.post(`${SALES_API}/orders/${id}/invoice`, {});
    showToast(t("common.saved"));
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

function printOrder(id) { window.open(`/documents/sales-order/${id}`, "_blank"); }
function downloadOrderPdf(id) { window.open(`/documents/sales-order/${id}/pdf`, "_blank"); }

// ==================== INVOICES ====================
function renderInvoices() {
  const tbody = document.getElementById("invoices-table");
  if (!allInvoices.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">🧾</div>${t("sales.noInvoices")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allInvoices.map((i) => `
    <tr>
      <td><strong>${escapeHtml(i.invoice_number)}</strong></td>
      <td>${escapeHtml(i.customer_name || "—")}</td>
      <td style="color:var(--muted-foreground);">${formatDate(i.issue_date)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(i.due_date)}</td>
      <td><strong>${formatMoney(i.amount)}</strong></td>
      <td style="color:var(--success);">${formatMoney(i.paid_amount)}</td>
      <td style="color:${(i.balance || 0) > 0 ? "var(--danger)" : "var(--muted-foreground)"};">${formatMoney(i.balance)}</td>
      <td>${salesStatusBadge(i.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("sales", "view") ? `<button class="btn btn-outline btn-sm" onclick="printInvoice(${i.id})" title="${t("doc.print")}">${t("doc.print")}</button>` : ""}
          ${canAction("sales", "view") ? `<button class="btn btn-outline btn-sm" onclick="downloadInvoicePdf(${i.id})" title="${t("common.download")}">PDF</button>` : ""}
          ${canAction("sales", "edit") ? `<button class="btn btn-outline btn-sm" onclick="submitEinvoice(${i.id}, this)" title="إرسال للمنظومة الضريبية">🧾${i.einv_status === "accepted" || i.einv_status === "submitted" ? " ✓" : ""}</button>` : ""}
          ${canAction("sales", "edit") && (i.balance || 0) > 0 ? `<button class="btn btn-success btn-sm" onclick="openPayModal(${JSON.stringify(i)})">${t("sales.recordPayment")}</button>` : ""}
          ${canAction("sales", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editInvoice(${JSON.stringify(i)})'>${t("common.edit")}</button>` : ""}
          ${canAction("sales", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteInvoice(${i.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function addInvoiceItem(desc = "", qty = 1, price = 0, tax = 0) {
  const body = document.getElementById("invoice-items-body");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="item-desc" value="${escapeHtml(desc)}" placeholder="${t("sales.itemDescription")}"></td>
    <td><input type="number" class="item-qty" min="0" step="0.01" value="${qty}" oninput="recalcInvoiceRow(this)"></td>
    <td><input type="number" class="item-price" min="0" step="0.01" value="${price}" oninput="recalcInvoiceRow(this)"></td>
    <td><input type="number" class="item-tax" min="0" step="0.01" value="${tax}"></td>
    <td class="item-total">0</td>
    <td><button class="btn btn-danger btn-sm" type="button" onclick="this.closest('tr').remove();">×</button></td>`;
  body.appendChild(tr);
  recalcInvoiceRow(tr.querySelector(".item-price"));
}

function recalcInvoiceRow(el) {
  const tr = el.closest("tr");
  const qty = parseFloat(tr.querySelector(".item-qty").value) || 0;
  const price = parseFloat(tr.querySelector(".item-price").value) || 0;
  const tax = parseFloat(tr.querySelector(".item-tax").value) || 0;
  tr.querySelector(".item-total").textContent = formatMoney(qty * price * (1 + tax / 100));
}

function openInvoiceModal() {
  document.getElementById("invoice-modal-title").textContent = t("sales.newInvoice");
  document.getElementById("invoice-id").value = "";
  const numEl = document.getElementById("invoice-number");
  numEl.value = "";
  prefillDocNumber(numEl, "invoice", "INV-");
  document.getElementById("invoice-customer").value = "";
  document.getElementById("invoice-issue").value = new Date().toISOString().slice(0, 10);
  document.getElementById("invoice-due").value = "";
  document.getElementById("invoice-paid").value = "0";
  document.getElementById("invoice-status").value = "pending";
  document.getElementById("invoice-notes").value = "";
  document.getElementById("invoice-items-body").innerHTML = "";
  addInvoiceItem("", 1, 0, 0);
  modal("invoice-modal");
}

function editInvoice(i) {
  document.getElementById("invoice-modal-title").textContent = t("sales.editInvoice");
  document.getElementById("invoice-id").value = i.id;
  document.getElementById("invoice-number").value = i.invoice_number || "";
  document.getElementById("invoice-customer").value = i.customer_id || "";
  document.getElementById("invoice-issue").value = i.issue_date || new Date().toISOString().slice(0, 10);
  document.getElementById("invoice-due").value = i.due_date || "";
  document.getElementById("invoice-paid").value = i.paid_amount || 0;
  document.getElementById("invoice-status").value = i.status || "pending";
  document.getElementById("invoice-notes").value = i.description || "";
  document.getElementById("invoice-items-body").innerHTML = "";
  (i.items && i.items.length ? i.items : [{}]).forEach((it) => addInvoiceItem(it.description, it.quantity, it.unit_price, it.tax_rate));
  modal("invoice-modal");
}

async function saveInvoice() {
  const id = document.getElementById("invoice-id").value;
  const items = collectItems("invoice-items-body");
  if (!items.length) { showToast(t("sales.itemsRequired"), "warning"); return; }
  if (!document.getElementById("invoice-customer").value) { showToast(t("sales.customerRequired"), "warning"); return; }
  const body = {
    invoice_number: document.getElementById("invoice-number").value,
    customer_id: document.getElementById("invoice-customer").value || null,
    issue_date: document.getElementById("invoice-issue").value,
    due_date: document.getElementById("invoice-due").value,
    paid_amount: parseFloat(document.getElementById("invoice-paid").value) || 0,
    status: document.getElementById("invoice-status").value,
    description: document.getElementById("invoice-notes").value,
    items,
  };
  try {
    if (id) await api.put(`${SALES_API}/invoices/${id}`, body);
    else await api.post(`${SALES_API}/invoices`, body);
    showToast(t("common.saved"));
    closeModal("invoice-modal");
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteInvoice(id) {
  if (!confirm(t("sales.confirmDelete"))) return;
  try {
    await api.delete(`${SALES_API}/invoices/${id}`);
    showToast(t("common.deleted"));
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

function openPayModal(i) {
  document.getElementById("pay-invoice-id").value = i.id;
  document.getElementById("pay-amount").value = i.balance || 0;
  document.getElementById("pay-date").value = new Date().toISOString().slice(0, 10);
  modal("pay-modal");
}

async function savePayment() {
  const id = document.getElementById("pay-invoice-id").value;
  const body = {
    amount: parseFloat(document.getElementById("pay-amount").value) || 0,
    payment_date: document.getElementById("pay-date").value,
  };
  if (body.amount <= 0) { showToast(t("sales.payAmountRequired"), "warning"); return; }
  try {
    await api.post(`${SALES_API}/invoices/${id}/pay`, body);
    showToast(t("common.saved"));
    closeModal("pay-modal");
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function submitEinvoice(id, btn){
  if(btn) btn.disabled = true;
  try{
    const r = await api.post(`/api/invoices/${id}/einvoice/submit`, {});
    const st = r.status || r.einv_status;
    showToast(st === "accepted" ? "تمت قبول الفاتورة ضريبياً" :
              st === "submitted" ? "أُرسلت الفاتورة للمنظومة" :
              st === "pending" ? (r.message || "بانتظار الإعداد") :
              (r.message || "رُفضت الفاتورة"), st === "rejected" || st === "error" ? "error" : "success");
    if(typeof loadInvoices === "function") loadInvoices();
  }catch(e){
    showToast(e.message || "فشل الإرسال", "error");
  }finally{
    if(btn) btn.disabled = false;
  }
}

function printInvoice(id) { window.open(`/documents/invoice/${id}`, "_blank"); }
function downloadInvoicePdf(id) { window.open(`/documents/invoice/${id}/pdf`, "_blank"); }

// ==================== RETURNS ====================
function renderReturns() {
  const tbody = document.getElementById("returns-table");
  if (!allReturns.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">↩️</div>${t("sales.noReturns")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allReturns.map((r) => `
    <tr>
      <td><strong>${escapeHtml(r.return_number)}</strong></td>
      <td>${escapeHtml(r.customer_name || "—")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(r.invoice_number || "—")}</td>
      <td style="color:var(--muted-foreground);">${formatDate(r.return_date)}</td>
      <td><strong>${formatMoney(r.amount)}</strong></td>
      <td>${salesStatusBadge(r.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("sales", "view") ? `<button class="btn btn-outline btn-sm" onclick="printReturn(${r.id})" title="${t("doc.print")}">${t("doc.print")}</button>` : ""}
          ${canAction("sales", "view") ? `<button class="btn btn-outline btn-sm" onclick="downloadReturnPdf(${r.id})" title="${t("common.download")}">PDF</button>` : ""}
          ${canAction("sales", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editReturn(${JSON.stringify(r)})'>${t("common.edit")}</button>` : ""}
          ${canAction("sales", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteReturn(${r.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function addReturnItem(desc = "", qty = 1, price = 0, tax = 0) {
  const body = document.getElementById("return-items-body");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="item-desc" value="${escapeHtml(desc)}" placeholder="${t("sales.itemDescription")}"></td>
    <td><input type="number" class="item-qty" min="0" step="0.01" value="${qty}" oninput="recalcReturnRow(this)"></td>
    <td><input type="number" class="item-price" min="0" step="0.01" value="${price}" oninput="recalcReturnRow(this)"></td>
    <td><input type="number" class="item-tax" min="0" step="0.01" value="${tax}"></td>
    <td class="item-total">0</td>
    <td><button class="btn btn-danger btn-sm" type="button" onclick="this.closest('tr').remove();">×</button></td>`;
  body.appendChild(tr);
  recalcReturnRow(tr.querySelector(".item-price"));
}

function recalcReturnRow(el) {
  const tr = el.closest("tr");
  const qty = parseFloat(tr.querySelector(".item-qty").value) || 0;
  const price = parseFloat(tr.querySelector(".item-price").value) || 0;
  const tax = parseFloat(tr.querySelector(".item-tax").value) || 0;
  tr.querySelector(".item-total").textContent = formatMoney(qty * price * (1 + tax / 100));
}

function openReturnModal() {
  document.getElementById("return-modal-title").textContent = t("sales.newReturn");
  document.getElementById("return-id").value = "";
  document.getElementById("return-invoice").value = "";
  document.getElementById("return-customer").value = "";
  document.getElementById("return-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("return-status").value = "draft";
  document.getElementById("return-reason").value = "";
  document.getElementById("return-items-body").innerHTML = "";
  addReturnItem("", 1, 0, 0);
  modal("return-modal");
}

function editReturn(r) {
  document.getElementById("return-modal-title").textContent = t("sales.editReturn");
  document.getElementById("return-id").value = r.id;
  document.getElementById("return-invoice").value = r.invoice_id || "";
  document.getElementById("return-customer").value = r.customer_id || "";
  document.getElementById("return-date").value = r.return_date || new Date().toISOString().slice(0, 10);
  document.getElementById("return-status").value = r.status || "draft";
  document.getElementById("return-reason").value = r.reason || "";
  document.getElementById("return-items-body").innerHTML = "";
  (r.items && r.items.length ? r.items : [{}]).forEach((it) => addReturnItem(it.description, it.quantity, it.unit_price, it.tax_rate));
  modal("return-modal");
}

async function saveReturn() {
  const id = document.getElementById("return-id").value;
  const items = collectItems("return-items-body");
  if (!items.length) { showToast(t("sales.itemsRequired"), "warning"); return; }
  const body = {
    invoice_id: document.getElementById("return-invoice").value || null,
    customer_id: document.getElementById("return-customer").value || null,
    return_date: document.getElementById("return-date").value,
    status: document.getElementById("return-status").value,
    reason: document.getElementById("return-reason").value,
    items,
  };
  try {
    if (id) await api.put(`${SALES_API}/returns/${id}`, body);
    else await api.post(`${SALES_API}/returns`, body);
    showToast(t("common.saved"));
    closeModal("return-modal");
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteReturn(id) {
  if (!confirm(t("sales.confirmDelete"))) return;
  try {
    await api.delete(`${SALES_API}/returns/${id}`);
    showToast(t("common.deleted"));
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

function printReturn(id) { window.open(`/documents/sales-return/${id}`, "_blank"); }
function downloadReturnPdf(id) { window.open(`/documents/sales-return/${id}/pdf`, "_blank"); }

// ==================== COMMISSIONS ====================
function renderCommissions() {
  const tbody = document.getElementById("commissions-table");
  if (!allCommissions.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">💰</div>${t("sales.noCommissions")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allCommissions.map((c) => `
    <tr>
      <td><strong>${escapeHtml(c.salesperson_name || "—")}</strong></td>
      <td style="color:var(--muted-foreground);">${escapeHtml(c.order_number || "—")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(c.invoice_number || "—")}</td>
      <td style="color:var(--muted-foreground);">${formatDate(c.commission_date)}</td>
      <td>${formatNumber(c.rate)}%</td>
      <td><strong>${formatMoney(c.amount)}</strong></td>
      <td>${salesStatusBadge(c.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("sales", "edit") && c.status === "pending" ? `<button class="btn btn-success btn-sm" onclick="commissionStatus(${c.id}, 'paid')">${t("sales.statusPaid")}</button>` : ""}
          ${canAction("sales", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editCommission(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
          ${canAction("sales", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteCommission(${c.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function openCommissionModal() {
  document.getElementById("commission-modal-title").textContent = t("sales.newCommission");
  document.getElementById("commission-id").value = "";
  document.getElementById("commission-salesperson").value = "";
  document.getElementById("commission-order").value = "";
  document.getElementById("commission-invoice").value = "";
  document.getElementById("commission-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("commission-rate").value = "0";
  document.getElementById("commission-amount").value = "";
  document.getElementById("commission-status").value = "pending";
  document.getElementById("commission-notes").value = "";
  modal("commission-modal");
}

function editCommission(c) {
  document.getElementById("commission-modal-title").textContent = t("common.edit");
  document.getElementById("commission-id").value = c.id;
  document.getElementById("commission-salesperson").value = c.salesperson_id || "";
  document.getElementById("commission-order").value = c.order_id || "";
  document.getElementById("commission-invoice").value = c.invoice_id || "";
  document.getElementById("commission-date").value = c.commission_date || new Date().toISOString().slice(0, 10);
  document.getElementById("commission-rate").value = c.rate || 0;
  document.getElementById("commission-amount").value = c.amount || "";
  document.getElementById("commission-status").value = c.status || "pending";
  document.getElementById("commission-notes").value = c.notes || "";
  modal("commission-modal");
}

async function saveCommission() {
  const id = document.getElementById("commission-id").value;
  if (!document.getElementById("commission-salesperson").value) { showToast(t("sales.salespersonRequired"), "warning"); return; }
  const amount = parseFloat(document.getElementById("commission-amount").value) || 0;
  if (amount <= 0) { showToast(t("sales.commissionAmountRequired"), "warning"); return; }
  const body = {
    salesperson_id: document.getElementById("commission-salesperson").value || null,
    order_id: document.getElementById("commission-order").value || null,
    invoice_id: document.getElementById("commission-invoice").value || null,
    commission_date: document.getElementById("commission-date").value,
    rate: parseFloat(document.getElementById("commission-rate").value) || 0,
    amount,
    status: document.getElementById("commission-status").value,
    notes: document.getElementById("commission-notes").value,
  };
  try {
    if (id) await api.put(`${SALES_API}/commissions/${id}`, body);
    else await api.post(`${SALES_API}/commissions`, body);
    showToast(t("common.saved"));
    closeModal("commission-modal");
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteCommission(id) {
  if (!confirm(t("sales.confirmDelete"))) return;
  try {
    await api.delete(`${SALES_API}/commissions/${id}`);
    showToast(t("common.deleted"));
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function commissionStatus(id, status) {
  try {
    await api.post(`${SALES_API}/commissions/${id}/status`, { status });
    showToast(t("common.saved"));
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

async function autoCommissions() {
  if (!confirm(t("sales.autoCommissionsConfirm"))) return;
  try {
    const res = await api.post(`${SALES_API}/commissions/auto`, {});
    showToast(t("sales.autoCommissionsDone").replace("{n}", res.created || 0));
    await loadAll();
  } catch (err) { showToast(err.message, "error"); }
}

// ==================== TEAM ====================
function renderTeam() {
  const tbody = document.getElementById("team-table");
  if (!allTeam.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">👥</div>${t("sales.noTeam")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allTeam.map((m) => `
    <tr>
      <td><strong>${escapeHtml(m.name)}</strong></td>
      <td style="color:var(--muted-foreground);">${escapeHtml(m.department || m.position || "—")}</td>
      <td>${formatNumber(m.orders_count)}</td>
      <td style="color:var(--success);">${formatNumber(m.orders_completed)}</td>
      <td><strong>${formatMoney(m.orders_value)}</strong></td>
      <td>${formatNumber(m.commissions_count)}</td>
      <td style="color:var(--success);">${formatMoney(m.paid_commissions)}</td>
      <td style="color:var(--amber);">${formatMoney(m.pending_commissions)}</td>
    </tr>`).join("");
}

async function loadSalesTeam() {
  try {
    allTeam = await api.get(`${SALES_API}/team`);
    renderTeam();
  } catch (err) { showToast(err.message, "error"); }
}

function printTeamReport() {
  document.body.classList.add("printing-team");
  window.print();
  setTimeout(() => document.body.classList.remove("printing-team"), 200);
}

window.openQuoteModal = openQuoteModal;
window.editQuote = editQuote;
window.addQuoteItem = addQuoteItem;
window.recalcQuote = recalcQuote;
window.saveQuote = saveQuote;
window.deleteQuote = deleteQuote;
window.convertQuote = convertQuote;
window.printQuote = printQuote;
window.downloadQuotePdf = downloadQuotePdf;

window.openOrderModal = openOrderModal;
window.editOrder = editOrder;
window.addOrderItem = addOrderItem;
window.recalcOrderRow = recalcOrderRow;
window.saveOrder = saveOrder;
window.deleteOrder = deleteOrder;
window.orderToInvoice = orderToInvoice;
window.printOrder = printOrder;
window.downloadOrderPdf = downloadOrderPdf;

window.openInvoiceModal = openInvoiceModal;
window.editInvoice = editInvoice;
window.addInvoiceItem = addInvoiceItem;
window.recalcInvoiceRow = recalcInvoiceRow;
window.saveInvoice = saveInvoice;
window.deleteInvoice = deleteInvoice;
window.openPayModal = openPayModal;
window.savePayment = savePayment;
window.printInvoice = printInvoice;
window.downloadInvoicePdf = downloadInvoicePdf;

window.openReturnModal = openReturnModal;
window.editReturn = editReturn;
window.addReturnItem = addReturnItem;
window.recalcReturnRow = recalcReturnRow;
window.saveReturn = saveReturn;
window.deleteReturn = deleteReturn;
window.printReturn = printReturn;
window.downloadReturnPdf = downloadReturnPdf;

window.openCommissionModal = openCommissionModal;
window.editCommission = editCommission;
window.saveCommission = saveCommission;
window.deleteCommission = deleteCommission;
window.commissionStatus = commissionStatus;
window.autoCommissions = autoCommissions;
window.refreshTeam = refreshTeam;
window.printTeamReport = printTeamReport;

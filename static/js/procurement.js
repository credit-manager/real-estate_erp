/* ============================================================
   Procurement Module JavaScript
   ============================================================ */

let allPOs = [];
let allSuppliers = [];
let allProjects = [];
let allPRs = [];
let allRFQs = [];
let allReceivings = [];
let allReturns = [];
let allSupplierInvoices = [];
let allItems = [];
let allWarehouses = [];
let defaultTaxRate = 0;
let currentTab = "po";

document.addEventListener("DOMContentLoaded", async () => {
  try {
    // Load base data
    [allPOs, allSuppliers, allProjects, allItems, allWarehouses] = await Promise.all([
      api.get("/api/purchase-orders"),
      api.get("/api/suppliers"),
      api.get("/api/projects"),
      api.get("/api/inventory/items"),
      api.get("/api/inventory/warehouses"),
    ]);
    if (allItems && allItems.items && Array.isArray(allItems.items)) allItems = allItems.items;
    if (allWarehouses && allWarehouses.warehouses && Array.isArray(allWarehouses.warehouses)) allWarehouses = allWarehouses.warehouses;
  } catch (err) {
    console.error("Base data load failed:", err);
  }

  // Render base tables regardless of other failures
  try {
    renderPurchaseOrders();
    renderSuppliers();
    populateSupplierSelect();
    populateProjectSelect();
  } catch (err) {
    console.error("Render failed:", err);
  }

  // Load each module independently - one failure should not block others
  loadPRs().catch(err => console.error("PR load failed:", err));
  loadRFQs().catch(err => console.error("RFQ load failed:", err));
  loadReceivings().catch(err => console.error("Receiving load failed:", err));
  loadReturns().catch(err => console.error("Returns load failed:", err));
  loadSupplierInvoices().catch(err => console.error("Supplier invoices load failed:", err));

  // Load financial year options independently
  try {
    await loadFinancialYearOptions();
    buildFinancialYearFilter("filter-year");
    document.getElementById("filter-year").addEventListener("change", () => {
      renderPurchaseOrders();
      renderPRs();
      renderRFQs();
      renderReceivings();
      renderReturns();
      renderSupplierInvoices();
    });
  } catch (err) {
    console.error("Financial year load failed:", err);
  }

  // Summary last (after all data attempts)
  try {
    renderSummary();
  } catch (err) {
    console.error("Summary render failed:", err);
  }

  api.get("/api/taxes/defaults").then((res) => {
    if (res && typeof res.default_rate === "number") defaultTaxRate = res.default_rate;
  }).catch(() => {});
});

// ===== Tab Switching =====
function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === "tab-" + tab);
  });
  if (tab === "compare") populateCompareSelect();
}

// ===== Data Loading =====
async function loadPRs() {
  allPRs = await api.get("/api/procurement/purchase-requests");
  renderPRs();
}

async function loadRFQs() {
  allRFQs = await api.get("/api/procurement/rfqs");
  renderRFQs();
  populateCompareSelect();
}

async function loadReceivings() {
  allReceivings = await api.get("/api/procurement/receivings");
  renderReceivings();
}

async function loadReturns() {
  allReturns = await api.get("/api/procurement/returns");
  renderReturns();
}

async function loadSupplierInvoices() {
  allSupplierInvoices = await api.get("/api/procurement/supplier-invoices");
  renderSupplierInvoices();
}

async function loadPOs() {
  allPOs = await api.get("/api/purchase-orders");
  renderPurchaseOrders();
}

// ===== Render Functions =====
function renderPurchaseOrders() {
  let year = null;
  try {
    year = selectedFinancialYear("filter-year");
  } catch (e) {
    year = null;
  }
  const rows = year ? allPOs.filter((po) => po.financial_year_id === year) : allPOs;
  const tbody = document.getElementById("purchase-table");
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">📦</div>' + t("procurement.noPOs") + '</div></td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((po) => {
    const supplier = allSuppliers.find((s) => s.id === po.supplier_id);
    return `
    <tr>
      <td><strong>${po.po_number}</strong>
        ${po.financial_year_name ? `<div class="table-sub">${t("financialYears.year")}: ${escapeHtml(po.financial_year_name)}</div>` : ""}
      </td>
      <td style="color:var(--muted-foreground);">
        ${supplier ? escapeHtml(supplier.company_name) : "—"}
        ${po.items_description ? `<div class="table-sub">${escapeHtml(po.items_description)}</div>` : ""}
      </td>
      <td><strong>${moneyWithCurrency(po.total, po)}</strong></td>
      <td>${statusBadge(po.status)}</td>
      <td>${approvalBadge(po.approval_status)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(po.order_date) || formatDate(po.created_at)}</td>
      <td>
        <div class="table-actions">
          <button class="btn btn-info btn-sm" onclick="window.open('/documents/po/${po.id}', '_blank')">${t("common.print")}</button>
          <button class="btn btn-outline btn-sm" onclick="downloadPDF('/documents/po/${po.id}/pdf')">${t("common.download")} PDF</button>
          ${canAction("procurement", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editPurchase(${JSON.stringify(po)})'>${t("common.edit")}</button>` : ""}
          ${canAction("procurement", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deletePurchase(${po.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}

function renderPRs() {
  const tbody = document.getElementById("pr-table");
  if (!allPRs.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">📋</div>' + t("procurement.noPRs") + '</div></td></tr>';
    return;
  }
  tbody.innerHTML = allPRs.map((pr) => {
    const project = allProjects.find((p) => p.id === pr.project_id);
    return `
    <tr>
      <td><strong>${pr.pr_number}</strong></td>
      <td>${escapeHtml(pr.title || "—")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(pr.requester || "—")}${project ? `<div class="table-sub">${escapeHtml(project.name)}</div>` : ""}</td>
      <td><strong>${moneyWithCurrency(pr.total, {})}</strong></td>
      <td>${statusBadge(pr.status)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(pr.request_date)}</td>
      <td>
        <div class="table-actions">
          ${canAction("procurement", "edit") ? `
            <button class="btn btn-secondary btn-sm" onclick='editPR(${JSON.stringify(pr)})'>${t("common.edit")}</button>
            ${pr.status === "draft" ? `<button class="btn btn-info btn-sm" onclick="submitPR(${pr.id})">${t("procurement.submit")}</button>` : ""}
            ${pr.status === "submitted" ? `<button class="btn btn-success btn-sm" onclick="approvePR(${pr.id})">${t("common.approve")}</button>` : ""}
            ${pr.status === "submitted" ? `<button class="btn btn-danger btn-sm" onclick="rejectPR(${pr.id})">${t("common.reject")}</button>` : ""}
            ${pr.status === "approved" ? `<button class="btn btn-primary btn-sm" onclick="convertPRToRFQ(${pr.id})">${t("procurement.convertToRFQ")}</button>` : ""}
          ` : ""}
          ${canAction("procurement", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deletePR(${pr.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}

function renderRFQs() {
  const tbody = document.getElementById("rfq-table");
  if (!allRFQs.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">📊</div>' + t("procurement.noRFQs") + '</div></td></tr>';
    return;
  }
  tbody.innerHTML = allRFQs.map((rfq) => {
    const project = allProjects.find((p) => p.id === rfq.project_id);
    return `
    <tr>
      <td><strong>${rfq.rfq_number}</strong></td>
      <td>${escapeHtml(rfq.title || "—")}</td>
      <td style="color:var(--muted-foreground);">${project ? escapeHtml(project.name) : "—"}</td>
      <td style="color:var(--muted-foreground);">${formatDate(rfq.deadline) || "—"}</td>
      <td><span class="badge badge-neutral">${rfq.quotes_count || 0}</span></td>
      <td>${statusBadge(rfq.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("procurement", "edit") ? `
            <button class="btn btn-secondary btn-sm" onclick='editRFQ(${JSON.stringify(rfq)})'>${t("common.edit")}</button>
            ${rfq.status === "draft" ? `<button class="btn btn-info btn-sm" onclick="sendRFQ(${rfq.id})">${t("procurement.send")}</button>` : ""}
            ${rfq.status === "sent" ? `<button class="btn btn-warning btn-sm" onclick="closeRFQ(${rfq.id})">${t("procurement.close")}</button>` : ""}
            <button class="btn btn-primary btn-sm" onclick="openQuoteModal(${rfq.id})">${t("procurement.addQuote")}</button>
            <button class="btn btn-info btn-sm" onclick="viewQuotes(${rfq.id})">${t("procurement.viewQuotes")}</button>
          ` : ""}
          ${canAction("procurement", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteRFQ(${rfq.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}

function renderReceivings() {
  const tbody = document.getElementById("receiving-table");
  if (!allReceivings.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">📥</div>' + t("procurement.noReceivings") + '</div></td></tr>';
    return;
  }
  tbody.innerHTML = allReceivings.map((rcv) => {
    const po = allPOs.find((p) => p.id === rcv.po_id);
    return `
    <tr>
      <td><strong>${rcv.receiving_number}</strong></td>
      <td>${po ? `<strong>${po.po_number}</strong>` : "—"}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(rcv.supplier_name || "—")}</td>
      <td>${escapeHtml(rcv.warehouse || "—")}</td>
      <td><strong>${moneyWithCurrency(rcv.total, {})}</strong></td>
      <td style="color:var(--muted-foreground);">${formatDate(rcv.received_date)}</td>
      <td>
        <div class="table-actions">
          ${canAction("procurement", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editReceiving(${JSON.stringify(rcv)})'>${t("common.edit")}</button>` : ""}
          ${canAction("procurement", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteReceiving(${rcv.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}

function renderReturns() {
  const tbody = document.getElementById("return-table");
  if (!allReturns.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">↩️</div>' + t("procurement.noReturns") + '</div></td></tr>';
    return;
  }
  tbody.innerHTML = allReturns.map((ret) => {
    const po = allPOs.find((p) => p.id === ret.po_id);
    return `
    <tr>
      <td><strong>${ret.return_number}</strong></td>
      <td>${po ? `<strong>${po.po_number}</strong>` : "—"}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(ret.supplier_name || "—")}</td>
      <td><strong>${moneyWithCurrency(ret.total, {})}</strong></td>
      <td>${statusBadge(ret.status)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(ret.return_date)}</td>
      <td>
        <div class="table-actions">
          ${canAction("procurement", "edit") ? `
            <button class="btn btn-secondary btn-sm" onclick='editReturn(${JSON.stringify(ret)})'>${t("common.edit")}</button>
            ${ret.status === "draft" ? `<button class="btn btn-info btn-sm" onclick="processReturn(${ret.id})">${t("procurement.process")}</button>` : ""}
            ${ret.status === "processed" ? `<button class="btn btn-success btn-sm" onclick="completeReturn(${ret.id})">${t("procurement.complete")}</button>` : ""}
          ` : ""}
          ${canAction("procurement", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteReturn(${ret.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}

function renderSupplierInvoices() {
  const tbody = document.getElementById("supplier-invoice-table");
  if (!allSupplierInvoices.length) {
    tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">🧾</div>' + t("procurement.noSupplierInvoices") + '</div></td></tr>';
    return;
  }
  tbody.innerHTML = allSupplierInvoices.map((inv) => {
    const supplier = allSuppliers.find((s) => s.id === inv.supplier_id);
    const balance = (inv.amount || 0) - (inv.paid_amount || 0);
    return `
    <tr>
      <td><strong>${inv.invoice_number}</strong></td>
      <td style="color:var(--muted-foreground);">${supplier ? escapeHtml(supplier.company_name) : "—"}</td>
      <td><strong>${moneyWithCurrency(inv.amount, inv)}</strong></td>
      <td>${moneyWithCurrency(inv.paid_amount, inv)}</td>
      <td>${moneyWithCurrency(balance, inv)}</td>
      <td>${statusBadge(inv.status)}</td>
      <td style="color:var(--muted-foreground);">${formatDate(inv.issue_date)}</td>
      <td>
        <div class="table-actions">
          <button class="btn btn-info btn-sm" onclick="window.open('/documents/invoice/${inv.id}', '_blank')">${t("common.print")}</button>
          ${canAction("procurement", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editSupplierInvoice(${JSON.stringify(inv)})'>${t("common.edit")}</button>` : ""}
          ${canAction("procurement", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteSupplierInvoice(${inv.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}

function renderSuppliers() {
  const tbody = document.getElementById("suppliers-table");
  if (!allSuppliers.length) {
    tbody.innerHTML = '<tr><td colspan="5"><div class="empty-state"><div class="empty-icon">🏭</div>' + t("procurement.noSuppliers") + '</div></td></tr>';
    return;
  }
  tbody.innerHTML = allSuppliers.map((s) => `
    <tr>
      <td><strong>${s.company_name}</strong></td>
      <td style="color:var(--muted-foreground);">${s.contact_name || "—"}</td>
      <td style="direction:ltr;text-align:right;">${s.phone || "—"}</td>
      <td><span class="badge badge-neutral">${tv(s.category) || "—"}</span></td>
      <td>
        <div class="table-actions">
          ${canAction("procurement", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editSupplier(${JSON.stringify(s)})'>${t("common.edit")}</button>` : ""}
          ${canAction("procurement", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteSupplier(${s.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");
}

function renderSummary() {
  animateCount(document.getElementById("po-total"), allPOs.length, formatNumber);
  animateCount(document.getElementById("pr-total"), allPRs.length, formatNumber);
  animateCount(document.getElementById("rfq-total"), allRFQs.length, formatNumber);
  animateCount(document.getElementById("rcv-total"), allReceivings.length, formatNumber);
  animateCount(document.getElementById("ret-total"), allReturns.length, formatNumber);
  animateCount(document.getElementById("po-suppliers"), allSuppliers.length, formatNumber);
}

// ===== Export =====
function exportPurchaseOrders() {
  const headers = [
    t("procurement.numberLabel"), t("common.supplier"), t("common.project"),
    t("common.materials"), t("common.total"), t("common.status"),
    t("procurement.orderDate"), t("procurement.deliveryDate"),
  ];
  const rows = allPOs.map((po) => {
    const supplier = allSuppliers.find((s) => s.id === po.supplier_id);
    const project = allProjects.find((p) => p.id === po.project_id);
    return [
      po.po_number,
      supplier ? supplier.company_name : "",
      project ? project.name : "",
      po.items_description || "",
      po.total || 0,
      STATUS_LABELS[po.status] || po.status,
      formatDate(po.order_date),
      formatDate(po.delivery_date),
    ];
  });
  exportCSV("purchase-orders.csv", headers, rows);
}

function exportSuppliers() {
  const headers = [
    t("common.company"), t("common.contact"), t("common.phone"),
    t("common.email"), t("common.category"),
  ];
  const rows = allSuppliers.map((s) => [
    s.company_name, s.contact_name || "", s.phone || "",
    s.email || "", tv(s.category) || "",
  ]);
  exportCSV("suppliers.csv", headers, rows);
}

// ===== PO Items Editor =====
function poItemRowHTML(it) {
  it = it || {};
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input type="text" class="item-desc" placeholder="${t("procurement.itemDescPlaceholder")}" value="${escapeHtml(it.description || "")}">
    <input type="number" class="item-qty" min="0" step="0.01" value="${it.quantity != null ? it.quantity : 1}" title="${t("procurement.itemQtyCol")}">
    <input type="number" class="item-price" min="0" step="0.01" value="${it.unit_price || ""}" placeholder="0.00" title="${t("procurement.itemPriceCol")}">
    <input type="number" class="item-tax" min="0" step="0.01" value="${it.tax_rate != null ? it.tax_rate : defaultTaxRate}" title="${t("procurement.itemTaxCol")}">
    <span class="item-line-total" title="${t("procurement.itemTotalCol")}">0.00</span>
    <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removePoItem(this)" title="${t("procurement.removeItem")}">✕</button>`;
  row.querySelectorAll("input").forEach((el) => el.addEventListener("input", recalcPoItems));
  recalcPoItems();
  return row;
}

function addPoItem() {
  document.getElementById("po-items").appendChild(poItemRowHTML());
  recalcPoItems();
  setPoTotalDisabled();
}

function removePoItem(btn) {
  const editor = document.getElementById("po-items");
  if (editor.children.length <= 1) {
    editor.innerHTML = "";
    editor.appendChild(poItemRowHTML());
    return;
  }
  btn.closest(".item-row").remove();
  recalcPoItems();
  setPoTotalDisabled();
}

function collectPoItems() {
  const rows = document.querySelectorAll("#po-items .item-row");
  const items = [];
  rows.forEach((row) => {
    const desc = row.querySelector(".item-desc").value.trim();
    if (!desc) return;
    items.push({
      description: desc,
      quantity: parseFloat(row.querySelector(".item-qty").value) || 0,
      unit_price: parseFloat(row.querySelector(".item-price").value) || 0,
      tax_rate: parseFloat(row.querySelector(".item-tax").value) || 0,
    });
  });
  return items;
}

function recalcPoItems() {
  const rows = document.querySelectorAll("#po-items .item-row");
  let grand = 0;
  rows.forEach((row) => {
    const qty = parseFloat(row.querySelector(".item-qty").value) || 0;
    const price = parseFloat(row.querySelector(".item-price").value) || 0;
    const tax = parseFloat(row.querySelector(".item-tax").value) || 0;
    const total = qty * price * (1 + tax / 100);
    row.querySelector(".item-line-total").textContent = formatMoney(total);
    grand += total;
  });
  const totalInput = document.getElementById("purchase-total");
  if (!totalInput.disabled) totalInput.value = grand ? grand.toFixed(2) : "";
}

function setPoTotalDisabled() {
  const totalInput = document.getElementById("purchase-total");
  totalInput.disabled = collectPoItems().length > 0;
}

// ===== Purchase Order Modal =====
function openPurchaseModal() {
  try {
    document.getElementById("purchase-modal-title").textContent = t("procurement.newPO");
    document.getElementById("purchase-id").value = "";
    const numEl = document.getElementById("purchase-number");
    numEl.value = "";
    try { prefillDocNumber(numEl, "po", "PO-"); } catch (e) {}
    document.getElementById("purchase-items").value = "";
    document.getElementById("purchase-total").value = "";
    document.getElementById("purchase-total").disabled = false;
    document.getElementById("purchase-status").value = "pending";
    document.getElementById("purchase-order-date").value = "";
    document.getElementById("purchase-delivery-date").value = "";
    document.getElementById("po-items").innerHTML = "";
    document.getElementById("po-items").appendChild(poItemRowHTML());
    try { populateSupplierSelect(); } catch (e) {}
    try { populateProjectSelect(); } catch (e) {}
    try { fillFinancialYearSelect("purchase-year"); } catch (e) {}
    document.getElementById("purchase-modal").classList.add("active");
  } catch (err) {
    console.error("openPurchaseModal error:", err);
  }
}

function editPurchase(po) {
  document.getElementById("purchase-modal-title").textContent = t("procurement.editPO");
  document.getElementById("purchase-id").value = po.id;
  document.getElementById("purchase-number").value = po.po_number || "";
  document.getElementById("purchase-items").value = po.items_description || "";
  document.getElementById("purchase-total").value = po.total || "";
  document.getElementById("purchase-status").value = po.status || "pending";
  document.getElementById("purchase-order-date").value = po.order_date || "";
  document.getElementById("purchase-delivery-date").value = po.delivery_date || "";
  const items = (po.items && po.items.length) ? po.items : [null];
  document.getElementById("po-items").innerHTML = "";
  items.forEach((it) => document.getElementById("po-items").appendChild(poItemRowHTML(it)));
  setPoTotalDisabled();
  populateSupplierSelect();
  populateProjectSelect();
  document.getElementById("purchase-supplier").value = po.supplier_id || "";
  document.getElementById("purchase-project").value = po.project_id || "";
  fillFinancialYearSelect("purchase-year", po.financial_year_id);
  document.getElementById("purchase-modal").classList.add("active");
}

function closePurchaseModal() {
  document.getElementById("purchase-modal").classList.remove("active");
}

async function savePurchase() {
  const id = document.getElementById("purchase-id").value;
  const items = collectPoItems();
  const body = {
    po_number: document.getElementById("purchase-number").value,
    supplier_id: parseInt(document.getElementById("purchase-supplier").value) || null,
    project_id: parseInt(document.getElementById("purchase-project").value) || null,
    items_description: document.getElementById("purchase-items").value,
    status: document.getElementById("purchase-status").value,
    financial_year_id: financialYearValue("purchase-year"),
    order_date: document.getElementById("purchase-order-date").value,
    delivery_date: document.getElementById("purchase-delivery-date").value,
  };
  if (items.length) body.items = items;
  else body.total = parseFloat(document.getElementById("purchase-total").value) || 0;
  if (!body.po_number) { showToast(t("procurement.numberRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/purchase-orders/${id}`, body);
    else await api.post("/api/purchase-orders", body);
    showToast(t("common.saved"));
    closePurchaseModal();
    allPOs = await api.get("/api/purchase-orders");
    renderPurchaseOrders();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deletePurchase(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/purchase-orders/${id}`);
    showToast(t("common.deleted"));
    allPOs = await api.get("/api/purchase-orders");
    renderPurchaseOrders();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== PR Items Editor =====
function prItemRowHTML(it) {
  it = it || {};
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input type="text" class="item-desc" placeholder="${t("procurement.itemDescPlaceholder")}" value="${escapeHtml(it.description || "")}">
    <input type="number" class="item-qty" min="0" step="0.01" value="${it.quantity != null ? it.quantity : 1}" title="${t("procurement.itemQtyCol")}">
    <input type="number" class="item-price" min="0" step="0.01" value="${it.unit_price || ""}" placeholder="0.00" title="${t("procurement.itemPriceCol")}">
    <input type="number" class="item-tax" min="0" step="0.01" value="${it.tax_rate != null ? it.tax_rate : defaultTaxRate}" title="${t("procurement.itemTaxCol")}">
    <span class="item-line-total" title="${t("procurement.itemTotalCol")}">0.00</span>
    <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removePrItem(this)" title="${t("procurement.removeItem")}">✕</button>`;
  row.querySelectorAll("input").forEach((el) => el.addEventListener("input", recalcPrItems));
  recalcPrItems();
  return row;
}

function addPrItem() {
  document.getElementById("pr-items").appendChild(prItemRowHTML());
  recalcPrItems();
}

function removePrItem(btn) {
  const editor = document.getElementById("pr-items");
  if (editor.children.length <= 1) {
    editor.innerHTML = "";
    editor.appendChild(prItemRowHTML());
    return;
  }
  btn.closest(".item-row").remove();
  recalcPrItems();
}

function collectPrItems() {
  const rows = document.querySelectorAll("#pr-items .item-row");
  const items = [];
  rows.forEach((row) => {
    const desc = row.querySelector(".item-desc").value.trim();
    if (!desc) return;
    items.push({
      description: desc,
      quantity: parseFloat(row.querySelector(".item-qty").value) || 0,
      unit_price: parseFloat(row.querySelector(".item-price").value) || 0,
      tax_rate: parseFloat(row.querySelector(".item-tax").value) || 0,
    });
  });
  return items;
}

function recalcPrItems() {
  const rows = document.querySelectorAll("#pr-items .item-row");
  let grand = 0;
  rows.forEach((row) => {
    const qty = parseFloat(row.querySelector(".item-qty").value) || 0;
    const price = parseFloat(row.querySelector(".item-price").value) || 0;
    const tax = parseFloat(row.querySelector(".item-tax").value) || 0;
    const total = qty * price * (1 + tax / 100);
    row.querySelector(".item-line-total").textContent = formatMoney(total);
    grand += total;
  });
}

// ===== PR Modal =====
function openPRModal() {
  try {
    document.getElementById("pr-modal-title").textContent = t("procurement.newPR");
    document.getElementById("pr-id").value = "";
    document.getElementById("pr-number").value = "";
    document.getElementById("pr-title").value = "";
    document.getElementById("pr-requester").value = "";
    document.getElementById("pr-department").value = "";
    document.getElementById("pr-request-date").value = "";
    document.getElementById("pr-needed-date").value = "";
    document.getElementById("pr-notes").value = "";
    document.getElementById("pr-status").value = "draft";
    document.getElementById("pr-items").innerHTML = "";
    document.getElementById("pr-items").appendChild(prItemRowHTML());
    try { populateProjectSelect(); } catch (e) {}
    document.getElementById("pr-modal").classList.add("active");
  } catch (err) {
    console.error("openPRModal error:", err);
  }
}

function editPR(pr) {
  document.getElementById("pr-modal-title").textContent = t("procurement.editPR");
  document.getElementById("pr-id").value = pr.id;
  document.getElementById("pr-number").value = pr.pr_number || "";
  document.getElementById("pr-title").value = pr.title || "";
  document.getElementById("pr-requester").value = pr.requester || "";
  document.getElementById("pr-department").value = pr.department || "";
  document.getElementById("pr-request-date").value = pr.request_date || "";
  document.getElementById("pr-needed-date").value = pr.needed_date || "";
  document.getElementById("pr-notes").value = pr.notes || "";
  document.getElementById("pr-status").value = pr.status || "draft";
  const items = (pr.items && pr.items.length) ? pr.items : [null];
  document.getElementById("pr-items").innerHTML = "";
  items.forEach((it) => document.getElementById("pr-items").appendChild(prItemRowHTML(it)));
  populateProjectSelect();
  document.getElementById("pr-project").value = pr.project_id || "";
  document.getElementById("pr-modal").classList.add("active");
}

function closePRModal() {
  document.getElementById("pr-modal").classList.remove("active");
}

async function savePR() {
  const id = document.getElementById("pr-id").value;
  const items = collectPrItems();
  const body = {
    pr_number: document.getElementById("pr-number").value,
    title: document.getElementById("pr-title").value,
    requester: document.getElementById("pr-requester").value,
    department: document.getElementById("pr-department").value,
    project_id: parseInt(document.getElementById("pr-project").value) || null,
    request_date: document.getElementById("pr-request-date").value,
    needed_date: document.getElementById("pr-needed-date").value,
    notes: document.getElementById("pr-notes").value,
    status: document.getElementById("pr-status").value,
  };
  if (items.length) body.items = items;
  if (!body.pr_number) { showToast(t("procurement.numberRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/procurement/purchase-requests/${id}`, body);
    else await api.post("/api/procurement/purchase-requests", body);
    showToast(t("common.saved"));
    closePRModal();
    await loadPRs();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deletePR(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/procurement/purchase-requests/${id}`);
    showToast(t("common.deleted"));
    await loadPRs();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function submitPR(id) {
  try {
    await api.post(`/api/procurement/purchase-requests/${id}/submit`);
    showToast(t("common.saved"));
    await loadPRs();
  } catch (err) { showToast(err.message, "error"); }
}

async function approvePR(id) {
  try {
    await api.post(`/api/procurement/purchase-requests/${id}/approve`);
    showToast(t("common.saved"));
    await loadPRs();
  } catch (err) { showToast(err.message, "error"); }
}

async function rejectPR(id) {
  try {
    await api.post(`/api/procurement/purchase-requests/${id}/reject`);
    showToast(t("common.saved"));
    await loadPRs();
  } catch (err) { showToast(err.message, "error"); }
}

async function convertPRToRFQ(id) {
  if (!confirm(t("procurement.convertToRFQConfirm"))) return;
  try {
    await api.post(`/api/procurement/purchase-requests/${id}/convert-to-rfq`);
    showToast(t("procurement.convertedToRFQ"));
    await loadPRs();
    await loadRFQs();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== RFQ Items Editor =====
function rfqItemRowHTML(it) {
  it = it || {};
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input type="text" class="item-desc" placeholder="${t("procurement.itemDescPlaceholder")}" value="${escapeHtml(it.description || "")}">
    <input type="number" class="item-qty" min="0" step="0.01" value="${it.quantity != null ? it.quantity : 1}" title="${t("procurement.itemQtyCol")}">
    <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removeRfqItem(this)" title="${t("procurement.removeItem")}">✕</button>`;
  return row;
}

function addRfqItem() {
  document.getElementById("rfq-items").appendChild(rfqItemRowHTML());
}

function removeRfqItem(btn) {
  const editor = document.getElementById("rfq-items");
  if (editor.children.length <= 1) {
    editor.innerHTML = "";
    editor.appendChild(rfqItemRowHTML());
    return;
  }
  btn.closest(".item-row").remove();
}

function collectRfqItems() {
  const rows = document.querySelectorAll("#rfq-items .item-row");
  const items = [];
  rows.forEach((row) => {
    const desc = row.querySelector(".item-desc").value.trim();
    if (!desc) return;
    items.push({
      description: desc,
      quantity: parseFloat(row.querySelector(".item-qty").value) || 0,
    });
  });
  return items;
}

// ===== RFQ Modal =====
function openRFQModal() {
  try {
    document.getElementById("rfq-modal-title").textContent = t("procurement.newRFQ");
    document.getElementById("rfq-id").value = "";
    document.getElementById("rfq-number").value = "";
    document.getElementById("rfq-title").value = "";
    document.getElementById("rfq-request-date").value = "";
    document.getElementById("rfq-deadline").value = "";
    document.getElementById("rfq-notes").value = "";
    document.getElementById("rfq-status").value = "draft";
    document.getElementById("rfq-items").innerHTML = "";
    document.getElementById("rfq-items").appendChild(rfqItemRowHTML());
    try { populateProjectSelect(); } catch (e) {}
    document.getElementById("rfq-modal").classList.add("active");
  } catch (err) {
    console.error("openRFQModal error:", err);
  }
}

function editRFQ(rfq) {
  document.getElementById("rfq-modal-title").textContent = t("procurement.editRFQ");
  document.getElementById("rfq-id").value = rfq.id;
  document.getElementById("rfq-number").value = rfq.rfq_number || "";
  document.getElementById("rfq-title").value = rfq.title || "";
  document.getElementById("rfq-request-date").value = rfq.request_date || "";
  document.getElementById("rfq-deadline").value = rfq.deadline || "";
  document.getElementById("rfq-notes").value = rfq.notes || "";
  document.getElementById("rfq-status").value = rfq.status || "draft";
  const items = (rfq.items && rfq.items.length) ? rfq.items : [null];
  document.getElementById("rfq-items").innerHTML = "";
  items.forEach((it) => document.getElementById("rfq-items").appendChild(rfqItemRowHTML(it)));
  populateProjectSelect();
  document.getElementById("rfq-project").value = rfq.project_id || "";
  document.getElementById("rfq-modal").classList.add("active");
}

function closeRFQModal() {
  document.getElementById("rfq-modal").classList.remove("active");
}

async function saveRFQ() {
  const id = document.getElementById("rfq-id").value;
  const items = collectRfqItems();
  const body = {
    rfq_number: document.getElementById("rfq-number").value,
    title: document.getElementById("rfq-title").value,
    project_id: parseInt(document.getElementById("rfq-project").value) || null,
    request_date: document.getElementById("rfq-request-date").value,
    deadline: document.getElementById("rfq-deadline").value,
    notes: document.getElementById("rfq-notes").value,
    status: document.getElementById("rfq-status").value,
  };
  if (items.length) body.items = items;
  if (!body.rfq_number) { showToast(t("procurement.numberRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/procurement/rfqs/${id}`, body);
    else await api.post("/api/procurement/rfqs", body);
    showToast(t("common.saved"));
    closeRFQModal();
    await loadRFQs();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteRFQ(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/procurement/rfqs/${id}`);
    showToast(t("common.deleted"));
    await loadRFQs();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function sendRFQ(id) {
  try {
    await api.post(`/api/procurement/rfqs/${id}/send`);
    showToast(t("common.saved"));
    await loadRFQs();
  } catch (err) { showToast(err.message, "error"); }
}

async function closeRFQ(id) {
  try {
    await api.post(`/api/procurement/rfqs/${id}/close`);
    showToast(t("common.saved"));
    await loadRFQs();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== Quotes =====
function openQuoteModal(rfqId) {
  const rfq = allRFQs.find((r) => r.id === rfqId);
  if (!rfq) return;
  document.getElementById("quote-rfq-id").value = rfqId;
  document.getElementById("quote-id").value = "";
  document.getElementById("quote-supplier").value = "";
  document.getElementById("quote-delivery-days").value = 0;
  document.getElementById("quote-notes").value = "";
  const editor = document.getElementById("quote-items");
  editor.innerHTML = "";
  (rfq.items || []).forEach((it) => {
  const row = document.createElement("div");
  row.className = "item-row";
    row.innerHTML = `
      <input type="text" class="item-desc" placeholder="${t("procurement.itemDescPlaceholder")}" value="${escapeHtml(it.description || "")}">
      <input type="number" class="item-qty" min="0" step="0.01" value="${it.quantity || 1}" title="${t("procurement.itemQtyCol")}">
      <input type="number" class="item-price" min="0" step="0.01" placeholder="0.00" title="${t("procurement.itemPriceCol")}">
      <input type="number" class="item-tax" min="0" step="0.01" value="${defaultTaxRate}" title="${t("procurement.itemTaxCol")}">
      <span class="item-line-total" title="${t("procurement.itemTotalCol")}">0.00</span>
      <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removeQuoteItem(this)" title="${t("procurement.removeItem")}">✕</button>`;
    row.querySelectorAll("input").forEach((el) => el.addEventListener("input", recalcQuoteItems));
    editor.appendChild(row);
  });
  if (!editor.children.length) editor.appendChild(quoteItemRowHTML());
  recalcQuoteItems();
  populateSupplierSelect();
  document.getElementById("quote-modal").classList.add("active");
}

function quoteItemRowHTML(it) {
  it = it || {};
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input type="text" class="item-desc" placeholder="${t("procurement.itemDescPlaceholder")}" value="${escapeHtml(it.description || "")}">
    <input type="number" class="item-qty" min="0" step="0.01" value="${it.quantity != null ? it.quantity : 1}" title="${t("procurement.itemQtyCol")}">
    <input type="number" class="item-price" min="0" step="0.01" value="${it.unit_price || ""}" placeholder="0.00" title="${t("procurement.itemPriceCol")}">
    <input type="number" class="item-tax" min="0" step="0.01" value="${it.tax_rate != null ? it.tax_rate : defaultTaxRate}" title="${t("procurement.itemTaxCol")}">
    <span class="item-line-total" title="${t("procurement.itemTotalCol")}">0.00</span>
    <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removeQuoteItem(this)" title="${t("procurement.removeItem")}">✕</button>`;
  row.querySelectorAll("input").forEach((el) => el.addEventListener("input", recalcQuoteItems));
  recalcQuoteItems();
  return row;
}

function addQuoteItem() {
  document.getElementById("quote-items").appendChild(quoteItemRowHTML());
  recalcQuoteItems();
}

function removeQuoteItem(btn) {
  const editor = document.getElementById("quote-items");
  if (editor.children.length <= 1) {
    editor.innerHTML = "";
    editor.appendChild(quoteItemRowHTML());
    return;
  }
  btn.closest(".item-row").remove();
  recalcQuoteItems();
}

function collectQuoteItems() {
  const rows = document.querySelectorAll("#quote-items .item-row");
  const items = [];
  rows.forEach((row) => {
    const desc = row.querySelector(".item-desc").value.trim();
    if (!desc) return;
    items.push({
      description: desc,
      quantity: parseFloat(row.querySelector(".item-qty").value) || 0,
      unit_price: parseFloat(row.querySelector(".item-price").value) || 0,
      tax_rate: parseFloat(row.querySelector(".item-tax").value) || 0,
    });
  });
  return items;
}

function recalcQuoteItems() {
  const rows = document.querySelectorAll("#quote-items .item-row");
  let grand = 0;
  rows.forEach((row) => {
    const qty = parseFloat(row.querySelector(".item-qty").value) || 0;
    const price = parseFloat(row.querySelector(".item-price").value) || 0;
    const tax = parseFloat(row.querySelector(".item-tax").value) || 0;
    const total = qty * price * (1 + tax / 100);
    row.querySelector(".item-line-total").textContent = formatMoney(total);
    grand += total;
  });
}

function closeQuoteModal() {
  document.getElementById("quote-modal").classList.remove("active");
}

async function saveQuote() {
  const id = document.getElementById("quote-id").value;
  const rfqId = document.getElementById("quote-rfq-id").value;
  const items = collectQuoteItems();
  const body = {
    supplier_id: parseInt(document.getElementById("quote-supplier").value) || null,
    delivery_days: parseInt(document.getElementById("quote-delivery-days").value) || 0,
    notes: document.getElementById("quote-notes").value,
  };
  if (items.length) body.items = items;
  if (!body.supplier_id) { showToast(t("procurement.supplierRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/procurement/rfq-quotes/${id}`, body);
    else await api.post(`/api/procurement/rfqs/${rfqId}/quotes`, body);
    showToast(t("common.saved"));
    closeQuoteModal();
    await loadRFQs();
  } catch (err) { showToast(err.message, "error"); }
}

async function viewQuotes(rfqId) {
  try {
    const quotes = await api.get(`/api/procurement/rfqs/${rfqId}/quotes`);
    if (!quotes.length) {
      showToast(t("procurement.noQuotes"), "warning");
      return;
    }
    const html = quotes.map((q) => `
      <div style="border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <strong>${escapeHtml(q.supplier_name || "—")}</strong>
          <span class="badge ${q.is_winner ? "badge-success" : "badge-neutral"}">${q.is_winner ? t("procurement.winner") : t("procurement.notWinner")}</span>
        </div>
        <div style="margin-top:8px;color:var(--muted-foreground);">
          ${t("procurement.deliveryDays")}: ${q.delivery_days || 0} · ${t("common.total")}: <strong>${moneyWithCurrency(q.total, {})}</strong>
        </div>
        <div style="margin-top:8px;display:flex;gap:8px;">
          ${canAction("procurement", "edit") ? `
            <button class="btn btn-success btn-sm" onclick="selectWinner(${q.id})">${t("procurement.selectWinner")}</button>
            <button class="btn btn-secondary btn-sm" onclick='editQuote(${JSON.stringify(q)})'>${t("common.edit")}</button>
          ` : ""}
          ${canAction("procurement", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteQuote(${q.id})">${t("common.delete")}</button>` : ""}
        </div>
      </div>
    `).join("");
    showModal(t("procurement.viewQuotes"), html);
  } catch (err) { showToast(err.message, "error"); }
}

function editQuote(q) {
  document.getElementById("quote-id").value = q.id;
  document.getElementById("quote-rfq-id").value = q.rfq_id;
  document.getElementById("quote-supplier").value = q.supplier_id || "";
  document.getElementById("quote-delivery-days").value = q.delivery_days || 0;
  document.getElementById("quote-notes").value = q.notes || "";
  const editor = document.getElementById("quote-items");
  editor.innerHTML = "";
  (q.items || []).forEach((it) => editor.appendChild(quoteItemRowHTML(it)));
  if (!editor.children.length) editor.appendChild(quoteItemRowHTML());
  recalcQuoteItems();
  populateSupplierSelect();
  document.getElementById("quote-modal").classList.add("active");
}

async function deleteQuote(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/procurement/rfq-quotes/${id}`);
    showToast(t("common.deleted"));
    await loadRFQs();
  } catch (err) { showToast(err.message, "error"); }
}

async function selectWinner(id) {
  if (!confirm(t("procurement.selectWinnerConfirm"))) return;
  try {
    await api.post(`/api/procurement/rfq-quotes/${id}/select-winner`);
    showToast(t("common.saved"));
    await loadRFQs();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== Comparison =====
function populateCompareSelect() {
  const select = document.getElementById("compare-rfq-select");
  const options = allRFQs.map((r) => `<option value="${r.id}">${escapeHtml(r.rfq_number)} - ${escapeHtml(r.title || "")}</option>`);
  select.innerHTML = `<option value="">${t("procurement.selectRFQ")}</option>` + options.join("");
}

async function loadComparison() {
  const rfqId = document.getElementById("compare-rfq-select").value;
  if (!rfqId) { showToast(t("procurement.selectRFQ"), "warning"); return; }
  try {
    const data = await api.get(`/api/procurement/rfqs/${rfqId}/compare`);
    const container = document.getElementById("compare-content");
    if (!data.quotes.length) {
      container.innerHTML = `<div class="empty-state" style="padding:40px;"><div class="empty-icon">⚖️</div><p>${t("procurement.noQuotesToCompare")}</p></div>`;
      return;
    }
    const suppliers = data.quotes.map((q) => q.supplier_name || "—");
    let html = `<div class="table-wrapper"><table><thead><tr><th>${t("procurement.itemDescCol")}</th><th>${t("procurement.itemQtyCol")}</th>`;
    suppliers.forEach((s) => html += `<th>${escapeHtml(s)}</th>`);
    html += `</tr></thead><tbody>`;
    data.comparison.forEach((row) => {
      html += `<tr><td>${escapeHtml(row.description)}</td><td>${row.quantity}</td>`;
      row.quotes.forEach((q) => {
        html += `<td>${q.unit_price ? moneyWithCurrency(q.unit_price, {}) : "—"}</td>`;
      });
      html += `</tr>`;
    });
    html += `<tr><td><strong>${t("common.total")}</strong></td><td></td>`;
    data.quotes.forEach((q) => {
      html += `<td><strong>${moneyWithCurrency(q.total, {})}</strong>${q.is_winner ? ` <span class="badge badge-success">${t("procurement.winner")}</span>` : ""}</td>`;
    });
    html += `</tr></tbody></table></div>`;
    container.innerHTML = html;
  } catch (err) { showToast(err.message, "error"); }
}

// ===== Receiving Items Editor =====
function receivingItemRowHTML(it) {
  it = it || {};
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input type="text" class="item-desc" placeholder="${t("procurement.itemDescPlaceholder")}" value="${escapeHtml(it.description || "")}">
    <input type="number" class="item-qty" min="0" step="0.01" value="${it.quantity != null ? it.quantity : 1}" title="${t("procurement.itemQtyCol")}">
    <input type="number" class="item-price" min="0" step="0.01" value="${it.unit_price || ""}" placeholder="0.00" title="${t("procurement.itemPriceCol")}">
    <input type="number" class="item-tax" min="0" step="0.01" value="${it.tax_rate != null ? it.tax_rate : defaultTaxRate}" title="${t("procurement.itemTaxCol")}">
    <span class="item-line-total" title="${t("procurement.itemTotalCol")}">0.00</span>
    <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removeReceivingItem(this)" title="${t("procurement.removeItem")}">✕</button>`;
  row.querySelectorAll("input").forEach((el) => el.addEventListener("input", recalcReceivingItems));
  recalcReceivingItems();
  return row;
}

function addReceivingItem() {
  document.getElementById("receiving-items").appendChild(receivingItemRowHTML());
  recalcReceivingItems();
}

function removeReceivingItem(btn) {
  const editor = document.getElementById("receiving-items");
  if (editor.children.length <= 1) {
    editor.innerHTML = "";
    editor.appendChild(receivingItemRowHTML());
    return;
  }
  btn.closest(".item-row").remove();
  recalcReceivingItems();
}

function collectReceivingItems() {
  const rows = document.querySelectorAll("#receiving-items .item-row");
  const items = [];
  rows.forEach((row) => {
    const desc = row.querySelector(".item-desc").value.trim();
    if (!desc) return;
    items.push({
      description: desc,
      quantity: parseFloat(row.querySelector(".item-qty").value) || 0,
      unit_price: parseFloat(row.querySelector(".item-price").value) || 0,
      tax_rate: parseFloat(row.querySelector(".item-tax").value) || 0,
    });
  });
  return items;
}

function recalcReceivingItems() {
  const rows = document.querySelectorAll("#receiving-items .item-row");
  let grand = 0;
  rows.forEach((row) => {
    const qty = parseFloat(row.querySelector(".item-qty").value) || 0;
    const price = parseFloat(row.querySelector(".item-price").value) || 0;
    const tax = parseFloat(row.querySelector(".item-tax").value) || 0;
    const total = qty * price * (1 + tax / 100);
    row.querySelector(".item-line-total").textContent = formatMoney(total);
    grand += total;
  });
}

// ===== Receiving Modal =====
function openReceivingModal() {
  document.getElementById("receiving-id").value = "";
  document.getElementById("receiving-number").value = "";
  document.getElementById("receiving-po").value = "";
  document.getElementById("receiving-date").value = "";
  document.getElementById("receiving-warehouse").value = "";
  document.getElementById("receiving-notes").value = "";
  document.getElementById("receiving-items").innerHTML = "";
  document.getElementById("receiving-items").appendChild(receivingItemRowHTML());
  const poSelect = document.getElementById("receiving-po");
  const approvedPOs = allPOs.filter((p) => p.status === "approved" || p.status === "delivered");
  poSelect.innerHTML = `<option value="">${t("common.select")}</option>` + approvedPOs.map((p) => `<option value="${p.id}">${escapeHtml(p.po_number)}</option>`).join("");
  document.getElementById("receiving-modal").classList.add("active");
}

function editReceiving(rcv) {
  document.getElementById("receiving-id").value = rcv.id;
  document.getElementById("receiving-number").value = rcv.receiving_number || "";
  document.getElementById("receiving-po").value = rcv.po_id || "";
  document.getElementById("receiving-date").value = rcv.received_date || "";
  document.getElementById("receiving-warehouse").value = rcv.warehouse || "";
  document.getElementById("receiving-notes").value = rcv.notes || "";
  const items = (rcv.items && rcv.items.length) ? rcv.items : [null];
  document.getElementById("receiving-items").innerHTML = "";
  items.forEach((it) => document.getElementById("receiving-items").appendChild(receivingItemRowHTML(it)));
  const poSelect = document.getElementById("receiving-po");
  const approvedPOs = allPOs.filter((p) => p.status === "approved" || p.status === "delivered");
  poSelect.innerHTML = `<option value="">${t("common.select")}</option>` + approvedPOs.map((p) => `<option value="${p.id}">${escapeHtml(p.po_number)}</option>`).join("");
  document.getElementById("receiving-po").value = rcv.po_id || "";
  document.getElementById("receiving-modal").classList.add("active");
}

function closeReceivingModal() {
  document.getElementById("receiving-modal").classList.remove("active");
}

async function saveReceiving() {
  const id = document.getElementById("receiving-id").value;
  const items = collectReceivingItems();
  const body = {
    receiving_number: document.getElementById("receiving-number").value,
    po_id: parseInt(document.getElementById("receiving-po").value) || null,
    received_date: document.getElementById("receiving-date").value,
    warehouse: document.getElementById("receiving-warehouse").value,
    notes: document.getElementById("receiving-notes").value,
  };
  if (items.length) body.items = items;
  if (!body.receiving_number) { showToast(t("procurement.numberRequired"), "warning"); return; }
  if (!body.po_id) { showToast(t("procurement.poRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/procurement/receivings/${id}`, body);
    else await api.post("/api/procurement/receivings", body);
    showToast(t("common.saved"));
    closeReceivingModal();
    await loadReceivings();
    await loadPOs();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteReceiving(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/procurement/receivings/${id}`);
    showToast(t("common.deleted"));
    await loadReceivings();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== Return Items Editor =====
function returnItemRowHTML(it) {
  it = it || {};
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input type="text" class="item-desc" placeholder="${t("procurement.itemDescPlaceholder")}" value="${escapeHtml(it.description || "")}">
    <input type="number" class="item-qty" min="0" step="0.01" value="${it.quantity != null ? it.quantity : 1}" title="${t("procurement.itemQtyCol")}">
    <input type="number" class="item-price" min="0" step="0.01" value="${it.unit_price || ""}" placeholder="0.00" title="${t("procurement.itemPriceCol")}">
    <input type="number" class="item-tax" min="0" step="0.01" value="${it.tax_rate != null ? it.tax_rate : defaultTaxRate}" title="${t("procurement.itemTaxCol")}">
    <span class="item-line-total" title="${t("procurement.itemTotalCol")}">0.00</span>
    <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removeReturnItem(this)" title="${t("procurement.removeItem")}">✕</button>`;
  row.querySelectorAll("input").forEach((el) => el.addEventListener("input", recalcReturnItems));
  recalcReturnItems();
  return row;
}

function addReturnItem() {
  document.getElementById("return-items").appendChild(returnItemRowHTML());
  recalcReturnItems();
}

function removeReturnItem(btn) {
  const editor = document.getElementById("return-items");
  if (editor.children.length <= 1) {
    editor.innerHTML = "";
    editor.appendChild(returnItemRowHTML());
    return;
  }
  btn.closest(".item-row").remove();
  recalcReturnItems();
}

function collectReturnItems() {
  const rows = document.querySelectorAll("#return-items .item-row");
  const items = [];
  rows.forEach((row) => {
    const desc = row.querySelector(".item-desc").value.trim();
    if (!desc) return;
    items.push({
      description: desc,
      quantity: parseFloat(row.querySelector(".item-qty").value) || 0,
      unit_price: parseFloat(row.querySelector(".item-price").value) || 0,
      tax_rate: parseFloat(row.querySelector(".item-tax").value) || 0,
    });
  });
  return items;
}

function recalcReturnItems() {
  const rows = document.querySelectorAll("#return-items .item-row");
  let grand = 0;
  rows.forEach((row) => {
    const qty = parseFloat(row.querySelector(".item-qty").value) || 0;
    const price = parseFloat(row.querySelector(".item-price").value) || 0;
    const tax = parseFloat(row.querySelector(".item-tax").value) || 0;
    const total = qty * price * (1 + tax / 100);
    row.querySelector(".item-line-total").textContent = formatMoney(total);
    grand += total;
  });
}

// ===== Return Modal =====
function openReturnModal() {
  document.getElementById("return-id").value = "";
  document.getElementById("return-number").value = "";
  document.getElementById("return-po").value = "";
  document.getElementById("return-supplier").value = "";
  document.getElementById("return-date").value = "";
  document.getElementById("return-reason").value = "";
  document.getElementById("return-status").value = "draft";
  document.getElementById("return-items").innerHTML = "";
  document.getElementById("return-items").appendChild(returnItemRowHTML());
  const poSelect = document.getElementById("return-po");
  poSelect.innerHTML = `<option value="">${t("common.select")}</option>` + allPOs.map((p) => `<option value="${p.id}">${escapeHtml(p.po_number)}</option>`).join("");
  populateSupplierSelect();
  document.getElementById("return-modal").classList.add("active");
}

function editReturn(ret) {
  document.getElementById("return-id").value = ret.id;
  document.getElementById("return-number").value = ret.return_number || "";
  document.getElementById("return-po").value = ret.po_id || "";
  document.getElementById("return-supplier").value = ret.supplier_id || "";
  document.getElementById("return-date").value = ret.return_date || "";
  document.getElementById("return-reason").value = ret.reason || "";
  document.getElementById("return-status").value = ret.status || "draft";
  const items = (ret.items && ret.items.length) ? ret.items : [null];
  document.getElementById("return-items").innerHTML = "";
  items.forEach((it) => document.getElementById("return-items").appendChild(returnItemRowHTML(it)));
  const poSelect = document.getElementById("return-po");
  poSelect.innerHTML = `<option value="">${t("common.select")}</option>` + allPOs.map((p) => `<option value="${p.id}">${escapeHtml(p.po_number)}</option>`).join("");
  populateSupplierSelect();
  document.getElementById("return-modal").classList.add("active");
}

function closeReturnModal() {
  document.getElementById("return-modal").classList.remove("active");
}

async function saveReturn() {
  const id = document.getElementById("return-id").value;
  const items = collectReturnItems();
  const body = {
    return_number: document.getElementById("return-number").value,
    po_id: parseInt(document.getElementById("return-po").value) || null,
    supplier_id: parseInt(document.getElementById("return-supplier").value) || null,
    return_date: document.getElementById("return-date").value,
    reason: document.getElementById("return-reason").value,
    status: document.getElementById("return-status").value,
  };
  if (items.length) body.items = items;
  if (!body.return_number) { showToast(t("procurement.numberRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/procurement/returns/${id}`, body);
    else await api.post("/api/procurement/returns", body);
    showToast(t("common.saved"));
    closeReturnModal();
    await loadReturns();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteReturn(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/procurement/returns/${id}`);
    showToast(t("common.deleted"));
    await loadReturns();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function processReturn(id) {
  try {
    await api.post(`/api/procurement/returns/${id}/process`);
    showToast(t("common.saved"));
    await loadReturns();
  } catch (err) { showToast(err.message, "error"); }
}

async function completeReturn(id) {
  try {
    await api.post(`/api/procurement/returns/${id}/complete`);
    showToast(t("common.saved"));
    await loadReturns();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== Supplier Invoice Items Editor =====
function supplierItemOptionsHTML(selectedId) {
  const itemLabel = typeof invT !== "undefined" ? invT("inventory.itemName") : "Item";
  const whLabel = typeof invT !== "undefined" ? invT("inventory.warehouse") : "Warehouse";
  const expLabel = typeof invT !== "undefined" ? invT("inventory.expiryDate") : "Expiry";
  return {
    itemLabel, whLabel, expLabel,
    opts: allItems.map((i) => {
      const label = `${i.code ? i.code + " - " : ""}${i.name}`;
      return `<option value="${i.id}" ${String(i.id) === String(selectedId) ? "selected" : ""}>${escapeHtml(label)}</option>`;
    }).join(""),
    whOpts: allWarehouses.map((w) =>
      `<option value="${w.id}" ${String(w.id) === String(selectedId) ? "selected" : ""}>${escapeHtml(w.name)}</option>`
    ).join(""),
  };
}

function supplierInvoiceItemRowHTML(it) {
  it = it || {};
  const m = supplierItemOptionsHTML(it.item_id);
  const row = document.createElement("div");
  row.className = "item-row supplier-item-row";
  row.innerHTML = `
    <select class="item-item-id" title="${m.itemLabel}"><option value="">—</option>${m.opts}</select>
    <select class="item-warehouse-id" title="${m.whLabel}"><option value="">—</option>${m.whOpts}</select>
    <input type="text" class="item-desc" placeholder="${t("procurement.itemDescPlaceholder")}" value="${escapeHtml(it.description || "")}">
    <input type="number" class="item-qty" min="0" step="0.01" value="${it.quantity != null ? it.quantity : 1}" title="${t("procurement.itemQtyCol")}">
    <input type="number" class="item-price" min="0" step="0.01" value="${it.unit_price || ""}" placeholder="0.00" title="${t("procurement.itemPriceCol")}">
    <input type="number" class="item-tax" min="0" step="0.01" value="${it.tax_rate != null ? it.tax_rate : defaultTaxRate}" title="${t("procurement.itemTaxCol")}">
    <input type="date" class="item-expiry" value="${escapeHtml(it.expiry_date || "")}" title="${m.expLabel}">
    <span class="item-line-total" title="${t("procurement.itemTotalCol")}">0.00</span>
    <button type="button" class="btn btn-danger btn-sm item-remove" onclick="removeSupplierInvoiceItem(this)" title="${t("procurement.removeItem")}">✕</button>`;
  row.querySelectorAll("input").forEach((el) => el.addEventListener("input", recalcSupplierInvoiceItems));
  row.querySelector(".item-item-id").addEventListener("change", (e) => {
    const itemId = e.target.value;
    const item = allItems.find((i) => String(i.id) === String(itemId));
    if (item) {
      const desc = row.querySelector(".item-desc");
      if (!desc.value) desc.value = item.name;
      const price = row.querySelector(".item-price");
      if (!price.value) price.value = item.cost_price != null ? item.cost_price : "";
    }
  });
  recalcSupplierInvoiceItems();
  return row;
}

function addSupplierInvoiceItem() {
  document.getElementById("supplier-invoice-items").appendChild(supplierInvoiceItemRowHTML());
  recalcSupplierInvoiceItems();
}

function removeSupplierInvoiceItem(btn) {
  const editor = document.getElementById("supplier-invoice-items");
  if (editor.children.length <= 1) {
    editor.innerHTML = "";
    editor.appendChild(supplierInvoiceItemRowHTML());
    return;
  }
  btn.closest(".item-row").remove();
  recalcSupplierInvoiceItems();
}

function collectSupplierInvoiceItems() {
  const rows = document.querySelectorAll("#supplier-invoice-items .item-row");
  const items = [];
  rows.forEach((row) => {
    const desc = row.querySelector(".item-desc").value.trim();
    if (!desc) return;
    items.push({
      item_id: parseInt(row.querySelector(".item-item-id").value) || null,
      warehouse_id: parseInt(row.querySelector(".item-warehouse-id").value) || null,
      description: desc,
      quantity: parseFloat(row.querySelector(".item-qty").value) || 0,
      unit_price: parseFloat(row.querySelector(".item-price").value) || 0,
      tax_rate: parseFloat(row.querySelector(".item-tax").value) || 0,
      expiry_date: row.querySelector(".item-expiry").value || null,
    });
  });
  return items;
}

function recalcSupplierInvoiceItems() {
  const rows = document.querySelectorAll("#supplier-invoice-items .item-row");
  let grand = 0;
  rows.forEach((row) => {
    const qty = parseFloat(row.querySelector(".item-qty").value) || 0;
    const price = parseFloat(row.querySelector(".item-price").value) || 0;
    const tax = parseFloat(row.querySelector(".item-tax").value) || 0;
    const total = qty * price * (1 + tax / 100);
    row.querySelector(".item-line-total").textContent = formatMoney(total);
    grand += total;
  });
  const totalInput = document.getElementById("supplier-invoice-total");
  if (!totalInput.disabled) totalInput.value = grand ? grand.toFixed(2) : "";
}

function setSupplierInvoiceTotalDisabled() {
  const totalInput = document.getElementById("supplier-invoice-total");
  totalInput.disabled = collectSupplierInvoiceItems().length > 0;
}

// ===== Supplier Invoice Modal =====
async function ensureInventoryData() {
  try {
    if (!allItems.length) {
      const d = await api.get("/api/inventory/items");
      if (d && d.items && Array.isArray(d.items)) allItems = d.items;
    }
    if (!allWarehouses.length) {
      const d = await api.get("/api/inventory/warehouses");
      if (d && d.warehouses && Array.isArray(d.warehouses)) allWarehouses = d.warehouses;
    }
  } catch (err) {
    console.error("Inventory data load failed:", err);
  }
}

async function openSupplierInvoiceModal() {
  await ensureInventoryData();
  document.getElementById("supplier-invoice-id").value = "";
  document.getElementById("supplier-invoice-number").value = "";
  document.getElementById("supplier-invoice-supplier").value = "";
  document.getElementById("supplier-invoice-project").value = "";
  document.getElementById("supplier-invoice-issue-date").value = "";
  document.getElementById("supplier-invoice-due-date").value = "";
  document.getElementById("supplier-invoice-description").value = "";
  document.getElementById("supplier-invoice-total").value = "";
  document.getElementById("supplier-invoice-total").disabled = false;
  document.getElementById("supplier-invoice-paid").value = 0;
  document.getElementById("supplier-invoice-status").value = "pending";
  document.getElementById("supplier-invoice-items").innerHTML = "";
  document.getElementById("supplier-invoice-items").appendChild(supplierInvoiceItemRowHTML());
  populateSupplierSelect();
  populateProjectSelect();
  fillFinancialYearSelect("supplier-invoice-year");
  document.getElementById("supplier-invoice-modal").classList.add("active");
}

async function editSupplierInvoice(inv) {
  await ensureInventoryData();
  document.getElementById("supplier-invoice-id").value = inv.id;
  document.getElementById("supplier-invoice-number").value = inv.invoice_number || "";
  document.getElementById("supplier-invoice-supplier").value = inv.supplier_id || "";
  document.getElementById("supplier-invoice-project").value = inv.project_id || "";
  document.getElementById("supplier-invoice-issue-date").value = inv.issue_date || "";
  document.getElementById("supplier-invoice-due-date").value = inv.due_date || "";
  document.getElementById("supplier-invoice-description").value = inv.description || "";
  document.getElementById("supplier-invoice-total").value = inv.amount || "";
  document.getElementById("supplier-invoice-paid").value = inv.paid_amount || 0;
  document.getElementById("supplier-invoice-status").value = inv.status || "pending";
  const items = (inv.items && inv.items.length) ? inv.items : [null];
  document.getElementById("supplier-invoice-items").innerHTML = "";
  items.forEach((it) => document.getElementById("supplier-invoice-items").appendChild(supplierInvoiceItemRowHTML(it)));
  setSupplierInvoiceTotalDisabled();
  populateSupplierSelect();
  populateProjectSelect();
  document.getElementById("supplier-invoice-supplier").value = inv.supplier_id || "";
  document.getElementById("supplier-invoice-project").value = inv.project_id || "";
  fillFinancialYearSelect("supplier-invoice-year", inv.financial_year_id);
  document.getElementById("supplier-invoice-modal").classList.add("active");
}

function closeSupplierInvoiceModal() {
  document.getElementById("supplier-invoice-modal").classList.remove("active");
}

async function saveSupplierInvoice() {
  const id = document.getElementById("supplier-invoice-id").value;
  const items = collectSupplierInvoiceItems();
  const body = {
    invoice_number: document.getElementById("supplier-invoice-number").value,
    supplier_id: parseInt(document.getElementById("supplier-invoice-supplier").value) || null,
    project_id: parseInt(document.getElementById("supplier-invoice-project").value) || null,
    issue_date: document.getElementById("supplier-invoice-issue-date").value,
    due_date: document.getElementById("supplier-invoice-due-date").value,
    description: document.getElementById("supplier-invoice-description").value,
    status: document.getElementById("supplier-invoice-status").value,
    paid_amount: parseFloat(document.getElementById("supplier-invoice-paid").value) || 0,
    financial_year_id: financialYearValue("supplier-invoice-year"),
  };
  if (items.length) body.items = items;
  else body.amount = parseFloat(document.getElementById("supplier-invoice-total").value) || 0;
  if (!body.invoice_number) { showToast(t("procurement.numberRequired"), "warning"); return; }
  if (!body.supplier_id) { showToast(t("procurement.supplierRequired"), "warning"); return; }
  const partial = items.find((i) => Boolean(i.item_id) !== Boolean(i.warehouse_id));
  if (partial) { showToast(t("procurement.itemWarehouseRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/procurement/supplier-invoices/${id}`, body);
    else await api.post("/api/procurement/supplier-invoices", body);
    showToast(t("common.saved"));
    closeSupplierInvoiceModal();
    await loadSupplierInvoices();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteSupplierInvoice(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/procurement/supplier-invoices/${id}`);
    showToast(t("common.deleted"));
    await loadSupplierInvoices();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== Supplier Modal =====
function openSupplierModal() {
  document.getElementById("supplier-modal-title").textContent = t("procurement.newSupplier");
  document.getElementById("supplier-id").value = "";
  ["supplier-company", "supplier-contact", "supplier-phone", "supplier-email"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("supplier-category").value = "";
  document.getElementById("supplier-modal").classList.add("active");
}

function editSupplier(s) {
  document.getElementById("supplier-modal-title").textContent = t("procurement.editSupplier");
  document.getElementById("supplier-id").value = s.id;
  document.getElementById("supplier-company").value = s.company_name || "";
  document.getElementById("supplier-contact").value = s.contact_name || "";
  document.getElementById("supplier-phone").value = s.phone || "";
  document.getElementById("supplier-email").value = s.email || "";
  document.getElementById("supplier-category").value = s.category || "";
  document.getElementById("supplier-modal").classList.add("active");
}

function closeSupplierModal() {
  document.getElementById("supplier-modal").classList.remove("active");
}

async function saveSupplier() {
  const id = document.getElementById("supplier-id").value;
  const body = {
    company_name: document.getElementById("supplier-company").value,
    contact_name: document.getElementById("supplier-contact").value,
    phone: document.getElementById("supplier-phone").value,
    email: document.getElementById("supplier-email").value,
    category: document.getElementById("supplier-category").value,
  };
  if (!body.company_name) { showToast(t("procurement.companyRequired"), "warning"); return; }

  try {
    if (id) await api.put(`/api/suppliers/${id}`, body);
    else await api.post("/api/suppliers", body);
    showToast(t("common.saved"));
    closeSupplierModal();
    allSuppliers = await api.get("/api/suppliers");
    renderSuppliers();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteSupplier(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/suppliers/${id}`);
    showToast(t("common.deleted"));
    allSuppliers = await api.get("/api/suppliers");
    renderSuppliers();
    renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== Window Exports =====
window.openPurchaseModal = openPurchaseModal;
window.closePurchaseModal = closePurchaseModal;
window.editPurchase = editPurchase;
window.deletePurchase = deletePurchase;
window.savePurchase = savePurchase;
window.addPoItem = addPoItem;
window.removePoItem = removePoItem;
window.openPRModal = openPRModal;
window.closePRModal = closePRModal;
window.editPR = editPR;
window.deletePR = deletePR;
window.savePR = savePR;
window.submitPR = submitPR;
window.approvePR = approvePR;
window.rejectPR = rejectPR;
window.convertPRToRFQ = convertPRToRFQ;
window.addPrItem = addPrItem;
window.removePrItem = removePrItem;
window.openRFQModal = openRFQModal;
window.closeRFQModal = closeRFQModal;
window.editRFQ = editRFQ;
window.deleteRFQ = deleteRFQ;
window.saveRFQ = saveRFQ;
window.sendRFQ = sendRFQ;
window.closeRFQ = closeRFQ;
window.addRfqItem = addRfqItem;
window.removeRfqItem = removeRfqItem;
window.openQuoteModal = openQuoteModal;
window.closeQuoteModal = closeQuoteModal;
window.saveQuote = saveQuote;
window.addQuoteItem = addQuoteItem;
window.removeQuoteItem = removeQuoteItem;
window.viewQuotes = viewQuotes;
window.editQuote = editQuote;
window.deleteQuote = deleteQuote;
window.selectWinner = selectWinner;
window.switchTab = switchTab;
window.loadComparison = loadComparison;
window.openReceivingModal = openReceivingModal;
window.closeReceivingModal = closeReceivingModal;
window.editReceiving = editReceiving;
window.deleteReceiving = deleteReceiving;
window.saveReceiving = saveReceiving;
window.addReceivingItem = addReceivingItem;
window.removeReceivingItem = removeReceivingItem;
window.openReturnModal = openReturnModal;
window.closeReturnModal = closeReturnModal;
window.editReturn = editReturn;
window.deleteReturn = deleteReturn;
window.saveReturn = saveReturn;
window.processReturn = processReturn;
window.completeReturn = completeReturn;
window.addReturnItem = addReturnItem;
window.removeReturnItem = removeReturnItem;
window.openSupplierInvoiceModal = openSupplierInvoiceModal;
window.closeSupplierInvoiceModal = closeSupplierInvoiceModal;
window.editSupplierInvoice = editSupplierInvoice;
window.deleteSupplierInvoice = deleteSupplierInvoice;
window.saveSupplierInvoice = saveSupplierInvoice;
window.addSupplierInvoiceItem = addSupplierInvoiceItem;
window.removeSupplierInvoiceItem = removeSupplierInvoiceItem;
window.openSupplierModal = openSupplierModal;
window.closeSupplierModal = closeSupplierModal;
window.editSupplier = editSupplier;
window.deleteSupplier = deleteSupplier;
window.saveSupplier = saveSupplier;
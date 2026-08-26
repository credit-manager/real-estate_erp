let reportsData = { warehouses: [], categories: [] };
let reportsCurrent = "stock_value";

document.addEventListener("DOMContentLoaded", async () => {
  await loadReport();
});

async function loadReport() {
  try {
    const params = new URLSearchParams({ report: reportsCurrent });
    const wh = document.getElementById("reports-warehouse").value;
    if (wh) params.set("warehouse_id", wh);
    const cat = document.getElementById("reports-category").value;
    if (cat) params.set("category_id", cat);
    const month = document.getElementById("movements-month");
    if (month && month.value) params.set("month", month.value);
    const year = document.getElementById("movements-year");
    if (year && year.value) params.set("year", year.value);
    const data = await api.request(`/api/inventory/reports?${params.toString()}`);
    if (data.warehouses) {
      reportsData.warehouses = data.warehouses;
      fillReportsWarehouseSelect();
    }
    if (data.categories) {
      reportsData.categories = data.categories;
      fillReportsCategorySelect();
    }
    renderReport(data);
  } catch (err) { showToast(err.message, "error"); }
}

function fillReportsWarehouseSelect() {
  const sel = document.getElementById("reports-warehouse");
  const current = sel.value;
  sel.innerHTML = `<option value="">${invT("inventory.allWarehouses")}</option>`;
  reportsData.warehouses.forEach((w) => {
    const opt = document.createElement("option");
    opt.value = w.id;
    opt.textContent = w.name;
    sel.appendChild(opt);
  });
  sel.value = current;
}

function fillReportsCategorySelect() {
  const sel = document.getElementById("reports-category");
  const current = sel.value;
  const show = reportsCurrent === "stock_value" || reportsCurrent === "expiry";
  sel.style.display = show ? "" : "none";
  if (!show) return;
  sel.innerHTML = `<option value="">${invT("inventory.allCategories")}</option>`;
  reportsData.categories.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    sel.appendChild(opt);
  });
  sel.value = current;
}

function switchReport(name) {
  reportsCurrent = name;
  document.querySelectorAll(".tabs .chip").forEach((b) => b.classList.remove("chip-active"));
  const tab = document.getElementById(`tab-${name}`);
  if (tab) tab.classList.add("chip-active");
  ["stock_value", "movements", "expiry", "suppliers"].forEach((p) => {
    const panel = document.getElementById(`panel-${p}`);
    if (panel) panel.style.display = p === name ? "" : "none";
  });
  const monthPanel = document.querySelector("#panel-movements .report-filters");
  if (monthPanel) monthPanel.style.display = name === "movements" ? "" : "none";
  fillReportsCategorySelect();
  loadReport();
}

function renderReport(data) {
  if (data.report === "stock_value") renderStockValue(data);
  else if (data.report === "movements") renderMovements(data);
  else if (data.report === "expiry") renderExpiry(data);
  else if (data.report === "suppliers") renderSuppliers(data);
}

function renderStockValue(data) {
  document.getElementById("stat-total-value").textContent = formatMoney(data.summary.total_value);
  document.getElementById("stat-items-count").textContent = formatNumber(data.summary.items_count);
  document.getElementById("stat-total-cost").textContent = formatMoney(data.summary.total_cost);
  document.getElementById("stock-value-count").textContent = data.rows.length;
  const tbody = document.getElementById("stock-value-table");
  tbody.innerHTML = "";
  data.rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(r.item_code || "")}</td>
      <td>${escapeHtml(r.item_name || "")}</td>
      <td>${escapeHtml(r.category_name || "")}</td>
      <td>${escapeHtml(r.warehouse_name || "")}</td>
      <td>${formatNumber(r.quantity)} ${escapeHtml(r.unit_name || "")}</td>
      <td>${formatMoney(r.avg_cost)}</td>
      <td><strong>${formatMoney(r.value)}</strong></td>`;
    tbody.appendChild(tr);
  });
  document.getElementById("stock-value-empty").style.display = data.rows.length ? "none" : "";
}

function renderMovements(data) {
  document.getElementById("movements-count").textContent = data.rows.length;
  const tbody = document.getElementById("movements-table");
  tbody.innerHTML = "";
  data.rows.forEach((m) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(formatDate(m.created_at) || "")}</td>
      <td>${escapeHtml(m.item_code || "")}</td>
      <td>${escapeHtml(m.item_name || "")}</td>
      <td>${escapeHtml(m.warehouse_name || "")}</td>
      <td>${movementTypeLabel(m.movement_type)}</td>
      <td>${formatNumber(m.quantity)}</td>
      <td>${escapeHtml(m.batch_number || "")}</td>
      <td>${escapeHtml(m.notes || "")}</td>`;
    tbody.appendChild(tr);
  });
  document.getElementById("movements-empty").style.display = data.rows.length ? "none" : "";
}

function renderExpiry(data) {
  document.getElementById("expiry-count").textContent = data.rows.length;
  const tbody = document.getElementById("expiry-table");
  tbody.innerHTML = "";
  data.rows.forEach((b) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(b.batch_number || "")}</td>
      <td>${escapeHtml(b.item_code || "")}</td>
      <td>${escapeHtml(b.item_name || "")}</td>
      <td>${escapeHtml(b.warehouse_name || "")}</td>
      <td>${formatNumber(b.quantity)}</td>
      <td>${escapeHtml(formatDate(b.expiry_date) || "")}</td>
      <td>${escapeHtml(formatDate(b.received_date) || "")}</td>
      <td>${expiryBadge(b.status)}</td>`;
    tbody.appendChild(tr);
  });
  document.getElementById("expiry-empty").style.display = data.rows.length ? "none" : "";
}

function expiryBadge(status) {
  if (status === "expired") return `<span class="badge badge-danger">${invT("inventory.expired")}</span>`;
  if (status === "expiring") return `<span class="badge badge-warning">${invT("inventory.expiringSoon")}</span>`;
  return `<span class="badge badge-success">${invT("inventory.valid")}</span>`;
}

function renderSuppliers(data) {
  document.getElementById("suppliers-count").textContent = data.rows.length;
  const tbody = document.getElementById("suppliers-table");
  tbody.innerHTML = "";
  data.rows.forEach((s) => {
    const tr = document.createElement("tr");
    const top = (s.items || []).slice(0, 3).map((i) => `${i.item_name} (${formatNumber(i.qty)})`).join("، ") || "—";
    tr.innerHTML = `<td><strong>${escapeHtml(s.company_name || "")}</strong></td>
      <td>${escapeHtml(s.contact_name || "")}</td>
      <td>${escapeHtml(s.phone || "")}</td>
      <td><strong>${formatMoney(s.total_purchased)}</strong></td>
      <td>${escapeHtml(top)}</td>`;
    tbody.appendChild(tr);
  });
  document.getElementById("suppliers-empty").style.display = data.rows.length ? "none" : "";
}

function movementTypeLabel(type) {
  const map = {
    in: invT("inventory.moveType.in"),
    out: invT("inventory.moveType.out"),
    transfer_in: invT("inventory.moveType.transfer_in"),
    transfer_out: invT("inventory.moveType.transfer_out"),
    adjust: invT("inventory.moveType.adjust"),
    stocktake: invT("inventory.moveType.stocktake"),
    sale: invT("inventory.moveType.sale"),
    purchase: invT("inventory.moveType.purchase"),
  };
  return map[type] || type;
}

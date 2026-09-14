let stockData = [];
let lowStockData = [];
let movementsData = [];
let stockWarehouses = [];

async function loadStockPage() {
  try {
    const whRes = await api.get("/api/inventory/warehouses");
    stockWarehouses = whRes.warehouses || [];
    const sel = document.getElementById("stock-warehouse");
    sel.innerHTML = `<option value="">${invT("inventory.warehouses")}</option>` +
      stockWarehouses.map((w) => `<option value="${w.id}">${escapeHtml(w.name)}</option>`).join("");
    await Promise.all([loadStock(), loadLowStock(), loadMovements()]);
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function loadStock() {
  const whId = document.getElementById("stock-warehouse").value;
  try {
    const res = await api.get(`/api/inventory/stock${whId ? "?warehouse_id=" + whId : ""}`);
    stockData = res.stock || [];
    renderStock();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.loadStock = loadStock;

async function loadLowStock() {
  try {
    const res = await api.get("/api/inventory/stock/low");
    lowStockData = res.items || [];
    renderLowStock();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function loadMovements() {
  try {
    const res = await api.get("/api/inventory/movements");
    movementsData = res.movements || [];
    renderMovements();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function switchStockTab(tab) {
  ["balance", "low", "moves"].forEach((t) => {
    document.getElementById("tab-" + t).classList.toggle("chip-active", t === tab);
    document.getElementById("panel-" + t).style.display = t === tab ? "" : "none";
  });
}
window.switchStockTab = switchStockTab;

function renderStock() {
  const q = (document.getElementById("stock-search").value || "").trim().toLowerCase();
  const list = q ? stockData.filter((s) =>
    (s.item_code + " " + s.item_name + " " + (s.warehouse_name || "")).toLowerCase().includes(q)) : stockData;
  const tbody = document.getElementById("stock-table");
  document.getElementById("stock-count").textContent = `(${list.length})`;
  document.getElementById("tab-balance-count").textContent = `(${list.length})`;
  document.getElementById("stock-empty").style.display = list.length ? "none" : "";
  tbody.innerHTML = list.map((s) => {
    const low = s.reorder_level > 0 && s.quantity <= s.reorder_level;
    return `
    <tr>
      <td><b>${escapeHtml(s.item_code)}</b></td>
      <td>${escapeHtml(s.item_name)}</td>
      <td>${escapeHtml(s.warehouse_name || "—")}</td>
      <td>${escapeHtml(s.unit_name || "—")}</td>
      <td><b>${formatNumber(s.quantity)}</b></td>
      <td>${formatNumber(s.reorder_level)}</td>
      <td>${low
        ? `<span class="badge badge-danger">${invT("inventory.lowStockItems")}</span>`
        : `<span class="badge badge-success">${invT("inventory.inStock")}</span>`}</td>
    </tr>`;
  }).join("");
}
window.renderStock = renderStock;

function renderLowStock() {
  const tbody = document.getElementById("low-table");
  document.getElementById("low-count").textContent = `(${lowStockData.length})`;
  document.getElementById("tab-low-count").textContent = `(${lowStockData.length})`;
  document.getElementById("low-empty").style.display = lowStockData.length ? "none" : "";
  tbody.innerHTML = lowStockData.map((i) => `
    <tr>
      <td><b>${escapeHtml(i.code)}</b></td>
      <td>${escapeHtml(i.name)}</td>
      <td>${escapeHtml(i.category_name || "—")}</td>
      <td>${escapeHtml(i.unit_name || "—")}</td>
      <td style="color:var(--danger);font-weight:600;">${formatNumber(i.quantity)}</td>
      <td>${formatNumber(i.reorder_level)}</td>
    </tr>
  `).join("");
}

function moveTypeLabel(type) {
  const key = "inventory.moveType." + (type || "adjust");
  return invT(key);
}

function renderMovements() {
  const tbody = document.getElementById("moves-table");
  document.getElementById("moves-empty").style.display = movementsData.length ? "none" : "";
  tbody.innerHTML = movementsData.map((m) => `
    <tr>
      <td>${formatDate(m.created_at)}</td>
      <td><span class="badge badge-secondary">${escapeHtml(moveTypeLabel(m.movement_type))}</span></td>
      <td>${escapeHtml(m.item_name || "—")}</td>
      <td>${escapeHtml(m.warehouse_name || "—")}</td>
      <td><b>${formatNumber(m.quantity)}</b></td>
      <td>${escapeHtml(m.notes || "—")}</td>
    </tr>
  `).join("");
}

loadStockPage();

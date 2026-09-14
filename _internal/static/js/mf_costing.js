/* ============================================================
   Manufacturing - Production Costing
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

async function loadData() {
  try {
    const data = await api.get("/api/mf/costing");
    const orders = data.orders || [];
    const totals = data.totals || {};
    renderKPI(totals);
    renderOrders(orders);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderKPI(t) {
  document.getElementById("kpi-material").textContent = formatNumber(t.material);
  document.getElementById("kpi-operation").textContent = formatNumber(t.operation);
  document.getElementById("kpi-labor").textContent = formatNumber(t.labor);
  document.getElementById("kpi-overhead").textContent = formatNumber(t.overhead);
  document.getElementById("kpi-total").textContent = formatNumber(t.total);
}

function renderOrders(orders) {
  document.getElementById("costing-empty").style.display = orders.length ? "none" : "block";
  document.getElementById("costing-table").innerHTML = orders.map((o) => {
    const c = o.costing || {};
    const variance = c.variance != null ? c.variance : 0;
    const varianceHtml = `<span style="color:${variance > 0 ? "var(--danger)" : "var(--success)"};">${formatNumber(variance)}</span>`;
    return `<tr>
      <td><div class="cell-main">${escapeHtml(o.order_number)}</div><div class="table-sub">${escapeHtml(o.bom_name || "")}</div></td>
      <td>${escapeHtml(o.product_name || "—")}</td>
      <td>${formatNumber(c.material_actual)}</td>
      <td>${formatNumber(c.operation_cost)}</td>
      <td>${formatNumber(c.labor)}</td>
      <td>${formatNumber(c.overhead)}</td>
      <td><strong>${formatNumber(c.total)}</strong></td>
      <td>${formatNumber(c.unit_cost)}</td>
      <td>${varianceHtml}</td>
    </tr>`;
  }).join("");
}

document.addEventListener("DOMContentLoaded", loadData);

/* ============================================================
   Manufacturing - Production Tracking
   ============================================================ */

const CT = window.T || {};

function cct(key) {
  if (CT[key] !== undefined && CT[key] !== null) return CT[key];
  return key;
}

async function loadData() {
  try {
    const data = await api.get("/api/mf/tracking");
    const orders = data.orders || [];
    const totals = data.totals || {};
    renderKPI(totals);
    renderOrders(orders);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderKPI(t) {
  document.getElementById("kpi-total").textContent = t.total || 0;
  document.getElementById("kpi-planned").textContent = t.planned || 0;
  document.getElementById("kpi-in-progress").textContent = t.in_progress || 0;
  document.getElementById("kpi-completed").textContent = t.completed || 0;
  document.getElementById("kpi-cancelled").textContent = t.cancelled || 0;
  document.getElementById("kpi-produced").textContent = formatNumber(t.total_produced);
}

function statusBadge(status) {
  const map = {
    planned: "badge-neutral",
    in_progress: "badge-primary",
    completed: "badge-success",
    cancelled: "badge-danger",
  };
  return `<span class="badge ${map[status] || "badge-neutral"}">${cct("mf.status." + status)}</span>`;
}

function progressBar(pct) {
  const p = Math.max(0, Math.min(100, Number(pct) || 0));
  return `<div style="width:120px;height:8px;background:var(--muted);border-radius:99px;overflow:hidden;">
    <div style="width:${p}%;height:100%;background:${p >= 100 ? "var(--success)" : "var(--primary)"};border-radius:99px;"></div>
  </div><div class="table-sub">${p}%</div>`;
}

function renderOrders(orders) {
  document.getElementById("tracking-empty").style.display = orders.length ? "none" : "block";
  document.getElementById("tracking-table").innerHTML = orders.map((o) => {
    return `<tr>
      <td><div class="cell-main">${escapeHtml(o.order_number)}</div><div class="table-sub">${escapeHtml(o.bom_name || "")}</div></td>
      <td><div class="cell-main">${escapeHtml(o.product_name || "—")}</div><div class="table-sub">${escapeHtml(o.warehouse_name || "")}</div></td>
      <td>${formatNumber(o.quantity)}</td>
      <td>${formatNumber(o.produced_qty)}</td>
      <td>${progressBar(o.progress)}</td>
      <td>${statusBadge(o.status)}</td>
      <td>${escapeHtml(o.start_date || "—")}</td>
      <td>${escapeHtml(o.due_date || "—")}</td>
    </tr>`;
  }).join("");
}

document.addEventListener("DOMContentLoaded", loadData);

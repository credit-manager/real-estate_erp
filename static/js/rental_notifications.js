/* ============================================================
   Rental Notifications JavaScript
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  loadNotifications();
});

async function loadNotifications() {
  const container = document.getElementById("notifications-list");
  container.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  try {
    const items = await api.get("/api/rentals/notifications");
    renderNotifications(items);
    renderNotificationSummary(items);
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">🔔</div>${t("rentals.notificationsError")}</div>`;
  }
}

function notifIcon(type) {
  if (type === "expired") return "⛔";
  if (type === "expiring") return "⏳";
  return "💰";
}

function renderNotifications(items) {
  const container = document.getElementById("notifications-list");
  if (!items.length) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">🔔</div>${t("rentals.noNotifications")}</div>`;
    return;
  }
  container.innerHTML = items.map((n) => {
    const detail =
      n.type === "overdue"
        ? `<div class="table-sub">${t("rentals.dueLabel")}: ${formatMoney(n.due)} — ${t("rentals.paidLabel")}: ${formatMoney(n.paid)} — ${t("rentals.balanceLabel")}: <strong style="color:var(--danger, #dc2626);">${formatMoney(n.balance)}</strong></div>`
        : n.type === "expiring"
          ? `<div class="table-sub">${t("rentals.daysLeft")}: <strong>${n.days_left}</strong></div>`
          : `<div class="table-sub">${t("rentals.daysOverdue")}: <strong>${n.days_overdue}</strong></div>`;
    return `
      <div class="notif-item" data-severity="${n.severity}" style="display:flex; gap:12px; padding:14px 16px; border-bottom:1px solid var(--border); align-items:flex-start;">
        <div style="font-size:22px;">${notifIcon(n.type)}</div>
        <div style="flex:1;">
          <div><strong>${t(n.title)}</strong></div>
          <div class="table-sub">${t(n.message)}</div>
          ${detail}
          <div class="table-sub" style="margin-top:4px;">
            ${escapeHtml(n.contract_number || "")}${n.customer_name ? " — " + escapeHtml(n.customer_name) : ""}${n.unit_code ? " — " + escapeHtml(n.unit_code) : ""}
          </div>
        </div>
        <div style="display:flex; gap:6px; flex-shrink:0;">
          <a class="btn btn-outline btn-sm" href="/rentals" onclick="location.href='/rentals'">${t("rentals.viewContract")}</a>
        </div>
      </div>`;
  }).join("");
}

function renderNotificationSummary(items) {
  animateCount(document.getElementById("notif-danger"), items.filter((x) => x.severity === "danger").length, formatNumber);
  animateCount(document.getElementById("notif-warning"), items.filter((x) => x.severity === "warning").length, formatNumber);
  animateCount(document.getElementById("notif-info"), items.filter((x) => x.severity === "info").length, formatNumber);
}

function refreshNotifications() {
  loadNotifications();
}

window.refreshNotifications = refreshNotifications;

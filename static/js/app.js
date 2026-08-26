/* ============================================================
   Dynamic Pro ERP - Main JavaScript
   ============================================================ */

// ===== i18n =====
const LANG = window.LANG || "ar";

function t(key) {
  const dict = window.T || {};
  if (dict[key] !== undefined && dict[key] !== null) return dict[key];
  return key;
}

const VALUE_LABELS = {
  "الهندسة": "val.engineering",
  "المبيعات": "val.sales",
  "المالية": "val.finance",
  "الموارد البشرية": "val.hr",
  "المخازن": "val.warehouses",
  "تقنية المعلومات": "val.it",
  "شقة": "val.apartment",
  "فيلا": "val.villa",
  "بنتهاوس": "val.penthouse",
  "محل": "val.shop",
  "مواد بناء": "val.building_materials",
  "معدات": "val.equipment",
  "مقاول": "val.contractor",
  "خدمات": "val.services",
};

function tv(value) {
  const key = VALUE_LABELS[value];
  return key ? t(key) : value;
}

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function approvalBadge(status) {
  if (!status || status === "not_required") return "";
  const map = {
    pending: { cls: "badge-warning", key: "workflow.badgePending" },
    approved: { cls: "badge-success", key: "workflow.badgeApproved" },
    rejected: { cls: "badge-danger", key: "workflow.badgeRejected" },
  };
  const m = map[status];
  if (!m) return "";
  return `<span class="badge ${m.cls}">${t(m.key)}</span>`;
}

function setLanguage(lang) {
  const options = { method: "POST" };
  if (window.CSRF_TOKEN) options.headers = { "X-CSRF-Token": window.CSRF_TOKEN };
  fetch("/api/language/" + lang, options).then(() => {
    window.location.reload();
  });
}

// ===== Permission helper (server-side RBAC mirror) =====
function canAction(module, action) {
  const p = window.PERMS || {};
  return !!(p[module] && p[module].includes(action));
}

// ===== Helper: API calls =====
const api = {  async request(url, method = "GET", body = null) {
    const options = { method, headers: { "Content-Type": "application/json" } };
    if (method !== "GET" && method !== "HEAD" && window.CSRF_TOKEN) {
      options.headers["X-CSRF-Token"] = window.CSRF_TOKEN;
    }
    if (body) options.body = JSON.stringify(body);

    const res = await fetch(url, options);
    if (res.status === 401) {
      window.location.href = "/login";
      throw new Error(t("common.notLoggedIn"));
    }
    const data = await res.json();
    if (!res.ok && data.message) {
      if (data.error_key && t(data.error_key) !== data.error_key) {
        throw new Error(t(data.error_key));
      }
      throw new Error(data.message);
    }
    return data;
  },

  get: (url) => api.request(url),
  post: (url, body) => api.request(url, "POST", body),
  put: (url, body) => api.request(url, "PUT", body),
  delete: (url) => api.request(url, "DELETE"),
};

// ===== Toast notifications =====
function showToast(message, type = "success") {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ===== Format helpers (language aware) =====
const LOCALE = LANG === "ar" ? "ar-EG" : "en-US";

const APP_SETTINGS = window.APP_SETTINGS || {};
const DECIMALS = (() => {
  const v = parseInt(APP_SETTINGS.number_decimals, 10);
  return Number.isFinite(v) && v >= 0 && v <= 3 ? v : 2;
})();
const DATE_FORMAT = APP_SETTINGS.date_format || "dd/mm/yyyy";

function formatNumber(num) {
  const n = num || 0;
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: 0,
    maximumFractionDigits: DECIMALS,
  }).format(n);
}

function formatMoney(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  const n = num || 0;
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: DECIMALS,
    maximumFractionDigits: DECIMALS,
  }).format(n);
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  let d;
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [y, m, day] = dateStr.split("-").map(Number);
    d = new Date(y, m - 1, day);
  } else {
    d = new Date(dateStr);
  }
  if (isNaN(d.getTime())) return "—";
  const y = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  if (DATE_FORMAT === "yyyy-mm-dd") return `${y}-${mm}-${dd}`;
  return `${dd}/${mm}/${y}`;
}

// ===== CSV export =====
function exportCSV(filename, headers, rows) {
  const esc = (v) => {
    const s = String(v == null ? "" : v);
    return /[",\n\r\u060C\u061B]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const content = [headers].concat(rows).map((r) => r.map(esc).join(",")).join("\r\n");
  const blob = new Blob(["\uFEFF" + content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ===== PDF download helper =====
function downloadPDF(url) {
  // Desktop app: save via native dialog. Browser fallback: anchor download.
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_pdf) {
    const m = url.match(/\/documents\/(invoice|po|contract|financial-year)\/(\d+)\/pdf/);
    if (m) {
      pywebview.api.save_pdf(m[1], parseInt(m[2], 10), LANG || "ar").then((res) => {
        if (res && res.ok) showToast(t("doc.downloadDone"), "success");
        else if (res && !res.cancelled) showToast(t("doc.downloadFailed") + (res.error ? " (" + res.error + ")" : ""), "error");
      });
      return;
    }
  }
  const a = document.createElement("a");
  a.href = url;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ===== Status label maps =====
const STATUS_LABELS = {
  active: t("status.active"),
  finishing: t("status.finishing"),
  completed: t("status.completed"),
  suspended: t("status.suspended"),
  available: t("status.available"),
  reserved: t("status.reserved"),
  sold: t("status.sold"),
  rented: t("status.rented"),
  pending: t("status.pending"),
  approved: t("status.approved"),
  delivered: t("status.delivered"),
  cancelled: t("status.cancelled"),
  paid: t("status.paid"),
  partial: t("status.partial"),
  overdue: t("status.overdue"),
  on_leave: t("status.on_leave"),
  terminated: t("status.terminated"),
  expired: t("status.expired"),
  individual: t("status.individual"),
  company: t("status.company"),
  high: t("status.high"),
  medium: t("status.medium"),
  low: t("status.low"),
};

function statusBadge(status) {
  const map = {
    active: "badge-success",
    completed: "badge-primary",
    available: "badge-success",
    delivered: "badge-success",
    paid: "badge-success",
    finishing: "badge-warning",
    reserved: "badge-warning",
    pending: "badge-warning",
    partial: "badge-warning",
    on_leave: "badge-warning",
    sold: "badge-info",
    approved: "badge-info",
    rented: "badge-neutral",
    overdue: "badge-danger",
    suspended: "badge-danger",
    cancelled: "badge-danger",
    terminated: "badge-danger",
    expired: "badge-danger",
  };
  const cls = map[status] || "badge-neutral";
  return `<span class="badge ${cls}">${STATUS_LABELS[status] || status}</span>`;
}

// ===== Theme =====
function getTheme() {
  try { return localStorage.getItem("dp-theme") || "light"; } catch (e) { return "light"; }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("dp-theme", theme); } catch (e) {}
}

// Sync toggle icon/tooltip with the actual (client-side) theme
function syncThemeIcons() {
  const dark = getTheme() === "dark";
  document.querySelectorAll(".theme-toggle").forEach((btn) => {
    const darkIcon = btn.querySelector(".theme-icon-dark");
    const lightIcon = btn.querySelector(".theme-icon-light");
    if (darkIcon) darkIcon.style.display = dark ? "none" : "";
    if (lightIcon) lightIcon.style.display = dark ? "" : "none";
    btn.title = dark ? t("common.light") : t("common.dark");
  });
}

// ===== Load chart theme colors (from CSS variables) =====
function cssVar(name) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || null;
}

const chartColors = {
  olive: cssVar("--primary") || "#2563eb",
  sage: cssVar("--sky") || "#0ea5e9",
  brown: cssVar("--amber") || "#f59e0b",
  terracotta: cssVar("--red") || "#ef4444",
  clay: cssVar("--violet") || "#8b5cf6",
  moss: cssVar("--emerald") || "#10b981",
  sand: cssVar("--orange") || "#f97316",
  terra: cssVar("--cyan") || "#06b6d4",
};

// Apply theme-aware global Chart defaults
if (typeof Chart !== "undefined") {
  const dark = getTheme() === "dark";
  Chart.defaults.color = dark ? "#94a3b8" : "#64748b";
  Chart.defaults.borderColor = dark ? "rgba(148,163,184,0.15)" : "rgba(15,23,42,0.06)";
}

// ===== Animated counter =====
function animateCount(el, target, formatter, duration = 600) {
  if (!el) return;
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) { el.textContent = formatter(target); return; }
  const start = performance.now();
  function step(now) {
    const p = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = formatter(target * eased);
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ===== Sidebar toggle + lang toggle + date =====
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("sidebar-toggle");
  const close = document.getElementById("sidebar-close");
  const sidebar = document.getElementById("sidebar");

  if (toggle) {
    toggle.addEventListener("click", () => {
      if (window.innerWidth <= 768) sidebar.classList.toggle("open");
      else sidebar.classList.toggle("collapsed");
    });
  }
  if (close) close.addEventListener("click", () => sidebar.classList.remove("open"));

  const langToggle = document.getElementById("lang-toggle");
  if (langToggle) {
    langToggle.addEventListener("click", () => {
      setLanguage(LANG === "ar" ? "en" : "ar");
    });
  }

  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const next = getTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      window.location.reload();
    });
  }

  syncThemeIcons();

  // Highlight active nav item
  const page = document.body.dataset.page;
  if (page) {
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.page === page);
    });
  }

  // Sidebar groups (collapsible lists)
  const navGroups = document.querySelectorAll(".nav-group");
  const activeNavItem = document.querySelector(".nav-item.active");
  const activeNavGroup = activeNavItem ? activeNavItem.closest(".nav-group") : null;
  let navState = {};
  try { navState = JSON.parse(localStorage.getItem("dp-nav-groups") || "{}") || {}; } catch (e) {}

  const applyNavGroup = (group, open) => {
    group.classList.toggle("open", open);
    const btn = group.querySelector(".nav-group-btn");
    if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
  };

  navGroups.forEach((group) => {
    const key = group.dataset.group;
    const saved = navState[key];
    const isActive = group === activeNavGroup;
    applyNavGroup(group, saved === undefined ? isActive : (saved || isActive));

    const btn = group.querySelector(".nav-group-btn");
    if (btn) {
      btn.addEventListener("click", () => {
        const nowOpen = !group.classList.contains("open");
        applyNavGroup(group, nowOpen);
        navState[key] = nowOpen;
        try { localStorage.setItem("dp-nav-groups", JSON.stringify(navState)); } catch (e) {}
      });
    }
  });

  // Topbar date
  const dateEl = document.getElementById("topbar-date");
  if (dateEl) {
    dateEl.textContent = new Date().toLocaleDateString(LOCALE, {
      weekday: "long", year: "numeric", month: "long", day: "numeric",
    });
  }

  // Logout
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await fetch("/logout", { method: "POST" });
      window.location.href = "/login";
    });
  }
});

// ===== Global topbar search =====
(function initGlobalSearch() {
  var input = document.getElementById("global-search");
  if (!input) return;
  var dropdown = document.getElementById("search-dropdown");
  var groupLabels = {
    customers: t("common.groupCustomers"),
    suppliers: t("common.groupSuppliers"),
    projects: t("common.groupProjects"),
    units: t("common.groupUnits"),
    invoices: t("common.groupInvoices"),
    employees: t("common.groupEmployees"),
    rentals: t("common.groupRentals"),
  };
  var groupIcons = {
    customers: "\u{1F464}", suppliers: "\u{1F3ED}", projects: "\u{1F5C2}\u{FE0F}", units: "\u{1F3E0}",
    invoices: "\u{1F9FE}", employees: "\u{1F465}", rentals: "\u{1F511}",
  };
  var results = [];
  var timer = null;

  function render() {
    if (!input.value.trim()) { dropdown.hidden = true; return; }
    if (results.length === 0) {
      dropdown.innerHTML = '<div class="search-result-empty">' + t("common.noResults") + '</div>';
    } else {
      var seen = {};
      var html = "";
      for (var i = 0; i < results.length; i++) {
        var r = results[i];
        if (!seen[r.group]) {
          seen[r.group] = true;
          html += '<div class="search-result-group">' + (groupIcons[r.group] || "") + " " + (groupLabels[r.group] || r.group) + '</div>';
        }
        html += '<a class="search-result-item" href="' + r.href + '" data-query="' + escapeHtml(input.value) + '">' +
          '<div class="search-result-text">' + escapeHtml(r.text) + '</div>' +
          '<div class="search-result-sub">' + escapeHtml(r.subtext || "") + '</div></a>';
      }
      dropdown.innerHTML = html;
    }
    dropdown.hidden = false;
  }

  function doSearch(query) {
    fetch("/api/search?q=" + encodeURIComponent(query))
      .then(function (res) { return res.ok ? res.json() : []; })
      .then(function (data) { results = data; render(); })
      .catch(function () { results = []; render(); });
  }

  input.addEventListener("input", function () {
    clearTimeout(timer);
    var q = input.value.trim();
    if (!q) { dropdown.hidden = true; return; }
    dropdown.innerHTML = '<div class="search-result-empty">' + t("common.searching") + '</div>';
    dropdown.hidden = false;
    timer = setTimeout(function () { doSearch(q); }, 250);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && results.length) {
      window.location.href = results[0].href;
    } else if (e.key === "Escape") {
      dropdown.hidden = true;
      closeAiPanel();
      input.blur();
    }
  });

  input.addEventListener("focus", render);
  document.addEventListener("click", function (e) {
    var topbarSearch = document.getElementById("topbar-search");
    if (topbarSearch && !topbarSearch.contains(e.target)) {
      dropdown.hidden = true;
      closeAiPanel();
    }
  });

  // ── AI Panel ─────────────────────────────────────────────────
  var aiToggle = document.getElementById("search-ai-toggle");
  var aiPanel = document.getElementById("ai-search-panel");
  var aiInput = document.getElementById("ai-search-input");
  var aiSend = document.getElementById("ai-search-send");
  var aiResult = document.getElementById("ai-search-result");
  var voiceBtn = document.getElementById("search-voice-btn");

  function closeAiPanel() {
    if (aiPanel) aiPanel.hidden = true;
    if (aiToggle) aiToggle.classList.remove("active");
  }

  if (aiToggle && aiPanel) {
    aiToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      var isOpen = !aiPanel.hidden;
      if (isOpen) { closeAiPanel(); return; }
      dropdown.hidden = true;
      aiPanel.hidden = false;
      aiToggle.classList.add("active");
      if (aiInput) aiInput.focus();
    });
  }

  function renderAiResult(data) {
    if (!aiResult) return;
    if (!data || !data.success) {
      aiResult.innerHTML = '<div class="ai-result-card">' + escapeHtml(data && data.answer || t("common.noResults")) + '</div>';
      return;
    }
    var html = "";
    var ans = data.answer || "";
    var type = data.type || "";

    if (type === "count") {
      html = '<div class="ai-result-card"><h4>' + escapeHtml(ans) + '</h4><div style="font-size:28px;font-weight:700;color:var(--primary);">' + (data.count || 0) + '</div></div>';
    } else if (type === "sum") {
      html = '<div class="ai-result-card"><h4>' + escapeHtml(ans) + '</h4><div style="font-size:28px;font-weight:700;color:var(--primary);">' + formatCompact(data.total || 0) + '</div></div>';
    } else if (type === "search" || type === "sql") {
      var rows = data.data || [];
      var cols = data.columns || (rows.length ? Object.keys(rows[0]) : []);
      if (rows.length === 0) {
        html = '<div class="ai-result-card">' + escapeHtml(ans || t("common.noResults")) + '</div>';
      } else {
        html = '<div class="ai-result-card"><h4>' + escapeHtml(ans) + ' (' + rows.length + ')</h4><table><thead><tr>';
        for (var ci = 0; ci < cols.length; ci++) {
          html += '<th>' + escapeHtml(cols[ci]) + '</th>';
        }
        html += '</tr></thead><tbody>';
        for (var ri = 0; ri < rows.length && ri < 50; ri++) {
          html += '<tr>';
          for (var cj = 0; cj < cols.length; cj++) {
            html += '<td>' + escapeHtml(String(rows[ri][cols[cj]] != null ? rows[ri][cols[cj]] : "")) + '</td>';
          }
          html += '</tr>';
        }
        html += '</tbody></table></div>';
      }
    } else if (type === "dashboard") {
      var d = data.data || {};
      html = '<div class="ai-result-card"><h4>' + escapeHtml(ans || "Dashboard") + '</h4>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;">' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">الموظفون النشطون</div><div style="font-size:20px;font-weight:700;">' + (d.employees_active || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">العملاء</div><div style="font-size:20px;font-weight:700;">' + (d.customers_count || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">الفواتير</div><div style="font-size:20px;font-weight:700;">' + (d.invoices_count || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">أقساط متأخرة</div><div style="font-size:20px;font-weight:700;color:#ef4444;">' + (d.overdue_installments || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">الإيرادات</div><div style="font-size:20px;font-weight:700;color:#22c55e;">' + formatCompact(d.total_revenue || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">المستحقات</div><div style="font-size:20px;font-weight:700;color:#f59e0b;">' + formatCompact(d.total_receivable || 0) + '</div></div>' +
        '</div></div>';
    } else {
      html = '<div class="ai-result-card">' + escapeHtml(ans || "OK") + '</div>';
    }
    aiResult.innerHTML = html;
  }

  function askAI(question) {
    if (!question.trim()) return;
    aiResult.innerHTML = '<div class="ai-result-loading">' + t("common.aiThinking") + '</div>';
    fetch("/api/ai/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) { renderAiResult(data); })
      .catch(function () { renderAiResult({ success: false, answer: "خطأ في الاتصال بالذكاء الصناعي" }); });
  }

  if (aiSend && aiInput) {
    aiSend.addEventListener("click", function () { askAI(aiInput.value); });
    aiInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); askAI(aiInput.value); }
    });
  }

  // ── Voice Recognition ────────────────────────────────────────
  var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var recognition = null;

  function startVoice(targetBtn, onResult) {
    if (!SpeechRecognition) {
      alert(t("common.voiceNotSupported") || "المتصفح لا يدعم التعرف على الصوت. استخدم Chrome.");
      return;
    }
    if (recognition) { recognition.abort(); recognition = null; }
    recognition = new SpeechRecognition();
    recognition.lang = document.documentElement.lang === "ar" ? "ar-SA" : "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    targetBtn.classList.add("recording");
    recognition.onresult = function (ev) {
      var text = ev.results[0][0].transcript;
      targetBtn.classList.remove("recording");
      onResult(text);
    };
    recognition.onerror = function () { targetBtn.classList.remove("recording"); };
    recognition.onend = function () { targetBtn.classList.remove("recording"); };
    recognition.start();
  }

  if (voiceBtn) {
    voiceBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      startVoice(voiceBtn, function (text) { input.value = text; input.dispatchEvent(new Event("input")); });
    });
  }

  var aiVoiceBtn = document.getElementById("ai-voice-btn");
  if (aiVoiceBtn) {
    aiVoiceBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      startVoice(aiVoiceBtn, function (text) { if (aiInput) aiInput.value = text; askAI(text); });
    });
  }

  function formatCompact(n) {
    n = parseFloat(n) || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return n.toLocaleString(document.documentElement.lang === "ar" ? "ar-EG" : "en-US", { maximumFractionDigits: 2 });
  }
})();

// ===== Notifications =====
(function initNotifications() {
  const btn = document.getElementById("notif-btn");
  if (!btn) return;
  const panel = document.getElementById("notif-dropdown");
  const list = document.getElementById("notif-list");
  const badge = document.getElementById("notif-badge");
  let last = [];

  function render() {
    if (last.length === 0) {
      list.innerHTML = `<div class="notif-empty">${t("notifications.empty")}</div>`;
    } else {
      list.innerHTML = last.map((n) => `
        <a class="notif-item severity-${n.severity}" href="${n.href}">
          <div class="notif-item-title">${escapeHtml(n.title)}</div>
          <div class="notif-item-message">${escapeHtml(n.message)}</div>
        </a>`).join("");
    }
    badge.hidden = last.length === 0;
    badge.textContent = last.length > 9 ? "9+" : last.length;
  }

  function load() {
    fetch(`/api/notifications?lang=${encodeURIComponent(LANG)}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => { last = data; render(); })
      .catch(() => {});
  }

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const opening = panel.hidden;
    if (opening) load();
    panel.hidden = !opening;
  });

  document.addEventListener("click", (e) => {
    if (!panel.contains(e.target)) panel.hidden = true;
  });

  load();
  setInterval(load, 60000);
})();

// ===== Document number prefill (from general settings) =====
async function prefillDocNumber(inputEl, docType, fallbackPrefix) {
  if (!inputEl || inputEl.value) return;
  try {
    const res = await fetch(`/general-settings/api/next-number?type=${encodeURIComponent(docType)}`);
    const data = await res.json();
    if (data && data.success && data.number) {
      inputEl.value = data.number;
    } else {
      inputEl.value = fallbackPrefix;
    }
  } catch (e) {
    inputEl.value = fallbackPrefix;
  }
}
window.prefillDocNumber = prefillDocNumber;

// ===== Horizontal Navigation Bar (Landscape Mode) =====
(function initHorizontalNav() {
  const body = document.body;
  const hnav = document.getElementById('hnav');
  const layoutToggle = document.getElementById('layout-toggle');
  const indicator = document.getElementById('hnav-indicator');
  const scrollEl = document.getElementById('hnav-scroll');
  const page = body.dataset.page;

  if (!hnav || !layoutToggle) return;

  const saved = localStorage.getItem('dp-layout');
  if (saved === 'horizontal') body.classList.add('layout-horizontal');

  layoutToggle.addEventListener('click', () => {
    body.classList.toggle('layout-horizontal');
    const isH = body.classList.contains('layout-horizontal');
    localStorage.setItem('dp-layout', isH ? 'horizontal' : 'vertical');
    requestAnimationFrame(() => moveIndicator(getActiveHnavItem()));
  });

  if (page) {
    hnav.querySelectorAll('.hnav-item.has-dd').forEach(item => {
      if (item.querySelector('[data-page="' + page + '"]')) {
        item.classList.add('has-active');
        const activeChild = item.querySelector('[data-page="' + page + '"]');
        if (activeChild) activeChild.classList.add('active');
      }
    });
    const directLink = hnav.querySelector('.hnav-item.direct a[data-page="' + page + '"]');
    if (directLink) directLink.classList.add('active');
  }

  const openItems = new Set();

  function closeAll(except) {
    hnav.querySelectorAll('.hnav-item.open').forEach(item => {
      if (item !== except) {
        item.classList.remove('open');
        const t = item.querySelector('.hnav-trigger');
        if (t) t.setAttribute('aria-expanded', 'false');
        openItems.delete(item);
      }
    });
  }

  hnav.querySelectorAll('.hnav-item.has-dd').forEach(item => {
    const trigger = item.querySelector('.hnav-trigger');
    let closeTimer;

    function openDD() {
      clearTimeout(closeTimer);
      closeAll(item);
      item.classList.add('open');
      openItems.add(item);
      trigger.setAttribute('aria-expanded', 'true');
      moveIndicator(item);
    }

    function scheduleClose() {
      closeTimer = setTimeout(() => {
        item.classList.remove('open');
        openItems.delete(item);
        trigger.setAttribute('aria-expanded', 'false');
        moveIndicator(getActiveHnavItem());
      }, 250);
    }

    trigger.addEventListener('mouseenter', openDD);
    trigger.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      if (item.classList.contains('open')) {
        scheduleClose();
      } else {
        openDD();
      }
    });

    item.addEventListener('mouseleave', scheduleClose);
    item.addEventListener('mouseenter', () => {
      clearTimeout(closeTimer);
    });

    const dd = item.querySelector('.hnav-dd');
    if (dd) {
      dd.addEventListener('mouseenter', () => clearTimeout(closeTimer));
      dd.addEventListener('mouseleave', scheduleClose);
    }
  });

  document.addEventListener('click', e => {
    if (!hnav.contains(e.target)) {
      closeAll();
      moveIndicator(getActiveHnavItem());
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      closeAll();
      moveIndicator(getActiveHnavItem());
    }
  });

  function getActiveHnavItem() {
    return hnav.querySelector('.hnav-item.open') || hnav.querySelector('.hnav-item.has-active') || null;
  }

  function moveIndicator(target) {
    if (!indicator || !scrollEl || !body.classList.contains('layout-horizontal')) {
      if (indicator) indicator.style.opacity = '0';
      return;
    }
    if (!target) { indicator.style.opacity = '0'; return; }

    const sRect = scrollEl.getBoundingClientRect();
    const tRect = target.getBoundingClientRect();
    const isRtl = document.documentElement.dir === 'rtl';
    let left = isRtl ? (sRect.right - tRect.right) : (tRect.left - sRect.left);
    left += scrollEl.scrollLeft;

    indicator.style.left = left + 'px';
    indicator.style.width = tRect.width + 'px';
    indicator.style.opacity = '1';
  }

  hnav.querySelectorAll('.hnav-item').forEach(item => {
    item.addEventListener('mouseenter', () => moveIndicator(item));
    item.addEventListener('mouseleave', () => moveIndicator(getActiveHnavItem()));
  });

  scrollEl.addEventListener('scroll', () => moveIndicator(getActiveHnavItem()));
  window.addEventListener('resize', () => moveIndicator(getActiveHnavItem()));

  requestAnimationFrame(() => {
    setTimeout(() => moveIndicator(getActiveHnavItem()), 150);
  });
})();

// Password visibility toggle
(function initPasswordToggles() {
  document.querySelectorAll(".pw-toggle").forEach(function(btn) {
    btn.addEventListener("click", function() {
      var wrap = btn.closest(".pw-wrap");
      var input = wrap ? wrap.querySelector("input") : null;
      if (!input) return;
      var isPassword = input.type === "password";
      input.type = isPassword ? "text" : "password";
      btn.classList.toggle("visible", isPassword);
      input.focus();
    });
  });
})();

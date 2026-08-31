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
  if (!dateStr) return "\u2014";
  let d;
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [y, m, day] = dateStr.split("-").map(Number);
    d = new Date(y, m - 1, day);
  } else {
    d = new Date(dateStr);
  }
  if (isNaN(d.getTime())) return "\u2014";
  const y = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  if (DATE_FORMAT === "yyyy-mm-dd") return `${y}-${mm}-${dd}`;
  return `${dd}/${mm}/${y}`;
}

const AR_WEEKDAYS = ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
const AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
const EN_WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function formatDateLong(date) {
  if (!(date instanceof Date) || isNaN(date.getTime())) return "\u2014";
  if (LANG === "ar") {
    const wd = AR_WEEKDAYS[date.getDay()];
    const mn = AR_MONTHS[date.getMonth()];
    const dd = date.getDate();
    const y = date.getFullYear();
    return `${wd}\u060C\u00A0${dd}\u00A0${mn}\u00A0${y}`;
  }
  const wd = EN_WEEKDAYS[date.getDay()];
  const mn = EN_MONTHS[date.getMonth()];
  const dd = date.getDate();
  const y = date.getFullYear();
  return `${wd}, ${mn} ${dd}, ${y}`;
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
    dateEl.textContent = formatDateLong(new Date());
  }

  // Convert <input type="date"> → text DD/MM/YYYY with .value override
  // .value getter returns ISO (YYYY-MM-DD), setter accepts ISO & displays DD/MM/YYYY
  function _isoToDMY(iso) {
    if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "";
    var p = iso.split("-");
    return p[2] + "/" + p[1] + "/" + p[0];
  }
  function _dmyToISO(dmy) {
    if (!dmy || !/^\d{2}\/\d{2}\/\d{4}$/.test(dmy)) return "";
    var p = dmy.split("/");
    return p[2] + "-" + p[1] + "-" + p[0];
  }

  function convertDateInput(inp) {
    if (inp.dataset.dateConverted) return;
    inp.dataset.dateConverted = "1";

    var isoVal = inp.value || "";
    inp.type = "text";
    inp.placeholder = "DD/MM/YYYY";
    inp.maxLength = 10;
    inp.autocomplete = "off";
    inp.value = _isoToDMY(isoVal);
    var isRTL = document.documentElement.dir === "rtl";
    inp.style[isRTL ? "paddingLeft" : "paddingRight"] = "34px";
    inp.style.textAlign = isRTL ? "right" : "left";

    var picker = document.createElement("input");
    picker.type = "date";
    picker.value = isoVal;
    picker.style.cssText = "position:absolute;top:0;" + (isRTL ? "left:0" : "right:0") + ";width:34px;height:100%;opacity:0;cursor:pointer;z-index:2;";
    var wrap = document.createElement("span");
    wrap.style.cssText = "position:relative;display:inline-block;width:100%";
    inp.parentNode.insertBefore(wrap, inp);
    wrap.appendChild(inp);
    wrap.appendChild(picker);

    var icon = document.createElement("span");
    icon.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>';
    icon.style.cssText = "position:absolute;top:50%;" + (isRTL ? "left:10px" : "right:10px") + ";transform:translateY(-50%);pointer-events:none;color:var(--muted-foreground,#999);display:flex;align-items:center;";
    wrap.appendChild(icon);

    picker.addEventListener("change", function () {
      inp.value = _isoToDMY(this.value);
      inp.dispatchEvent(new Event("change"));
    });

    inp.addEventListener("focus", function () { this.select(); });

    var nativeSet = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    var nativeGet = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").get;

    Object.defineProperty(inp, "value", {
      get: function () {
        var dmy = nativeGet.call(this);
        var iso = _dmyToISO(dmy);
        return iso || dmy;
      },
      set: function (v) {
        if (/^\d{4}-\d{2}-\d{2}$/.test(v)) {
          nativeSet.call(this, _isoToDMY(v));
          picker.value = v;
        } else {
          nativeSet.call(this, v);
          picker.value = _dmyToISO(v) || "";
        }
      },
      configurable: true,
      enumerable: true,
    });

    inp.addEventListener("input", function () {
      var raw = this.value.replace(/\D/g, "");
      if (raw.length > 8) raw = raw.slice(0, 8);
      var fmt = "";
      if (raw.length >= 1) fmt += raw.slice(0, Math.min(2, raw.length));
      if (raw.length > 2) fmt += "/" + raw.slice(2, Math.min(4, raw.length));
      if (raw.length > 4) fmt += "/" + raw.slice(4, Math.min(8, raw.length));
      nativeSet.call(this, fmt);
      var iso = _dmyToISO(fmt);
      if (iso) picker.value = iso;
    });

    inp.addEventListener("blur", function () {
      var v = _dmyToISO(nativeGet.call(this));
      if (this.value && !v) {
        this.style.borderColor = "var(--danger, red)";
        setTimeout(() => { this.style.borderColor = ""; }, 2000);
      }
    });
  }

  document.querySelectorAll('input[type="date"]').forEach(convertDateInput);
  window._convertDateInput = convertDateInput;

  // Logout
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await fetch("/logout", { method: "POST" });
      window.location.href = "/login";
    });
  }

  // Topbar user dropdown
  const topbarUserBtn = document.getElementById("topbar-user-btn");
  const topbarUserDd = document.getElementById("topbar-user-dd");
  if (topbarUserBtn && topbarUserDd) {
    topbarUserBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      topbarUserDd.hidden = !topbarUserDd.hidden;
    });
    document.addEventListener("click", () => { topbarUserDd.hidden = true; });
    topbarUserDd.addEventListener("click", (e) => { e.stopPropagation(); });
  }

  // Topbar logout
  const topbarLogoutBtn = document.getElementById("topbar-logout-btn");
  if (topbarLogoutBtn) {
    topbarLogoutBtn.addEventListener("click", async () => {
      await fetch("/logout", { method: "POST" });
      window.location.href = "/login";
    });
  }
});

// ===== Global topbar search + AI (inside the same dropdown) =====
(function initGlobalSearch() {
  var input = document.getElementById("global-search");
  if (!input) return;
  var dropdown = document.getElementById("search-dropdown");
  var searchResults = document.getElementById("search-results");
  var groupLabels = {
    customers: t("common.groupCustomers"),
    suppliers: t("common.groupSuppliers"),
    projects: t("common.groupProjects"),
    units: t("common.groupUnits"),
    invoices: t("common.groupInvoices"),
    employees: t("common.groupEmployees"),
    rentals: t("common.groupRentals"),
    sales_orders: t("common.groupSalesOrders"),
    sales_returns: t("common.groupSalesReturns"),
    purchase_orders: t("common.groupPurchaseOrders"),
    items: t("common.groupItems"),
    warehouses: t("common.groupWarehouses"),
    accounts: t("common.groupAccounts"),
    journal_entries: t("common.groupJournalEntries"),
    cost_centers: t("common.groupCostCenters"),
    fixed_assets: t("common.groupFixedAssets"),
    departments: t("common.groupDepartments"),
    positions: t("common.groupPositions"),
  };
  var groupIcons = {
    customers: "\u{1F464}", suppliers: "\u{1F3ED}", projects: "\u{1F5C2}\u{FE0F}", units: "\u{1F3E0}",
    invoices: "\u{1F9FE}", employees: "\u{1F465}", rentals: "\u{1F511}",
    sales_orders: "\u{1F4C3}", sales_returns: "\u{1F504}", purchase_orders: "\u{1F4B0}",
    items: "\u{1F4E6}", warehouses: "\u{1F3DB}", accounts: "\u{1F4B9}",
    journal_entries: "\u{1F4CB}", cost_centers: "\u{1F4C1}", fixed_assets: "\u{1F48E}",
    departments: "\u{1F3E2}", positions: "\u{1F4BC}",
  };
  var defaultGroupLabel = t("common.search");
  var defaultGroupIcon = "\u{1F50D}";
  var results = [];
  var timer = null;

  // ── AI references (lives inside the same dropdown) ──────────
  var aiToggle = document.getElementById("search-ai-toggle");
  var aiInline = document.getElementById("ai-inline");
  var aiInput = document.getElementById("ai-search-input");
  var aiSend = document.getElementById("ai-search-send");
  var aiChatLog = document.getElementById("ai-chat-log");
  var aiEmptyHint = document.getElementById("ai-empty-hint");
  var aiClearBtn = document.getElementById("ai-clear-btn");
  var aiChips = document.getElementById("ai-chips");
  var voiceBtn = document.getElementById("search-voice-btn");
  var aiHistory = [];
  var aiBusy = false;

  function showSearchMode() {
    if (aiInline) aiInline.hidden = true;
    if (searchResults) searchResults.hidden = false;
    if (aiToggle) aiToggle.classList.remove("active");
  }

  function showAiMode() {
    if (searchResults) searchResults.hidden = true;
    if (aiInline) aiInline.hidden = false;
    if (aiToggle) aiToggle.classList.add("active");
  }

  function closeSd() {
    dropdown.hidden = true;
    showSearchMode();
  }

  function render() {
    if (!input.value.trim()) {
      if (aiToggle && aiToggle.classList.contains("active")) { dropdown.hidden = false; return; }
      dropdown.hidden = true;
      return;
    }
    showSearchMode();
    dropdown.hidden = false;
    if (!searchResults) return;
    if (results.length === 0) {
      searchResults.innerHTML = '<div class="search-result-empty">' + t("common.noResults") + '</div>';
    } else {
      var seen = {};
      var html = "";
      for (var i = 0; i < results.length; i++) {
        var r = results[i];
        if (!seen[r.group]) {
          seen[r.group] = true;
          html += '<div class="search-result-group">' + (groupIcons[r.group] || defaultGroupIcon) + " " + (groupLabels[r.group] || defaultGroupLabel) + '</div>';
        }
        html += '<a class="search-result-item" href="' + r.href + '" data-query="' + escapeHtml(input.value) + '">' +
          '<div class="search-result-text">' + escapeHtml(r.text) + '</div>' +
          '<div class="search-result-sub">' + escapeHtml(r.subtext || "") + '</div></a>';
      }
      searchResults.innerHTML = html;
    }
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
    showSearchMode();
    if (!q) { dropdown.hidden = true; return; }
    if (searchResults) searchResults.innerHTML = '<div class="search-result-empty">' + t("common.searching") + '</div>';
    dropdown.hidden = false;
    timer = setTimeout(function () { doSearch(q); }, 250);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && results.length && !(aiToggle && aiToggle.classList.contains("active"))) {
      window.location.href = results[0].href;
    } else if (e.key === "Escape") {
      closeSd();
      input.blur();
    }
  });

  input.addEventListener("focus", render);
  document.addEventListener("click", function (e) {
    var topbarSearch = document.getElementById("topbar-search");
    if (topbarSearch && !topbarSearch.contains(e.target)) {
      closeSd();
    }
  });

  // ── AI toggle: opens the AI pane inside the search dropdown ──
  if (aiToggle) {
    aiToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      if (aiToggle.classList.contains("active")) {
        closeSd();
        if (aiInput) aiInput.blur();
        return;
      }
      dropdown.hidden = false;
      showAiMode();
      aiScroll();
      if (aiInput) aiInput.focus();
    });
  }

  function aiScroll() {
    if (aiChatLog) aiChatLog.scrollTop = aiChatLog.scrollHeight;
  }

  function aiSourceTag(data) {
    if (!data || !data.source || data.source === "dashboard") return "";
    return '<div class="ai-source">' + t("common.aiSource") + ": <b>" + escapeHtml(data.source) + "</b></div>";
  }

  function aiAnswerHtml(data) {
    var html = "";
    var ans = data.answer || "";
    var type = data.type || "";

    if (type === "count") {
      html = '<h4>' + escapeHtml(ans) + '</h4><div class="ai-stat-num">' + escapeHtml(String(data.count || 0)) + '</div>';
    } else if (type === "sum") {
      html = '<h4>' + escapeHtml(ans) + '</h4><div class="ai-stat-num">' + formatCompact(data.total || 0) + '</div>';
    } else if (type === "search" || type === "sql") {
      var rows = data.data || [];
      var cols = data.columns || (rows.length ? Object.keys(rows[0]) : []);
      if (rows.length === 0) {
        html = '<div class="ai-answer-text">' + escapeHtml(ans || t("common.noResults")) + '</div>';
      } else {
        html = '<h4>' + escapeHtml(ans) + ' (' + rows.length + ')</h4><table><thead><tr>';
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
        html += '</tbody></table>';
      }
    } else if (type === "dashboard") {
      var d = data.data || {};
      html = '<h4>' + escapeHtml(ans || "Dashboard") + '</h4>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;">' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">الموظفون النشطون</div><div style="font-size:20px;font-weight:700;">' + (d.employees_active || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">العملاء</div><div style="font-size:20px;font-weight:700;">' + (d.customers_count || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">الفواتير</div><div style="font-size:20px;font-weight:700;">' + (d.invoices_count || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">أقساط متأخرة</div><div style="font-size:20px;font-weight:700;color:#ef4444;">' + (d.overdue_installments || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">الإيرادات</div><div style="font-size:20px;font-weight:700;color:#22c55e;">' + formatCompact(d.total_revenue || 0) + '</div></div>' +
        '<div><div style="font-size:11px;color:var(--muted-foreground);">المستحقات</div><div style="font-size:20px;font-weight:700;color:#f59e0b;">' + formatCompact(d.total_receivable || 0) + '</div></div>' +
        '</div>';
    } else if (type === "report") {
      html = '<div class="ai-answer-text">' + escapeHtml(ans) + '</div>';
      var its = data.items || [];
      if (its.length) {
        html += '<div class="ai-report-grid">';
        for (var ii = 0; ii < its.length; ii++) {
          html += '<div class="ai-report-item"><div class="ai-report-label">' + escapeHtml(String(its[ii].label)) + '</div><div class="ai-report-value">' + escapeHtml(String(its[ii].value)) + '</div></div>';
        }
        html += '</div>';
      }
      var rows = data.rows || [];
      var c2 = data.columns || (rows.length ? Object.keys(rows[0]) : []);
      if (rows.length) {
        html += '<table><thead><tr>';
        for (var ci = 0; ci < c2.length; ci++) html += '<th>' + escapeHtml(c2[ci]) + '</th>';
        html += '</tr></thead><tbody>';
        for (var ri = 0; ri < rows.length && ri < 50; ri++) {
          html += '<tr>';
          for (var cj = 0; cj < c2.length; cj++) {
            html += '<td>' + escapeHtml(String(rows[ri][c2[cj]] != null ? rows[ri][c2[cj]] : "")) + '</td>';
          }
          html += '</tr>';
        }
        html += '</tbody></table>';
      }
    } else {
      html = '<div class="ai-answer-text">' + escapeHtml(ans || "OK") + '</div>';
    }
    return html + aiSourceTag(data);
  }

  function appendAiUser(text) {
    if (!aiChatLog) return;
    var wrap = document.createElement("div");
    wrap.className = "ai-msg-user";
    var b = document.createElement("div");
    b.textContent = text;
    wrap.appendChild(b);
    aiChatLog.appendChild(wrap);
    aiScroll();
  }

  function appendAiMessage(html) {
    if (!aiChatLog) return;
    var wrap = document.createElement("div");
    wrap.className = "ai-msg-bot";
    var card = document.createElement("div");
    card.className = "ai-result-card";
    card.innerHTML = html;
    wrap.appendChild(card);
    aiChatLog.appendChild(wrap);
    aiScroll();
  }

  function appendAiLoading() {
    if (!aiChatLog) return null;
    var wrap = document.createElement("div");
    wrap.className = "ai-msg-bot";
    wrap.innerHTML = '<div class="ai-result-loading">' + t("common.aiThinking") + '</div>';
    aiChatLog.appendChild(wrap);
    aiScroll();
    return wrap;
  }

  function appendAiAnswer(question, data) {
    if (data && data.success) {
      appendAiMessage(aiAnswerHtml(data));
      aiHistory.push({ q: question, a: data.answer || "" });
      if (aiHistory.length > 6) aiHistory.shift();
    } else {
      var msg = (data && data.answer) || t("common.aiError");
      if (data && data.error_key && t(data.error_key) !== data.error_key) msg = t(data.error_key);
      appendAiMessage('<div class="ai-error">' + escapeHtml(msg) + '</div>');
    }
  }

  function askAI(question) {
    if (!question.trim() || aiBusy) return;
    aiBusy = true;
    question = question.trim();
    dropdown.hidden = false;
    showAiMode();
    if (aiInput) aiInput.value = "";
    if (aiEmptyHint) aiEmptyHint.hidden = true;
    appendAiUser(question);
    var loading = appendAiLoading();
    fetch("/api/ai/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": window.CSRF_TOKEN || "",
      },
      body: JSON.stringify({ question: question, history: aiHistory.slice(-6) }),
    })
      .then(function (res) {
        return res.json().catch(function () { return null; })
          .then(function (data) { return { data: data }; });
      })
      .then(function (box) {
        aiBusy = false;
        if (loading && loading.parentNode) loading.remove();
        appendAiAnswer(question, box.data);
      })
      .catch(function () {
        aiBusy = false;
        if (loading && loading.parentNode) loading.remove();
        appendAiAnswer(question, null);
      });
  }

  if (aiSend && aiInput) {
    aiSend.addEventListener("click", function () { askAI(aiInput.value); });
    aiInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); askAI(aiInput.value); }
      else if (e.key === "Escape") { closeSd(); }
    });
  }

  if (aiClearBtn) {
    aiClearBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      aiHistory = [];
      if (aiChatLog) aiChatLog.innerHTML = "";
      if (aiEmptyHint) {
        aiEmptyHint.hidden = false;
        if (aiChatLog) aiChatLog.appendChild(aiEmptyHint);
      }
      if (aiChips) aiChips.hidden = false;
      aiScroll();
    });
  }

  if (aiChips) {
    var aiChipBtns = aiChips.querySelectorAll(".ai-chip");
    for (var ci = 0; ci < aiChipBtns.length; ci++) {
      (function (chip) {
        chip.addEventListener("click", function (e) {
          e.stopPropagation();
          var q = chip.getAttribute("data-q") || "";
          if (q) askAI(q);
        });
      })(aiChipBtns[ci]);
    }
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
      var inAi = aiToggle && aiToggle.classList.contains("active");
      startVoice(voiceBtn, function (text) {
        if (inAi) {
          if (aiInput) aiInput.value = text;
          askAI(text);
        } else {
          input.value = text;
          input.dispatchEvent(new Event("input"));
        }
      });
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
    let left = tRect.left - sRect.left + scrollEl.scrollLeft;

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

// ===== Global functions for page scripts =====
window.api = api;
window.escapeHtml = escapeHtml;
window.formatMoney = formatMoney;
window.formatDate = formatDate;
window.formatDateLong = formatDateLong;
window.formatNumber = formatNumber;
window.showToast = showToast;
window.t = t;
window.tv = tv;
window.statusBadge = statusBadge;
window.approvalBadge = approvalBadge;
window.canAction = canAction;
window.exportCSV = exportCSV;
window.prefillDocNumber = prefillDocNumber;

function toastError(err) {
  var msg = err && err.message ? err.message : String(err || "Error");
  showToast(msg, "error");
}
window.toastError = toastError;

function closeModal(id) {
  var el = document.getElementById(id);
  if (el) el.classList.remove("active");
}
window.closeModal = closeModal;

function openModal(id) {
  var el = document.getElementById(id);
  if (el) {
    el.classList.add("active");
    if (window._convertDateInput) {
      el.querySelectorAll('input[type="date"]').forEach(window._convertDateInput);
    }
  }
}
window.openModal = openModal;

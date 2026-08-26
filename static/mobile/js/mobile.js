/* ============================================================
   Dynamic Pro — Mobile PWA App
   ============================================================ */
const T = window.T || {};
function tr(key) {
  if (T[key] !== undefined && T[key] !== null) return T[key];
  return key;
}

let ME = null;
let state = {
  current: "home",
  role: "",
  visits: [],
  collections: [],
  notifs: [],
};

const ICONS = {
  home: '<svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>',
  attendance: '<svg viewBox="0 0 24 24"><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm4.2 14.2L11 13V7h1.5v5.3l4.5 2.7-.8 1.2z"/></svg>',
  gps: '<svg viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 8c0 5.25 7 13 7 13s7-7.75 7-13c0-2.87-3.13-5-7-5zm0 9.5A2.5 2.5 0 0112 6a2.5 2.5 0 010 5.5z"/></svg>',
  visits: '<svg viewBox="0 0 24 24"><path d="M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm2 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>',
  collections: '<svg viewBox="0 0 24 24"><path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z"/></svg>',
  employees: '<svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>',
  leaves: '<svg viewBox="0 0 24 24"><path d="M20 13H4c-1.1 0-2 .9-2 2v6c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2v-6c0-1.1-.9-2-2-2zM7 19c-1.66 0-3-1.34-3-3 0-1.66 1.34-3 3-3s3 1.34 3 3c0 1.66-1.34 3-3 3zm13-12h-2V5c0-1.1-.9-2-2-2h-2c-1.1 0-2 .9-2 2v2H7c-1.1 0-2 .9-2 2v1h18V9c0-1.1-.9-2-2-2z"/></svg>',
  projects: '<svg viewBox="0 0 24 24"><path d="M22 19V5h-2v14H4v2h16a2 2 0 002-2zM2 17h8V3H2v14zm4-10h4v8H6V7zm10 0h4v8h-4V7z"/></svg>',
  notifications: '<svg viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>',
};

/* ===== API helper ===== */
async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (opts.method && opts.method !== "GET" && window.CSRF_TOKEN) {
    headers["X-CSRF-Token"] = window.CSRF_TOKEN;
  }
  const res = await fetch(path, {
    method: opts.method || "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401) {
    window.location.href = "/mobile/login";
    throw new Error("unauthorized");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || "Error");
  return data;
}

function toast(msg, type = "success") {
  const el = document.createElement("div");
  el.className = "m-toast";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function money(v) {
  return Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function todayISO() {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}

/* ===== Boot ===== */
document.addEventListener("DOMContentLoaded", async () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/mobile/sw.js").catch(() => {});
  }
  try {
    ME = await api("/api/mobile/me");
    document.getElementById("m-user-name").textContent = ME.full_name || ME.username;
    document.getElementById("m-app-title").textContent = roleTitle(ME.role);
    buildNav(ME);
    await loadNotifications();
    await openSection("home");
    if (ME.apps.delegate || ME.apps.manager || ME.apps.hr) startGpsReporting();
    startClock();
    setupPush();
    setupNotifStream();
  } catch (e) {
    toast(e.message, "error");
  }
});

function roleTitle(role) {
  if (role === "admin") return tr("mobile.roleManager");
  return tr("mobile.appTitle");
}

function buildNav(me) {
  const apps = me.apps;
  const items = [];
  items.push({ key: "home", icon: ICONS.home, label: tr("mobile.tabHome") });
  items.push({ key: "attendance", icon: ICONS.attendance, label: tr("mobile.tabAttendance") });
  if (apps.manager) items.push({ key: "gps", icon: ICONS.gps, label: tr("mobile.tabGps") });
  if (apps.delegate) {
    items.push({ key: "visits", icon: ICONS.visits, label: tr("mobile.tabVisits") });
    items.push({ key: "collections", icon: ICONS.collections, label: tr("mobile.tabCollections") });
  }
  if (apps.engineer) items.push({ key: "projects", icon: ICONS.projects, label: tr("mobile.tabProjects") });
  if (apps.hr) {
    items.push({ key: "leaves", icon: ICONS.leaves, label: tr("mobile.tabLeaves") });
  }
  items.push({ key: "notifications", icon: ICONS.notifications, label: tr("mobile.tabNotif") });
  state.nav = items;
  const navEl = document.getElementById("m-nav-items");
  navEl.innerHTML = `<div class="m-nav-inner">${items.map((i) =>
    `<button class="m-nav-item" data-section="${i.key}" onclick="openSection('${i.key}')">${i.icon}<span>${esc(i.label)}</span></button>`
  ).join("")}</div>`;
  document.getElementById("m-bottom-nav").hidden = false;
  setupNavScroll(navEl);
}

function setupNavScroll(navEl) {
  const inner = navEl.querySelector(".m-nav-inner");
  const scroller = document.getElementById("m-bottom-nav");
  const target = scroller || inner;
  if (!target || !("scrollLeft" in target)) return;
  let isDown = false, startX = 0, startScroll = 0, moved = false;
  target.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    isDown = true; moved = false;
    startX = e.clientX; startScroll = target.scrollLeft;
  });
  window.addEventListener("pointermove", (e) => {
    if (!isDown) return;
    const dx = e.clientX - startX;
    if (Math.abs(dx) > 6) moved = true;
    target.scrollLeft = startScroll - dx;
  });
  window.addEventListener("pointerup", () => { isDown = false; });
  target.addEventListener("click", (e) => {
    if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; }
  }, true);
  target.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaX) < Math.abs(e.deltaY)) {
      e.preventDefault();
      target.scrollLeft += e.deltaY;
    }
  }, { passive: false });
}

async function openSection(key) {
  state.current = key;
  document.querySelectorAll(".m-nav-item").forEach((b) => {
    b.classList.toggle("active", b.dataset.section === key);
  });
  const main = document.getElementById("m-main");
  const renderers = {
    home: renderHome,
    attendance: renderAttendance,
    gps: renderGps,
    visits: renderVisits,
    collections: renderCollections,
    projects: renderProjects,
    leaves: renderLeaves,
    notifications: renderNotifSection,
  };
  const fn = renderers[key];
  if (!fn) return;
  main.innerHTML = '<div class="m-loading"><div class="m-spinner"></div></div>';
  try {
    await fn(main);
  } catch (e) {
    main.innerHTML = `<div class="m-empty">${esc(e.message)}</div>`;
  }
  window.scrollTo(0, 0);
}
window.openSection = openSection;

/* ===== Home / dashboards ===== */
async function renderHome(main) {
  const dash = await api("/api/mobile/dashboard");
  const s = dash.stats || {};
  let html = `<h2 class="m-card-title" style="padding:4px 2px;">${esc(ME.full_name || ME.username)}</h2>`;

  if (ME.role === "admin") {
    html += `<div class="m-grid m-grid-3">
      <div class="m-stat"><div class="m-stat-value">${s.customers || 0}</div><div class="m-stat-label">${tr("mobile.statCustomers")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.units || 0}</div><div class="m-stat-label">${tr("mobile.statUnits")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.projects || 0}</div><div class="m-stat-label">${tr("mobile.statProjects")}</div></div>
    </div>
    <div class="m-grid m-grid-3">
      <div class="m-stat"><div class="m-stat-value">${s.today_attendance || 0}</div><div class="m-stat-label">${tr("mobile.statTodayAttendance")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.pending_leaves || 0}</div><div class="m-stat-label">${tr("mobile.statPendingLeaves")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.active_contracts || 0}</div><div class="m-stat-label">${tr("mobile.statActiveContracts")}</div></div>
    </div>`;
  } else if (dash.role === "delegate") {
    html += `<div class="m-grid">
      <div class="m-stat"><div class="m-stat-value">${s.today_visits || 0}</div><div class="m-stat-label">${tr("mobile.statTodayVisits")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.pending_visits || 0}</div><div class="m-stat-label">${tr("mobile.statPendingVisits")}</div></div>
    </div>
    <div class="m-grid">
      <div class="m-stat"><div class="m-stat-value">${s.done_visits || 0}</div><div class="m-stat-label">${tr("mobile.statDoneVisits")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.active_contracts || 0}</div><div class="m-stat-label">${tr("mobile.statActiveContracts")}</div></div>
    </div>`;
  } else if (dash.role === "engineer") {
    html += `<div class="m-grid m-grid-3">
      <div class="m-stat"><div class="m-stat-value">${s.total || 0}</div><div class="m-stat-label">${tr("mobile.statProjects")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.active || 0}</div><div class="m-stat-label">${tr("mobile.statActiveProjects")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.phases || 0}</div><div class="m-stat-label">${tr("mobile.statPhases")}</div></div>
    </div>`;
  } else if (dash.role === "hr") {
    html += `<div class="m-grid m-grid-3">
      <div class="m-stat"><div class="m-stat-value">${s.employees || 0}</div><div class="m-stat-label">${tr("mobile.statEmployees")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.present || 0}</div><div class="m-stat-label">${tr("mobile.statPresent")}</div></div>
      <div class="m-stat"><div class="m-stat-value">${s.pending_leaves || 0}</div><div class="m-stat-label">${tr("mobile.statPendingLeaves")}</div></div>
    </div>`;
  }

  html += `
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.quickActions")}</div>
      <div class="m-row" style="gap:8px; flex-wrap:wrap;">
        <button class="m-btn m-btn-primary m-btn-sm" onclick="openSection('attendance')">${tr("mobile.checkAttendance")}</button>
        ${ME.apps.delegate ? `<button class="m-btn m-btn-outline m-btn-sm" onclick="openSection('visits')">${tr("mobile.tabVisits")}</button>
        <button class="m-btn m-btn-outline m-btn-sm" onclick="openSection('collections')">${tr("mobile.tabCollections")}</button>` : ""}
        ${ME.apps.manager || ME.apps.hr ? `<button class="m-btn m-btn-outline m-btn-sm" onclick="openSection('gps')">${tr("mobile.tabGps")}</button>` : ""}
      </div>
    </div>`;
  main.innerHTML = html;
}

/* ===== Attendance ===== */
let attTimer = null;
async function renderAttendance(main) {
  const today = await api("/api/mobile/attendance/today");
  const rec = today.record;
  main.innerHTML = `
    <div class="m-card m-clock">
      <div class="m-clock-time" id="m-clock"></div>
      <div class="m-clock-date" id="m-clock-date"></div>
      <div class="m-gps-indicator" id="m-gps-ind"><span class="m-dot" id="m-gps-dot"></span><span id="m-gps-text">${tr("mobile.gpsAcquiring")}</span></div>
      <div id="m-att-status-wrap"></div>
      <div style="margin-top:18px;" class="m-row-between">
        <button class="m-btn m-btn-success" id="m-check-in" onclick="doCheckIn()" ${rec && rec.check_in ? "disabled" : ""}>${tr("mobile.checkIn")}</button>
        <button class="m-btn m-btn-danger" id="m-check-out" onclick="doCheckOut()" ${!rec || !rec.check_in || rec.check_out ? "disabled" : ""}>${tr("mobile.checkOut")}</button>
      </div>
    </div>
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.recentAttendance")}</div>
      <div id="m-att-history"></div>
    </div>`;
  startClock();
  if (attTimer) clearInterval(attTimer);
  attTimer = setInterval(() => refreshAttStatus(), 15000);
  await refreshAttStatus();
  loadAttendanceHistory();
}

function startClock() {
  const tick = () => {
    const el1 = document.getElementById("m-clock");
    const el2 = document.getElementById("m-clock-date");
    if (el1) el1.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (el2) el2.textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  };
  tick();
  setInterval(tick, 1000);
}

let lastGps = null;
let lastGpsAt = 0;

async function fetchIpLocation() {
  const urls = ["https://ipapi.co/json/", "https://ip-api.com/json/"];
  for (const u of urls) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 6000);
      const res = await fetch(u, { signal: ctrl.signal });
      clearTimeout(t);
      if (!res.ok) continue;
      const d = await res.json();
      const lat = parseFloat(d.latitude);
      const lng = parseFloat(d.longitude);
      if (!isNaN(lat) && !isNaN(lng)) {
        return { latitude: lat, longitude: lng, accuracy: 5000, source: "ip" };
      }
    } catch (e) {}
  }
  return null;
}

async function currentGps() {
  if (lastGps && Date.now() - lastGpsAt < 20000) return lastGps;
  if (navigator.geolocation) {
    try {
      const pos = await new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
          (p) => resolve(p),
          (err) => resolve({ error: err }),
          { timeout: 6000, enableHighAccuracy: true, maximumAge: 30000 }
        );
      });
      if (pos && !pos.error && pos.coords) {
        lastGps = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy || 0,
          source: "gps",
        };
        lastGpsAt = Date.now();
        return lastGps;
      }
    } catch (e) {}
  }
  const ip = await fetchIpLocation();
  if (ip) { lastGps = ip; lastGpsAt = Date.now(); }
  return lastGps;
}

async function refreshAttStatus() {
  try {
    const data = await api("/api/mobile/attendance/today");
    const rec = data.record;
    const wrap = document.getElementById("m-att-status-wrap");
    if (wrap) {
      if (rec && rec.check_in && rec.check_out) {
        wrap.innerHTML = `<div class="m-att-status m-att-out">${tr("mobile.doneToday")} — ${rec.check_in} → ${rec.check_out} (${rec.working_hours}h)</div>`;
      } else if (rec && rec.check_in) {
        wrap.innerHTML = `<div class="m-att-status m-att-in">${tr("mobile.checkedIn")} ${rec.check_in}</div>`;
      }
    }
    const gps = await currentGps();
    const dot = document.getElementById("m-gps-dot");
    const txt = document.getElementById("m-gps-text");
    if (dot && txt) {
      if (gps && gps.source === "ip") { dot.classList.add("ok"); txt.textContent = tr("mobile.gpsApprox"); }
      else if (gps) { dot.classList.add("ok"); txt.textContent = tr("mobile.gpsReady"); }
      else { dot.classList.remove("ok"); txt.textContent = tr("mobile.gpsUnavailable"); }
    }
    const ci = document.getElementById("m-check-in");
    const co = document.getElementById("m-check-out");
    if (ci) ci.disabled = !!(rec && rec.check_in);
    if (co) co.disabled = !rec || !rec.check_in || !!rec.check_out;
  } catch (e) {}
}

async function doCheckIn() {
  const gps = await currentGps();
  try {
    await api("/api/mobile/attendance/check-in", { method: "POST", body: gps || {} });
    toast(tr("mobile.checkedIn"));
    refreshAttStatus();
  } catch (e) { toast(e.message, "error"); }
}
window.doCheckIn = doCheckIn;

async function doCheckOut() {
  const gps = await currentGps();
  try {
    await api("/api/mobile/attendance/check-out", { method: "POST", body: gps || {} });
    toast(tr("mobile.checkedOut"));
    refreshAttStatus();
  } catch (e) { toast(e.message, "error"); }
}
window.doCheckOut = doCheckOut;

async function loadAttendanceHistory() {
  const wrap = document.getElementById("m-att-history");
  if (!wrap) return;
  try {
    const data = await api("/api/mobile/attendance/history?days=14");
    const rows = data.records || [];
    if (!rows.length) { wrap.innerHTML = `<div class="m-empty">${tr("mobile.noData")}</div>`; return; }
    wrap.innerHTML = rows.map((r) => `
      <div class="m-list-item">
        <div class="m-list-icon">${r.status === "late" ? "⚠️" : r.status === "present" ? "✅" : "⏰"}</div>
        <div class="m-list-main">
          <div class="m-list-title">${esc(r.date)}</div>
          <div class="m-list-sub">${esc(r.check_in || "—")} → ${esc(r.check_out || "—")} · ${r.working_hours || 0}h</div>
        </div>
        <span class="m-chip ${r.status === "late" ? "m-chip-amber" : r.status === "present" ? "m-chip-green" : "m-chip-gray"}">${esc(r.status)}</span>
      </div>`).join("");
  } catch (e) {}
}

/* ===== GPS ===== */
let gpsInterval = null;
function startGpsReporting() {
  if (gpsInterval) clearInterval(gpsInterval);
  const report = async () => {
    const gps = await currentGps();
    if (!gps) return;
    try {
      await api("/api/mobile/gps/report", { method: "POST", body: { ...gps, source: gps.source || "app" } });
    } catch (e) {}
  };
  report();
  gpsInterval = setInterval(report, 30000);
}

let map = null;
let mapMarkers = [];
async function renderGps(main) {
  main.innerHTML = `
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.liveTracking")}</div>
      <div class="m-map" id="m-map"></div>
      <div class="m-row-between" style="margin-top:10px;">
        <span class="m-muted">${tr("mobile.updatedEvery")} 30s</span>
        <button class="m-btn m-btn-outline m-btn-sm" onclick="refreshGpsMap()">${tr("mobile.refresh")}</button>
      </div>
    </div>
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.team")}</div>
      <div id="m-gps-list"></div>
    </div>`;
  await refreshGpsMap();
  if (gpsInterval) clearInterval(gpsInterval);
  gpsInterval = setInterval(refreshGpsMap, 30000);
}

async function refreshGpsMap() {
  try {
    const data = await api("/api/mobile/gps/live");
    const locs = data.locations || [];
    const listEl = document.getElementById("m-gps-list");
    if (listEl) {
      listEl.innerHTML = locs.length ? locs.map((l) => `
        <div class="m-list-item">
          <div class="m-list-icon">📍</div>
          <div class="m-list-main">
            <div class="m-list-title">${esc(l.user_name)}</div>
            <div class="m-list-sub">${esc(l.role)} · ${esc(l.recorded_at || "")}</div>
          </div>
        </div>`).join("") : `<div class="m-empty">${tr("mobile.noLocation")}</div>`;
    }
    const mapEl = document.getElementById("m-map");
    if (!mapEl || !locs.length) return;
    if (!map) {
      map = L.map("m-map").setView([locs[0].latitude, locs[0].longitude], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "" }).addTo(map);
    }
    mapMarkers.forEach((m) => m.remove());
    mapMarkers = [];
    locs.forEach((l) => {
      const m = L.marker([l.latitude, l.longitude])
        .addTo(map)
        .bindPopup(`<b>${esc(l.user_name)}</b><br>${esc(l.role)}`);
      mapMarkers.push(m);
    });
    if (locs.length) map.setView([locs[0].latitude, locs[0].longitude], 13);
  } catch (e) {}
}
window.refreshGpsMap = refreshGpsMap;

/* ===== Visits (مندوب) ===== */
let lookupsCache = null;
async function getLookups() {
  if (lookupsCache) return lookupsCache;
  lookupsCache = await api("/api/mobile/lookups");
  return lookupsCache;
}

async function renderVisits(main) {
  const data = await api("/api/mobile/visits?mine=1");
  state.visits = data.visits || [];
  const rows = state.visits;
  main.innerHTML = `
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.tabVisits")}
        <button class="m-btn m-btn-primary m-btn-sm" onclick="showVisitModal()">+ ${tr("mobile.newVisit")}</button>
      </div>
      <div id="m-visits-list">
        ${rows.length ? rows.map(visitRow).join("") : `<div class="m-empty">${tr("mobile.noVisits")}</div>`}
      </div>
    </div>`;
}

function visitRow(v) {
  const statusChip = {
    planned: `<span class="m-chip m-chip-blue">${tr("mobile.visitPlanned")}</span>`,
    done: `<span class="m-chip m-chip-green">${tr("mobile.visitDone")}</span>`,
    cancelled: `<span class="m-chip m-chip-gray">${tr("mobile.visitCancelled")}</span>`,
    missed: `<span class="m-chip m-chip-red">${tr("mobile.visitMissed")}</span>`,
  }[v.status] || `<span class="m-chip m-chip-gray">${esc(v.status)}</span>`;
  const typeChip = {
    collection: `<span class="m-chip m-chip-amber">${tr("mobile.visitCollection")}</span>`,
    followup: `<span class="m-chip m-chip-green">${tr("mobile.visitFollowup")}</span>`,
    inspection: `<span class="m-chip m-chip-blue">${tr("mobile.visitInspection")}</span>`,
    new_lead: `<span class="m-chip m-chip-gray">${tr("mobile.visitNewLead")}</span>`,
  }[v.visit_type] || "";
  return `
    <div class="m-list-item">
      <div class="m-list-icon">📋</div>
      <div class="m-list-main">
        <div class="m-list-title">${esc(v.customer_name || v.unit_code || v.visit_number)}</div>
        <div class="m-list-sub">${esc(v.scheduled_date || "")} ${esc(v.scheduled_time || "")} · ${esc(v.purpose || "")}</div>
        <div style="margin-top:6px; display:flex; gap:6px;">${typeChip} ${statusChip}</div>
      </div>
      <div class="m-list-actions">
        ${v.status === "planned" ? `<button class="m-btn m-btn-primary m-btn-sm" onclick="startVisit(${v.id})">${tr("mobile.start")}</button>` : ""}
        ${v.status === "planned" ? `<button class="m-btn m-btn-outline m-btn-sm" onclick="editVisit(${v.id})">✏️</button>` : ""}
      </div>
    </div>`;
}

async function showVisitModal() {
  const lk = await getLookups();
  const wrap = el(`
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.newVisit")} <button class="m-icon-btn" onclick="this.closest('.m-card').remove()">✕</button></div>
      <div class="m-field"><label>${tr("mobile.visitType")}</label>
        <select id="v-type">
          <option value="collection">${tr("mobile.visitCollection")}</option>
          <option value="followup">${tr("mobile.visitFollowup")}</option>
          <option value="inspection">${tr("mobile.visitInspection")}</option>
          <option value="new_lead">${tr("mobile.visitNewLead")}</option>
        </select>
      </div>
      <div class="m-field"><label>${tr("common.customer")}</label>
        <select id="v-customer"><option value="">${tr("common.select")}</option>
          ${(lk.customers || []).map((c) => `<option value="${c.id}">${esc(c.full_name)}</option>`).join("")}
        </select>
      </div>
      <div class="m-field"><label>${tr("mobile.unit")}</label>
        <select id="v-unit"><option value="">${tr("common.select")}</option>
          ${(lk.units || []).map((u) => `<option value="${u.id}">${esc(u.unit_code)}</option>`).join("")}
        </select>
      </div>
      <div class="m-form-row">
        <div class="m-field"><label>${tr("mobile.visitDate")}</label><input type="date" id="v-date" value="${todayISO()}"></div>
        <div class="m-field"><label>${tr("mobile.visitTime")}</label><input type="time" id="v-time"></div>
      </div>
      <div class="m-field"><label>${tr("mobile.purpose")}</label><input type="text" id="v-purpose"></div>
      <div class="m-field"><label>${tr("mobile.notes")}</label><textarea id="v-notes" rows="2"></textarea></div>
      <button class="m-btn m-btn-primary m-btn-block" onclick="createVisit()">${tr("common.save")}</button>
    </div>`);
  document.getElementById("m-main").prepend(wrap);
  window.scrollTo(0, 0);
}
window.showVisitModal = showVisitModal;

async function createVisit() {
  const body = {
    visit_type: document.getElementById("v-type").value,
    customer_id: document.getElementById("v-customer").value || null,
    unit_id: document.getElementById("v-unit").value || null,
    scheduled_date: document.getElementById("v-date").value,
    scheduled_time: document.getElementById("v-time").value,
    purpose: document.getElementById("v-purpose").value,
    notes: document.getElementById("v-notes").value,
  };
  try {
    await api("/api/mobile/visits", { method: "POST", body });
    toast(tr("common.saved"));
    openSection("visits");
  } catch (e) { toast(e.message, "error"); }
}
window.createVisit = createVisit;

async function startVisit(id) {
  const gps = await currentGps();
  try {
    await api(`/api/mobile/visits/${id}/start`, { method: "POST", body: gps || {} });
    toast(tr("mobile.visitStarted"));
    openSection("visits");
  } catch (e) { toast(e.message, "error"); }
}
window.startVisit = startVisit;

async function editVisit(id) {
  const v = state.visits.find((x) => x.id === id);
  if (!v) return;
  const result = prompt(tr("mobile.visitResult"), v.result || "");
  if (result === null) return;
  try {
    await api(`/api/mobile/visits/${id}/complete`, { method: "POST", body: { result } });
    toast(tr("common.saved"));
    openSection("visits");
  } catch (e) { toast(e.message, "error"); }
}
window.editVisit = editVisit;

/* ===== Collections (مندوب) ===== */
async function renderCollections(main) {
  const data = await api("/api/mobile/collections");
  state.collections = data.collections || [];
  main.innerHTML = `
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.tabCollections")}</div>
      <div>
        ${state.collections.length ? state.collections.map((c) => `
          <div class="m-list-item">
            <div class="m-list-icon">💰</div>
            <div class="m-list-main">
              <div class="m-list-title">${esc(c.customer_name || "—")} <span class="m-muted">(${esc(c.contract_number)})</span></div>
              <div class="m-list-sub">${esc(c.unit_code || "")} · ${tr("mobile.monthlyRent")}: ${money(c.monthly_rent)}</div>
              <div class="m-list-sub">${tr("mobile.balance")}: <span class="${c.balance > 0 ? "m-money-red" : "m-money"}">${money(c.balance)}</span></div>
            </div>
            <button class="m-btn m-btn-success m-btn-sm" onclick="showPayModal(${c.contract_id}, '${esc(c.customer_name || "")}', ${c.monthly_rent})">${tr("mobile.collect")}</button>
          </div>`).join("") : `<div class="m-empty">${tr("mobile.noData")}</div>`}
      </div>
    </div>`;
}

function showPayModal(contractId, customerName, monthlyRent) {
  const wrap = el(`
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.collectPayment")} <button class="m-icon-btn" onclick="this.closest('.m-card').remove()">✕</button></div>
      <div class="m-list-sub" style="margin-bottom:10px;">${esc(customerName)}</div>
      <div class="m-field"><label>${tr("mobile.amount")} *</label><input type="number" id="p-amount" value="${monthlyRent}" step="0.01" min="0"></div>
      <div class="m-form-row">
        <div class="m-field"><label>${tr("mobile.paymentDate")}</label><input type="date" id="p-date" value="${todayISO()}"></div>
        <div class="m-field"><label>${tr("mobile.method")}</label>
          <select id="p-method">
            <option value="cash">${tr("mobile.methodCash")}</option>
            <option value="bank">${tr("mobile.methodBank")}</option>
            <option value="transfer">${tr("mobile.methodTransfer")}</option>
          </select>
        </div>
      </div>
      <div class="m-field"><label>${tr("mobile.reference")}</label><input type="text" id="p-ref"></div>
      <button class="m-btn m-btn-primary m-btn-block" onclick="savePayment(${contractId})">${tr("common.save")}</button>
    </div>`);
  document.getElementById("m-main").prepend(wrap);
  window.scrollTo(0, 0);
}
window.showPayModal = showPayModal;

async function savePayment(contractId) {
  const body = {
    contract_id: contractId,
    amount: document.getElementById("p-amount").value,
    payment_date: document.getElementById("p-date").value,
    method: document.getElementById("p-method").value,
    reference: document.getElementById("p-ref").value,
  };
  try {
    await api("/api/mobile/collections/pay", { method: "POST", body });
    toast(tr("mobile.paymentRecorded"));
    openSection("collections");
  } catch (e) { toast(e.message, "error"); }
}
window.savePayment = savePayment;

/* ===== Projects (مهندس) ===== */
async function renderProjects(main) {
  const dash = await api("/api/mobile/dashboard");
  const projects = dash.projects || [];
  main.innerHTML = `
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.tabProjects")}</div>
      ${projects.length ? projects.map((p) => `
        <div class="m-list-item">
          <div class="m-list-icon">🏗️</div>
          <div class="m-list-main">
            <div class="m-list-title">${esc(p.name)}</div>
            <div class="m-list-sub">${esc(p.location || "")} · ${tr("mobile.status")}: ${esc(p.status || "")}</div>
          </div>
          <span class="m-chip ${p.status === "done" ? "m-chip-green" : p.status === "cancelled" ? "m-chip-red" : "m-chip-blue"}">${esc(p.status || "")}</span>
        </div>`).join("") : `<div class="m-empty">${tr("mobile.noProjects")}</div>`}
    </div>`;
}

/* ===== Leaves (HR) ===== */
async function renderLeaves(main) {
  main.innerHTML = `
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.submitLeave")}</div>
      <div class="m-field"><label>${tr("mobile.leaveType")}</label>
        <select id="lv-type">
          <option value="annual">${tr("mobile.leaveAnnual")}</option>
          <option value="sick">${tr("mobile.leaveSick")}</option>
          <option value="unpaid">${tr("mobile.leaveUnpaid")}</option>
          <option value="emergency">${tr("mobile.leaveEmergency")}</option>
          <option value="maternity">${tr("mobile.leaveMaternity")}</option>
        </select>
      </div>
      <div class="m-form-row">
        <div class="m-field"><label>${tr("mobile.startDate")} *</label><input type="date" id="lv-start" value="${todayISO()}"></div>
        <div class="m-field"><label>${tr("mobile.endDate")}</label><input type="date" id="lv-end" value="${todayISO()}"></div>
      </div>
      <div class="m-field"><label>${tr("mobile.reason")}</label><textarea id="lv-reason" rows="2"></textarea></div>
      <button class="m-btn m-btn-primary m-btn-block" onclick="submitLeave()">${tr("mobile.sendRequest")}</button>
    </div>`;
}

async function submitLeave() {
  const body = {
    leave_type: document.getElementById("lv-type").value,
    start_date: document.getElementById("lv-start").value,
    end_date: document.getElementById("lv-end").value,
    reason: document.getElementById("lv-reason").value,
  };
  try {
    await api("/api/mobile/leaves", { method: "POST", body });
    toast(tr("mobile.leaveSubmitted"));
    openSection("home");
  } catch (e) { toast(e.message, "error"); }
}
window.submitLeave = submitLeave;

/* ===== Notifications ===== */
async function loadNotifications() {
  try {
    const data = await api("/api/mobile/notifications");
    state.notifs = data.notifications || [];
    updateNotifBadge();
    updateNotifList();
  } catch (e) {}
}

function updateNotifBadge() {
  const unread = state.notifs.filter((n) => !n.is_read).length;
  const badge = document.getElementById("m-notif-count");
  if (badge) { badge.hidden = unread === 0; badge.textContent = unread > 99 ? "99+" : unread; }
}

function updateNotifList() {
  const list = document.getElementById("m-notif-list");
  if (!list) return;
  if (!state.notifs.length) {
    list.innerHTML = `<div class="m-empty">${tr("mobile.noNotifications")}</div>`;
    return;
  }
  list.innerHTML = state.notifs.slice(0, 30).map((n) => `
    <div class="m-notif-item ${n.is_read ? "" : "unread"}" onclick="markOne(${n.id})">
      <div class="m-notif-title">${esc(n.title)}</div>
      <div class="m-notif-msg">${esc(n.message || "")}</div>
      <div class="m-notif-time">${esc(n.created_at || "")}</div>
    </div>`).join("");
}

async function toggleNotifPanel() {
  const panel = document.getElementById("m-notif-panel");
  panel.hidden = !panel.hidden;
  if (!panel.hidden) await loadNotifications();
}
window.toggleNotifPanel = toggleNotifPanel;

async function markOne(id) {
  try {
    await api("/api/mobile/notifications/read", { method: "POST", body: { id } });
    const n = state.notifs.find((x) => x.id === id);
    if (n) n.is_read = true;
    updateNotifBadge();
    updateNotifList();
  } catch (e) {}
}
window.markOne = markOne;

async function markAllRead() {
  try {
    await api("/api/mobile/notifications/read", { method: "POST", body: {} });
    state.notifs.forEach((n) => (n.is_read = true));
    updateNotifBadge();
    updateNotifList();
  } catch (e) {}
}
window.markAllRead = markAllRead;

async function renderNotifSection(main) {
  await loadNotifications();
  main.innerHTML = `
    <div class="m-card">
      <div class="m-card-title">${tr("mobile.notificationsTitle")}
        <button class="m-btn m-btn-outline m-btn-sm" onclick="markAllRead()">${tr("mobile.markAllRead")}</button>
      </div>
      <div id="m-notif-section-list"></div>
    </div>`;
  const list = document.getElementById("m-notif-section-list");
  if (!state.notifs.length) { list.innerHTML = `<div class="m-empty">${tr("mobile.noNotifications")}</div>`; return; }
  list.innerHTML = state.notifs.map((n) => `
    <div class="m-list-item ${n.is_read ? "" : "unread"}">
      <div class="m-list-icon">🔔</div>
      <div class="m-list-main">
        <div class="m-list-title">${esc(n.title)}</div>
        <div class="m-list-sub">${esc(n.message || "")}</div>
        <div class="m-notif-time">${esc(n.created_at || "")}</div>
      </div>
    </div>`).join("");
}

function setupNotifStream() {
  try {
    const es = new EventSource("/api/mobile/notifications/stream");
    es.onmessage = (e) => {
      const n = JSON.parse(e.data);
      if (!n || !n.id) return;
      if (!state.notifs.find((x) => x.id === n.id)) {
        state.notifs.unshift(n);
        updateNotifBadge();
        updateNotifList();
      }
    };
  } catch (e) {}
}

function setupPush() {
  if (!("Notification" in window)) return;
  if ("serviceWorker" in navigator && "PushManager" in window) {
    Notification.requestPermission().then((perm) => {
      if (perm === "granted") registerPush();
    });
  }
}

async function registerPush() {
  try {
    const reg = await navigator.serviceWorker.ready;
    if (Notification.permission !== "granted") return;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: null, // VAPID يُضاف عند إعداد FCM
    });
    await api("/api/mobile/devices", {
      method: "POST",
      body: { token: sub.toJSON ? JSON.stringify(sub.toJSON()) : "", platform: "web" },
    });
  } catch (e) {}
}

async function doLogout() {
  try { await fetch("/mobile/logout", { method: "POST" }); } catch (e) {}
  window.location.href = "/mobile/login";
}
window.doLogout = doLogout;

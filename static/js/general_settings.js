(function () {
  "use strict";

  var T = window.T || {};
  var lt = function (k) { return T[k] !== undefined && T[k] !== null ? T[k] : k; };

  var wrap = document.getElementById("settings-form-wrap");
  var loading = document.getElementById("settings-loading");
  var msg = document.getElementById("settings-msg");
  var saveBtn = document.getElementById("settings-save");
  if (!wrap) return;

  if (loading) loading.style.display = "none";
  wrap.style.display = "";

  function showMsg(text, kind) {
    msg.textContent = text;
    msg.className = "settings-msg " + (kind || "");
    msg.style.display = "block";
    setTimeout(function () { msg.style.display = "none"; }, 4000);
  }
  function hideMsg() { msg.style.display = "none"; }

  function optHTML(value, label) {
    return '<option value="' + value + '">' + escapeHtml(label) + '</option>';
  }
  function fillSelect(id, options, selected) {
    var sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = '<option value="">' + lt("common.choose") + '</option>';
    options.forEach(function (o) { sel.innerHTML += optHTML(o.value, o.label); });
    if (selected) sel.value = selected;
  }

  // ── Section Navigation ──────────────────────────────────────
  var navItems = document.querySelectorAll(".settings-nav-item");
  var sections = document.querySelectorAll(".settings-section");

  navItems.forEach(function (item) {
    item.addEventListener("click", function () {
      var target = item.getAttribute("data-section");
      navItems.forEach(function (n) { n.classList.remove("active"); });
      sections.forEach(function (s) { s.classList.remove("active"); });
      item.classList.add("active");
      var sec = document.getElementById("section-" + target);
      if (sec) sec.classList.add("active");
    });
  });

  // ── Theme preview radios ────────────────────────────────────
  var themeInput = document.getElementById("set-default-theme");
  var themeRadios = document.querySelectorAll('input[name="theme-pick"]');
  themeRadios.forEach(function (r) {
    r.addEventListener("change", function () {
      if (themeInput) themeInput.value = r.value;
    });
  });

  // ── Language radios ─────────────────────────────────────────
  var langInput = document.getElementById("set-default-lang");
  var langRadios = document.querySelectorAll('input[name="lang-pick"]');
  langRadios.forEach(function (r) {
    r.addEventListener("change", function () {
      if (langInput) langInput.value = r.value;
    });
  });

  // ── Layout preview radios ───────────────────────────────────
  var layoutInput = document.getElementById("set-layout-style");
  var layoutRadios = document.querySelectorAll('input[name="layout-pick"]');
  layoutRadios.forEach(function (r) {
    r.addEventListener("change", function () {
      if (layoutInput) layoutInput.value = r.value;
    });
  });

  // ── Sidebar width slider ────────────────────────────────────
  var widthSlider = document.getElementById("set-sidebar-width");
  var widthVal = document.getElementById("sidebar-width-val");
  if (widthSlider) {
    widthSlider.addEventListener("input", function () {
      if (widthVal) widthVal.textContent = widthSlider.value + "px";
    });
  }

  // ── Load settings ───────────────────────────────────────────
  function loadSettings() {
    fetch("/general-settings/api").then(function (res) { return res.json(); }).then(function (data) {
      if (!data.success) throw new Error("load");
      var s = data.settings || {};
      var o = data.options || {};

      // Appearance
      var el;
      el = document.getElementById("set-system-name"); if (el) el.value = s.system_name || "";
      el = document.getElementById("set-logo-url"); if (el) el.value = s.system_logo || "";
      el = document.getElementById("set-number-decimals"); if (el) el.value = s.number_decimals || "2";
      el = document.getElementById("set-date-format"); if (el) el.value = s.date_format || "dd/mm/yyyy";

      // Theme
      if (themeInput) themeInput.value = s.default_theme || "light";
      themeRadios.forEach(function (r) { r.checked = r.value === (s.default_theme || "light"); });

      // Language
      if (langInput) langInput.value = s.default_lang || "ar";
      langRadios.forEach(function (r) { r.checked = r.value === (s.default_lang || "ar"); });

      // Layout (from localStorage)
      var savedLayout = localStorage.getItem("dp-layout") || "vertical";
      if (layoutInput) layoutInput.value = savedLayout;
      layoutRadios.forEach(function (r) { r.checked = r.value === savedLayout; });

      // Sidebar width
      var savedWidth = localStorage.getItem("dp-sidebar-width") || "258";
      if (widthSlider) widthSlider.value = savedWidth;
      if (widthVal) widthVal.textContent = savedWidth + "px";

      // Compact menu
      var compactEl = document.getElementById("set-compact-menu");
      if (compactEl) compactEl.checked = localStorage.getItem("dp-compact") === "1";

      // Grouped modules
      var groupedEl = document.getElementById("set-grouped-modules");
      if (groupedEl) groupedEl.checked = localStorage.getItem("dp-grouped") !== "0";

      // Defaults
      fillSelect("set-default-company", (o.companies || []).map(function (c) { return { value: c.id, label: c.name }; }), s.default_company_id);
      fillSelect("set-default-currency", (o.currencies || []).map(function (c) { return { value: c.id, label: c.code + " - " + c.name }; }), s.default_currency_id);
      fillSelect("set-default-year", (o.financial_years || []).map(function (f) { return { value: f.id, label: f.name }; }), s.default_financial_year_id);
      fillSelect("set-default-tax", (o.tax_types || []).map(function (t) { return { value: t.id, label: t.name }; }), s.default_tax_id);

      // Printing
      el = document.getElementById("set-invoice-prefix"); if (el) el.value = s.invoice_prefix || "";
      el = document.getElementById("set-po-prefix"); if (el) el.value = s.po_prefix || "";
      el = document.getElementById("set-contract-prefix"); if (el) el.value = s.contract_prefix || "";
      el = document.getElementById("set-doc-tax-rate"); if (el) el.value = s.doc_default_tax_rate || "";
      el = document.getElementById("set-footer-text"); if (el) el.value = s.doc_footer_text || "";

      // AI (from server settings)
      fetch("/api/server-settings").then(function (r2) { return r2.json(); }).then(function (d2) {
        if (!d2.success) return;
        var gk = document.getElementById("set-gemini-key");
        var gm = document.getElementById("set-gemini-model");
        if (gk) gk.placeholder = d2.gemini_api_key_set ? "••••••••" : "";
        if (gm) gm.value = d2.gemini_model || "gemini-2.0-flash";
      }).catch(function () {});

      // Backup
      el = document.getElementById("set-backup-auto-enabled"); if (el) el.checked = s.backup_auto_enabled === "1" || s.backup_auto_enabled === true;
      el = document.getElementById("set-backup-interval"); if (el) el.value = s.backup_auto_interval_days || "1";
      el = document.getElementById("set-backup-keep"); if (el) el.value = s.backup_auto_keep || "10";
      el = document.getElementById("set-backup-folder"); if (el) el.value = s.backup_auto_folder || "";
      if (s.backup_auto_last) {
        var lastInfo = document.getElementById("backup-last-info");
        var lastVal = document.getElementById("backup-last-value");
        if (lastInfo) lastInfo.style.display = "";
        if (lastVal) lastVal.textContent = s.backup_auto_last;
      }

      // Company
      var companies = o.companies || [];
      fillSelect("set-company-select", companies.map(function (c) { return { value: c.id, label: c.name }; }), "");
      var compSel = document.getElementById("set-company-select");
      if (compSel) {
        compSel.addEventListener("change", function () {
          var cid = compSel.value;
          var comp = companies.find(function (c) { return c.id == cid; });
          if (!comp) return;
          var f = function (id, v) { var e = document.getElementById(id); if (e) e.value = v || ""; };
          f("set-company-name", comp.name);
          f("set-company-legal", comp.legal_name);
          f("set-company-tax", comp.tax_number);
          f("set-company-commercial", comp.commercial_registration);
          f("set-company-phone", comp.phone);
          f("set-company-email", comp.email);
          f("set-company-address", comp.address);
        });
      }

      // Mobile
      el = document.getElementById("set-work-lat"); if (el) el.value = s.mobile_work_lat || "";
      el = document.getElementById("set-work-lng"); if (el) el.value = s.mobile_work_lng || "";
      el = document.getElementById("set-attendance-radius"); if (el) el.value = s.mobile_attendance_radius_meters || "200";
      el = document.getElementById("set-gps-interval"); if (el) el.value = s.mobile_gps_interval_seconds || "30";

    }).catch(function () {
      if (wrap) wrap.innerHTML = '<div class="settings-loading">' + lt("serverSettings.error") + '</div>';
    });
  }

  // ── Use my location ─────────────────────────────────────────
  var locBtn = document.getElementById("set-use-my-location");
  if (locBtn) {
    locBtn.addEventListener("click", function () {
      if (!navigator.geolocation) { alert(lt("settings.locationUnavailable")); return; }
      navigator.geolocation.getCurrentPosition(function (pos) {
        var lat = document.getElementById("set-work-lat");
        var lng = document.getElementById("set-work-lng");
        if (lat) lat.value = pos.coords.latitude.toFixed(6);
        if (lng) lng.value = pos.coords.longitude.toFixed(6);
      }, function () { alert(lt("settings.locationUnavailable")); });
    });
  }

  // ── Save ────────────────────────────────────────────────────
  if (saveBtn) {
    saveBtn.addEventListener("click", function () {
      saveBtn.disabled = true;
      var orig = saveBtn.innerHTML;
      saveBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="10"/></svg> ' + lt("serverSettings.saving");
      hideMsg();

      var v = function (id) { var e = document.getElementById(id); return e ? e.value.trim() : ""; };
      var body = {
        system_name: v("set-system-name"),
        system_logo: v("set-logo-url"),
        default_lang: v("set-default-lang") || "ar",
        default_theme: v("set-default-theme") || "light",
        number_decimals: v("set-number-decimals") || "2",
        date_format: v("set-date-format") || "dd/mm/yyyy",
        default_company_id: v("set-default-company"),
        default_currency_id: v("set-default-currency"),
        default_financial_year_id: v("set-default-year"),
        default_tax_id: v("set-default-tax"),
        invoice_prefix: v("set-invoice-prefix"),
        po_prefix: v("set-po-prefix"),
        contract_prefix: v("set-contract-prefix"),
        doc_default_tax_rate: v("set-doc-tax-rate"),
        doc_footer_text: v("set-footer-text"),
        mobile_work_lat: v("set-work-lat"),
        mobile_work_lng: v("set-work-lng"),
        mobile_attendance_radius_meters: v("set-attendance-radius"),
        mobile_gps_interval_seconds: v("set-gps-interval"),
      };

      // Backup
      var be = document.getElementById("set-backup-auto-enabled");
      body.backup_auto_enabled = be && be.checked ? "1" : "0";
      body.backup_auto_interval_days = v("set-backup-interval") || "1";
      body.backup_auto_keep = v("set-backup-keep") || "10";
      body.backup_auto_folder = v("set-backup-folder");

      fetch("/general-settings/api", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then(function (res) { return res.json(); }).then(function (data) {
        if (data.success) {
          showMsg(lt("settings.saved"), "settings-msg-ok");
          // Apply theme & layout immediately
          var tVal = body.default_theme;
          document.documentElement.dataset.theme = tVal;
          localStorage.setItem("dp-theme", tVal);
          // Layout
          var lVal = v("set-layout-style") || "vertical";
          if (lVal === "horizontal") { document.body.classList.add("layout-horizontal"); } else { document.body.classList.remove("layout-horizontal"); }
          localStorage.setItem("dp-layout", lVal);
          // Sidebar width
          var wVal = v("set-sidebar-width") || "258";
          localStorage.setItem("dp-sidebar-width", wVal);
          document.documentElement.style.setProperty("--sidebar-width", wVal + "px");
          // Compact
          var cEl = document.getElementById("set-compact-menu");
          localStorage.setItem("dp-compact", cEl && cEl.checked ? "1" : "0");
          // Grouped
          var gEl = document.getElementById("set-grouped-modules");
          localStorage.setItem("dp-grouped", gEl && gEl.checked ? "1" : "0");
        } else {
          showMsg(data.message || lt("serverSettings.error"), "settings-msg-error");
        }
      }).catch(function () {
        showMsg(lt("serverSettings.error"), "settings-msg-error");
      }).then(function () {
        saveBtn.disabled = false;
        saveBtn.innerHTML = orig;
      });

      // Save AI settings separately (server settings endpoint)
      var gk = document.getElementById("set-gemini-key");
      var gm = document.getElementById("set-gemini-model");
      if (gk && gk.value.trim()) {
        fetch("/api/server-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ gemini_api_key: gk.value.trim(), gemini_model: gm ? gm.value : "gemini-2.0-flash" }),
        });
      } else if (gm) {
        fetch("/api/server-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ gemini_model: gm.value }),
        });
      }
    });
  }

  loadSettings();
})();

(function () {
  "use strict";

  var T = window.T || {};
  var lt = function (k) { return T[k] !== undefined && T[k] !== null ? T[k] : k; };

  var wrap = document.getElementById("settings-form-wrap");
  if (!wrap) return;

  wrap.style.display = "";

  // ── Helpers ──────────────────────────────────────────────────
  function v(id) { var e = document.getElementById(id); return e ? e.value.trim() : ""; }
  function c(id) { var e = document.getElementById(id); return e ? e.checked : false; }
  function setVal(id, val) { var e = document.getElementById(id); if (e) e.value = val || ""; }

  function csrfHeaders() {
    var h = { "Content-Type": "application/json" };
    if (window.CSRF_TOKEN) h["X-CSRF-Token"] = window.CSRF_TOKEN;
    return h;
  }

  function showSectionMsg(el, text, kind) {
    if (!el) return;
    el.textContent = text;
    el.className = "settings-section-msg msg-" + (kind || "ok");
    setTimeout(function () { el.textContent = ""; el.className = "settings-section-msg"; }, 4000);
  }

  function optHTML(value, label) {
    return '<option value="' + value + '">' + escapeHtml(label) + '</option>';
  }
  function fillSelect(id, options, selected) {
    var sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = '<option value="">' + lt("common.choose") + '</option>';
    options.forEach(function (o) { sel.innerHTML += optHTML(o.value, o.label); });
    if (selected !== undefined && selected !== null) sel.value = selected;
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

  // ── Per-section Save ────────────────────────────────────────
  function gatherSectionData(section) {
    switch (section) {
      case "profile":
        return { system_name: v("set-system-name"), system_logo: v("set-logo-url") };
      case "appearance":
        return {
          default_theme: v("set-default-theme") || "light",
          default_lang: v("set-default-lang") || "ar",
          number_decimals: v("set-number-decimals") || "2",
          date_format: v("set-date-format") || "dd/mm/yyyy",
        };
      case "documents":
        return {
          invoice_prefix: v("set-invoice-prefix"),
          po_prefix: v("set-po-prefix"),
          contract_prefix: v("set-contract-prefix"),
          renewal_prefix: v("set-renewal-prefix"),
          payment_prefix: v("set-payment-prefix"),
          doc_default_tax_rate: v("set-doc-tax-rate"),
          doc_footer_text: v("set-footer-text"),
        };
      case "defaults":
        return {
          default_company_id: v("set-default-company"),
          default_currency_id: v("set-default-currency"),
          default_financial_year_id: v("set-default-year"),
          default_tax_id: v("set-default-tax"),
        };
      case "realestate":
        return {
          realestate_max_discount_percent: v("set-realestate-max-discount"),
          realestate_vat_percent: v("set-realestate-vat"),
          realestate_contract_approval: c("set-realestate-approval") ? "1" : "0",
        };
      case "rentals":
        return {
          rental_escalation_enabled: c("set-rental-escalation-enabled") ? "1" : "0",
          rental_escalation_percent: v("set-rental-escalation-percent"),
        };
      case "sales":
        return { sales_commission_rate: v("set-sales-commission-rate") };
      case "einvoice":
        return {
          einv_enabled: v("set-einv-enabled") === "true" ? "1" : (v("set-einv-enabled") === "false" ? "0" : ""),
          einv_country: v("set-einv-country") || "EG",
          einv_mode: v("set-einv-mode") || "",
          einv_environment: v("set-einv-environment") || "preprod",
          einv_client_id: v("set-einv-client-id"),
          einv_client_secret: v("set-einv-client-secret"),
          einv_api_key: v("set-einv-api-key"),
          einv_provider_url: v("set-einv-provider-url"),
          einv_activity_code: v("set-einv-activity-code"),
        };
      case "backup":
        return {
          backup_auto_enabled: c("set-backup-auto-enabled") ? "1" : "0",
          backup_auto_interval_days: v("set-backup-interval") || "1",
          backup_auto_keep: v("set-backup-keep") || "10",
          backup_auto_folder: v("set-backup-folder"),
          backup_encryption_password: v("set-backup-encryption-password"),
        };
      case "mobile":
        return {
          mobile_work_lat: v("set-work-lat"),
          mobile_work_lng: v("set-work-lng"),
          mobile_attendance_radius_meters: v("set-attendance-radius"),
          mobile_gps_interval_seconds: v("set-gps-interval"),
          fcm_server_key: v("set-fcm-server-key"),
        };
      default:
        return {};
    }
  }

  function applySectionEffects(section, body) {
    if (section === "appearance") {
      document.documentElement.dataset.theme = body.default_theme;
      localStorage.setItem("dp-theme", body.default_theme);
      if (body.default_lang) {
        document.cookie = "lang=" + encodeURIComponent(body.default_lang) + ";path=/;max-age=" + (60 * 60 * 24 * 365);
        setTimeout(function () { window.location.reload(); }, 100);
        return;
      }
    }
  }

  function saveSection(section, btn) {
    var msgEl = document.getElementById("section-msg-" + section);
    btn.disabled = true;
    var origHTML = btn.innerHTML;
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="10"/></svg> ...';

    var body = gatherSectionData(section);

    if (section === "ai") {
      saveAI(btn, msgEl, origHTML);
      return;
    }
    if (section === "company") {
      saveCompany(btn, msgEl, origHTML);
      return;
    }

    fetch("/general-settings/api/" + section, {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify(body),
    }).then(function (res) { return res.json(); }).then(function (data) {
      if (data.success) {
        showSectionMsg(msgEl, lt("settings.sectionSaved"), "ok");
        applySectionEffects(section, body);
      } else {
        showSectionMsg(msgEl, lt("settings.sectionError"), "error");
      }
    }).catch(function () {
      showSectionMsg(msgEl, lt("settings.sectionError"), "error");
    }).then(function () {
      btn.disabled = false;
      btn.innerHTML = origHTML;
    });
  }

  // ── AI Settings (multi-provider) ────────────────────────────
  var AI_PROVIDERS = ["gemini", "groq", "openrouter", "cerebras", "mistral", "qwen"];

  function saveAI(btn, msgEl, origHTML) {
    var providers = {};
    AI_PROVIDERS.forEach(function (name) {
      var card = document.querySelector('.ai-provider-card[data-provider="' + name + '"]');
      if (!card) return;
      var enabled = card.querySelector(".ai-enabled");
      var apiKey = card.querySelector(".ai-api-key");
      var model = card.querySelector(".ai-model");
      var entry = {
        enabled: enabled ? enabled.checked : false,
        model: model ? model.value : "",
      };
      // Only send api_key if the user typed something (not placeholder)
      if (apiKey && apiKey.value.trim()) {
        entry.api_key = apiKey.value.trim();
      }
      providers[name] = entry;
    });
    fetch("/api/server-settings", {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify({ ai_providers: providers }),
    }).then(function (res) { return res.json(); }).then(function (data) {
      if (data.success) {
        showSectionMsg(msgEl, lt("settings.sectionSaved"), "ok");
        // Clear password fields after save
        AI_PROVIDERS.forEach(function (name) {
          var card = document.querySelector('.ai-provider-card[data-provider="' + name + '"]');
          if (card) {
            var apiKey = card.querySelector(".ai-api-key");
            if (apiKey) { apiKey.value = ""; apiKey.placeholder = "••••••••"; }
          }
        });
      } else {
        showSectionMsg(msgEl, lt("settings.sectionError"), "error");
      }
    }).catch(function () {
      showSectionMsg(msgEl, lt("settings.sectionError"), "error");
    }).then(function () {
      btn.disabled = false;
      btn.innerHTML = origHTML;
    });
  }

  // ── AI Provider Test ────────────────────────────────────────
  document.querySelectorAll(".ai-test-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var name = btn.getAttribute("data-provider");
      var card = document.querySelector('.ai-provider-card[data-provider="' + name + '"]');
      if (!card) return;
      var apiKey = card.querySelector(".ai-api-key");
      var model = card.querySelector(".ai-model");
      var key = apiKey ? apiKey.value.trim() : "";
      var mdl = model ? model.value : "";
      if (!key || !mdl) {
        alert("أدخل المفتاح والنموذج أولاً");
        return;
      }
      btn.disabled = true;
      btn.textContent = "جاري الاختبار...";
      fetch("/api/ai-provider-test", {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify({ name: name, api_key: key, model: mdl }),
      }).then(function (r) { return r.json(); }).then(function (data) {
        if (data.success) {
          alert("✅ نجح الاتصال!\n" + (data.response || "").substring(0, 150));
        } else {
          alert("❌ فشل الاتصال:\n" + (data.error || "unknown error"));
        }
      }).catch(function (e) {
        alert("❌ خطأ: " + e.message);
      }).then(function () {
        btn.disabled = false;
        btn.textContent = "اختبار الاتصال";
      });
    });
  });

  // ── AI Provider enable/disable toggle ────────────────────────
  document.querySelectorAll(".ai-enabled").forEach(function (chk) {
    chk.addEventListener("change", function () {
      var card = chk.closest(".ai-provider-card");
      if (card) card.classList.toggle("ai-provider-enabled", chk.checked);
    });
  });
  // Initialize on load
  document.querySelectorAll(".ai-provider-card").forEach(function (card) {
    var chk = card.querySelector(".ai-enabled");
    if (chk && chk.checked) card.classList.add("ai-provider-enabled");
  });

  // ── Company Save (separate endpoint) ─────────────────────────
  function saveCompany(btn, msgEl, origHTML) {
    var sel = document.getElementById("set-company-select");
    var body = {
      id: sel ? sel.value : "",
      name: v("set-company-name"),
      legal_name: v("set-company-legal"),
      tax_number: v("set-company-tax"),
      commercial_registration: v("set-company-commercial"),
      phone: v("set-company-phone"),
      email: v("set-company-email"),
      address: v("set-company-address"),
      website: v("set-company-website"),
    };
    if (!body.id) {
      showSectionMsg(msgEl, lt("settings.noCompanySelected"), "error");
      btn.disabled = false;
      btn.innerHTML = origHTML;
      return;
    }
    fetch("/general-settings/api/company", {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify(body),
    }).then(function (res) { return res.json(); }).then(function (data) {
      if (data.success) {
        showSectionMsg(msgEl, lt("settings.sectionSaved"), "ok");
      } else {
        showSectionMsg(msgEl, lt("settings.sectionError"), "error");
      }
    }).catch(function () {
      showSectionMsg(msgEl, lt("settings.sectionError"), "error");
    }).then(function () {
      btn.disabled = false;
      btn.innerHTML = origHTML;
    });
  }

  // ── Bind per-section save buttons ───────────────────────────
  document.querySelectorAll(".settings-section-save").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var section = btn.getAttribute("data-section");
      if (section) saveSection(section, btn);
    });
  });

  // ── Use my location ─────────────────────────────────────────
  var locBtn = document.getElementById("set-use-my-location");
  if (locBtn) {
    locBtn.addEventListener("click", function () {
      if (!navigator.geolocation) { alert(lt("settings.locationUnavailable")); return; }
      navigator.geolocation.getCurrentPosition(function (pos) {
        setVal("set-work-lat", pos.coords.latitude.toFixed(6));
        setVal("set-work-lng", pos.coords.longitude.toFixed(6));
      }, function () { alert(lt("settings.locationUnavailable")); });
    });
  }

  // ── Load settings ───────────────────────────────────────────
  function loadSettings() {
    fetch("/general-settings/api").then(function (res) { return res.json(); }).then(function (data) {
      if (!data.success) throw new Error("load");
      var s = data.settings || {};
      var o = data.options || {};

      // Profile
      setVal("set-system-name", s.system_name);
      setVal("set-logo-url", s.system_logo);

      // Appearance
      setVal("set-number-decimals", s.number_decimals || "2");
      setVal("set-date-format", s.date_format || "dd/mm/yyyy");
      if (themeInput) themeInput.value = s.default_theme || "light";
      themeRadios.forEach(function (r) { r.checked = r.value === (s.default_theme || "light"); });
      if (langInput) langInput.value = s.default_lang || "ar";
      langRadios.forEach(function (r) { r.checked = r.value === (s.default_lang || "ar"); });

      // Documents
      setVal("set-invoice-prefix", s.invoice_prefix);
      setVal("set-po-prefix", s.po_prefix);
      setVal("set-contract-prefix", s.contract_prefix);
      setVal("set-renewal-prefix", s.renewal_prefix);
      setVal("set-payment-prefix", s.payment_prefix);
      setVal("set-doc-tax-rate", s.doc_default_tax_rate);
      setVal("set-footer-text", s.doc_footer_text);

      // Defaults
      fillSelect("set-default-company", (o.companies || []).map(function (c) { return { value: c.id, label: c.name }; }), s.default_company_id);
      fillSelect("set-default-currency", (o.currencies || []).map(function (c) { return { value: c.id, label: c.code + " - " + c.name }; }), s.default_currency_id);
      fillSelect("set-default-year", (o.financial_years || []).map(function (f) { return { value: f.id, label: f.name }; }), s.default_financial_year_id);
      fillSelect("set-default-tax", (o.tax_types || []).map(function (t) { return { value: t.id, label: t.name }; }), s.default_tax_id);

      // Real Estate
      setVal("set-realestate-max-discount", s.realestate_max_discount_percent);
      setVal("set-realestate-vat", s.realestate_vat_percent);
      var ra = document.getElementById("set-realestate-approval");
      if (ra) ra.checked = s.realestate_contract_approval === "1" || s.realestate_contract_approval === true;

      // Rentals
      var re = document.getElementById("set-rental-escalation-enabled");
      if (re) re.checked = s.rental_escalation_enabled === "1" || s.rental_escalation_enabled === true;
      setVal("set-rental-escalation-percent", s.rental_escalation_percent);

      // Sales
      setVal("set-sales-commission-rate", s.sales_commission_rate);

      // E-Invoicing
      var ee = document.getElementById("set-einv-enabled");
      if (ee) ee.value = s.einv_enabled === "1" || s.einv_enabled === true ? "true" : (s.einv_enabled === "0" ? "false" : "");
      setVal("set-einv-country", s.einv_country || "EG");
      setVal("set-einv-mode", s.einv_mode || "");
      setVal("set-einv-environment", s.einv_environment || "preprod");
      setVal("set-einv-client-id", s.einv_client_id);
      var ecs = document.getElementById("set-einv-client-secret");
      if (ecs) { ecs.value = ""; ecs.placeholder = s.einv_client_secret_set ? "••••••••" : ""; }
      var eak = document.getElementById("set-einv-api-key");
      if (eak) { eak.value = ""; eak.placeholder = s.einv_api_key_set ? "••••••••" : ""; }
      setVal("set-einv-provider-url", s.einv_provider_url);
      setVal("set-einv-activity-code", s.einv_activity_code);

      // Backup
      var ba = document.getElementById("set-backup-auto-enabled");
      if (ba) ba.checked = s.backup_auto_enabled === "1" || s.backup_auto_enabled === true;
      setVal("set-backup-interval", s.backup_auto_interval_days || "1");
      setVal("set-backup-keep", s.backup_auto_keep || "10");
      setVal("set-backup-folder", s.backup_auto_folder);
      var bep = document.getElementById("set-backup-encryption-password");
      if (bep) { bep.value = ""; bep.placeholder = s.backup_encryption_password_set ? "••••••••" : ""; }
      if (s.backup_auto_last) {
        var lastInfo = document.getElementById("backup-last-info");
        var lastVal = document.getElementById("backup-last-value");
        if (lastInfo) lastInfo.style.display = "";
        if (lastVal) lastVal.textContent = s.backup_auto_last;
      }

      // Mobile
      setVal("set-work-lat", s.mobile_work_lat);
      setVal("set-work-lng", s.mobile_work_lng);
      setVal("set-attendance-radius", s.mobile_attendance_radius_meters || "200");
      setVal("set-gps-interval", s.mobile_gps_interval_seconds || "30");
      var fcm = document.getElementById("set-fcm-server-key");
      if (fcm) { fcm.value = ""; fcm.placeholder = s.fcm_server_key_set ? "••••••••" : ""; }

      // Company
      var companies = o.companies || [];
      fillSelect("set-company-select", companies.map(function (c) { return { value: c.id, label: c.name }; }), "");
      var compSel = document.getElementById("set-company-select");
      if (compSel) {
        compSel.addEventListener("change", function () {
          var cid = compSel.value;
          var comp = companies.find(function (c) { return c.id == cid; });
          if (!comp) return;
          setVal("set-company-name", comp.name);
          setVal("set-company-legal", comp.legal_name);
          setVal("set-company-tax", comp.tax_number);
          setVal("set-company-commercial", comp.commercial_registration);
          setVal("set-company-phone", comp.phone);
          setVal("set-company-email", comp.email);
          setVal("set-company-address", comp.address);
          setVal("set-company-website", comp.website);
        });
      }

      // AI (from server settings — multi-provider)
      fetch("/api/server-settings").then(function (r2) { return r2.json(); }).then(function (d2) {
        if (!d2.success) return;
        var providers = d2.ai_providers || {};
        AI_PROVIDERS.forEach(function (name) {
          var card = document.querySelector('.ai-provider-card[data-provider="' + name + '"]');
          if (!card) return;
          var pcfg = providers[name] || {};
          var enabled = card.querySelector(".ai-enabled");
          var apiKey = card.querySelector(".ai-api-key");
          var model = card.querySelector(".ai-model");
          if (enabled) enabled.checked = !!pcfg.enabled;
          if (apiKey) apiKey.placeholder = pcfg.api_key_set ? "••••••••" : "";
          if (model && pcfg.model) model.value = pcfg.model;
        });
      }).catch(function () {});

      // Server (read-only info)
      setVal("set-server-port", window.location.port || "80");

    }).catch(function () {
      if (wrap) wrap.innerHTML = '<div class="settings-loading">' + lt("settings.sectionError") + '</div>';
    });
  }

  loadSettings();

  // ── Factory Reset ──
  var btnPreview = document.getElementById("btn-reset-preview");
  var btnExecute = document.getElementById("btn-reset-execute");
  var confirmInput = document.getElementById("reset-confirm-input");
  var resetMsg = document.getElementById("reset-msg");

  if (btnPreview) {
    btnPreview.addEventListener("click", function () {
      btnPreview.disabled = true;
      btnPreview.textContent = "جاري المعاينة...";
      fetch("/api/factory-reset/preview", {
        method: "POST",
        headers: { "X-CSRF-Token": CSRF_TOKEN }
      }).then(function (r) { return r.json(); }).then(function (d) {
        btnPreview.disabled = false;
        btnPreview.textContent = "معاينة";
        if (!d.success) { resetMsg.textContent = d.message || "خطأ"; resetMsg.style.color = "#dc3545"; return; }
        var preview = d.preview;
        var wrap = document.getElementById("reset-preview");
        var summary = document.getElementById("reset-summary-text");
        var tbody = document.querySelector("#reset-preview-table tbody");
        wrap.style.display = "block";
        summary.textContent = "إجمالي: " + preview.total_rows + " صف سيُحذف من " + preview.items.length + " جدول";
        tbody.innerHTML = "";
        preview.items.forEach(function (item) {
          var tr = document.createElement("tr");
          tr.innerHTML = "<td>" + item.table + "</td><td>" + item.description + "</td><td>" + item.count + "</td>";
          tbody.appendChild(tr);
        });
      }).catch(function () {
        btnPreview.disabled = false;
        btnPreview.textContent = "معاينة";
        resetMsg.textContent = "خطأ في الاتصال";
        resetMsg.style.color = "#dc3545";
      });
    });
  }

  if (confirmInput) {
    confirmInput.addEventListener("input", function () {
      btnExecute.disabled = confirmInput.value.trim() !== "RESET";
    });
  }

  if (btnExecute) {
    btnExecute.addEventListener("click", function () {
      if (!confirm("هل أنت متأكد من حذف جميع البيانات؟")) return;
      btnExecute.disabled = true;
      btnExecute.textContent = "جاري الحذف...";
      fetch("/api/factory-reset", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF_TOKEN },
        body: JSON.stringify({
          confirm: confirmInput.value.trim(),
          seed_demo: document.getElementById("reset-seed-demo").checked
        })
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (d.success) {
          resetMsg.textContent = "تم! " + d.total_deleted + " صف تم حذفه. إعادة تحميل...";
          resetMsg.style.color = "#28a745";
          setTimeout(function () { location.reload(); }, 2000);
        } else {
          resetMsg.textContent = d.error || d.message || "خطأ";
          resetMsg.style.color = "#dc3545";
          btnExecute.disabled = false;
          btnExecute.textContent = "حذف جميع البيانات";
        }
      }).catch(function () {
        resetMsg.textContent = "خطأ في الاتصال";
        resetMsg.style.color = "#dc3545";
        btnExecute.disabled = false;
        btnExecute.textContent = "حذف جميع البيانات";
      });
    });
  }
})();

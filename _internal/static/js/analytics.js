/* لوحة التحليل التنفيذي — تحميل المؤشرات والتنبيهات محلياً */
(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function money(n, sym) {
    var v = Number(n || 0);
    var s = v.toLocaleString("en-US", { maximumFractionDigits: 2 });
    return sym ? s + " " + sym : s;
  }
  function fmtDate(iso) {
    if (!iso) return "—";
    var d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("en-GB");
  }

  var SYMBOL = "";
  var charts = [];

  function fetchJS(url, cb) {
    fetch(url, {
      method: "GET",
      headers: { "X-CSRF-Token": window.CSRF_TOKEN || "" }
    }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(cb).catch(function (err) {
      if (parseInt(err.message.split(" ")[1]) === 403) {
        $("anx-loading").textContent = "لا تملك صلاحية الوصول للتحليلات.";
      } else {
        $("anx-loading").textContent = "تعذر تحميل البيانات: " + err.message;
      }
    });
  }

  function kpiCard(label, icon, value, cls) {
    var div = document.createElement("div");
    div.className = "anx-kpi " + (cls || "");
    div.innerHTML =
      '<div class="anx-kpi-label">' + icon + " " + esc(label) + "</div>" +
      '<div class="anx-kpi-value">' + value + "</div>";
    return div;
  }

  function renderKPIs(k) {
    var g = $("anx-kpis");
    function card(l, ic, v, cls) {
      g.appendChild(kpiCard(l, ic, "<span>" + v + "</span>", cls));
    }
    card("إجمالي المبيعات", "💵", money(k.revenue, SYMBOL));
    card("المحصل من المبيعات", "✅", money(k.revenue_paid, SYMBOL));
    card("مستحق من المبيعات", "⏳", money(k.revenue_pending, SYMBOL), k.revenue_pending > 0 ? "warn" : "good");
    card("إجمالي المصروفات", "🧾", money(k.expenses, SYMBOL));
    card("صافي النتيجة", "📈", money(k.net_margin, SYMBOL), k.net_margin >= 0 ? (k.net_margin > 0 ? "good" : "") : "bad");
    card("الذمم المدينة", "🏦", money(k.receivables, SYMBOL), k.receivables > 0 ? "warn" : "");
    card("الذمم المتأخرة", "🚨", money(k.receivables_overdue, SYMBOL), k.receivables_overdue > 0 ? "bad" : "good");
    card("الذمم الدائنة", "🔄", money(k.payables, SYMBOL));
    card("قيمة المخزون", "📦", money(k.stock_value, SYMBOL));
    card("بنود إعادة الطلب", "⚠️", k.low_stock_items, k.low_stock_items > 0 ? "bad" : "good");
    card("عدد العملاء", "👥", k.customers_count);
    card("عدد الموردين", "🚚", k.suppliers_count);
  }

  function mkChart(id, config, emptyMsg) {
    var el = $(id);
    if (config.data && config.data.labels && config.data.labels.length) {
      if (typeof Chart !== "undefined") {
        charts.push(new Chart(el, config));
      } else {
        el.parentElement.innerHTML = '<div class="anx-empty">مكتبة الرسم البياني غير متاحة</div>';
      }
    } else {
      el.parentElement.innerHTML = '<div class="anx-empty">' + esc(emptyMsg) + "</div>";
    }
  }

  function renderTrend(trend) {
    mkChart("anx-chart-trend", {
      type: "line",
      data: {
        labels: trend.map(function (m) { return m.month; }),
        datasets: [
          {
            label: "الإيرادات",
            data: trend.map(function (m) { return m.revenue; }),
            borderColor: "#30a46c",
            backgroundColor: "rgba(48,164,108,.15)",
            fill: true,
            tension: .35,
            pointRadius: 2,
            borderWidth: 2
          },
          {
            label: "المصروفات",
            data: trend.map(function (m) { return m.expenses; }),
            borderColor: "#e5484d",
            backgroundColor: "rgba(229,72,77,.12)",
            fill: true,
            tension: .35,
            pointRadius: 2,
            borderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: { y: { beginAtZero: true } }
      }
    }, "لا توجد بيانات اتجاه بعد — حرّر فواتير لعرض الاتجاه");
  }

  function renderAging(aging) {
    var labels = {
      "0_30": "أقل من 30 يوم",
      "31_60": "31 - 60 يوم",
      "61_90": "61 - 90 يوم",
      "90_plus": "أكثر من 90 يوم"
    };
    var keys = ["0_30", "31_60", "61_90", "90_plus"];
    mkChart("anx-chart-aging", {
      type: "doughnut",
      data: {
        labels: keys.map(function (k) { return labels[k]; }),
        datasets: [{
          data: keys.map(function (k) { return aging[k] || 0; }),
          backgroundColor: ["#30a46c", "#f5a623", "#f76b15", "#e5484d"]
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } }
      }
    }, "لا توجد ذمم متأخرة 🎉");
  }

  function renderProducts(top) {
    mkChart("anx-chart-products", {
      type: "bar",
      data: {
        labels: top.map(function (p) {
          var t = (p.name || "").length > 22 ? p.name.slice(0, 22) + "…" : p.name;
          return t;
        }).reverse(),
        datasets: [{
          label: "الإيراد",
          data: top.map(function (p) { return p.revenue; }).reverse(),
          backgroundColor: "#3b82f6",
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } }
      }
    }, "لا توجد بيانات منتجات");
  }

  function renderCustomers(top) {
    mkChart("anx-chart-customers", {
      type: "bar",
      data: {
        labels: top.map(function (c) {
          var t = (c.name || "").length > 22 ? c.name.slice(0, 22) + "…" : c.name;
          return t;
        }).reverse(),
        datasets: [{
          label: "الإيراد",
          data: top.map(function (c) { return c.revenue; }).reverse(),
          backgroundColor: "#8e4ec6",
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } }
      }
    }, "لا توجد بيانات عملاء");
  }

  function renderLowStock(list) {
    var wrap = $("anx-lowstock");
    if (!list || !list.length) {
      wrap.innerHTML = '<div class="anx-empty">ممتاز — لا توجد بنود تحت مستوى إعادة الطلب ✅</div>';
      return;
    }
    var rows = list.map(function (it) {
      return "<tr><td><b>" + esc(it.name) + "</b><div style='color:var(--text-muted);font-size:.72rem'>" +
        esc(it.code) + "</div></td><td>" + it.quantity + "</td><td>" + it.reorder_level +
        "</td><td>" + (it.monthly_consumption || "—") + "</td><td>" +
        (it.suggested_order != null ? "<b>" + it.suggested_order + "</b>" : "—") +
        "</td></tr>";
    }).join("");
    wrap.innerHTML =
      '<table class="anx-table"><thead><tr><th>العنصر</th><th>الكمية</th><th>الحد الأدنى</th><th>الاستهلاك/شهر</th><th>اقتراح الطلب</th></tr></thead><tbody>' +
      rows + "</tbody></table>";
  }

  function renderReorder(list) {
    var wrap = $("anx-reorder");
    if (!list || !list.length) {
      wrap.innerHTML = '<div class="anx-empty">لا توجد توصيات طلب حالياً ✅</div>';
      return;
    }
    var rows = list.map(function (it) {
      var badge = it.urgency === "critical"
        ? '<span class="anx-badge critical">نفد</span>'
        : '<span class="anx-badge warning">منخفض</span>';
      return "<tr><td><b>" + esc(it.name) + "</b><div style='color:var(--text-muted);font-size:.72rem'>" +
        esc(it.code) + "</div></td><td>" + it.quantity + "</td><td>" + it.reorder_level +
        "</td><td>" + (it.monthly_consumption || "—") + "</td><td>" +
        (it.coverage_days != null ? it.coverage_days : "∞") + "</td><td><b>" + it.suggested_order +
        "</b></td><td>" + badge + "</td></tr>";
    }).join("");
    wrap.innerHTML =
      '<table class="anx-table"><thead><tr><th>العنصر</th><th>الرصيد</th><th>الحد الأدنى</th><th>استهلاك/شهر</th><th>أيام التغطية</th><th>كمية الطلب</th><th>الحالة</th></tr></thead><tbody>' +
      rows + "</tbody></table>";
  }

  function renderProjects(list) {
    var wrap = $("anx-projects");
    if (!list || !list.length) {
      wrap.innerHTML = '<div class="anx-empty">لا توجد مشاريع نشطة</div>';
      return;
    }
    var rows = list.map(function (p) {
      var risk = p.at_risk
        ? '<span class="anx-badge warning">مخاطر</span>'
        : '<span class="anx-badge ok">ضمن الخطة</span>';
      var bar = '<div style="background:var(--surface-2);border-radius:6px;height:8px;overflow:hidden;min-width:70px">' +
        '<div style="height:100%;width:' + Math.min(100, p.completion) + '%;background:' +
        (p.at_risk ? "#f76b15" : "#30a46c") + ';border-radius:6px"></div></div>';
      return "<tr><td><b>" + esc(p.name) + "</b><div style='color:var(--text-muted);font-size:.72rem'>" +
        esc(p.code || p.id) + "</div></td><td>" + p.completion + "%</td><td>" +
        p.spent.toLocaleString("en-US", { maximumFractionDigits: 0 }) + " / " +
        p.budget.toLocaleString("en-US", { maximumFractionDigits: 0 }) +
        "</td><td>" + bar + "</td><td>" + (p.deadline ? fmtDate(p.deadline) : "—") +
        "</td><td>" + risk + "</td></tr>";
    }).join("");
    wrap.innerHTML =
      '<table class="anx-table"><thead><tr><th>المشروع</th><th>الإنجاز</th><th>مصروف / ميزانية</th><th>الاتجاه</th><th>الموعد</th><th>الحالة</th></tr></thead><tbody>' +
      rows + "</tbody></table>";
  }

  function renderAlerts(data) {
    var list = data.alerts || [];
    var badges = $("anx-badges");
    var wrap = $("anx-alerts");
    var s = data.summary || {};
    badges.innerHTML =
      '<span class="anx-badge critical">حرج: ' + (s.critical || 0) + "</span>" +
      '<span class="anx-badge warning">مهم: ' + (s.warning || 0) + "</span>" +
      '<span class="anx-badge info">معلومات: ' + (s.info || 0) + "</span>" +
      '<span class="anx-badge ok">متابعة: ' + list.length + "</span>";
    if (!list.length) {
      wrap.innerHTML = '<div class="anx-empty">لا توجد تنبيهات تستدعي الانتباه 🎉</div>';
      return;
    }
    var icons = {
      low_stock: "📦", overdue_invoice: "🚨", contract_expiring: "📅",
      pending_po: "🛒", expired_quotes: "💼", project_at_risk: "🏗️"
    };
    var html = list.map(function (a) {
      var link = a.link ? ' <a href="' + esc(a.link) + '" style="color:var(--accent,var(--primary));font-size:.74rem;text-decoration:none">افتح ←</a>' : "";
      return '<div class="anx-alert"><span class="anx-dot ' + esc(a.severity) + '"></span>' +
        "<div><b>(" + (icons[a.type] || "•") + ") " + esc(a.title) + " " + link + "</b>" +
        "<p>" + esc(a.detail) + "</p></div></div>";
    }).join("");
    wrap.innerHTML = html;
  }

  function renderRoadmap() {
    $("anx-roadmap").innerHTML =
      '<ul style="margin:0;padding-right:18px">' +
      "<li><b>مُنفَّذ:</b> تحليلات تنفيذية محلية، تنبيهات ذكية، توصيات كميات إعادة الطلب، مؤشرات مشاريع (ميزانية/مخاطر)، PWA، بيع/تجديد سنوي في لوحة /admin</li>" +
      "<li><b>قائم أصلاً:</b> فواتير إلكترونية (22 دولة، منها ETA و ZATCA)، نسخ احتياطي مشفّر AES-256 GCM مع مجدول تلقائي</li>" +
      "<li><b>مؤجَّل:</b> OCR للفواتير الورقية، مساعد ذكي عربي، وحدات دول الخليج — تحتاج نماذج/اتصال خارجي. التفاصيل في ROADMAP_2026.md</li>" +
      "</ul>";
  }

  function renderEinv() {
    $("anx-einv").innerHTML =
      '<ul style="margin:0;padding-right:18px">' +
      "<li>مصر ETA: الإلزام فوق عتبة 250,000 ج.م بدءاً من 31/3/2026 — النظام يدعم التقديم عبر منظومة الفاتورة الإلكترونية.</li>" +
      "<li>السعودية ZATCA + 20 دولة عربية أخرى مدعومة في موحّد الأدوات (<code style='direction:ltr'>utils/einvoice.py</code>).</li>" +
      "<li>يبقى تفعيل الإرسال الفعلي: شهادة x.509 وبيانات اعتماد المنظومة لكل شركة (إعدادات الفوترة الإلكترونية).</li>" +
      "</ul>";
  }

  function load() {
    fetchJS("/api/bi/analytics", function (data) {
      SYMBOL = (data.currency && data.currency.symbol) || "";
      renderKPIs(data.kpis || {});
      renderTrend(data.trend || []);
      renderAging(data.aging || {});
      renderProducts(data.top_products || []);
      renderCustomers(data.top_customers || []);
      renderLowStock(data.low_stock_list || []);
      renderReorder(data.reorder_recommendations || []);
      renderProjects((data.projects && data.projects.projects) || []);
      renderRoadmap();
      renderEinv();
      $("anx-loading").hidden = true;
      $("anx-body").hidden = false;
    });
    fetchJS("/api/bi/alerts", renderAlerts);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
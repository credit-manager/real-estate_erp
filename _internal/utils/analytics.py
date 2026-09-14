"""التحليلات التنفيذية والتنبيهات الذكية.

تُحسب مؤشرات الأداء الرئيسية (KPIs) والتنبيهات مباشرة من بيانات شركة ERP
بدون أي اعتماد خارجي — متاحة محلياً وأميناً للبيانات.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import case as sa_case
from sqlalchemy import func as sa_func

from database import db
from models import (
    Currency, Customer, Invoice, InvoiceItem, Item, ItemStock,
    Project, ProjectMilestone, PurchaseOrder, Quote, RentalContract,
    StockMovement, Supplier,
)

# حركات تخريد المخزون (استهلاك فعلي) — نقل المخزون بين المخازن لا يُعد استهلاكاً.
_OUT_TYPES = {"out", "production_out", "sale", "consumption", "waste"}
_LOOKBACK_DAYS = 90


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _currency_info():
    c = Currency.query.filter_by(is_base=True).first()
    if c:
        return {"code": c.code, "symbol": c.symbol or c.code, "name": c.name or c.code}
    return None


def _trend(months=12):
    today = datetime.now()
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    keys.reverse()

    trend = {k: {"revenue": 0.0, "expenses": 0.0} for k in keys}
    rows = db.session.query(
        sa_func.extract("year", Invoice.issue_date),
        sa_func.extract("month", Invoice.issue_date),
        Invoice.invoice_type,
        sa_func.coalesce(sa_func.sum(Invoice.amount), 0),
    ).filter(Invoice.issue_date.isnot(None)).group_by(
        sa_func.extract("year", Invoice.issue_date),
        sa_func.extract("month", Invoice.issue_date),
        Invoice.invoice_type,
    ).all()
    for row in rows:
        k = (int(row[0]), int(row[1]))
        if k in trend:
            amt = _f(row[3])
            if row[2] == "sales":
                trend[k]["revenue"] += amt
            elif row[2] == "purchase":
                trend[k]["expenses"] += amt

    return [
        {"month": f"{y}-{m:02d}", **v} for (y, m), v in trend.items()
    ]


def _aging_buckets():
    """توزيع الذمم المتأخرة للمبيعات حسب عمر الدين (بالأيام)."""
    today = date.today()
    c90 = today - timedelta(days=90)
    c60 = today - timedelta(days=60)
    c30 = today - timedelta(days=30)
    expr = sa_case(
        (Invoice.due_date < c90, "90_plus"),
        (Invoice.due_date < c60, "61_90"),
        (Invoice.due_date < c30, "31_60"),
        else_="0_30",
    )
    rows = db.session.query(
        expr,
        sa_func.coalesce(sa_func.sum(Invoice.amount - Invoice.paid_amount), 0),
    ).filter(
        Invoice.invoice_type == "sales",
        Invoice.due_date.isnot(None),
        Invoice.due_date < today,
        Invoice.amount > Invoice.paid_amount,
    ).group_by(expr).all()
    buckets = {"0_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}
    for label, amt in rows:
        buckets[label or "0_30"] = round(_f(amt), 2)
    return buckets


def _stock_rows(cap=100000):
    """كل عنصر مع مجموع الكميات ونقطة إعادة الطلب (البنود المفعّلة فقط)."""
    return db.session.query(
        Item.id, Item.name, Item.code, Item.cost_price, Item.reorder_level,
        sa_func.coalesce(sa_func.sum(ItemStock.quantity), 0),
    ).outerjoin(ItemStock).filter(Item.is_active.is_(True)).group_by(
        Item.id, Item.name, Item.code, Item.cost_price, Item.reorder_level,
    ).all()


def _consumption(item_id):
    """متوسط الاستهلاك الشهري لعنصر من حركات المخزون خلال نافذة الاسترجاع.

    يعيد (monthly_rate, coverage_days):
      - monthly_rate: استهلاك شهري تقريبي (وحدة/شهر)
      - coverage_days: عدد أيام التغطية حسب المعدل الحالي (None إن لم يوجد استهلاك)
    """
    cutoff = datetime.now() - timedelta(days=_LOOKBACK_DAYS)
    rows = db.session.query(
        sa_func.coalesce(sa_func.sum(StockMovement.quantity), 0),
        sa_func.min(StockMovement.created_at),
        sa_func.max(StockMovement.created_at),
    ).filter(
        StockMovement.item_id == item_id,
        StockMovement.movement_type.in_(list(_OUT_TYPES)),
        StockMovement.created_at.isnot(None),
        StockMovement.created_at >= cutoff,
    ).first()
    total_out = _f(rows[0]) if rows else 0.0
    first_ts, last_ts = (rows[1], rows[2]) if rows else (None, None)
    if total_out <= 0 or not first_ts or not last_ts:
        return 0.0, None
    span_days = max(1, (last_ts - first_ts).days + 1)
    daily = total_out / span_days
    return round(daily * 30.4, 2), None if daily <= 0 else round(1.0 / daily if daily else 0, 0)


def _lead_days():
    """مهلة التوريد الافتراضية (أيام) من الإعدادات — تستخدم في اقتراح كمية الطلب."""
    try:
        import utils.settings as settings
        days = settings.get_int("reorder_lead_days", 14) or 14
        return max(1, days)
    except Exception:
        return 14


def compute_reorder_recommendations():
    """توصيات كمية إعادة الطلب بناءً على معدل الاستهلاك + مهلة التوريد + نقطة إعادة الطلب."""
    lead = _lead_days()
    out = []
    for row in _stock_rows():
        qty = _f(row[5])
        rl = _f(row[4])
        if rl <= 0:
            continue
        monthly, _coverage = _consumption(row[0])
        daily = monthly / 30.4 if monthly > 0 else 0.0
        if daily > 0:
            coverage_days = round(qty / daily, 1)
            days_to_min = round((qty - rl) / daily, 1)
            need = lead * daily
            suggested = max(0.0, round(need + rl - qty, 2))
            urgency = "critical" if qty <= 0 else "warning"
        else:
            coverage_days = None
            days_to_min = None
            suggested = max(0.0, round(rl - qty, 2))
            urgency = "warning"
        if qty > rl and suggested <= 0:
            continue
        out.append({
            "id": row[0], "name": row[1], "code": row[2],
            "cost_price": round(_f(row[3]), 2),
            "quantity": round(qty, 2),
            "reorder_level": rl,
            "monthly_consumption": monthly,
            "coverage_days": coverage_days,
            "days_to_min": days_to_min,
            "suggested_order": round(suggested, 2),
            "lead_days": lead,
            "urgency": urgency,
        })
    order = {"critical": 0, "warning": 1}
    out.sort(key=lambda x: order.get(x["urgency"], 2))
    return out[:50]


def compute_project_kpis():
    """مؤشرات المشاريع: ميزانية/مصروف/نسبة إنجاز + مخاطر الموعد/الميزانية/المراحل."""
    today = date.today()
    projects = Project.query.filter(Project.status.in_(["active", "finishing"])).all()
    horizon = today + timedelta(days=30)
    items = []
    for p in projects:
        budget = _f(p.budget)
        spent = _f(p.spent)
        completion = int(p.completion or 0)
        deadline = p.deadline
        reasons = []
        if deadline and completion < 100:
            days_left = (deadline - today).days
            if days_left <= 0:
                reasons.append("deadline_passed")
            elif days_left <= 30:
                reasons.append("deadline_soon")
        if spent > budget and budget > 0 and completion < 100:
            reasons.append("budget_overrun")
        delayed = ProjectMilestone.query.filter(
            ProjectMilestone.project_id == p.id,
            ProjectMilestone.status == "delayed",
        ).count()
        if delayed:
            reasons.append("milestones_delayed")
        items.append({
            "id": p.id,
            "name": p.name or p.name_ar,
            "code": p.project_code,
            "status": p.status,
            "completion": completion,
            "budget": round(budget, 2),
            "spent": round(spent, 2),
            "budget_utilization": round(spent / budget * 100, 1) if budget > 0 else 0.0,
            "deadline": deadline.isoformat() if deadline else None,
            "delayed_milestones": delayed,
            "at_risk": bool(reasons),
            "risk_reasons": reasons,
        })
    items.sort(key=lambda x: (0 if not x["at_risk"] else 1, x["budget_utilization"] or 0))
    active = [i for i in items if i["status"] == "active"]
    at_risk = [i for i in items if i["at_risk"]]
    return {
        "summary": {
            "active": len(active),
            "tracked": len(items),
            "at_risk": len(at_risk),
            "total_budget": round(sum(i["budget"] for i in items), 2),
            "total_spent": round(sum(i["spent"] for i in items), 2),
            "total_utilization": round(
                sum(i["spent"] for i in items) / sum(i["budget"] for i in items) * 100, 1
            ) if sum(i["budget"] for i in items) > 0 else 0.0,
        },
        "projects": items,
    }


def compute_analytics():
    """مؤشرات لوحة التحليل التنفيذي (إيراد / مصروف / ذمم / مخزون / أداء)."""
    def _sum(inv_type):
        return _f(db.session.query(
            sa_func.coalesce(sa_func.sum(Invoice.amount), 0)
        ).filter_by(invoice_type=inv_type).scalar())

    def _paid(inv_type):
        return _f(db.session.query(
            sa_func.coalesce(sa_func.sum(Invoice.paid_amount), 0)
        ).filter_by(invoice_type=inv_type).scalar())

    def _pending(inv_type, overdue_only=False):
        q = db.session.query(
            sa_func.coalesce(sa_func.sum(Invoice.amount - Invoice.paid_amount), 0)
        ).filter(
            Invoice.invoice_type == inv_type,
            Invoice.amount > Invoice.paid_amount,
        )
        if overdue_only:
            q = q.filter(Invoice.due_date.isnot(None), Invoice.due_date < date.today())
        return _f(q.scalar())

    revenue = _sum("sales")
    expenses = _sum("purchase")
    revenue_paid = _paid("sales")
    expenses_paid = _paid("purchase")

    # المخزون
    stock_value = _f(db.session.query(
        sa_func.coalesce(sa_func.sum(ItemStock.quantity * ItemStock.avg_cost), 0)
    ).scalar())
    recommendations = compute_reorder_recommendations()
    low_stock_list = [
        {k: r[k] for k in ("id", "name", "code", "quantity", "reorder_level",
                           "monthly_consumption", "coverage_days",
                           "suggested_order", "urgency")}
        for r in recommendations if r["quantity"] <= r["reorder_level"]
    ][:30]
    low_stock_count = len(low_stock_list)

    # أفضل المنتجات (إيراد)
    top_products = db.session.query(
        InvoiceItem.description,
        sa_func.coalesce(sa_func.sum(InvoiceItem.quantity * InvoiceItem.unit_price), 0),
    ).join(Invoice, Invoice.id == InvoiceItem.invoice_id).filter(
        Invoice.invoice_type == "sales",
        Invoice.deleted_at.is_(None),
    ).group_by(InvoiceItem.description).order_by(
        sa_func.sum(InvoiceItem.quantity * InvoiceItem.unit_price).desc()
    ).limit(10).all()
    top_products = [
        {"name": name or "—", "revenue": round(_f(amt), 2)}
        for name, amt in top_products
    ]

    # أفضل العملاء (إيراد + رصيد مستحق)
    top_customers = db.session.query(
        Customer.full_name,
        Invoice.customer_id,
        sa_func.coalesce(sa_func.sum(Invoice.amount), 0),
        sa_func.coalesce(sa_func.sum(Invoice.amount - Invoice.paid_amount), 0),
    ).join(Invoice, Invoice.customer_id == Customer.id).filter(
        Invoice.invoice_type == "sales",
        Invoice.deleted_at.is_(None),
    ).group_by(Customer.full_name, Invoice.customer_id).order_by(
        sa_func.sum(Invoice.amount).desc()
    ).limit(10).all()
    top_customers = [
        {"name": name or "—", "revenue": round(_f(rev), 2), "balance": round(_f(bal), 2)}
        for name, _cid, rev, bal in top_customers
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "currency": _currency_info(),
        "kpis": {
            "revenue": round(revenue, 2),
            "revenue_paid": round(revenue_paid, 2),
            "revenue_pending": round(revenue - revenue_paid, 2),
            "expenses": round(expenses, 2),
            "expenses_paid": round(expenses_paid, 2),
            "net_margin": round(revenue - expenses, 2),
            "receivables": round(_pending("sales"), 2),
            "receivables_overdue": round(_pending("sales", True), 2),
            "payables": round(_pending("purchase"), 2),
            "payables_overdue": round(_pending("purchase", True), 2),
            "stock_value": round(stock_value, 2),
            "low_stock_items": low_stock_count,
            "customers_count": Customer.query.count(),
            "suppliers_count": Supplier.query.count(),
        },
        "trend": _trend(),
        "aging": _aging_buckets(),
        "top_products": top_products,
        "top_customers": top_customers,
        "low_stock_list": low_stock_list,
        "reorder_recommendations": recommendations,
        "projects": compute_project_kpis(),
    }


def _add_alert(alerts, alert_type, severity, title, detail, link=None):
    alerts.append({
        "type": alert_type,
        "severity": severity,
        "title": title,
        "detail": detail,
        "link": link,
    })


def compute_alerts():
    """تنبيهات قابلة للتنفيذ: إعادة طلب، ذمم متأخرة، عقود تنتهي، أوامر/عروض معلقة."""
    alerts = []
    today = date.today()

    # مخزون منخفض → إعادة طلب
    for row in _stock_rows():
        qty = _f(row[5])
        rl = _f(row[4])
        if rl > 0 and qty <= rl:
            monthly, _cov = _consumption(row[0])
            suggested = max(0.0, round(float(_lead_days()) / 30.4 * monthly + rl - qty, 2)) if monthly > 0 \
                else max(0.0, round(rl - qty, 2))
            _add_alert(
                alerts, "low_stock",
                "critical" if qty == 0 else "warning",
                f"إعادة طلب: {row[1]} ({row[2]})",
                f"الكمية الحالية {round(qty, 2)} والحد {rl:g} — يُنصح بطلب {suggested:g} وحدة",
                "/inventory",
            )
        if len(alerts) >= 40:
            break

    # مشاريع معرّضة للخطر (ميزانية/موعد/مراحل متأخرة)
    proj = compute_project_kpis()
    for p in proj["projects"]:
        if p["at_risk"]:
            parts = []
            if "budget_overrun" in p["risk_reasons"]:
                parts.append(f"تجاوزت الميزانية ({p['budget_utilization']:.0f}٪)")
            if "deadline_passed" in p["risk_reasons"]:
                parts.append("تجاوز موعد التسليم")
            elif "deadline_soon" in p["risk_reasons"]:
                parts.append(f"الموعد خلال {max(0, (date.fromisoformat(p['deadline']) - today).days)} يوم")
            if "milestones_delayed" in p["risk_reasons"]:
                parts.append(f"{p['delayed_milestones']} مرحلة متأخرة")
            _add_alert(
                alerts, "project_at_risk", "critical" if "deadline_passed" in p["risk_reasons"] else "warning",
                f"مشروع معرّض للخطر: {p['name']}",
                "، ".join(parts) + f" — الإنجاز {p['completion']}٪",
                "/projects",
            )

    # فواتير مبيعات متأخرة
    late = Invoice.query.filter(
        Invoice.invoice_type == "sales",
        Invoice.due_date.isnot(None),
        Invoice.due_date < today,
        Invoice.amount > Invoice.paid_amount,
        Invoice.deleted_at.is_(None),
    ).order_by(Invoice.due_date.asc()).limit(15).all()
    for i in late:
        balance = round(_f(i.amount) - _f(i.paid_amount), 2)
        days = (today - i.due_date).days
        _add_alert(
            alerts, "overdue_invoice", "critical",
            f"فاتورة متأخرة {i.invoice_number}",
            f"«{i.customer.full_name if i.customer else 'عميل'}» — مستحق {balance:,.2f} منذ {days} يوم",
            "/finance",
        )

    # عقود إيجار تنتهي خلال 30 يوماً
    horizon = today + timedelta(days=30)
    exp = RentalContract.query.filter(
        RentalContract.status == "active",
        RentalContract.end_date.isnot(None),
        RentalContract.end_date >= today,
        RentalContract.end_date <= horizon,
    ).order_by(RentalContract.end_date.asc()).limit(15).all()
    for c in exp:
        days = (c.end_date - today).days
        _add_alert(
            alerts, "contract_expiring", "warning",
            f"عقد ينتهي خلال {days} يوم {c.contract_number}",
            f"الإيجار الشهري {_f(c.monthly_rent):,.2f} — تاريخ الانتهاء {c.end_date}",
            "/rentals",
        )

    # أوامر شراء معلّقة
    po_count = PurchaseOrder.query.filter_by(status="pending").count()
    if po_count:
        _add_alert(
            alerts, "pending_po", "info",
            f"{po_count} أمر شراء بانتظار الاعتماد",
            "أوامر شراء مفتوحة تحتاج مراجعة وتنفيذ",
            "/procurement",
        )

    # عروض سعرية مفتوحة تخطّت صلاحيتها
    stale = Quote.query.filter(
        Quote.status.in_(["draft", "sent"]),
        Quote.valid_until.isnot(None),
        Quote.valid_until < today,
    ).order_by(Quote.valid_until.asc()).limit(10).all()
    if stale:
        _add_alert(
            alerts, "expired_quotes", "info",
            f"{len(stale)} عرض سعري انتهت صلاحيته",
            "عروض مفتوحة تجاوزت تاريخ الصلاحية — يُنصح بالتواصل مع العملاء",
            "/crm",
        )

    order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: order.get(a["severity"], 3))
    return {
        "alerts": alerts,
        "summary": {
            "critical": sum(1 for a in alerts if a["severity"] == "critical"),
            "warning": sum(1 for a in alerts if a["severity"] == "warning"),
            "info": sum(1 for a in alerts if a["severity"] == "info"),
        },
    }
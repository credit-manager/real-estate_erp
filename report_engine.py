"""محرك البحث التحليلي المحلي — يفهم أسئلة بالعربية ويرد بأرقام من قاعدة البيانات مباشرة.

يعمل بدون مفتاح Gemini ويجيب عن أسئلة مثل:
"إجمالي الإيرادات خلال الشهر"، "كم وحدة متاحة"، "إجمالي الأقساط المتأخرة"،
"متوسط سعر الوحدة"، "عدد عقود البيع"، "نسبة الإشغال" ...

Usage:
    from report_engine import analyze_question
    result = analyze_question("كم وحدة متاحة في بورسعيد؟")
    # -> dict (JSON-safe) أو None إذا لم يُفهم السؤال
"""
import re
import unicodedata
from datetime import date, timedelta

from sqlalchemy import text
from database import db

# ── تطبيع النص العربي ───────────────────────────────────────────
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670]")
_REPLACES = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي",
})
_PUNCT = re.compile(r"[\_\-ـ,،.;:!؟?()\[\]{}'\"\u2018\u2019\u201C\u201D\\/|&*^%#@$+<>]")


def normalize(q: str) -> str:
    s = unicodedata.normalize("NFKC", q or "")
    s = _DIACRITICS.sub("", s)
    s = s.translate(_REPLACES)
    s = _PUNCT.sub(" ", s)
    s = " ".join(s.split())
    return " " + s.strip() + " "


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def has(q, *tokens) -> bool:
    return any(normalize(t).strip() in q for t in tokens)


# ── تحديد الفترة الزمنية ─────────────────────────────────────────
def detect_period(q: str):
    """يرجع (label_ar, start_date, end_date) أو (None, None, None)."""
    today = date.today()
    try:
        this_month = today.replace(day=1)
        next_month = (this_month.replace(year=this_month.year + 1, day=1)
                      if this_month.month == 12
                      else this_month.replace(month=this_month.month + 1))
        last_month_start = (this_month - timedelta(days=1)).replace(day=1)

        if has(q, "امبارح", "البارحه"):
            d = today - timedelta(days=1)
            return "أمس", d, d
        if has(q, "الشهر الماضي", "الشهر الماضى", "الشهر السابق", "الشهر اللي فات",
               "الشهر اللي قبل", "الشهر الفايت", "الشهر اللي راح"):
            return "الشهر الماضي", last_month_start, this_month - timedelta(days=1)
        if has(q, "الاسبوع الماضي", "الاسبوع الماضى", "الاسبوع السابق", "الاسبوع الفايت",
               "الاسبوع اللي فات"):
            return "الأسبوع الماضي", today - timedelta(days=13), today - timedelta(days=7)
        if has(q, "الاسبوع"):
            return "الأسبوع الحالي", today - timedelta(days=6), today
        if has(q, "العام الماضي", "العام الماضى", "السنه الماضيه", "السنة الماضية",
               "السنه اللي فاتت"):
            return "العام الماضي", date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
        if has(q, "الشهر", "الشهر ده", "الشهر الداخل", "الشهر دي"):
            return "الشهر الحالي", this_month, next_month - timedelta(days=1)
        if has(q, "العام", "السنه", "السنة", "العام الحالي", "السته دى"):
            return "العام الحالي", date(today.year, 1, 1), date(today.year, 12, 31)
        if has(q, "اليوم", "النهارده"):
            return "اليوم", today, today

        m = re.search(r"(اخر|آخر|الاخيره|الاخيرة)\s+(\d{1,3})\s*(يوم|ايام|أيام)", q)
        if m:
            n = max(1, min(int(m.group(2)), 3650))
            return f"آخر {n} يوم", today - timedelta(days=n - 1), today
    except Exception:
        pass
    return None, None, None


# ── عملة العرض ───────────────────────────────────────────────────
def money(x) -> str:
    cur = "ج.م"
    try:
        row = db.session.execute(text(
            "SELECT code, symbol FROM currencies WHERE is_base = TRUE "
            "ORDER BY company_id LIMIT 1")).fetchone()
        if row:
            cur = row[1] or row[0] or cur
    except Exception:
        pass
    return f"{float(x or 0):,.2f} {cur}"


def num(x) -> str:
    return f"{int(x or 0):,}"


# ── أدوات استعلام مساعدة ─────────────────────────────────────────
def _scalar(sql, **params):
    row = db.session.execute(text(sql), params).fetchone()
    return row[0] if row else 0


def _rows(sql, **params):
    r = db.session.execute(text(sql), params)
    return [dict(m) for m in r.mappings().all()]


# ── أنماط الأسئلة ────────────────────────────────────────────────
def _period_txt(label):
    return f" خلال {label}" if label else " (الإجمالي الكلي)"


def intent_revenue(q, d1, d2, label):
    inst = _scalar(
        "SELECT COALESCE(SUM(paid_amount),0) FROM installments "
        "WHERE status IN ('paid','partial')"
        + (" AND paid_date BETWEEN :d1 AND :d2" if d1 else ""),
        d1=d1, d2=d2)
    rent = _scalar(
        "SELECT COALESCE(SUM(amount),0) FROM rental_payments"
        + (" WHERE payment_date BETWEEN :d1 AND :d2" if d1 else ""),
        d1=d1, d2=d2)
    inv = _scalar(
        "SELECT COALESCE(SUM(amount),0) FROM invoices "
        "WHERE status='paid' AND deleted_at IS NULL"
        + (" AND issue_date BETWEEN :d1 AND :d2" if d1 else ""),
        d1=d1, d2=d2)
    total = inst + rent + inv
    return {
        "type": "report",
        "answer": f"إجمالي الإيرادات{_period_txt(label)} = {money(total)}",
        "items": [
            {"label": "أقساط محصلة", "value": money(inst)},
            {"label": "إيجارات محصلة", "value": money(rent)},
            {"label": "فواتير مدفوعة", "value": money(inv)},
            {"label": "إجمالي الإيرادات", "value": money(total)},
        ],
        "source": "installments, rental_payments, invoices",
    }


def intent_rental_revenue(q, d1, d2, label):
    rent = _scalar(
        "SELECT COALESCE(SUM(amount),0) FROM rental_payments"
        + (" WHERE payment_date BETWEEN :d1 AND :d2" if d1 else ""),
        d1=d1, d2=d2)
    return {
        "type": "report",
        "answer": f"إيرادات الإيجار{_period_txt(label)} = {money(rent)}",
        "items": [{"label": "إيرادات الإيجار", "value": money(rent)}],
        "source": "rental_payments",
    }


def intent_sales_revenue(q, d1, d2, label):
    sql = "SELECT COUNT(*), COALESCE(SUM(paid_amount),0) FROM installments " \
          "WHERE status IN ('paid','partial')"
    params = {}
    if d1:
        sql += " AND paid_date BETWEEN :d1 AND :d2"
        params = {"d1": d1, "d2": d2}
    row = db.session.execute(text(sql), params).fetchone()
    cnt, total = (int(row[0]), float(row[1])) if row else (0, 0)
    return {
        "type": "report",
        "answer": f"إيرادات المبيعات (أقساط محصلة){_period_txt(label)} = {money(total)}",
        "items": [
            {"label": "إيرادات الأقساط", "value": money(total)},
            {"label": "عدد الأقساط المسددة", "value": num(cnt)},
        ],
        "source": "installments",
    }


def intent_overdue(q, d1, d2, label):
    cnt = _scalar("SELECT COUNT(*) FROM installments WHERE status='overdue'")
    total = _scalar("SELECT COALESCE(SUM(amount - paid_amount),0) FROM installments "
                    "WHERE status='overdue'")
    due_late = _scalar("SELECT COALESCE(SUM(amount - paid_amount),0) FROM installments "
                       "WHERE status IN ('pending','partial') AND due_date < CURRENT_DATE")
    return {
        "type": "report",
        "answer": f"الأقساط المتأخرة = {num(cnt)} قسط بقيمة متبقية {money(total)}",
        "items": [
            {"label": "أقساط متأخرة", "value": num(cnt)},
            {"label": "قيمة المتأخرات", "value": money(total)},
            {"label": "متأخر + مستحق سابقاً", "value": money(total + due_late)},
        ],
        "source": "installments",
    }


def intent_installments_due(q, d1, d2, label):
    if d1 is None:
        this_month = date.today().replace(day=1)
        nxt = (this_month.replace(year=this_month.year + 1, day=1)
               if this_month.month == 12
               else this_month.replace(month=this_month.month + 1))
        d1, d2, label = this_month, nxt - timedelta(days=1), "الشهر الحالي"
    cnt = _scalar("SELECT COUNT(*) FROM installments WHERE due_date BETWEEN :d1 AND :d2",
                  d1=d1, d2=d2)
    total = _scalar("SELECT COALESCE(SUM(amount - paid_amount),0) FROM installments "
                    "WHERE due_date BETWEEN :d1 AND :d2", d1=d1, d2=d2)
    return {
        "type": "report",
        "answer": f"الأقساط المستحقة {label} = {num(cnt)} قسط بقيمة {money(total)}",
        "items": [
            {"label": "عدد الأقساط", "value": num(cnt)},
            {"label": "قيمة المستحق", "value": money(total)},
        ],
        "source": "installments",
    }


def _unit_status_counts():
    rows = _rows("SELECT status, COUNT(*) AS n FROM real_estate_units "
                 "WHERE deleted_at IS NULL GROUP BY status")
    return {r["status"]: r["n"] for r in rows}


def intent_units_status(q, d1, d2, label):
    counts = _unit_status_counts()
    total = sum(counts.values())
    sold = counts.get("sold", 0)
    rented = counts.get("rented", 0)
    reserved = counts.get("reserved", 0)
    available = counts.get("available", 0)
    other = total - sold - rented - reserved - available

    answer = f"عدد الوحدات الكلي = {num(total)}"
    if has(q, "متاح", "متاحه", "فاضل", "متبقي", "متبقيه"):
        answer = f"الوحدات المتاحة = {num(available)} من إجمالي {num(total)}"
    elif has(q, "محجوز", "محجوزه"):
        answer = f"الوحدات المحجوزة = {num(reserved)} من إجمالي {num(total)}"
    elif has(q, "مباع", "مباعه", "اتبعت"):
        answer = f"الوحدات المباعة = {num(sold)} من إجمالي {num(total)}"
    elif has(q, "مؤجر", "مؤجره", "ايجار"):
        answer = f"الوحدات المؤجرة = {num(rented)} من إجمالي {num(total)}"

    items = [
        {"label": "مباعة", "value": num(sold)},
        {"label": "مؤجرة", "value": num(rented)},
        {"label": "محجوزة", "value": num(reserved)},
        {"label": "متاحة", "value": num(available)},
    ]
    if other:
        items.append({"label": "حالات أخرى", "value": num(other)})
    return {"type": "report", "answer": answer, "items": items,
            "source": "real_estate_units"}


def intent_units_sold_period(q, d1, d2, label):
    sql = ("SELECT COUNT(*) AS n, COALESCE(SUM(net_amount),0) AS total FROM sales_contracts "
           "WHERE status IN ('active','completed') AND deleted_at IS NULL")
    params = {}
    if d1:
        sql += " AND contract_date BETWEEN :d1 AND :d2"
        params = {"d1": d1, "d2": d2}
    row = db.session.execute(text(sql), params).fetchone()
    n, total = (int(row.n), float(row.total)) if row else (0, 0)
    ptxt = f" خلال {label}" if label else ""
    return {
        "type": "report",
        "answer": f"عدد الوحدات المباعة{ptxt} = {num(n)} بقيمة {money(total)}",
        "items": [
            {"label": "وحدات مباعة", "value": num(n)},
            {"label": "قيمة المبيعات", "value": money(total)},
        ],
        "source": "sales_contracts",
    }


def intent_sales_total(q, d1, d2, label):
    sql = ("SELECT COUNT(*) AS n, COALESCE(SUM(net_amount),0) AS total, "
           "COALESCE(SUM(vat_amount),0) AS vat FROM sales_contracts "
           "WHERE status IN ('active','completed') AND deleted_at IS NULL")
    params = {}
    if d1:
        sql += " AND contract_date BETWEEN :d1 AND :d2"
        params = {"d1": d1, "d2": d2}
    row = db.session.execute(text(sql), params).fetchone()
    n, total, vat = (int(row.n), float(row.total), float(row.vat)) if row else (0, 0, 0)
    ptxt = f" خلال {label}" if label else ""
    return {
        "type": "report",
        "answer": f"إجمالي قيمة عقود البيع{ptxt} = {money(total)} ({num(n)} عقد)",
        "items": [
            {"label": "عدد العقود", "value": num(n)},
            {"label": "صافي المبيعات", "value": money(total)},
            {"label": "ضريبة القيمة المضاف", "value": money(vat)},
        ],
        "source": "sales_contracts",
    }


def intent_avg_price(q, d1, d2, label):
    row = db.session.execute(text(
        "SELECT COALESCE(AVG(price),0) AS avg, COALESCE(MIN(price),0) AS mn, "
        "COALESCE(MAX(price),0) AS mx, COUNT(*) AS n FROM real_estate_units "
        "WHERE deleted_at IS NULL")).fetchone()
    return {
        "type": "report",
        "answer": f"متوسط سعر الوحدة = {money(row.avg)} (من {num(row.n)} وحدة)",
        "items": [
            {"label": "متوسط السعر", "value": money(row.avg)},
            {"label": "أقل سعر", "value": money(row.mn)},
            {"label": "أعلى سعر", "value": money(row.mx)},
        ],
        "source": "real_estate_units",
    }


def intent_price_extremes(q, d1, d2, label):
    hi = _rows("SELECT unit_code, price FROM real_estate_units "
               "WHERE deleted_at IS NULL ORDER BY price DESC LIMIT 5")
    lo = _rows("SELECT unit_code, price FROM real_estate_units "
               "WHERE deleted_at IS NULL ORDER BY price ASC LIMIT 5")
    rows = [{"نوع": "أغلى وحدة", "الوحدة": r["unit_code"], "السعر": money(r["price"])} for r in hi]
    rows += [{"نوع": "أرخص وحدة", "الوحدة": r["unit_code"], "السعر": money(r["price"])} for r in lo]
    top = hi[0]["price"] if hi else 0
    bot = lo[0]["price"] if lo else 0
    return {
        "type": "report",
        "answer": f"أعلى سعر وحدة = {money(top)} ، أدنى سعر = {money(bot)}",
        "items": [
            {"label": "أعلى سعر", "value": money(top)},
            {"label": "أدنى سعر", "value": money(bot)},
        ],
        "columns": ["نوع", "الوحدة", "السعر"],
        "rows": rows,
        "source": "real_estate_units",
    }


def intent_occupancy(q, d1, d2, label):
    counts = _unit_status_counts()
    total = sum(counts.values())
    occupied = counts.get("sold", 0) + counts.get("rented", 0) + counts.get("reserved", 0)
    pct = (occupied * 100 / total) if total else 0
    return {
        "type": "report",
        "answer": f"نسبة إشغال الوحدات = {pct:.1f}% ({num(occupied)} من {num(total)})",
        "items": [
            {"label": "وحدات مشغولة", "value": num(occupied)},
            {"label": "إجمالي الوحدات", "value": num(total)},
            {"label": "نسبة الإشغال", "value": f"{pct:.1f}%"},
        ],
        "source": "real_estate_units",
    }


def intent_contracts(q, d1, d2, label):
    sale = _scalar("SELECT COUNT(*) FROM sales_contracts WHERE deleted_at IS NULL")
    rent = _scalar("SELECT COUNT(*) FROM rental_contracts")
    return {
        "type": "report",
        "answer": f"عدد العقود الكلي = {num(sale + rent)} ({num(sale)} بيع و {num(rent)} إيجار)",
        "items": [
            {"label": "عقود البيع", "value": num(sale)},
            {"label": "عقود الإيجار", "value": num(rent)},
        ],
        "source": "sales_contracts, rental_contracts",
    }


def intent_customers(q, d1, d2, label):
    total = _scalar("SELECT COUNT(*) FROM customers")
    return {
        "type": "report",
        "answer": f"عدد العملاء = {num(total)}",
        "items": [{"label": "العملاء", "value": num(total)}],
        "source": "customers",
    }


def intent_employees(q, d1, d2, label):
    total = _scalar("SELECT COUNT(*) FROM employees WHERE status = 'active'")
    if total == 0:
        total = _scalar("SELECT COUNT(*) FROM employees")
    by_dept = _rows("SELECT department, COUNT(*) AS n FROM employees "
                    "WHERE status = 'active' GROUP BY department ORDER BY n DESC")
    items = [{"label": "إجمالي الموظفين", "value": num(total)}]
    for r in by_dept[:5]:
        items.append({"label": r["department"] or "غير محدد", "value": num(r["n"])})
    return {
        "type": "report",
        "answer": f"عدد الموظفين = {num(total)}",
        "items": items,
        "source": "employees",
    }


def intent_rent_projection(q, d1, d2, label):
    n = _scalar("SELECT COUNT(*) FROM rental_contracts WHERE status='active'")
    monthly = _scalar("SELECT COALESCE(SUM(monthly_rent),0) FROM rental_contracts "
                      "WHERE status='active'")
    return {
        "type": "report",
        "answer": f"إجمالي الإيجارات الشهرية للعقود النشطة ({num(n)} عقد) = {money(monthly)}",
        "items": [
            {"label": "عقود إيجار نشطة", "value": num(n)},
            {"label": "إيجار شهري متوقع", "value": money(monthly)},
            {"label": "إيجار سنوي متوقع", "value": money(monthly * 12)},
        ],
        "source": "rental_contracts",
    }


def intent_deliveries(q, d1, d2, label):
    sql = "SELECT COUNT(*) FROM unit_deliveries WHERE status='delivered'"
    params = {}
    if d1:
        sql += " AND delivery_date BETWEEN :d1 AND :d2"
        params = {"d1": d1, "d2": d2}
    n = _scalar(sql, **params)
    ptxt = f" خلال {label}" if label else ""
    return {
        "type": "report",
        "answer": f"عدد الوحدات المسلّمة{ptxt} = {num(n)}",
        "items": [{"label": "تسليمات تمت", "value": num(n)}],
        "source": "unit_deliveries",
    }


def intent_reservations(q, d1, d2, label):
    sql = "SELECT COUNT(*), COALESCE(SUM(deposit),0) FROM unit_reservations WHERE status='active'"
    params = {}
    if d1:
        sql += " AND reserved_date BETWEEN :d1 AND :d2"
        params = {"d1": d1, "d2": d2}
    row = db.session.execute(text(sql), params).fetchone()
    n, dep = (int(row[0]), float(row[1])) if row else (0, 0)
    ptxt = f" خلال {label}" if label else ""
    return {
        "type": "report",
        "answer": f"الحجوزات النشطة{ptxt} = {num(n)} بعربون {money(dep)}",
        "items": [
            {"label": "حجوزات نشطة", "value": num(n)},
            {"label": "إجمالي العربونات", "value": money(dep)},
        ],
        "source": "unit_reservations",
    }


# ── جدول الأنماط (بالترتيب، أول تطابق يفوز) ─────────────────────
_INTENTS = [
    (intent_rental_revenue, ["ايراد", "ايرادات"], ["ايجار", "اجاره", "اجارات"]),
    (intent_sales_revenue, ["ايراد", "ايرادات"], ["بيع", "مبيعات"]),
    (intent_revenue, ["ايراد", "ايرادات", "تحصيل", "حصله", "استلم", "استلام", "قبض", "مدفوع", "عملت ايه"], []),
    (intent_installments_due, ["قسط", "اقساط", "استحقاق"], ["مستحق", "مستحقه", "بعده", "تحل"]),
    (intent_overdue, ["متاخر", "متأخر", "متاخره", "مستحق", "مستحقه", "متبقى", "متبقي", "دين"], []),
    (intent_deliveries, ["تسليم", "تسليمات", "سلم", "مسلم"], []),
    (intent_reservations, ["حجز", "حجوزات", "عربون", "عربونات"], []),
    (intent_contracts, ["عقد", "عقود"], ["عدد", "كم", "كام", "اجمالي"]),
    (intent_customers, ["عملاء", "عميل", "العملاء"], []),
    (intent_employees, ["موظف", "موظفين", "الموظفين", "coeficient", "عامل", "عمال", "cocaine"], []),
    (intent_units_sold_period, ["بيع", "مباع", "مباعه", "اتبعت", "بعت", "باع", "باعت"], ["وحده", "وحدات", "شقه", "شقق"]),
    (intent_sales_total, ["مبيعات", "اجمالي المبيعات", "حجم مبيعات", "قيمه المبيعات", "قيمة المبيعات"], []),
    (intent_avg_price, ["متوسط", "معدل", "الوسط"], ["سعر", "ثمن"]),
    (intent_price_extremes, ["اغلى", "اغلي", "اعلى", "اكبر", "ارخص", "اقل", "أقل", "غالي", "رخيص"], ["سعر", "ثمن", "وحده", "شقه"]),
    (intent_occupancy, ["اشغال", "إشغال", "تشغيل", "نسبه اشغال", "نسبة الاشغال"], []),
    (intent_rent_projection, ["ايجار", "علوت"], ["شهري", "شهريه", "متوقع"]),
    (intent_units_status, ["وحدات", "وحده", "شقق", "شقه", "عقارات", "متاح", "محجوز", "مؤجر", "مباع"], []),
]


def analyze_question(question: str):
    """يحلل سؤالاً بالعربية ويرجع نتيجة JSON-safe أو None إن لم يُفهم."""
    q = normalize(question)
    if len(q.strip()) < 3:
        return None

    pl, d1, d2 = detect_period(q)

    for fn, anyof, need in _NORM_INTENTS:
        any_hit = any(t in q for t in anyof)
        need_hit = (any(t in q for t in need) if need else True)
        if any_hit and need_hit:
            try:
                return fn(q, d1, d2, pl)
            except Exception:
                return None
    return None


_NORM_INTENTS = [
    (fn, [normalize(t).strip() for t in anyof], [normalize(t).strip() for t in need])
    for fn, anyof, need in _INTENTS
]
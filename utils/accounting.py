"""محاسبة القيد المزدوج: دليل حسابات، قيود، أرصدة، تقارير، ترحيل تلقائي."""
import datetime

from database import db
from models import (
    Account, JournalEntry, JournalEntryLine, CostCenter,
    FixedAsset, DepreciationRecord, BudgetLine, FinancialYear,
)
from models.setting import SystemSetting
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

ACCOUNT_TYPES = ["asset", "liability", "equity", "revenue", "expense"]

TYPE_LABELS = {
    "asset": "accounting.asset",
    "liability": "accounting.liability",
    "equity": "accounting.equity",
    "revenue": "accounting.revenue",
    "expense": "accounting.expense",
}

# الحسابات الافتراضية (بأكواد ثابتة تُستخدم كمرجع للترحيل التلقائي)
DEFAULT_COA = [
    {"code": "100000", "name": "الأصول", "type": "asset"},
    {"code": "110000", "name": "أصول متداولة", "type": "asset", "parent": "100000"},
    {"code": "110100", "name": "الصندوق - النقدية", "type": "asset", "parent": "110000", "is_cash": True},
    {"code": "110200", "name": "البنوك", "type": "asset", "parent": "110000", "is_bank": True},
    {"code": "120100", "name": "الذمم المدينة - العملاء", "type": "asset", "parent": "110000"},
    {"code": "120200", "name": "ضريبة القيمة المضافة المدينة", "type": "asset", "parent": "110000"},
    {"code": "130000", "name": "أصول ثابتة", "type": "asset", "parent": "100000"},
    {"code": "130100", "name": "مبانٍ وآلات ومعدات", "type": "asset", "parent": "130000"},
    {"code": "130200", "name": "مجمع إهلاك الأصول الثابتة", "type": "asset", "parent": "130000", "is_contra": True},
    {"code": "200000", "name": "الخصوم", "type": "liability"},
    {"code": "210000", "name": "خصوم متداولة", "type": "liability", "parent": "200000"},
    {"code": "210100", "name": "الذمم الدائنة - الموردون", "type": "liability", "parent": "210000"},
    {"code": "220100", "name": "ضريبة القيمة المضافة الدائنة", "type": "liability", "parent": "210000"},
    {"code": "230000", "name": "خصوم طويلة الأجل", "type": "liability", "parent": "200000"},
    {"code": "230100", "name": "قروض وتمويلات", "type": "liability", "parent": "230000"},
    {"code": "300000", "name": "حقوق الملكية", "type": "equity"},
    {"code": "310100", "name": "رأس المال", "type": "equity", "parent": "300000"},
    {"code": "320100", "name": "أرباح مرحلة", "type": "equity", "parent": "300000"},
    {"code": "330100", "name": "صافي النتيجة (أرباح/خسائر)", "type": "equity", "parent": "300000"},
    {"code": "400000", "name": "الإيرادات", "type": "revenue"},
    {"code": "410100", "name": "إيرادات المبيعات", "type": "revenue", "parent": "400000"},
    {"code": "410200", "name": "إيرادات الإيجارات", "type": "revenue", "parent": "400000"},
    {"code": "410300", "name": "إيرادات أخرى", "type": "revenue", "parent": "400000"},
    {"code": "500000", "name": "المصروفات", "type": "expense"},
    {"code": "510100", "name": "تكلفة المشتريات", "type": "expense", "parent": "500000"},
    {"code": "510200", "name": "رواتب وأجور", "type": "expense", "parent": "500000"},
    {"code": "510300", "name": "إيجارات ومصروفات تشغيلية", "type": "expense", "parent": "500000"},
    {"code": "510400", "name": "مصروفات عامة وإدارية", "type": "expense", "parent": "500000"},
    {"code": "510500", "name": "مصروفات إهلاك", "type": "expense", "parent": "500000"},
    {"code": "510600", "name": "مصروفات ضريبية", "type": "expense", "parent": "500000"},
]

DEFAULT_ACCOUNT_MAP = {
    "acc_default_receivable": "120100",   # الذمم المدينة
    "acc_default_payable": "210100",      # الذمم الدائنة
    "acc_default_cash": "110100",         # الصندوق
    "acc_default_bank": "110200",         # البنوك
    "acc_default_revenue": "410100",      # إيرادات المبيعات
    "acc_default_expense": "510100",      # مصروفات المشتريات
    "acc_default_equity": "320100",       # أرباح مرحلة (رصيد افتتاحي)
    "acc_default_asset": "130100",        # الأصول الثابتة
    "acc_default_accumulated": "130200",  # مجمع الإهلاك
    "acc_default_depreciation": "510500", # مصروفات الإهلاك
    "acc_default_tax_in": "120200",       # ضريبة المدينة
    "acc_default_tax_out": "220100",      # ضريبة الدائنة
}


def seed_default_coa():
    """إنشاء دليل الحسابات الافتراضي + تعيين الحسابات الافتراضية (مرة واحدة)."""
    if Account.query.count() > 0:
        _ensure_default_mapping()
        return
    parents = {}
    for item in DEFAULT_COA:
        acc = Account(
            code=item["code"],
            name=item["name"],
            type=item["type"],
            is_cash=item.get("is_cash", False),
            is_bank=item.get("is_bank", False),
            is_contra=item.get("is_contra", False),
        )
        if item.get("parent"):
            acc.parent_id = parents[item["parent"]]
        db.session.add(acc)
        db.session.flush()
        parents[item["code"]] = acc.id
    db.session.commit()
    _ensure_default_mapping()


def _ensure_default_mapping():
    """تحديث قيم الحسابات الافتراضية المخزنة في الإعدادات عند توفرها."""
    existing = {s.key: s.value for s in SystemSetting.query.all()}
    changed = False
    for key, code in DEFAULT_ACCOUNT_MAP.items():
        acc = Account.query.filter_by(code=code).first()
        if acc and key not in existing:
            db.session.add(SystemSetting(key=key, value=str(acc.id)))
            changed = True
    if changed:
        db.session.commit()


def default_account_id(key):
    """قراءة معرف الحساب الافتراضي من الإعدادات."""
    if key not in DEFAULT_ACCOUNT_MAP:
        return None
    row = SystemSetting.query.filter_by(key=key).first()
    if row and row.value:
        try:
            return int(row.value)
        except (TypeError, ValueError):
            return None
    acc = Account.query.filter_by(code=DEFAULT_ACCOUNT_MAP[key]).first()
    return acc.id if acc else None


def set_default_account_id(key, account_id):
    row = SystemSetting.query.filter_by(key=key).first()
    if row:
        row.value = str(account_id)
    else:
        db.session.add(SystemSetting(key=key, value=str(account_id)))
    db.session.commit()


def next_entry_number(year_id):
    year = db.session.get(FinancialYear, year_id) if year_id else None
    prefix = "JV"
    if year and year.name:
        prefix = f"JV-{year.name.split()[0] if year.name else ''}"
    # استعلام SQL مباشر لأحدث رقم تسلسلي (بدلاً من جلب كل القيود)
    like_prefix = f"{prefix}-%"
    q = JournalEntry.query.filter(JournalEntry.entry_number.like(like_prefix))
    if year_id:
        q = q.filter(JournalEntry.financial_year_id == year_id)
    last = q.order_by(JournalEntry.id.desc()).first()
    seq = 1
    if last and last.entry_number:
        try:
            seq = int(str(last.entry_number).split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}-{seq:04d}"


def d0(v):
    try:
        return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (TypeError, ValueError, InvalidOperation):
        return Decimal("0.00")


def _clean_year(year_id):
    """تطبيع معرف السنة المالية (قد يأتي None/سلسلة فارغة/"0")."""
    if year_id in (None, "", 0, "0"):
        return None
    try:
        return int(year_id)
    except (TypeError, ValueError):
        return None


def make_entry(lines, date=None, description="", financial_year_id=None,
               source="manual", ref_type=None, ref_id=None, commit=True):
    """إنشاء قيد مرتّب ومتوازن. lines = [dict(account_id, debit, credit, cost_center_id, description)]"""
    total_dr = d0(0)
    total_cr = d0(0)
    clean = []
    for ln in lines:
        debit = d0(ln.get("debit"))
        credit = d0(ln.get("credit"))
        if debit == 0 and credit == 0:
            continue
        if debit > 0 and credit > 0:
            raise ValueError("accounting.oneSideOnly")
        if not ln.get("account_id"):
            raise ValueError("accounting.accountRequired")
        total_dr += debit
        total_cr += credit
        clean.append({
            "account_id": int(ln["account_id"]),
            "cost_center_id": ln.get("cost_center_id") or None,
            "debit": debit,
            "credit": credit,
            "description": (ln.get("description") or "").strip(),
        })
    if not clean:
        raise ValueError("accounting.emptyEntry")
    if abs(total_dr - total_cr) > 0.005:
        raise ValueError("accounting.notBalanced")

    entry = JournalEntry(
        date=date or datetime.date.today(),
        financial_year_id=financial_year_id,
        description=(description or "").strip(),
        source=source,
        ref_type=ref_type,
        ref_id=ref_id,
        status="posted",
    )
    entry.entry_number = next_entry_number(financial_year_id)
    for ln in clean:
        entry.lines.append(JournalEntryLine(
            account_id=ln["account_id"],
            cost_center_id=ln["cost_center_id"],
            debit=ln["debit"],
            credit=ln["credit"],
            description=ln["description"],
        ))
    db.session.add(entry)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return entry


def delete_source_entries(source, ref_type, ref_id, commit=True):
    """حذف القيود المرتبطة بمصدر خارجي (فاتورة/قسمة...)."""
    if ref_id in (None, ""):
        return 0
    entries = JournalEntry.query.filter_by(source=source, ref_type=ref_type, ref_id=int(ref_id)).all()
    for e in entries:
        db.session.delete(e)
    if entries and commit:
        db.session.commit()
    return len(entries)


def account_balance(account, end_date=None, year_id=None):
    """رصيد حساب بعد اعتبار نوعه (مدين/دائن) والرصيد الافتتاحي."""
    year_id = _clean_year(year_id)
    sums = db.session.query(
        db.func.coalesce(db.func.sum(JournalEntryLine.debit), 0),
        db.func.coalesce(db.func.sum(JournalEntryLine.credit), 0),
    ).join(
        JournalEntry, JournalEntryLine.entry_id == JournalEntry.id
    ).filter(
        JournalEntryLine.account_id == account.id,
        JournalEntry.status == "posted",
    )
    if end_date:
        sums = sums.filter(JournalEntry.date <= end_date)
    if year_id:
        sums = sums.filter(JournalEntry.financial_year_id == year_id)
    debit, credit = sums.first()
    opening = d0(account.opening_balance)
    if account.is_debit_normal:
        return float(opening + d0(debit) - d0(credit))
    return float(opening + d0(credit) - d0(debit))


def ledger(account_id, start_date=None, end_date=None, year_id=None):
    """دفتر الأستاذ لحساب: سطور + رصيد تراكمي."""
    year_id = _clean_year(year_id)
    q = db.session.query(JournalEntryLine).join(
        JournalEntry, JournalEntryLine.entry_id == JournalEntry.id
    ).filter(
        JournalEntryLine.account_id == account_id,
        JournalEntry.status == "posted",
    )
    if start_date:
        q = q.filter(JournalEntry.date >= start_date)
    if end_date:
        q = q.filter(JournalEntry.date <= end_date)
    if year_id:
        q = q.filter(JournalEntry.financial_year_id == year_id)
    rows = q.order_by(JournalEntry.date.asc(), JournalEntry.id.asc()).all()
    out = []
    running = d0(0)
    acc = db.session.get(Account, account_id)
    opening = d0(acc.opening_balance) if acc else d0(0)
    running = opening
    for line in rows:
        running += d0(line.debit) - d0(line.credit) if (acc and acc.is_debit_normal) else d0(line.credit) - d0(line.debit)
        out.append({
            "id": line.id,
            "date": line.entry.date.isoformat() if line.entry.date else None,
            "entry_id": line.entry_id,
            "entry_number": line.entry.entry_number if line.entry else None,
            "description": line.description or (line.entry.description if line.entry else ""),
            "debit": float(line.debit or 0),
            "credit": float(line.credit or 0),
            "balance": float(running),
        })
    return out


def trial_balance(year_id=None, end_date=None):
    """ميزان المراجعة: كل الحسابات النشطة مع حركة وأرصدة."""
    year_id = _clean_year(year_id)
    rows = []
    total_dr = d0(0)
    total_cr = d0(0)
    for acc in Account.query.order_by(Account.code.asc()).all():
        q = db.session.query(
            db.func.coalesce(db.func.sum(JournalEntryLine.debit), 0),
            db.func.coalesce(db.func.sum(JournalEntryLine.credit), 0),
        ).join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id).filter(
            JournalEntryLine.account_id == acc.id,
            JournalEntry.status == "posted",
        )
        if end_date:
            q = q.filter(JournalEntry.date <= end_date)
        if year_id:
            q = q.filter(JournalEntry.financial_year_id == year_id)
        debit, credit = q.first()
        debit = d0(debit)
        credit = d0(credit)
        if debit == 0 and credit == 0 and acc.opening_balance == 0:
            continue
        opening = d0(acc.opening_balance)
        if acc.is_debit_normal:
            total_dr += opening + debit
            total_cr += credit
            balance = opening + debit - credit
        else:
            total_dr += debit
            total_cr += opening + credit
            balance = opening + credit - debit
        rows.append({
            "code": acc.code,
            "name": acc.name,
            "type": acc.type,
            "debit": float(debit),
            "credit": float(credit),
            "opening": float(opening),
            "balance": float(balance),
        })
    return {"rows": rows, "total_debit": float(total_dr), "total_credit": float(total_cr)}


def _revenue_balance(end_date=None, year_id=None):
    total = d0(0)
    for acc in Account.query.filter_by(type="revenue").all():
        total += d0(account_balance(acc, end_date, year_id))
    return total


def _expense_balance(end_date=None, year_id=None):
    total = d0(0)
    for acc in Account.query.filter_by(type="expense").all():
        total += d0(account_balance(acc, end_date, year_id))
    return total


def income_statement(start_date=None, end_date=None, year_id=None):
    """الأرباح والخسائر (بند لكل حساب إيراد/مصروف)."""
    revenues = []
    expenses = []
    total_rev = d0(0)
    total_exp = d0(0)
    for acc in Account.query.filter_by(type="revenue").order_by(Account.code.asc()).all():
        bal = account_balance(acc, end_date, year_id)
        if bal != 0:
            revenues.append({"code": acc.code, "name": acc.name, "amount": bal})
            total_rev += d0(bal)
    for acc in Account.query.filter_by(type="expense").order_by(Account.code.asc()).all():
        bal = account_balance(acc, end_date, year_id)
        if bal != 0:
            expenses.append({"code": acc.code, "name": acc.name, "amount": bal})
            total_exp += d0(bal)
    net = float(total_rev - total_exp)
    return {
        "revenues": revenues, "expenses": expenses,
        "total_revenue": float(total_rev), "total_expense": float(total_exp),
        "net_income": net,
    }


def balance_sheet(end_date=None, year_id=None):
    """الميزانية العمومية: أصول = خصوم + حقوق ملكية."""
    assets = []
    liabilities = []
    equity = []
    total_assets = d0(0)
    total_liab = d0(0)
    total_eq = d0(0)

    def add_section(items, total, acc, bal):
        contribution = -d0(bal) if acc.is_contra else d0(bal)
        items.append({"code": acc.code, "name": acc.name, "amount": float(contribution)})
        return total + contribution

    for acc in Account.query.filter_by(type="asset").order_by(Account.code.asc()).all():
        bal = account_balance(acc, end_date, year_id)
        if bal != 0:
            total_assets = add_section(assets, total_assets, acc, bal)
    for acc in Account.query.filter_by(type="liability").order_by(Account.code.asc()).all():
        bal = account_balance(acc, end_date, year_id)
        if bal != 0:
            total_liab = add_section(liabilities, total_liab, acc, bal)
    for acc in Account.query.filter_by(type="equity").order_by(Account.code.asc()).all():
        bal = account_balance(acc, end_date, year_id)
        if bal != 0:
            total_eq = add_section(equity, total_eq, acc, bal)
    net = d0(_revenue_balance(end_date, year_id) - _expense_balance(end_date, year_id))
    total_eq += net
    if net != 0:
        equity.append({"code": "-", "name": "صافي النتيجة (الحالي)", "amount": float(net)})
    return {
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "total_assets": float(total_assets),
        "total_liabilities": float(total_liab),
        "total_equity": float(total_eq),
        "balanced": abs(total_assets - (total_liab + total_eq)) < 0.05,
    }


def cash_flow(start_date=None, end_date=None, year_id=None):
    """قائمة التدفقات النقدية (طريقة مباشرة مبسطة) من القيود المؤثرة على النقدية."""
    year_id = _clean_year(year_id)
    cash_account_ids = [a.id for a in Account.query.filter(
        (Account.is_cash == True) | (Account.is_bank == True)).all()]  # noqa: E712
    q = db.session.query(JournalEntry).filter(
        JournalEntry.status == "posted",
    )
    if year_id:
        q = q.filter(JournalEntry.financial_year_id == year_id)
    entries = q.order_by(JournalEntry.date.asc()).all()
    if start_date:
        entries = [e for e in entries if e.date >= start_date]
    if end_date:
        entries = [e for e in entries if e.date <= end_date]

    op_in, op_out = d0(0), d0(0)
    inv_in, inv_out = d0(0), d0(0)
    fin_in, fin_out = d0(0), d0(0)

    recv_id = default_account_id("acc_default_receivable")
    pay_id = default_account_id("acc_default_payable")
    op_counter_ids = {recv_id, pay_id,
                      default_account_id("acc_default_tax_in"),
                      default_account_id("acc_default_tax_out")}

    for e in entries:
        cash_lines = [l for l in e.lines if l.account_id in cash_account_ids]
        if not cash_lines:
            continue
        net_cash = d0(sum(l.debit for l in cash_lines) - sum(l.credit for l in cash_lines))
        others = [l for l in e.lines if l.account_id not in cash_account_ids]
        kind = None
        for l in others:
            if l.account_id in op_counter_ids:
                kind = "operating"
                break
        if kind is None:
            for l in others:
                t = l.account.type if l.account else None
                if t in ("revenue", "expense"):
                    kind = "operating"
                    break
        if kind is None:
            for l in others:
                t = l.account.type if l.account else None
                if t in ("asset", "liability", "equity"):
                    if t == "asset":
                        kind = "investing"
                    else:
                        kind = "financing"
                    break
        if kind is None:
            kind = "operating"
        if net_cash > 0:
            if kind == "investing":
                inv_in += net_cash
            elif kind == "financing":
                fin_in += net_cash
            else:
                op_in += net_cash
        elif net_cash < 0:
            net_cash = abs(net_cash)
            if kind == "investing":
                inv_out += net_cash
            elif kind == "financing":
                fin_out += net_cash
            else:
                op_out += net_cash

    return {
        "operating_in": float(op_in), "operating_out": float(op_out),
        "investing_in": float(inv_in), "investing_out": float(inv_out),
        "financing_in": float(fin_in), "financing_out": float(fin_out),
        "net_operating": float(op_in - op_out),
        "net_investing": float(inv_in - inv_out),
        "net_financing": float(fin_in - fin_out),
        "net_cash": float(op_in - op_out + inv_in - inv_out + fin_in - fin_out),
    }


def posting_enabled():
    row = SystemSetting.query.filter_by(key="acc_autopost_invoices").first()
    return row is None or row.value in ("1", "true", "True", "yes")


def post_invoice_entries(invoice):
    """ترحيل تلقائي للفواتير (مبيعات/مشتريات/مصروفات) بقيد متوازن."""
    if not posting_enabled():
        return None
    try:
        dr_acc = default_account_id("acc_default_receivable")
        cr_acc = default_account_id("acc_default_payable")
        rev_acc = default_account_id("acc_default_revenue")
        exp_acc = default_account_id("acc_default_expense")
        tax_in = default_account_id("acc_default_tax_in")
        tax_out = default_account_id("acc_default_tax_out")
        if not (dr_acc and cr_acc and rev_acc and exp_acc):
            return None

        delete_source_entries("invoice", "invoice", invoice.id, commit=False)

        items = invoice.items or []
        if items:
            subtotal = d0(sum(d0(i.quantity) * d0(i.unit_price) for i in items))
            tax = d0(sum(d0(i.quantity) * d0(i.unit_price) * d0(i.tax_rate) / 100 for i in items))
            total = subtotal + tax
        else:
            total = d0(invoice.amount)
            subtotal = total
            tax = d0(0)

        date = invoice.issue_date or datetime.date.today()
        desc = f"{invoice.invoice_number} - {invoice.description or ''}".strip()
        lines = []
        if invoice.invoice_type == "sales":
            lines = [
                {"account_id": dr_acc, "debit": total, "credit": 0, "description": desc},
                {"account_id": rev_acc, "debit": 0, "credit": subtotal, "description": desc},
            ]
            if tax > 0 and tax_out:
                lines.append({"account_id": tax_out, "debit": 0, "credit": tax, "description": desc})
        elif invoice.invoice_type in ("purchase", "expense"):
            lines = [
                {"account_id": exp_acc, "debit": subtotal, "credit": 0, "description": desc},
            ]
            if tax > 0 and tax_in:
                lines.append({"account_id": tax_in, "debit": tax, "credit": 0, "description": desc})
            lines.append({"account_id": cr_acc, "debit": 0, "credit": total, "description": desc})
        if not lines:
            return None
        entry = make_entry(
            lines, date=date, description=f"فاتورة {invoice.invoice_number}",
            financial_year_id=invoice.financial_year_id,
            source="invoice", ref_type="invoice", ref_id=invoice.id,
            commit=False,
        )
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        raise


def post_payment_entries(source, ref_type, ref_id, amount, date=None,
                         financial_year_id=None, is_receipt=True, description=""):
    """ترحيل تلقائي للدفعات/التحصيلات: استلام (صندوق ← ذمم) أو دفع (ذمم ← صندوق).

    إعادة الترحيل idempotent: يحذف القيود القديمة للمصدر ثم ينشئ قيد المبلغ الكامل.
    """
    if not posting_enabled():
        return None
    amount = d0(amount)
    if amount <= 0:
        delete_source_entries(source, ref_type, ref_id)
        return None
    try:
        cash = default_account_id("acc_default_cash")
        receivable = default_account_id("acc_default_receivable")
        payable = default_account_id("acc_default_payable")
        if not (cash and receivable and payable):
            return None
        delete_source_entries(source, ref_type, ref_id, commit=False)
        if is_receipt:
            lines = [
                {"account_id": cash, "debit": amount, "credit": 0},
                {"account_id": receivable, "debit": 0, "credit": amount},
            ]
            text = f"تحصيل {description}".strip()
        else:
            lines = [
                {"account_id": payable, "debit": amount, "credit": 0},
                {"account_id": cash, "debit": 0, "credit": amount},
            ]
            text = f"دفعة {description}".strip()
        entry = make_entry(
            lines, date=date or datetime.date.today(),
            description=text,
            financial_year_id=financial_year_id,
            source=source, ref_type=ref_type, ref_id=ref_id,
            commit=False,
        )
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        raise


def post_purchase_order_entries(po):
    """ترحيل تلقائي لأمر الشراء عند الاعتماد (مصروف ← ذمم دائنة)."""
    if not posting_enabled():
        return None
    try:
        exp_acc = default_account_id("acc_default_expense")
        cr_acc = default_account_id("acc_default_payable")
        tax_in = default_account_id("acc_default_tax_in")
        if not (exp_acc and cr_acc):
            return None
        delete_source_entries("po", "po", po.id, commit=False)
        items = po.items or []
        if items:
            subtotal = d0(sum(d0(i.quantity) * d0(i.unit_price) for i in items))
            tax = d0(sum(d0(i.quantity) * d0(i.unit_price) * d0(i.tax_rate) / 100 for i in items))
            total = subtotal + tax
        else:
            total = d0(po.total)
            subtotal = total
            tax = d0(0)
        date = po.order_date or datetime.date.today()
        lines = [{"account_id": exp_acc, "debit": subtotal, "credit": 0}]
        if tax > 0 and tax_in:
            lines.append({"account_id": tax_in, "debit": tax, "credit": 0})
        lines.append({"account_id": cr_acc, "debit": 0, "credit": total})
        entry = make_entry(
            lines, date=date, description=f"أمر شراء {po.po_number}",
            financial_year_id=po.financial_year_id,
            source="po", ref_type="po", ref_id=po.id,
            commit=False,
        )
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        raise


def post_contract_entries(contract):
    """ترحيل تلقائي لعقد الإيجار عند الاعتماد (ذمم مدينة ← إيراد قيمة العقد)."""
    if not posting_enabled():
        return None
    try:
        dr_acc = default_account_id("acc_default_receivable")
        rev_acc = default_account_id("acc_default_revenue")
        if not (dr_acc and rev_acc):
            return None
        delete_source_entries("contract", "rental_contract", contract.id, commit=False)
        monthly = d0(contract.monthly_rent)
        if contract.start_date and contract.end_date:
            days = (contract.end_date - contract.start_date).days
            months = max(1, (days + 29) // 30)
        else:
            months = 1
        total = monthly * months
        if total <= 0:
            return None
        date = contract.start_date or datetime.date.today()
        entry = make_entry(
            [
                {"account_id": dr_acc, "debit": total, "credit": 0},
                {"account_id": rev_acc, "debit": 0, "credit": total},
            ],
            date=date, description=f"عقد إيجار {contract.contract_number}",
            financial_year_id=contract.financial_year_id,
            source="contract", ref_type="rental_contract", ref_id=contract.id,
            commit=False,
        )
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        raise


def reverse_entry(entry, description="إلغاء قيد"):
    """عكس قيد مرتّب بقيد معاكس."""
    lines = []
    for l in entry.lines:
        lines.append({
            "account_id": l.account_id,
            "cost_center_id": l.cost_center_id,
            "debit": d0(l.credit),
            "credit": d0(l.debit),
            "description": description,
        })
    new = make_entry(
        lines, date=datetime.date.today(), description=description,
        financial_year_id=entry.financial_year_id,
        source="manual", ref_type=None, ref_id=None, commit=False,
    )
    new.reversed_of = entry.id
    db.session.commit()
    return new

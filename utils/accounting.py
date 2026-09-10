"""محاسبة القيد المزدوج: دليل حسابات، قيود، أرصدة، تقارير، ترحيل تلقائي."""
import datetime

from database import db
from models import (
    Account, JournalEntry, JournalEntryLine, CostCenter,
    FixedAsset, DepreciationRecord, BudgetLine, FinancialYear,
)
from models.setting import SystemSetting
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from sqlalchemy import text

ACCOUNT_TYPES = ["asset", "liability", "equity", "revenue", "expense"]

TYPE_LABELS = {
    "asset": "accounting.asset",
    "liability": "accounting.liability",
    "equity": "accounting.equity",
    "revenue": "accounting.revenue",
    "expense": "accounting.expense",
}

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
    {"code": "130300", "name": "أراضٍ قيد الاستخدام", "type": "asset", "parent": "130000"},
    {"code": "130400", "name": "مباني تحت الإنشاء", "type": "asset", "parent": "130000"},
    {"code": "130500", "name": "تراخيص وتصاريح عقارية", "type": "asset", "parent": "130000"},
    {"code": "520100", "name": "تكاليف أراضٍ", "type": "expense", "parent": "500000"},
    {"code": "520200", "name": "تكاليف بناء وإنشاء", "type": "expense", "parent": "500000"},
    {"code": "520300", "name": "تراخيص وتصاريح مشاريع", "type": "expense", "parent": "500000"},
    {"code": "520400", "name": "تكاليف تشغيل مشاريع", "type": "expense", "parent": "500000"},
    {"code": "520500", "name": "عمالة مشاريع", "type": "expense", "parent": "500000"},
    {"code": "520600", "name": "هندسة وإشراف مشاريع", "type": "expense", "parent": "500000"},
    {"code": "420100", "name": "إيرادات مبيعات عقارية", "type": "revenue", "parent": "400000"},
    {"code": "420200", "name": "إيرادات إيجارات عقارية", "type": "revenue", "parent": "400000"},
]

DEFAULT_ACCOUNT_MAP = {
    "acc_default_receivable": "120100", "acc_default_payable": "210100",
    "acc_default_cash": "110100", "acc_default_bank": "110200",
    "acc_default_revenue": "410100", "acc_default_expense": "510100",
    "acc_default_equity": "320100", "acc_default_asset": "130100",
    "acc_default_accumulated": "130200", "acc_default_depreciation": "510500",
    "acc_default_tax_in": "120200", "acc_default_tax_out": "220100",
    "acc_re_project_land": "130300", "acc_re_project_building": "130400",
    "acc_re_project_license": "130500", "acc_re_cost_land": "520100",
    "acc_re_cost_construction": "520200", "acc_re_cost_licensing": "520300",
    "acc_re_cost_operating": "520400", "acc_re_cost_labor": "520500",
    "acc_re_cost_engineering": "520600", "acc_re_revenue_sales": "420100",
    "acc_re_revenue_rent": "420200",
}


def seed_default_coa():
    """إنشاء دليل الحسابات الافتراضي + تعيين الحسابات الافتراضية (مرة واحدة)."""
    if Account.query.count() > 0:
        _ensure_default_mapping()
        return
    parents = {}
    for item in DEFAULT_COA:
        acc = Account(
            code=item["code"], name=item["name"], type=item["type"],
            is_cash=item.get("is_cash", False), is_bank=item.get("is_bank", False),
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
    if key not in DEFAULT_ACCOUNT_MAP:
        raise ValueError("accounting.invalidDefaultAccount")
    account_id = int(account_id) if account_id else None
    if account_id is not None and db.session.get(Account, account_id) is None:
        raise ValueError("accounting.accountNotFound")
    row = SystemSetting.query.filter_by(key=key).first()
    if row:
        row.value = str(account_id) if account_id is not None else ""
    else:
        db.session.add(SystemSetting(key=key, value=str(account_id) if account_id is not None else ""))
    db.session.commit()


def next_entry_number(year_id):
    """Generate a journal number safely; PostgreSQL serializes concurrent writers."""
    year = db.session.get(FinancialYear, year_id) if year_id else None
    prefix = "JV"
    if year and year.name:
        prefix = f"JV-{year.name.split()[0]}"

    if db.engine.dialect.name == "postgresql":
        # Transaction-scoped advisory lock: only one writer computes the next
        # number for this prefix at a time. The lock is released on commit/rollback.
        lock_key = f"dynamicpro:journal-seq:{prefix}"
        db.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": lock_key},
        )

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
    if year_id in (None, "", 0, "0"):
        return None
    try:
        return int(year_id)
    except (TypeError, ValueError):
        return None


def make_entry(lines, date=None, description="", financial_year_id=None,
               source="manual", ref_type=None, ref_id=None, commit=True):
    total_dr = d0(0)
    total_cr = d0(0)
    clean = []
    for ln in lines:
        debit = d0(ln.get("debit"))
        credit = d0(ln.get("credit"))
        if debit == 0 and credit == 0:
            continue
        if debit < 0 or credit < 0:
            raise ValueError("accounting.amountNegative")
        if debit > 0 and credit > 0:
            raise ValueError("accounting.oneSideOnly")
        if not ln.get("account_id"):
            raise ValueError("accounting.accountRequired")
        if db.session.get(Account, int(ln["account_id"])) is None:
            raise ValueError("accounting.accountNotFound")
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
    if abs(total_dr - total_cr) > Decimal("0.005"):
        raise ValueError("accounting.notBalanced")

    entry = JournalEntry(
        date=date or datetime.date.today(), financial_year_id=financial_year_id,
        description=(description or "").strip(), source=source, ref_type=ref_type,
        ref_id=ref_id, status="posted",
    )
    entry.entry_number = next_entry_number(financial_year_id)
    for ln in clean:
        entry.lines.append(JournalEntryLine(
            account_id=ln["account_id"], cost_center_id=ln["cost_center_id"],
            debit=ln["debit"], credit=ln["credit"], description=ln["description"],
        ))
    db.session.add(entry)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return entry


def delete_source_entries(source, ref_type, ref_id, commit=True):
    """Preserve posted entries by creating auditable reversal entries.

    Kept under the legacy function name for compatibility with callers. A source
    entry is reversed at most once; the original posting is never physically deleted.
    """
    if ref_id in (None, ""):
        return 0
    entries = JournalEntry.query.filter_by(
        source=source, ref_type=ref_type, ref_id=int(ref_id), status="posted"
    ).all()
    reversed_count = 0
    for entry in entries:
        already_reversed = JournalEntry.query.filter_by(reversed_of=entry.id).first()
        if already_reversed:
            continue
        lines = []
        for line in entry.lines:
            lines.append({
                "account_id": line.account_id,
                "cost_center_id": line.cost_center_id,
                "debit": d0(line.credit),
                "credit": d0(line.debit),
                "description": f"عكس القيد {entry.entry_number}",
            })
        reversal = make_entry(
            lines,
            date=datetime.date.today(),
            description=f"عكس ترحيل {source}/{ref_type} #{ref_id}",
            financial_year_id=entry.financial_year_id,
            source="reversal",
            ref_type=source,
            ref_id=int(ref_id),
            commit=False,
        )
        reversal.reversed_of = entry.id
        reversed_count += 1
    if reversed_count and commit:
        db.session.commit()
    return reversed_count


def account_balance(account, end_date=None, year_id=None):
    year_id = _clean_year(year_id)
    sums = db.session.query(
        db.func.coalesce(db.func.sum(JournalEntryLine.debit), 0),
        db.func.coalesce(db.func.sum(JournalEntryLine.credit), 0),
    ).join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id).filter(
        JournalEntryLine.account_id == account.id, JournalEntry.status == "posted",
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
    year_id = _clean_year(year_id)
    q = db.session.query(JournalEntryLine).join(
        JournalEntry, JournalEntryLine.entry_id == JournalEntry.id
    ).filter(JournalEntryLine.account_id == account_id, JournalEntry.status == "posted")
    if start_date:
        q = q.filter(JournalEntry.date >= start_date)
    if end_date:
        q = q.filter(JournalEntry.date <= end_date)
    if year_id:
        q = q.filter(JournalEntry.financial_year_id == year_id)
    rows = q.order_by(JournalEntry.date.asc(), JournalEntry.id.asc()).all()
    out = []
    acc = db.session.get(Account, account_id)
    running = d0(acc.opening_balance) if acc else d0(0)
    for line in rows:
        running += (d0(line.debit) - d0(line.credit)) if (acc and acc.is_debit_normal) else (d0(line.credit) - d0(line.debit))
        out.append({
            "id": line.id, "date": line.entry.date.isoformat() if line.entry.date else None,
            "entry_id": line.entry_id, "entry_number": line.entry.entry_number if line.entry else None,
            "description": line.description or (line.entry.description if line.entry else ""),
            "debit": float(line.debit or 0), "credit": float(line.credit or 0),
            "balance": float(running),
        })
    return out


def trial_balance(year_id=None, end_date=None):
    year_id = _clean_year(year_id)
    rows = []
    total_dr = d0(0)
    total_cr = d0(0)
    for acc in Account.query.order_by(Account.code.asc()).all():
        q = db.session.query(
            db.func.coalesce(db.func.sum(JournalEntryLine.debit), 0),
            db.func.coalesce(db.func.sum(JournalEntryLine.credit), 0),
        ).join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id).filter(
            JournalEntryLine.account_id == acc.id, JournalEntry.status == "posted",
        )
        if end_date:
            q = q.filter(JournalEntry.date <= end_date)
        if year_id:
            q = q.filter(JournalEntry.financial_year_id == year_id)
        debit, credit = q.first()
        debit, credit = d0(debit), d0(credit)
        opening = d0(acc.opening_balance)
        if debit == 0 and credit == 0 and opening == 0:
            continue
        if acc.is_debit_normal:
            total_dr += opening + debit
            total_cr += credit
            balance = opening + debit - credit
        else:
            total_dr += debit
            total_cr += opening + credit
            balance = opening + credit - debit
        rows.append({"code": acc.code, "name": acc.name, "type": acc.type,
                     "debit": float(debit), "credit": float(credit),
                     "opening": float(opening), "balance": float(balance)})
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
    revenues, expenses = [], []
    total_rev, total_exp = d0(0), d0(0)
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
    return {"revenues": revenues, "expenses": expenses,
            "total_revenue": float(total_rev), "total_expense": float(total_exp),
            "net_income": float(total_rev - total_exp)}


def balance_sheet(end_date=None, year_id=None):
    assets, liabilities, equity = [], [], []
    total_assets, total_liab, total_eq = d0(0), d0(0), d0(0)

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
        "total_assets": float(total_assets), "total_liabilities": float(total_liab),
        "total_equity": float(total_eq),
        "balanced": abs(total_assets - (total_liab + total_eq)) < 0.05,
    }


def cash_flow(start_date=None, end_date=None, year_id=None):
    year_id = _clean_year(year_id)
    cash_account_ids = [a.id for a in Account.query.filter(
        (Account.is_cash == True) | (Account.is_bank == True)).all()]  # noqa: E712
    q = db.session.query(JournalEntry).filter(JournalEntry.status == "posted")
    if year_id:
        q = q.filter(JournalEntry.financial_year_id == year_id)
    entries = q.order_by(JournalEntry.date.asc()).all()
    if start_date:
        entries = [e for e in entries if e.date >= start_date]
    if end_date:
        entries = [e for e in entries if e.date <= end_date]

    op_in = op_out = inv_in = inv_out = fin_in = fin_out = d0(0)
    recv_id = default_account_id("acc_default_receivable")
    pay_id = default_account_id("acc_default_payable")
    op_counter_ids = {recv_id, pay_id, default_account_id("acc_default_tax_in"), default_account_id("acc_default_tax_out")}
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
                if l.account.type in ("revenue", "expense") if l.account else False:
                    kind = "operating"
                    break
        if kind is None:
            for l in others:
                t = l.account.type if l.account else None
                if t in ("asset", "liability", "equity"):
                    kind = "investing" if t == "asset" else "financing"
                    break
        kind = kind or "operating"
        if net_cash > 0:
            if kind == "investing": inv_in += net_cash
            elif kind == "financing": fin_in += net_cash
            else: op_in += net_cash
        elif net_cash < 0:
            net_cash = abs(net_cash)
            if kind == "investing": inv_out += net_cash
            elif kind == "financing": fin_out += net_cash
            else: op_out += net_cash

    return {
        "operating_in": float(op_in), "operating_out": float(op_out),
        "investing_in": float(inv_in), "investing_out": float(inv_out),
        "financing_in": float(fin_in), "financing_out": float(fin_out),
        "net_operating": float(op_in - op_out), "net_investing": float(inv_in - inv_out),
        "net_financing": float(fin_in - fin_out),
        "net_cash": float(op_in - op_out + inv_in - inv_out + fin_in - fin_out),
    }


def posting_enabled():
    row = SystemSetting.query.filter_by(key="acc_autopost_invoices").first()
    return row is None or row.value in ("1", "true", "True", "yes")


def post_invoice_entries(invoice):
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
            total = d0(invoice.amount); subtotal = total; tax = d0(0)
        date = invoice.issue_date or datetime.date.today()
        desc = f"{invoice.invoice_number} - {invoice.description or ''}".strip()
        if invoice.invoice_type == "sales":
            lines = [
                {"account_id": dr_acc, "debit": total, "credit": 0, "description": desc},
                {"account_id": rev_acc, "debit": 0, "credit": subtotal, "description": desc},
            ]
            if tax > 0 and tax_out:
                lines.append({"account_id": tax_out, "debit": 0, "credit": tax, "description": desc})
        elif invoice.invoice_type in ("purchase", "expense"):
            lines = [{"account_id": exp_acc, "debit": subtotal, "credit": 0, "description": desc}]
            if tax > 0 and tax_in:
                lines.append({"account_id": tax_in, "debit": tax, "credit": 0, "description": desc})
            lines.append({"account_id": cr_acc, "debit": 0, "credit": total, "description": desc})
        else:
            return None
        entry = make_entry(
            lines, date=date, description=f"فاتورة {invoice.invoice_number}",
            financial_year_id=invoice.financial_year_id,
            source="invoice", ref_type="invoice", ref_id=invoice.id, commit=False,
        )
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        raise


def post_payment_entries(source, ref_type, ref_id, amount, date=None,
                         financial_year_id=None, is_receipt=True, description=""):
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
            lines = [{"account_id": cash, "debit": amount, "credit": 0}, {"account_id": receivable, "debit": 0, "credit": amount}]
            text_desc = f"تحصيل {description}".strip()
        else:
            lines = [{"account_id": payable, "debit": amount, "credit": 0}, {"account_id": cash, "debit": 0, "credit": amount}]
            text_desc = f"دفعة {description}".strip()
        entry = make_entry(lines, date=date or datetime.date.today(), description=text_desc,
                           financial_year_id=financial_year_id, source=source,
                           ref_type=ref_type, ref_id=ref_id, commit=False)
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        raise


def post_purchase_order_entries(po):
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
            total = d0(po.total); subtotal = total; tax = d0(0)
        date = po.order_date or datetime.date.today()
        lines = [{"account_id": exp_acc, "debit": subtotal, "credit": 0}]
        if tax > 0 and tax_in:
            lines.append({"account_id": tax_in, "debit": tax, "credit": 0})
        lines.append({"account_id": cr_acc, "debit": 0, "credit": total})
        entry = make_entry(lines, date=date, description=f"أمر شراء {po.po_number}",
                           financial_year_id=po.financial_year_id, source="po", ref_type="po",
                           ref_id=po.id, commit=False)
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        raise


def post_contract_entries(contract):
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
        entry = make_entry(
            [{"account_id": dr_acc, "debit": total, "credit": 0},
             {"account_id": rev_acc, "debit": 0, "credit": total}],
            date=contract.start_date or datetime.date.today(),
            description=f"عقد إيجار {contract.contract_number}",
            financial_year_id=contract.financial_year_id, source="contract",
            ref_type="rental_contract", ref_id=contract.id, commit=False,
        )
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        raise


def reverse_entry(entry, description="إلغاء قيد"):
    if entry.status != "posted":
        raise ValueError("accounting.entryNotPosted")
    existing = JournalEntry.query.filter_by(reversed_of=entry.id).first()
    if existing:
        return existing
    lines = [{
        "account_id": l.account_id, "cost_center_id": l.cost_center_id,
        "debit": d0(l.credit), "credit": d0(l.debit), "description": description,
    } for l in entry.lines]
    new = make_entry(lines, date=datetime.date.today(), description=description,
                     financial_year_id=entry.financial_year_id, source="reversal",
                     ref_type="journal_entry", ref_id=entry.id, commit=False)
    new.reversed_of = entry.id
    db.session.commit()
    return new

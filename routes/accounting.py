"""الإدارة المالية (قيد مزدوج): صفحات + واجهات برمجة."""
import datetime

from flask import Blueprint, render_template, request, jsonify, session
from database import db
from permissions import require_page, require_api
from auditlog import log_action
from models import (
    Account, CostCenter, JournalEntry, JournalEntryLine,
    FixedAsset, DepreciationRecord, BudgetLine, FinancialYear,
    Invoice, Customer, Supplier,
)
from routes.financial_years import financial_year_error
import utils.accounting as acct
from utils.pagination import paged_or_cap

accounting_bp = Blueprint("accounting", __name__, url_prefix="/accounting")


def _d(s):
    if not s:
        return None
    try:
        return datetime.datetime.strptime(str(s), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _years():
    return [y.to_dict() for y in FinancialYear.query.order_by(FinancialYear.start_date.desc()).all()]


def _year_error(fy_id):
    if fy_id in (None, "", 0):
        return None
    return financial_year_error(fy_id)


def _log(action, entity, entity_id, description):
    log_action(action, entity, entity_id, description)


# ==================== صفحات ====================

@accounting_bp.route("/")
@require_page("accounting")
def dashboard():
    return render_template("accounting.html")


@accounting_bp.route("/chart")
@require_page("accounting")
def chart_page():
    return render_template("accounting_chart.html")


@accounting_bp.route("/cost-centers")
@require_page("accounting")
def cost_centers_page():
    return render_template("accounting_costcenters.html")


@accounting_bp.route("/journal")
@require_page("accounting")
def journal_page():
    return render_template("accounting_journal.html")


@accounting_bp.route("/cash")
@require_page("accounting")
def cash_page():
    return render_template("accounting_cash.html")


@accounting_bp.route("/banks")
@require_page("accounting")
def banks_page():
    return render_template("accounting_banks.html")


@accounting_bp.route("/receivables")
@require_page("accounting")
def receivables_page():
    return render_template("accounting_receivables.html")


@accounting_bp.route("/expenses")
@require_page("accounting")
def expenses_page():
    return render_template("accounting_expenses.html")


@accounting_bp.route("/budget")
@require_page("accounting")
def budget_page():
    return render_template("accounting_budget.html")


@accounting_bp.route("/reconciliations")
@require_page("accounting")
def reconciliations_page():
    return render_template("accounting_reconciliations.html")


@accounting_bp.route("/fixed-assets")
@require_page("accounting")
def assets_page():
    return render_template("accounting_assets.html")


@accounting_bp.route("/reports")
@require_page("accounting")
def reports_page():
    return render_template("accounting_reports.html")


# ==================== بيانات عامة ====================

@accounting_bp.route("/api/meta")
@require_api("accounting", "view")
def meta():
    accounts = [a.to_dict() for a in Account.query.order_by(Account.code.asc()).all()]
    cost_centers = [c.to_dict() for c in CostCenter.query.all()]
    cash_accounts = [a.to_dict() for a in Account.query.filter_by(is_cash=True).order_by(Account.code.asc()).all()]
    bank_accounts = [a.to_dict() for a in Account.query.filter_by(is_bank=True).order_by(Account.code.asc()).all()]
    defaults = {}
    for key in acct.DEFAULT_ACCOUNT_MAP:
        defaults[key] = acct.default_account_id(key)
    customers = [{"id": c.id, "name": c.full_name} for c in Customer.query.order_by(Customer.full_name.asc()).limit(500).all()]
    suppliers = [{"id": s.id, "name": s.company_name} for s in Supplier.query.order_by(Supplier.company_name.asc()).limit(500).all()]
    return jsonify({
        "accounts": accounts,
        "cost_centers": cost_centers,
        "cash_accounts": cash_accounts,
        "bank_accounts": bank_accounts,
        "defaults": defaults,
        "years": _years(),
        "customers": customers,
        "suppliers": suppliers,
    })


# ==================== دليل الحسابات ====================

@accounting_bp.route("/api/accounts")
@require_api("accounting", "view")
def list_accounts():
    end_date = _d(request.args.get("end_date"))
    year_id = request.args.get("year_id")
    accounts = Account.query.order_by(Account.code.asc()).all()
    out = []
    for a in accounts:
        d = a.to_dict()
        d["balance"] = acct.account_balance(a, end_date, year_id)
        out.append(d)
    return jsonify(out)


@accounting_bp.route("/api/accounts", methods=["POST"])
@require_api("accounting", "create")
def create_account():
    data = request.get_json(force=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        return jsonify({"message": "common.required"}), 400
    if Account.query.filter_by(code=code).first():
        return jsonify({"message": "accounting.codeExists"}), 400
    opening_balance = float(data.get("opening_balance") or 0)
    acc = Account(
        code=code,
        name=name,
        type=data.get("type", "asset"),
        parent_id=data.get("parent_id") or None,
        is_active=bool(data.get("is_active", True)),
        is_cash=bool(data.get("is_cash")),
        is_bank=bool(data.get("is_bank")),
        is_contra=bool(data.get("is_contra")),
        bank_name=(data.get("bank_name") or "").strip() or None,
        account_number=(data.get("account_number") or "").strip() or None,
        currency_code=(data.get("currency_code") or "").strip() or None,
        opening_balance=0,
        description=(data.get("description") or "").strip() or None,
    )
    db.session.add(acc)
    try:
        db.session.flush()
        if opening_balance != 0:
            _post_opening_entry(acc, opening_balance)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
    _log("create", "account", acc.id, f"إنشاء حساب: {acc.code} - {acc.name}")
    return jsonify({"success": True, "account": acc.to_dict()})


def _default_fy_and_date():
    """السنة المالية المفتوحة النشطة + تاريخ بدايتها للقيود الافتتاحية."""
    from utils.settings import get_int
    year_id = get_int("default_financial_year_id")
    year = db.session.get(FinancialYear, year_id) if year_id else None
    if not year:
        year = FinancialYear.query.filter_by(is_active=True, is_closed=False) \
            .order_by(FinancialYear.start_date.desc()).first()
    if year and not year.is_closed:
        return year.id, (year.start_date or datetime.date.today())
    return None, datetime.date.today()


def _post_opening_entry(acc, amount):
    """قيد افتتاحي للرصيد الافتتاحي (مقابل حساب أرباح مرحلة) للحفاظ على توازن القيد المزدوج."""
    if amount == 0:
        return
    counter = acct.default_account_id("acc_default_equity")
    if not counter:
        raise ValueError("accounting.equityAccountRequired")
    year_id, date = _default_fy_and_date()
    if acc.is_debit_normal:
        lines = [
            {"account_id": acc.id, "debit": amount, "credit": 0, "description": "رصيد افتتاحي"},
            {"account_id": counter, "debit": 0, "credit": amount, "description": "رصيد افتتاحي"},
        ]
    else:
        lines = [
            {"account_id": acc.id, "debit": 0, "credit": amount, "description": "رصيد افتتاحي"},
            {"account_id": counter, "debit": amount, "credit": 0, "description": "رصيد افتتاحي"},
        ]
    acct.make_entry(lines, date=date,
                    description=f"رصيد افتتاحي - {acc.code}",
                    financial_year_id=year_id,
                    source="opening", ref_type="account", ref_id=acc.id,
                    commit=False)


@accounting_bp.route("/api/accounts/<int:account_id>", methods=["PUT"])
@require_api("accounting", "edit")
def update_account(account_id):
    acc = db.session.get(Account, account_id)
    if not acc:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    dup = Account.query.filter(Account.code == code, Account.id != account_id).first()
    if dup:
        return jsonify({"message": "accounting.codeExists"}), 400
    if code:
        acc.code = code
    if name:
        acc.name = name
    if "type" in data:
        acc.type = data.get("type", acc.type)
    if "parent_id" in data:
        acc.parent_id = data.get("parent_id") or None
    if "is_active" in data:
        acc.is_active = bool(data.get("is_active"))
    if "is_cash" in data:
        acc.is_cash = bool(data.get("is_cash"))
    if "is_bank" in data:
        acc.is_bank = bool(data.get("is_bank"))
    if "is_contra" in data:
        acc.is_contra = bool(data.get("is_contra"))
    acc.bank_name = (data.get("bank_name") or "").strip() or None
    acc.account_number = (data.get("account_number") or "").strip() or None
    acc.currency_code = (data.get("currency_code") or "").strip() or None
    if "description" in data:
        acc.description = (data.get("description") or "").strip() or None
    db.session.commit()
    _log("update", "account", acc.id, f"تعديل حساب: {acc.code} - {acc.name}")
    return jsonify({"success": True, "account": acc.to_dict()})


@accounting_bp.route("/api/accounts/<int:account_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_account(account_id):
    acc = db.session.get(Account, account_id)
    if not acc:
        return jsonify({"message": "common.notFound"}), 404
    used = JournalEntryLine.query.filter_by(account_id=account_id).first()
    if used:
        return jsonify({"message": "accounting.accountUsed"}), 400
    if Account.query.filter_by(parent_id=account_id).first():
        return jsonify({"message": "accounting.hasChildren"}), 400
    if acct.default_account_id("acc_default_cash") == account_id or \
       acct.default_account_id("acc_default_bank") == account_id:
        return jsonify({"message": "accounting.isDefault"}), 400
    db.session.delete(acc)
    db.session.commit()
    _log("delete", "account", account_id, f"حذف حساب: {acc.code} - {acc.name}")
    return jsonify({"success": True})


@accounting_bp.route("/api/accounts/defaults", methods=["POST"])
@require_api("accounting", "edit")
def save_defaults():
    data = request.get_json(force=True) or {}
    for key in acct.DEFAULT_ACCOUNT_MAP:
        if key in data:
            val = data.get(key)
            acct.set_default_account_id(key, int(val) if val else None)
    _log("update", "account", 0, "تحديث الحسابات الافتراضية للترحيل")
    return jsonify({"success": True})


# ==================== مراكز التكلفة ====================

@accounting_bp.route("/api/cost-centers")
@require_api("accounting", "view")
def list_cost_centers():
    return jsonify([c.to_dict() for c in CostCenter.query.order_by(CostCenter.code.asc()).all()])


@accounting_bp.route("/api/cost-centers", methods=["POST"])
@require_api("accounting", "create")
def create_cost_center():
    data = request.get_json(force=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        return jsonify({"message": "common.required"}), 400
    if CostCenter.query.filter_by(code=code).first():
        return jsonify({"message": "accounting.codeExists"}), 400
    cc = CostCenter(code=code, name=name, is_active=bool(data.get("is_active", True)))
    db.session.add(cc)
    db.session.commit()
    _log("create", "cost_center", cc.id, f"إنشاء مركز تكلفة: {cc.code} - {cc.name}")
    return jsonify({"success": True, "cost_center": cc.to_dict()})


@accounting_bp.route("/api/cost-centers/<int:cc_id>", methods=["PUT"])
@require_api("accounting", "edit")
def update_cost_center(cc_id):
    cc = db.session.get(CostCenter, cc_id)
    if not cc:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    dup = CostCenter.query.filter(CostCenter.code == code, CostCenter.id != cc_id).first()
    if dup:
        return jsonify({"message": "accounting.codeExists"}), 400
    if code:
        cc.code = code
    if name:
        cc.name = name
    if "is_active" in data:
        cc.is_active = bool(data.get("is_active"))
    db.session.commit()
    _log("update", "cost_center", cc.id, f"تعديل مركز تكلفة: {cc.code}")
    return jsonify({"success": True, "cost_center": cc.to_dict()})


@accounting_bp.route("/api/cost-centers/<int:cc_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_cost_center(cc_id):
    cc = db.session.get(CostCenter, cc_id)
    if not cc:
        return jsonify({"message": "common.notFound"}), 404
    if JournalEntryLine.query.filter_by(cost_center_id=cc_id).first():
        return jsonify({"message": "accounting.ccUsed"}), 400
    db.session.delete(cc)
    db.session.commit()
    _log("delete", "cost_center", cc_id, f"حذف مركز تكلفة: {cc.code}")
    return jsonify({"success": True})


# ==================== القيود اليومية ====================

def _entry_dict(e):
    return e.to_dict()


@accounting_bp.route("/api/journal")
@require_api("accounting", "view")
def list_journal():
    q = JournalEntry.query
    year_id = request.args.get("year_id")
    start = _d(request.args.get("start"))
    end = _d(request.args.get("end"))
    source = request.args.get("source")
    if year_id not in (None, "", "0"):
        q = q.filter_by(financial_year_id=int(year_id))
    if start:
        q = q.filter(JournalEntry.date >= start)
    if end:
        q = q.filter(JournalEntry.date <= end)
    if source:
        q = q.filter_by(source=source)
    items, envelope = paged_or_cap(q.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()), serializer=_entry_dict)
    return jsonify(envelope if envelope else items)


@accounting_bp.route("/api/journal", methods=["POST"])
@require_api("accounting", "create")
def create_journal():
    data = request.get_json(force=True) or {}
    date = _d(data.get("date"))
    if not date:
        return jsonify({"message": "accounting.dateRequired"}), 400
    fy_id = data.get("financial_year_id")
    err = _year_error(fy_id)
    if err:
        return jsonify({"message": err}), 400
    lines = data.get("lines") or []
    try:
        entry = acct.make_entry(
            lines,
            date=date,
            description=data.get("description") or "",
            financial_year_id=int(fy_id) if fy_id not in (None, "", 0) else None,
            source="manual",
        )
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    _log("create", "journal", entry.id, f"قيد {entry.entry_number}")
    return jsonify({"success": True, "entry": _entry_dict(entry)})


@accounting_bp.route("/api/journal/<int:entry_id>")
@require_api("accounting", "view")
def get_journal(entry_id):
    e = db.session.get(JournalEntry, entry_id)
    if not e:
        return jsonify({"message": "common.notFound"}), 404
    return jsonify(_entry_dict(e))


@accounting_bp.route("/api/journal/<int:entry_id>/reverse", methods=["POST"])
@require_api("accounting", "create")
def reverse_journal(entry_id):
    e = db.session.get(JournalEntry, entry_id)
    if not e:
        return jsonify({"message": "common.notFound"}), 404
    err = _year_error(e.financial_year_id)
    if err:
        return jsonify({"message": err}), 400
    new = acct.reverse_entry(e, description=f"عكس قيد {e.entry_number}")
    _log("create", "journal", new.id, f"عكس قيد {e.entry_number}")
    return jsonify({"success": True, "entry": _entry_dict(new)})


@accounting_bp.route("/api/journal/<int:entry_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_journal(entry_id):
    e = db.session.get(JournalEntry, entry_id)
    if not e:
        return jsonify({"message": "common.notFound"}), 404
    if e.source != "manual":
        return jsonify({"message": "accounting.deleteSourceBlocked"}), 400
    err = _year_error(e.financial_year_id)
    if err:
        return jsonify({"message": err}), 400
    num = e.entry_number
    # Soft-delete: أرشفة القيد بدل حذفه الفعلي (سجل محاسبي يجب ألا يُفقد)
    e.status = "cancelled"
    from datetime import datetime as _dt
    e.deleted_at = _dt.now()
    db.session.commit()
    _log("delete", "journal", entry_id, f"إلغاء/أرشفة قيد {num}")
    return jsonify({"success": True})


# ==================== الصندوق والبنوك ====================

def _cash_bank_list(is_bank):
    q = Account.query.filter_by(is_bank=True) if is_bank else Account.query.filter_by(is_cash=True)
    out = []
    for a in q.order_by(Account.code.asc()).all():
        d = a.to_dict()
        d["balance"] = acct.account_balance(a)
        out.append(d)
    return out


@accounting_bp.route("/api/cash")
@require_api("accounting", "view")
def list_cash():
    accounts = _cash_bank_list(False)
    return jsonify({"accounts": accounts, "defaults": {
        "cash": acct.default_account_id("acc_default_cash"),
        "receivable": acct.default_account_id("acc_default_receivable"),
        "payable": acct.default_account_id("acc_default_payable"),
        "expense": acct.default_account_id("acc_default_expense"),
        "revenue": acct.default_account_id("acc_default_revenue"),
    }})


@accounting_bp.route("/api/banks")
@require_api("accounting", "view")
def list_banks():
    accounts = _cash_bank_list(True)
    return jsonify({"accounts": accounts, "defaults": {
        "bank": acct.default_account_id("acc_default_bank"),
        "receivable": acct.default_account_id("acc_default_receivable"),
        "payable": acct.default_account_id("acc_default_payable"),
        "expense": acct.default_account_id("acc_default_expense"),
        "revenue": acct.default_account_id("acc_default_revenue"),
    }})


@accounting_bp.route("/api/<string:kind>/op", methods=["POST"])
@require_api("accounting", "create")
def cash_bank_op(kind):
    if kind not in ("cash", "bank"):
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    account_id = data.get("account_id")
    amount = float(data.get("amount") or 0)
    direction = data.get("direction")  # receive | pay
    if not account_id:
        return jsonify({"message": "accounting.accountRequired"}), 400
    if amount <= 0:
        return jsonify({"message": "accounting.amountPositive"}), 400
    if direction not in ("receive", "pay"):
        return jsonify({"message": "common.required"}), 400
    acc = db.session.get(Account, int(account_id))
    if not acc or (kind == "cash" and not acc.is_cash) or (kind == "bank" and not acc.is_bank):
        return jsonify({"message": "accounting.notCashAccount"}), 400
    fy_id = data.get("financial_year_id")
    err = _year_error(fy_id)
    if err:
        return jsonify({"message": err}), 400
    counter_id = data.get("counterpart_account_id")
    if not counter_id:
        counter_id = acct.default_account_id(
            "acc_default_receivable" if direction == "receive" else "acc_default_expense")
    if not counter_id:
        return jsonify({"message": "accounting.counterpartRequired"}), 400
    description = (data.get("description") or "").strip()
    date = _d(data.get("date")) or datetime.date.today()
    if direction == "receive":
        lines = [
            {"account_id": int(account_id), "debit": amount, "credit": 0,
             "cost_center_id": data.get("cost_center_id") or None, "description": description},
            {"account_id": int(counter_id), "debit": 0, "credit": amount, "description": description},
        ]
    else:
        lines = [
            {"account_id": int(account_id), "debit": 0, "credit": amount,
             "cost_center_id": data.get("cost_center_id") or None, "description": description},
            {"account_id": int(counter_id), "debit": amount, "credit": 0, "description": description},
        ]
    try:
        entry = acct.make_entry(
            lines, date=date, description=description,
            financial_year_id=int(fy_id) if fy_id not in (None, "", 0) else None,
            source=kind, ref_type=kind, ref_id=int(account_id))
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    _log("create", "journal", entry.id, f"{'قبض' if direction == 'receive' else 'صرف'} {amount} - {acc.name}")
    return jsonify({"success": True, "entry": _entry_dict(entry)})


@accounting_bp.route("/api/<string:kind>/ledger")
@require_api("accounting", "view")
def cash_bank_ledger(kind):
    if kind not in ("cash", "bank"):
        return jsonify({"message": "common.notFound"}), 404
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"message": "accounting.accountRequired"}), 400
    start = _d(request.args.get("start"))
    end = _d(request.args.get("end"))
    rows = acct.ledger(int(account_id), start, end)
    acc = db.session.get(Account, int(account_id))
    return jsonify({
        "account": acc.to_dict() if acc else None,
        "balance": acct.account_balance(acc, end) if acc else 0,
        "rows": rows,
    })


# ==================== الذمم (المدينة/الدائنة) ====================

def _aging(records, side):
    """تجميع الأرصدة حسب الفترات العمرية."""
    buckets = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    today = datetime.date.today()
    for r in records:
        if not r.get("due_date"):
            buckets["0-30"] += r["balance"]
            continue
        days = (today - _d(r["due_date"])).days if _d(r["due_date"]) else 0
        if days <= 30:
            buckets["0-30"] += r["balance"]
        elif days <= 60:
            buckets["31-60"] += r["balance"]
        elif days <= 90:
            buckets["61-90"] += r["balance"]
        else:
            buckets["90+"] += r["balance"]
    return buckets


@accounting_bp.route("/api/receivables")
@require_api("accounting", "view")
def receivables():
    customers = Customer.query.order_by(Customer.full_name.asc()).all()
    rows = []
    total = 0.0
    for c in customers:
        invs = [i for i in c.invoices if i.invoice_type == "sales"]
        for i in invs:
            bal = float((i.amount or 0) - (i.paid_amount or 0))
            if bal > 0:
                rows.append({
                    "party_id": c.id,
                    "party": c.full_name,
                    "invoice_number": i.invoice_number,
                    "date": i.issue_date.isoformat() if i.issue_date else None,
                    "due_date": i.due_date.isoformat() if i.due_date else None,
                    "amount": float(i.amount or 0),
                    "paid": float(i.paid_amount or 0),
                    "balance": bal,
                })
                total += bal
    return jsonify({"rows": rows, "total": total, "aging": _aging(rows, "ar"),
                    "account_balance": acct.account_balance(db.session.get(Account, acct.default_account_id("acc_default_receivable")))
                    if acct.default_account_id("acc_default_receivable") else 0})


@accounting_bp.route("/api/payables")
@require_api("accounting", "view")
def payables():
    suppliers = Supplier.query.order_by(Supplier.company_name.asc()).all()
    rows = []
    total = 0.0
    for s in suppliers:
        for i in s.invoices:
            if i.invoice_type not in ("purchase", "expense"):
                continue
            bal = float((i.amount or 0) - (i.paid_amount or 0))
            if bal > 0:
                rows.append({
                    "party_id": s.id,
                    "party": s.company_name,
                    "invoice_number": i.invoice_number,
                    "date": i.issue_date.isoformat() if i.issue_date else None,
                    "due_date": i.due_date.isoformat() if i.due_date else None,
                    "amount": float(i.amount or 0),
                    "paid": float(i.paid_amount or 0),
                    "balance": bal,
                })
                total += bal
    return jsonify({"rows": rows, "total": total, "aging": _aging(rows, "ap"),
                    "account_balance": acct.account_balance(db.session.get(Account, acct.default_account_id("acc_default_payable")))
                    if acct.default_account_id("acc_default_payable") else 0})


# ==================== المصروفات والإيرادات ====================

@accounting_bp.route("/api/entries/by-type")
@require_api("accounting", "view")
def entries_by_type():
    etype = request.args.get("type")  # expense | revenue
    if etype not in ("expense", "revenue"):
        return jsonify({"message": "common.required"}), 400
    account_ids = [a.id for a in Account.query.filter_by(type=etype).all()]
    start = _d(request.args.get("start"))
    end = _d(request.args.get("end"))
    lines = JournalEntryLine.query.filter(
        JournalEntryLine.account_id.in_(account_ids) if account_ids else False
    ).join(JournalEntry).filter(JournalEntry.status == "posted")
    if start:
        lines = lines.filter(JournalEntry.date >= start)
    if end:
        lines = lines.filter(JournalEntry.date <= end)
    rows = []
    for l in lines.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).all():
        rows.append({
            "id": l.id,
            "date": l.entry.date.isoformat() if l.entry.date else None,
            "entry_number": l.entry.entry_number if l.entry else None,
            "account_code": l.account.code if l.account else None,
            "account_name": l.account.name if l.account else None,
            "cost_center": l.cost_center.name if l.cost_center else None,
            "description": l.description or (l.entry.description if l.entry else ""),
            "amount": float((l.debit or 0) + (l.credit or 0)),
        })
    return jsonify({"rows": rows})


@accounting_bp.route("/api/expense", methods=["POST"])
@require_api("accounting", "create")
def create_expense():
    return _create_inc_exp("expense")


@accounting_bp.route("/api/revenue", methods=["POST"])
@require_api("accounting", "create")
def create_revenue():
    return _create_inc_exp("revenue")


def _create_inc_exp(etype):
    data = request.get_json(force=True) or {}
    account_id = data.get("account_id")
    amount = float(data.get("amount") or 0)
    date = _d(data.get("date")) or datetime.date.today()
    fy_id = data.get("financial_year_id")
    err = _year_error(fy_id)
    if err:
        return jsonify({"message": err}), 400
    if not account_id:
        return jsonify({"message": "accounting.accountRequired"}), 400
    if amount <= 0:
        return jsonify({"message": "accounting.amountPositive"}), 400
    acc = db.session.get(Account, int(account_id))
    if not acc or acc.type != etype:
        return jsonify({"message": "accounting.typeMismatch"}), 400
    description = (data.get("description") or "").strip()
    if etype == "expense":
        funding = data.get("funding", "credit")  # cash | bank | credit
        if funding in ("cash", "bank"):
            cash_id = data.get("cash_account_id") or acct.default_account_id(
                "acc_default_cash" if funding == "cash" else "acc_default_bank")
            if not cash_id:
                return jsonify({"message": "accounting.counterpartRequired"}), 400
            lines = [
                {"account_id": int(account_id), "debit": amount, "credit": 0,
                 "cost_center_id": data.get("cost_center_id") or None, "description": description},
                {"account_id": int(cash_id), "debit": 0, "credit": amount, "description": description},
            ]
        else:
            pay_id = data.get("counterpart_account_id") or acct.default_account_id("acc_default_payable")
            if not pay_id:
                return jsonify({"message": "accounting.counterpartRequired"}), 400
            lines = [
                {"account_id": int(account_id), "debit": amount, "credit": 0,
                 "cost_center_id": data.get("cost_center_id") or None, "description": description},
                {"account_id": int(pay_id), "debit": 0, "credit": amount, "description": description},
            ]
    else:
        funding = data.get("funding", "credit")  # cash | bank | credit
        if funding in ("cash", "bank"):
            cash_id = data.get("cash_account_id") or acct.default_account_id(
                "acc_default_cash" if funding == "cash" else "acc_default_bank")
            if not cash_id:
                return jsonify({"message": "accounting.counterpartRequired"}), 400
            lines = [
                {"account_id": int(account_id), "debit": 0, "credit": amount,
                 "cost_center_id": data.get("cost_center_id") or None, "description": description},
                {"account_id": int(cash_id), "debit": amount, "credit": 0, "description": description},
            ]
        else:
            recv_id = data.get("counterpart_account_id") or acct.default_account_id("acc_default_receivable")
            if not recv_id:
                return jsonify({"message": "accounting.counterpartRequired"}), 400
            lines = [
                {"account_id": int(account_id), "debit": 0, "credit": amount,
                 "cost_center_id": data.get("cost_center_id") or None, "description": description},
                {"account_id": int(recv_id), "debit": amount, "credit": 0, "description": description},
            ]
    try:
        entry = acct.make_entry(
            lines, date=date, description=description,
            financial_year_id=int(fy_id) if fy_id not in (None, "", 0) else None,
            source="manual")
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    _log("create", "journal", entry.id, f"{'مصروف' if etype == 'expense' else 'إيراد'} {amount}")
    return jsonify({"success": True, "entry": _entry_dict(entry)})


# ==================== التسويات ====================

@accounting_bp.route("/api/reconciliations")
@require_api("accounting", "view")
def reconciliations():
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"message": "accounting.accountRequired"}), 400
    acc = db.session.get(Account, int(account_id))
    end = _d(request.args.get("end")) or datetime.date.today()
    lines = JournalEntryLine.query.filter_by(account_id=int(account_id)).all()
    unrec = [l for l in lines if not l.reconciled]
    rec_lines = [l for l in lines if l.reconciled]
    data = []
    for l in unrec:
        data.append({
            "line_id": l.id,
            "date": l.entry.date.isoformat() if l.entry.date else None,
            "entry_number": l.entry.entry_number if l.entry else None,
            "description": l.description or (l.entry.description if l.entry else ""),
            "debit": float(l.debit or 0),
            "credit": float(l.credit or 0),
            "reconciled": False,
        })
    return jsonify({
        "account": acc.to_dict() if acc else None,
        "balance": acct.account_balance(acc, end) if acc else 0,
        "rows": data,
        "reconciled_count": len(rec_lines),
    })


@accounting_bp.route("/api/reconciliations/reconcile", methods=["POST"])
@require_api("accounting", "edit")
def reconcile():
    data = request.get_json(force=True) or {}
    line_ids = data.get("line_ids") or []
    for lid in line_ids:
        line = db.session.get(JournalEntryLine, int(lid))
        if line:
            line.reconciled = True
            line.reconciled_at = datetime.datetime.now()
    db.session.commit()
    _log("update", "journal", 0, f"تسوية {len(line_ids)} عملية")
    return jsonify({"success": True})


@accounting_bp.route("/api/reconciliations/undo", methods=["POST"])
@require_api("accounting", "edit")
def reconcile_undo():
    data = request.get_json(force=True) or {}
    line_ids = data.get("line_ids") or []
    for lid in line_ids:
        line = db.session.get(JournalEntryLine, int(lid))
        if line:
            line.reconciled = False
            line.reconciled_at = None
    db.session.commit()
    return jsonify({"success": True})


# ==================== الميزانية ====================

@accounting_bp.route("/api/budget")
@require_api("accounting", "view")
def budget():
    year_id = request.args.get("year_id")
    rows = []
    q = BudgetLine.query
    if year_id not in (None, "", "0"):
        q = q.filter_by(financial_year_id=int(year_id))
    for b in q.order_by(BudgetLine.id.asc()).all():
        actual = acct.account_balance(b.account) if b.account else 0
        d = b.to_dict()
        d["actual"] = actual
        d["variance"] = float(acct.d0(b.amount) - acct.d0(actual))
        rows.append(d)
    total_budget = sum(float(r["amount"] or 0) for r in rows)
    total_actual = sum(float(r["actual"] or 0) for r in rows)
    return jsonify({"rows": rows, "total_budget": total_budget, "total_actual": total_actual})


@accounting_bp.route("/api/budget", methods=["POST"])
@require_api("accounting", "create")
def save_budget():
    data = request.get_json(force=True) or {}
    year_id = data.get("financial_year_id")
    lines = data.get("lines") or []
    if year_id in (None, "", 0):
        return jsonify({"message": "accounting.yearRequired"}), 400
    err = _year_error(year_id)
    if err:
        return jsonify({"message": err}), 400
    for ln in lines:
        account_id = ln.get("account_id")
        amount = float(ln.get("amount") or 0)
        if not account_id:
            continue
        existing = BudgetLine.query.filter_by(
            financial_year_id=int(year_id), account_id=int(account_id)).first()
        if existing:
            existing.amount = amount
        else:
            db.session.add(BudgetLine(
                financial_year_id=int(year_id), account_id=int(account_id), amount=amount))
    db.session.commit()
    _log("create", "budget", 0, f"حفظ الميزانية للسنة {year_id}")
    return jsonify({"success": True})


# ==================== الأصول الثابتة ====================

@accounting_bp.route("/api/assets")
@require_api("accounting", "view")
def list_assets():
    q = FixedAsset.query
    status = request.args.get("status")
    search = request.args.get("search", "").strip()
    if status:
        q = q.filter_by(status=status)
    if search:
        q = q.filter(FixedAsset.name.ilike("%" + search + "%"))
    items, envelope = paged_or_cap(q.order_by(FixedAsset.asset_code.asc()))
    return jsonify(envelope if envelope else items)


@accounting_bp.route("/api/assets", methods=["POST"])
@require_api("accounting", "create")
def create_asset():
    data = request.get_json(force=True) or {}
    code = str(data.get("asset_code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        return jsonify({"message": "common.required"}), 400
    if FixedAsset.query.filter_by(asset_code=code).first():
        return jsonify({"message": "accounting.codeExists"}), 400
    cost = float(data.get("cost") or 0)
    asset = FixedAsset(
        asset_code=code,
        name=name,
        category=(data.get("category") or "").strip() or None,
        purchase_date=_d(data.get("purchase_date")),
        cost=cost,
        useful_life_years=int(data.get("useful_life_years") or 5),
        salvage_value=float(data.get("salvage_value") or 0),
        method=data.get("method", "straight"),
        status=data.get("status", "active"),
        account_id=data.get("account_id") or None,
        expense_account_id=data.get("expense_account_id") or None,
        accumulated_account_id=data.get("accumulated_account_id") or None,
        description=(data.get("description") or "").strip() or None,
    )
    asset.monthly_depreciation = asset.compute_monthly()
    db.session.add(asset)
    db.session.commit()
    _post_asset_purchase(asset, cost, data)
    _log("create", "asset", asset.id, f"إضافة أصل: {asset.asset_code} - {asset.name}")
    return jsonify({"success": True, "asset": asset.to_dict()})


def _post_asset_purchase(asset, cost, data):
    """ترحيل شراء الأصل: مدين حساب الأصل / دائن صندوق أو ذمم."""
    if cost <= 0:
        return
    if not acct.default_account_id("acc_default_asset"):
        return
    funding = data.get("funding", "credit")
    if funding in ("cash", "bank"):
        counter = data.get("cash_account_id") or acct.default_account_id(
            "acc_default_cash" if funding == "cash" else "acc_default_bank")
    else:
        counter = data.get("counterpart_account_id") or acct.default_account_id("acc_default_payable")
    if not counter:
        return
    year_id, _ = _default_fy_and_date()
    try:
        acct.make_entry(
            [
                {"account_id": asset.account_id or acct.default_account_id("acc_default_asset"),
                 "debit": cost, "credit": 0, "description": f"شراء أصل {asset.name}"},
                {"account_id": int(counter), "debit": 0, "credit": cost, "description": f"شراء أصل {asset.name}"},
            ],
            date=asset.purchase_date or datetime.date.today(),
            description=f"شراء أصل ثابت {asset.asset_code}",
            financial_year_id=year_id,
            source="asset", ref_type="asset", ref_id=asset.id)
    except Exception:
        db.session.rollback()


@accounting_bp.route("/api/assets/<int:asset_id>", methods=["PUT"])
@require_api("accounting", "edit")
def update_asset(asset_id):
    asset = db.session.get(FixedAsset, asset_id)
    if not asset:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    code = str(data.get("asset_code") or "").strip()
    dup = FixedAsset.query.filter(FixedAsset.asset_code == code, FixedAsset.id != asset_id).first()
    if dup:
        return jsonify({"message": "accounting.codeExists"}), 400
    if code:
        asset.asset_code = code
    if data.get("name"):
        asset.name = data["name"]
    if "category" in data:
        asset.category = (data.get("category") or "").strip() or None
    if "purchase_date" in data:
        asset.purchase_date = _d(data.get("purchase_date"))
    if "cost" in data:
        asset.cost = float(data.get("cost") or 0)
    if "useful_life_years" in data:
        asset.useful_life_years = int(data.get("useful_life_years") or 5)
    if "salvage_value" in data:
        asset.salvage_value = float(data.get("salvage_value") or 0)
    if "method" in data:
        asset.method = data.get("method", "straight")
    if "status" in data:
        asset.status = data.get("status", "active")
    if "account_id" in data:
        asset.account_id = data.get("account_id") or None
    if "expense_account_id" in data:
        asset.expense_account_id = data.get("expense_account_id") or None
    if "accumulated_account_id" in data:
        asset.accumulated_account_id = data.get("accumulated_account_id") or None
    if "description" in data:
        asset.description = (data.get("description") or "").strip() or None
    asset.monthly_depreciation = asset.compute_monthly()
    db.session.commit()
    _log("update", "asset", asset.id, f"تعديل أصل: {asset.asset_code}")
    return jsonify({"success": True, "asset": asset.to_dict()})


@accounting_bp.route("/api/assets/<int:asset_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_asset(asset_id):
    asset = db.session.get(FixedAsset, asset_id)
    if not asset:
        return jsonify({"message": "common.notFound"}), 404
    if DepreciationRecord.query.filter_by(asset_id=asset_id).first():
        return jsonify({"message": "accounting.assetHasDepreciation"}), 400
    acct.delete_source_entries("asset", "asset", asset_id)
    db.session.delete(asset)
    db.session.commit()
    _log("delete", "asset", asset_id, f"حذف أصل: {asset.asset_code}")
    return jsonify({"success": True})


@accounting_bp.route("/api/assets/<int:asset_id>/depreciate", methods=["POST"])
@require_api("accounting", "create")
def depreciate(asset_id):
    asset = db.session.get(FixedAsset, asset_id)
    if not asset:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    period = str(data.get("period") or datetime.date.today().strftime("%Y-%m"))
    date = _d(data.get("date")) or datetime.date.today()
    if DepreciationRecord.query.filter_by(asset_id=asset_id, period=period).first():
        return jsonify({"message": "accounting.periodAlready"}), 400
    if asset.net_book_value <= 0 or asset.status != "active":
        return jsonify({"message": "accounting.fullyDepreciated"}), 400
    exp_acc = asset.expense_account_id or acct.default_account_id("acc_default_depreciation")
    acc_acc = asset.accumulated_account_id or acct.default_account_id("acc_default_accumulated")
    if not (exp_acc and acc_acc):
        return jsonify({"message": "accounting.deprAccountsRequired"}), 400
    amount = float(asset.monthly_depreciation or asset.compute_monthly())
    if amount > asset.net_book_value:
        amount = asset.net_book_value
    fy_id = data.get("financial_year_id")
    err = _year_error(fy_id)
    if err:
        return jsonify({"message": err}), 400
    try:
        entry = acct.make_entry(
            [
                {"account_id": int(exp_acc), "debit": amount, "credit": 0, "description": f"إهلاك {asset.name}"},
                {"account_id": int(acc_acc), "debit": 0, "credit": amount, "description": f"إهلاك {asset.name}"},
            ],
            date=date,
            description=f"إهلاك أصل {asset.asset_code} - {period}",
            financial_year_id=int(fy_id) if fy_id not in (None, "", 0) else None,
            source="depreciation", ref_type="asset", ref_id=asset.id)
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    asset.accumulated_depreciation = float(asset.accumulated_depreciation or 0) + amount
    db.session.add(DepreciationRecord(
        asset_id=asset.id, entry_id=entry.id, period=period, date=date, amount=amount))
    db.session.commit()
    _log("create", "journal", entry.id, f"إهلاك {asset.asset_code} {period}")
    return jsonify({"success": True, "asset": asset.to_dict(), "amount": amount})


@accounting_bp.route("/api/assets/<int:asset_id>/records")
@require_api("accounting", "view")
def asset_records(asset_id):
    records = DepreciationRecord.query.filter_by(asset_id=asset_id).order_by(DepreciationRecord.period.asc()).all()
    return jsonify([r.to_dict() for r in records])


# ==================== التقارير ====================

@accounting_bp.route("/api/reports/trial-balance")
@require_api("accounting", "view")
def report_trial_balance():
    end = _d(request.args.get("end_date"))
    return jsonify(acct.trial_balance(request.args.get("year_id"), end))


@accounting_bp.route("/api/reports/ledger")
@require_api("accounting", "view")
def report_ledger():
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"message": "accounting.accountRequired"}), 400
    start = _d(request.args.get("start"))
    end = _d(request.args.get("end"))
    year_id = request.args.get("year_id")
    acc = db.session.get(Account, int(account_id))
    rows = acct.ledger(int(account_id), start, end, year_id)
    return jsonify({
        "account": acc.to_dict() if acc else None,
        "opening": float(acc.opening_balance or 0) if acc else 0,
        "rows": rows,
        "balance": acct.account_balance(acc, end, year_id) if acc else 0,
    })


@accounting_bp.route("/api/reports/pl")
@require_api("accounting", "view")
def report_pl():
    start = _d(request.args.get("start"))
    end = _d(request.args.get("end"))
    year_id = request.args.get("year_id")
    return jsonify(acct.income_statement(start, end, year_id))


@accounting_bp.route("/api/reports/balance-sheet")
@require_api("accounting", "view")
def report_balance_sheet():
    end = _d(request.args.get("end_date"))
    year_id = request.args.get("year_id")
    return jsonify(acct.balance_sheet(end, year_id))


@accounting_bp.route("/api/reports/cash-flow")
@require_api("accounting", "view")
def report_cash_flow():
    start = _d(request.args.get("start"))
    end = _d(request.args.get("end"))
    year_id = request.args.get("year_id")
    return jsonify(acct.cash_flow(start, end, year_id))

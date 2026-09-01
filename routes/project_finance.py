"""التكامل المحاسبي للمشاريع العقارية: قيود تلقائية لكل تعامل مالي."""
import datetime
from flask import Blueprint, request, jsonify
from database import db
from permissions import require_api
from auditlog import log_action
from models import Project, Account, JournalEntry
from models.project_costs import ProjectCostItem, CompanyExpense
from models.real_estate_invest import SalesContract, Building, Floor
from models.unit import RealEstateUnit
from models.payment import PaymentPlan, Installment
from utils import accounting as acct
from utils.pagination import paged_or_cap
from sqlalchemy import func

project_finance_bp = Blueprint("project_finance", __name__, url_prefix="/api/project-finance")

CATEGORY_ACCOUNT_MAP = {
    "land": "acc_re_cost_land",
    "papers": "acc_re_cost_licensing",
    "construction": "acc_re_cost_construction",
    "equipment": "acc_re_cost_operating",
    "labor": "acc_re_cost_labor",
    "engineering": "acc_re_cost_engineering",
    "operating": "acc_re_cost_operating",
    "marketing": "acc_re_cost_operating",
    "other": "acc_re_cost_operating",
}

EXPENSE_CATEGORY_MAP = {
    "utilities": "510300",
    "salary": "510200",
    "rent": "510300",
    "maintenance": "510400",
    "marketing": "510400",
    "travel": "510400",
    "office": "510400",
    "insurance": "510400",
    "tax": "510600",
    "other": "510400",
}


def _get_or_default_account(key):
    """Get account ID from system settings defaults."""
    acc_id = acct.default_account_id(key)
    if acc_id:
        return acc_id
    code = acct.DEFAULT_ACCOUNT_MAP.get(key)
    if code:
        acc = Account.query.filter_by(code=code).first()
        if acc:
            return acc.id
    return None


def _resolve_account(key):
    """Resolve an account key to an Account object."""
    acc_id = _get_or_default_account(key)
    if acc_id:
        return db.session.get(Account, acc_id)
    return None


# ==================== تكاليف المشاريع ====================

@project_finance_bp.route("/costs", methods=["GET"])
@require_api("projects", "view")
def list_costs():
    pid = request.args.get("project_id")
    cat = request.args.get("category")
    q = ProjectCostItem.query
    if pid:
        q = q.filter_by(project_id=int(pid))
    if cat:
        q = q.filter_by(category=cat)
    items = q.order_by(ProjectCostItem.cost_date.desc(), ProjectCostItem.id.desc()).all()
    return jsonify([c.to_dict() for c in items])


@project_finance_bp.route("/costs", methods=["POST"])
@require_api("projects", "create")
def create_cost():
    data = request.get_json() or {}
    project_id = data.get("project_id")
    amount = float(data.get("amount") or 0)
    if not project_id or amount <= 0:
        return jsonify({"message": "بيانات غير مكتملة أو مبلغ غير صحيح"}), 400

    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"message": "المشروع غير موجود"}), 404

    category = data.get("category", "other")
    payment_method = data.get("payment_method", "cash")
    cost_date_str = data.get("cost_date")
    cost_date = _parse_date(cost_date_str) or datetime.date.today()

    # Determine expense account
    expense_acc_id = data.get("account_id")
    if not expense_acc_id:
        acc_key = CATEGORY_ACCOUNT_MAP.get(category, "acc_re_cost_operating")
        expense_acc_id = _get_or_default_account(acc_key)
    expense_acc = db.session.get(Account, expense_acc_id) if expense_acc_id else None

    # Determine credit account
    if payment_method == "credit":
        credit_acc = _resolve_account("acc_default_payable")
    else:
        credit_acc = _resolve_account("acc_default_cash")

    if not expense_acc or not credit_acc:
        return jsonify({"message": "لم يتم العثور على الحسابات المحاسبية المطلوبة، تأكد من إعدادات الحسابات الافتراضية"}), 400

    # Create cost item
    cost = ProjectCostItem(
        project_id=project_id,
        cost_date=cost_date,
        category=category,
        description=data.get("description", ""),
        amount=amount,
        account_id=expense_acc.id,
        payment_method=payment_method,
        supplier_account_id=credit_acc.id if payment_method == "credit" else None,
        reference=data.get("reference"),
        notes=data.get("notes"),
    )

    # Create journal entry
    try:
        year_id, _ = _default_fy()
        lines = [
            {"account_id": expense_acc.id, "debit": amount, "credit": 0, "description": f"تكلفة مشروع: {data.get('description', '')}"},
            {"account_id": credit_acc.id, "debit": 0, "credit": amount, "description": f"تكلفة مشروع: {data.get('description', '')}"},
        ]
        entry = acct.make_entry(
            lines, date=cost_date,
            description=f"تكلفة {category} - {project.name}: {data.get('description', '')}",
            financial_year_id=year_id,
            source="project_cost",
            ref_type="project_cost_item",
            ref_id=None,
            commit=False,
        )
        cost.journal_entry_id = entry.id if entry else None
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"خطأ في إنشاء القيد المحاسبي: {str(e)}"}), 400

    db.session.add(cost)
    db.session.commit()

    # Update project totals
    _update_project_totals(project_id)

    log_action("create", "project_cost_item", cost.id, f"تكلفة مشروع {project.name}: {cost.description}")
    return jsonify(cost.to_dict()), 201


@project_finance_bp.route("/costs/<int:cost_id>", methods=["DELETE"])
@require_api("projects", "delete")
def delete_cost(cost_id):
    cost = db.session.get(ProjectCostItem, cost_id)
    if not cost:
        return jsonify({"message": "غير موجود"}), 404
    pid = cost.project_id
    db.session.delete(cost)
    db.session.commit()
    _update_project_totals(pid)
    log_action("delete", "project_cost_item", cost_id, "")
    return jsonify({"success": True})


# ==================== مصروفات الشركة ====================

@project_finance_bp.route("/expenses", methods=["GET"])
@require_api("projects", "view")
def list_expenses():
    pid = request.args.get("project_id")
    cat = request.args.get("category")
    q = CompanyExpense.query
    if pid:
        q = q.filter_by(project_id=int(pid))
    if cat:
        q = q.filter_by(category=cat)
    items = q.order_by(CompanyExpense.expense_date.desc(), CompanyExpense.id.desc()).all()
    return jsonify([e.to_dict() for e in items])


@project_finance_bp.route("/expenses", methods=["POST"])
@require_api("projects", "create")
def create_expense():
    data = request.get_json() or {}
    amount = float(data.get("amount") or 0)
    description = data.get("description", "")
    if amount <= 0 or not description:
        return jsonify({"message": "بيانات غير مكتملة"}), 400

    category = data.get("category", "other")
    payment_method = data.get("payment_method", "cash")
    expense_date_str = data.get("expense_date")
    expense_date = _parse_date(expense_date_str) or datetime.date.today()

    # Determine expense account
    expense_acc_id = data.get("account_id")
    if not expense_acc_id:
        code = EXPENSE_CATEGORY_MAP.get(category, "510400")
        acc = Account.query.filter_by(code=code).first()
        expense_acc_id = acc.id if acc else None
    expense_acc = db.session.get(Account, expense_acc_id) if expense_acc_id else None

    # Determine credit account
    if payment_method == "bank":
        credit_acc = _resolve_account("acc_default_bank")
    elif payment_method == "credit":
        credit_acc = _resolve_account("acc_default_payable")
    else:
        credit_acc = _resolve_account("acc_default_cash")

    if not expense_acc or not credit_acc:
        return jsonify({"message": "لم يتم العثور على الحسابات المطلوبة"}), 400

    expense = CompanyExpense(
        project_id=data.get("project_id"),
        expense_date=expense_date,
        category=category,
        subcategory=data.get("subcategory"),
        description=description,
        amount=amount,
        account_id=expense_acc.id,
        payment_method=payment_method,
        payee_type=data.get("payee_type"),
        payee_id=data.get("payee_id"),
        supplier_account_id=credit_acc.id if payment_method == "credit" else None,
        reference=data.get("reference"),
        notes=data.get("notes"),
        is_recurring=data.get("is_recurring", False),
        recurring_period=data.get("recurring_period", "monthly"),
    )

    # Create journal entry
    try:
        year_id, _ = _default_fy()
        lines = [
            {"account_id": expense_acc.id, "debit": amount, "credit": 0, "description": description},
            {"account_id": credit_acc.id, "debit": 0, "credit": amount, "description": description},
        ]
        entry = acct.make_entry(
            lines, date=expense_date,
            description=f"مصروف {category}: {description}",
            financial_year_id=year_id,
            source="company_expense",
            ref_type="company_expense",
            ref_id=None,
            commit=False,
        )
        expense.journal_entry_id = entry.id if entry else None
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"خطأ في إنشاء القيد: {str(e)}"}), 400

    db.session.add(expense)
    db.session.commit()

    if expense.project_id:
        _update_project_totals(expense.project_id)

    log_action("create", "company_expense", expense.id, f"مصروف: {description}")
    return jsonify(expense.to_dict()), 201


@project_finance_bp.route("/expenses/<int:expense_id>", methods=["DELETE"])
@require_api("projects", "delete")
def delete_expense(expense_id):
    expense = db.session.get(CompanyExpense, expense_id)
    if not expense:
        return jsonify({"message": "غير موجود"}), 404
    pid = expense.project_id
    db.session.delete(expense)
    db.session.commit()
    if pid:
        _update_project_totals(pid)
    log_action("delete", "company_expense", expense_id, "")
    return jsonify({"success": True})


# ==================== إيرادات المبيعات ====================

@project_finance_bp.route("/post-sale-revenue", methods=["POST"])
@require_api("projects", "create")
def post_sale_revenue():
    data = request.get_json() or {}
    contract_id = data.get("sales_contract_id")
    if not contract_id:
        return jsonify({"message": "contract_id مطلوب"}), 400

    contract = db.session.get(SalesContract, contract_id)
    if not contract:
        return jsonify({"message": "عقد البيع غير موجود"}), 404

    unit = db.session.get(RealEstateUnit, contract.unit_id)
    if not unit:
        return jsonify({"message": "الوحدة غير موجودة"}), 404

    amount = float(data.get("amount") or contract.net_amount or 0)
    if amount <= 0:
        return jsonify({"message": "المبلغ غير صحيح"}), 400

    payment_method = data.get("payment_method", "cash")
    payment_acc_id = data.get("payment_account_id")

    # Revenue account
    revenue_acc = _resolve_account("acc_re_revenue_sales")
    if not revenue_acc:
        revenue_acc = _resolve_account("acc_default_revenue")

    # Payment/receivable account
    if payment_method == "cash":
        payment_acc = db.session.get(Account, payment_acc_id) if payment_acc_id else _resolve_account("acc_default_cash")
    elif payment_method == "bank":
        payment_acc = db.session.get(Account, payment_acc_id) if payment_acc_id else _resolve_account("acc_default_bank")
    else:
        payment_acc = _resolve_account("acc_default_receivable")

    if not revenue_acc or not payment_acc:
        return jsonify({"message": "الحسابات المحاسبية غير متوفرة"}), 400

    try:
        year_id, _ = _default_fy()
        lines = [
            {"account_id": payment_acc.id, "debit": amount, "credit": 0, "description": f"إيراد بيع - {contract.contract_number}"},
            {"account_id": revenue_acc.id, "debit": 0, "credit": amount, "description": f"إيراد بيع - {contract.contract_number}"},
        ]
        entry = acct.make_entry(
            lines, date=_parse_date(data.get("date")) or datetime.date.today(),
            description=f"إيراد بيع وحدة {unit.unit_code} - عقد {contract.contract_number}",
            financial_year_id=year_id,
            source="sale_revenue",
            ref_type="sales_contract",
            ref_id=contract.id,
            commit=True,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"خطأ في الترحيل: {str(e)}"}), 400

    # Update project revenue
    if unit.project_id:
        _update_project_totals(unit.project_id)

    log_action("create", "journal_entry", entry.id, f"إيراد بيع - {contract.contract_number}")
    return jsonify({"success": True, "journal_entry": entry.to_dict()}), 201


# ==================== تحصيل الأقساط ====================

@project_finance_bp.route("/post-installment-payment", methods=["POST"])
@require_api("projects", "create")
def post_installment_payment():
    data = request.get_json() or {}
    installment_id = data.get("installment_id")
    if not installment_id:
        return jsonify({"message": "installment_id مطلوب"}), 400

    installment = db.session.get(Installment, installment_id)
    if not installment:
        return jsonify({"message": "القسط غير موجود"}), 404

    amount = float(data.get("amount") or installment.amount or 0)
    if amount <= 0:
        return jsonify({"message": "المبلغ غير صحيح"}), 400

    payment_method = data.get("payment_method", "cash")
    payment_acc_id = data.get("payment_account_id")

    if payment_method == "bank":
        cash_acc = db.session.get(Account, payment_acc_id) if payment_acc_id else _resolve_account("acc_default_bank")
    else:
        cash_acc = db.session.get(Account, payment_acc_id) if payment_acc_id else _resolve_account("acc_default_cash")

    receivable_acc = _resolve_account("acc_default_receivable")

    if not cash_acc or not receivable_acc:
        return jsonify({"message": "الحسابات المحاسبية غير متوفرة"}), 400

    try:
        year_id, _ = _default_fy()
        lines = [
            {"account_id": cash_acc.id, "debit": amount, "credit": 0, "description": f"تحصيل قسط رقم {installment.installment_number}"},
            {"account_id": receivable_acc.id, "debit": 0, "credit": amount, "description": f"تحصيل قسط رقم {installment.installment_number}"},
        ]
        entry = acct.make_entry(
            lines, date=_parse_date(data.get("date")) or datetime.date.today(),
            description=f"تحصيل قسط - plan #{installment.plan_id}",
            financial_year_id=year_id,
            source="installment_payment",
            ref_type="installment",
            ref_id=installment.id,
            commit=True,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"خطأ في الترحيل: {str(e)}"}), 400

    # Update installment
    installment.paid_amount = float(installment.paid_amount or 0) + amount
    installment.paid_date = _parse_date(data.get("date")) or datetime.date.today()
    if installment.paid_amount >= float(installment.amount or 0):
        installment.status = "paid"
    else:
        installment.status = "partial"
    db.session.commit()

    log_action("create", "journal_entry", entry.id, f"تحصيل قسط #{installment.installment_number}")
    return jsonify({"success": True, "journal_entry": entry.to_dict()}), 201


# ==================== إيرادات الإيجار ====================

@project_finance_bp.route("/post-rent", methods=["POST"])
@require_api("projects", "create")
def post_rent():
    data = request.get_json() or {}
    project_id = data.get("project_id")
    amount = float(data.get("amount") or 0)
    if amount <= 0:
        return jsonify({"message": "المبلغ غير صحيح"}), 400

    description = data.get("description", "إيراد إيجار")
    payment_method = data.get("payment_method", "cash")
    payment_acc_id = data.get("payment_account_id")

    revenue_acc = _resolve_account("acc_re_revenue_rent")
    if not revenue_acc:
        revenue_acc = _resolve_account("acc_default_revenue")

    if payment_method == "bank":
        cash_acc = db.session.get(Account, payment_acc_id) if payment_acc_id else _resolve_account("acc_default_bank")
    else:
        cash_acc = db.session.get(Account, payment_acc_id) if payment_acc_id else _resolve_account("acc_default_cash")

    if not revenue_acc or not cash_acc:
        return jsonify({"message": "الحسابات المحاسبية غير متوفرة"}), 400

    try:
        year_id, _ = _default_fy()
        lines = [
            {"account_id": cash_acc.id, "debit": amount, "credit": 0, "description": description},
            {"account_id": revenue_acc.id, "debit": 0, "credit": amount, "description": description},
        ]
        entry = acct.make_entry(
            lines, date=_parse_date(data.get("date")) or datetime.date.today(),
            description=f"إيراد إيجار: {description}",
            financial_year_id=year_id,
            source="rent_revenue",
            ref_type="rent",
            ref_id=project_id,
            commit=True,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"خطأ في الترحيل: {str(e)}"}), 400

    if project_id:
        _update_project_totals(project_id)

    log_action("create", "journal_entry", entry.id, f"إيراد إيجار: {description}")
    return jsonify({"success": True, "journal_entry": entry.to_dict()}), 201


# ==================== ملخص مالي لمشروع ====================

@project_finance_bp.route("/summary", methods=["GET"])
@require_api("projects", "view")
def project_summary():
    pid = request.args.get("project_id")
    if not pid:
        return jsonify({"message": "project_id مطلوب"}), 400

    project = db.session.get(Project, int(pid))
    if not project:
        return jsonify({"message": "المشروع غير موجود"}), 404

    # Costs
    total_costs = float(db.session.query(func.coalesce(func.sum(ProjectCostItem.amount), 0))
                        .filter_by(project_id=int(pid)).scalar() or 0)
    costs_by_cat = (db.session.query(ProjectCostItem.category, func.sum(ProjectCostItem.amount))
                    .filter_by(project_id=int(pid))
                    .group_by(ProjectCostItem.category).all())

    # Company expenses linked to project
    total_expenses = float(db.session.query(func.coalesce(func.sum(CompanyExpense.amount), 0))
                           .filter_by(project_id=int(pid)).scalar() or 0)

    # Revenue from sales contracts on units in this project
    unit_ids = [u.id for u in RealEstateUnit.query.filter_by(project_id=int(pid)).all()]
    total_sales_revenue = 0
    total_rental_revenue = 0
    if unit_ids:
        total_sales_revenue = float(db.session.query(
            func.coalesce(func.sum(SalesContract.net_amount), 0))
            .filter(SalesContract.unit_id.in_(unit_ids),
                    SalesContract.status.in_(["active", "completed"])).scalar() or 0)

    # Units summary
    from models.real_estate_invest import Reservation as Res
    total_units = len(unit_ids)
    sold_units = RealEstateUnit.query.filter_by(project_id=int(pid), status="sold").count() if unit_ids else 0
    rented_units = RealEstateUnit.query.filter_by(project_id=int(pid), status="rented").count() if unit_ids else 0
    available_units = RealEstateUnit.query.filter_by(project_id=int(pid), status="available").count() if unit_ids else 0

    buildings_count = Building.query.filter_by(project_id=int(pid)).count()
    floors_count = db.session.query(func.count(Floor.id)).join(Building).filter(Building.project_id == int(pid)).scalar() or 0

    net_profit = total_sales_revenue + total_rental_revenue - total_costs - total_expenses
    occupancy = round((sold_units + rented_units) / total_units * 100, 1) if total_units > 0 else 0

    return jsonify({
        "project_id": int(pid),
        "project_name": project.name,
        "buildings_count": buildings_count,
        "floors_count": floors_count,
        "total_units": total_units,
        "sold_units": sold_units,
        "rented_units": rented_units,
        "available_units": available_units,
        "occupancy_rate": occupancy,
        "total_costs": round(total_costs, 2),
        "costs_by_category": {c[0]: float(c[1] or 0) for c in costs_by_cat},
        "total_expenses": round(total_expenses, 2),
        "total_sales_revenue": round(total_sales_revenue, 2),
        "total_rental_revenue": round(total_rental_revenue, 2),
        "total_revenue": round(total_sales_revenue + total_rental_revenue, 2),
        "net_profit": round(net_profit, 2),
        "budget": float(project.budget or 0),
        "budget_utilization": round((total_costs + total_expenses) / float(project.budget or 1) * 100, 1),
    })


# ==================== ملخص كل المشاريع (لوحة التحكم) ====================

@project_finance_bp.route("/all-projects-summary", methods=["GET"])
@require_api("projects", "view")
def all_projects_summary():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    result = []
    for p in projects:
        unit_ids = [u.id for u in RealEstateUnit.query.filter_by(project_id=p.id).all()]
        total_units = len(unit_ids)
        sold = RealEstateUnit.query.filter_by(project_id=p.id, status="sold").count() if unit_ids else 0
        rented = RealEstateUnit.query.filter_by(project_id=p.id, status="rented").count() if unit_ids else 0
        available = RealEstateUnit.query.filter_by(project_id=p.id, status="available").count() if unit_ids else 0

        costs = float(db.session.query(func.coalesce(func.sum(ProjectCostItem.amount), 0))
                      .filter_by(project_id=p.id).scalar() or 0)
        expenses = float(db.session.query(func.coalesce(func.sum(CompanyExpense.amount), 0))
                         .filter_by(project_id=p.id).scalar() or 0)
        revenue = 0
        if unit_ids:
            revenue = float(db.session.query(
                func.coalesce(func.sum(SalesContract.net_amount), 0))
                .filter(SalesContract.unit_id.in_(unit_ids),
                        SalesContract.status.in_(["active", "completed"])).scalar() or 0)

        occupancy = round((sold + rented) / total_units * 100, 1) if total_units > 0 else 0
        net_profit = revenue - costs - expenses

        result.append({
            "id": p.id,
            "name": p.name,
            "status": p.status,
            "total_units": total_units,
            "sold_units": sold,
            "rented_units": rented,
            "available_units": available,
            "occupancy_rate": occupancy,
            "total_costs": round(costs, 2),
            "total_expenses": round(expenses, 2),
            "total_revenue": round(revenue, 2),
            "net_profit": round(net_profit, 2),
            "budget": float(p.budget or 0),
        })

    return jsonify(result)


# ==================== التوقعات المستقبلية ====================

@project_finance_bp.route("/forecast", methods=["GET"])
@require_api("projects", "view")
def forecast():
    pid = request.args.get("project_id")
    if not pid:
        return jsonify({"message": "project_id مطلوب"}), 400

    project = db.session.get(Project, int(pid))
    if not project:
        return jsonify({"message": "المشروع غير موجود"}), 404

    unit_ids = [u.id for u in RealEstateUnit.query.filter_by(project_id=int(pid)).all()]

    # Expected revenue from pending installments
    expected_from_installments = 0
    if unit_ids:
        plans = PaymentPlan.query.filter(PaymentPlan.unit_id.in_(unit_ids)).all()
        plan_ids = [pl.id for pl in plans]
        if plan_ids:
            expected_from_installments = float(db.session.query(
                func.coalesce(func.sum(Installment.amount - Installment.paid_amount), 0))
                .filter(Installment.plan_id.in_(plan_ids),
                        Installment.status.in_(["pending", "upcoming", "overdue"])).scalar() or 0)

    # Expected rental revenue (estimate: rented units * average rent * 12 months)
    expected_rental_annual = 0
    rented_count = RealEstateUnit.query.filter_by(project_id=int(pid), status="rented").count()

    # Expected expenses from recurring company expenses
    from sqlalchemy import and_
    recurring = CompanyExpense.query.filter(
        CompanyExpense.project_id == int(pid),
        CompanyExpense.is_recurring == True
    ).all()
    expected_recurring = 0
    for exp in recurring:
        period = exp.recurring_period or "monthly"
        if period == "monthly":
            expected_recurring += float(exp.amount or 0) * 12
        elif period == "quarterly":
            expected_recurring += float(exp.amount or 0) * 4
        elif period == "yearly":
            expected_recurring += float(exp.amount or 0)

    projected_profit = expected_from_installments + expected_rental_annual - expected_recurring

    return jsonify({
        "project_id": int(pid),
        "expected_from_installments": round(expected_from_installments, 2),
        "expected_rental_annual": round(expected_rental_annual, 2),
        "total_expected_revenue": round(expected_from_installments + expected_rental_annual, 2),
        "expected_recurring_expenses": round(expected_recurring, 2),
        "projected_profit": round(projected_profit, 2),
    })


# ==================== Helpers ====================

def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.datetime.strptime(str(s), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _default_fy():
    from models.financial_year import FinancialYear
    from utils.settings import get_int
    year_id = get_int("default_financial_year_id")
    year = db.session.get(FinancialYear, year_id) if year_id else None
    if not year:
        year = FinancialYear.query.filter_by(is_active=True, is_closed=False) \
            .order_by(FinancialYear.start_date.desc()).first()
    if year and not year.is_closed:
        return year.id, (year.start_date or datetime.date.today())
    return None, datetime.date.today()


def _update_project_totals(project_id):
    """Recalculate project financial totals."""
    project = db.session.get(Project, project_id)
    if not project:
        return
    total_costs = float(db.session.query(
        func.coalesce(func.sum(ProjectCostItem.amount), 0))
        .filter_by(project_id=project_id).scalar() or 0)
    total_expenses = float(db.session.query(
        func.coalesce(func.sum(CompanyExpense.amount), 0))
        .filter_by(project_id=project_id).scalar() or 0)

    unit_ids = [u.id for u in RealEstateUnit.query.filter_by(project_id=project_id).all()]
    total_revenue = 0
    if unit_ids:
        total_revenue = float(db.session.query(
            func.coalesce(func.sum(SalesContract.net_amount), 0))
            .filter(SalesContract.unit_id.in_(unit_ids),
                    SalesContract.status.in_(["active", "completed"])).scalar() or 0)

    project.spent = total_costs + total_expenses
    project.total_invested = total_costs
    project.total_revenue = total_revenue
    project.total_expenses = total_expenses
    # Break down costs by category
    land_cost = float(db.session.query(func.coalesce(func.sum(ProjectCostItem.amount), 0))
                      .filter_by(project_id=project_id, category="land").scalar() or 0)
    papers_cost = float(db.session.query(func.coalesce(func.sum(ProjectCostItem.amount), 0))
                        .filter_by(project_id=project_id, category="papers").scalar() or 0)
    construction_cost = float(db.session.query(func.coalesce(func.sum(ProjectCostItem.amount), 0))
                              .filter_by(project_id=project_id, category="construction").scalar() or 0)
    project.land_cost = land_cost
    project.papers_cost = papers_cost
    project.construction_cost = construction_cost
    db.session.commit()

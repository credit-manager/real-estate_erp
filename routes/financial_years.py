from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import and_, or_
from database import db
from models import (
    FinancialYear, Company, Invoice, PurchaseOrder, RentalContract,
    PaymentPlan, JournalEntry,
)
from permissions import require_api
from auditlog import log_action

financial_years_bp = Blueprint("financial_years", __name__, url_prefix="/api/financial-years")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _summary(year):
    return {
        "invoices": Invoice.query.filter_by(financial_year_id=year.id).count(),
        "orders": PurchaseOrder.query.filter_by(financial_year_id=year.id).count(),
        "contracts": RentalContract.query.filter_by(financial_year_id=year.id).count(),
        "plans": PaymentPlan.query.filter_by(financial_year_id=year.id).count(),
        "journal_entries": JournalEntry.query.filter_by(financial_year_id=year.id, deleted_at=None).count(),
    }


def _year_dict(year):
    data = year.to_dict()
    data.update(_summary(year))
    return data


def _validate(data, partial=False, existing=None):
    company_id = data.get("company_id") if "company_id" in data else (existing.company_id if existing else None)
    name = (data.get("name") if "name" in data else (existing.name if existing else "")) or ""
    start = _parse_date(data.get("start_date")) if "start_date" in data else (existing.start_date if existing else None)
    end = _parse_date(data.get("end_date")) if "end_date" in data else (existing.end_date if existing else None)

    if not partial or "company_id" in data:
        company = db.session.get(Company, company_id)
        if not company:
            return "financialYears.companyRequired"
    if not partial or "name" in data:
        if not str(name).strip():
            return "financialYears.nameRequired"
    if not partial or "start_date" in data:
        if not start:
            return "financialYears.datesRequired"
    if not partial or "end_date" in data:
        if not end:
            return "financialYears.datesRequired"
    if start and end and end <= start:
        return "financialYears.invalidDateRange"

    if start and end and company_id:
        query = FinancialYear.query.filter(
            FinancialYear.company_id == company_id,
            FinancialYear.start_date <= end,
            FinancialYear.end_date >= start,
        )
        if existing is not None:
            query = query.filter(FinancialYear.id != existing.id)
        if query.first() is not None:
            return "financialYears.overlap"

    return None


@financial_years_bp.route("", methods=["GET"])
@require_api("financial_years", "view")
def list_years():
    years = FinancialYear.query.order_by(FinancialYear.start_date.desc()).all()
    return jsonify({"years": [_year_dict(y) for y in years]})


@financial_years_bp.route("/options", methods=["GET"])
@require_api("finance", "view")
def open_options():
    """السنوات المفتوحة فقط لاستخدامها في مستندات الفواتير وأوامر الشراء..."""
    years = FinancialYear.query.filter_by(is_closed=False).order_by(
        FinancialYear.start_date.desc()).all()
    return jsonify({"years": [{
        "id": y.id,
        "name": y.name,
        "company_id": y.company_id,
        "company_name": y.company.name if y.company else None,
        "is_active": bool(y.is_active),
    } for y in years]})


@financial_years_bp.route("", methods=["POST"])
@require_api("financial_years", "create")
def create_year():
    data = request.get_json(silent=True) or {}
    err = _validate(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    normalized_name = str(data["name"]).strip()
    dup = FinancialYear.query.filter_by(
        company_id=data["company_id"], name=normalized_name).first()
    if dup:
        return jsonify({"message": "financialYears.duplicate", "error_key": "financialYears.duplicate"}), 400
    year = FinancialYear(
        company_id=data["company_id"],
        name=normalized_name,
        start_date=_parse_date(data.get("start_date")),
        end_date=_parse_date(data.get("end_date")),
        is_active=bool(data.get("is_active", False)),
        is_closed=bool(data.get("is_closed", False)),
    )
    if year.is_active and year.is_closed:
        return jsonify({"message": "financialYears.closedActive", "error_key": "financialYears.closedActive"}), 400
    if year.is_active:
        _clear_active(year.company_id)
    db.session.add(year)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "financialYears.saveFailed", "error_key": "financialYears.saveFailed"}), 409
    log_action("create", "financial_year", year.id, f"سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)}), 201


@financial_years_bp.route("/<int:year_id>", methods=["PUT"])
@require_api("financial_years", "edit")
def update_year(year_id):
    year = db.session.get(FinancialYear, year_id)
    if not year:
        return jsonify({"message": "financialYears.notFound", "error_key": "financialYears.notFound"}), 404
    data = request.get_json(silent=True) or {}
    err = _validate(data, partial=True, existing=year)
    if err:
        return jsonify({"message": err, "error_key": err}), 400

    target_company_id = data.get("company_id", year.company_id)
    target_start = _parse_date(data["start_date"]) if "start_date" in data else year.start_date
    target_end = _parse_date(data["end_date"]) if "end_date" in data else year.end_date
    target_closed = bool(data.get("is_closed")) if "is_closed" in data else bool(year.is_closed)
    target_active = bool(data.get("is_active")) if "is_active" in data else bool(year.is_active)

    if target_active and target_closed:
        return jsonify({"message": "financialYears.closedActive", "error_key": "financialYears.closedActive"}), 400
    if year.is_closed and (target_company_id != year.company_id or target_start != year.start_date or target_end != year.end_date):
        return jsonify({"message": "financialYears.closedImmutable", "error_key": "financialYears.closedImmutable"}), 409

    if "company_id" in data:
        year.company_id = target_company_id
    if "name" in data:
        year.name = str(data["name"]).strip()
    if "start_date" in data:
        year.start_date = target_start
    if "end_date" in data:
        year.end_date = target_end
    if "is_active" in data:
        year.is_active = target_active
        if year.is_active:
            _clear_active(year.company_id, exclude=year.id)
    if "is_closed" in data:
        year.is_closed = target_closed

    db.session.commit()
    log_action("update", "financial_year", year.id, f"سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)})


@financial_years_bp.route("/<int:year_id>", methods=["DELETE"])
@require_api("financial_years", "delete")
def delete_year(year_id):
    year = db.session.get(FinancialYear, year_id)
    if not year:
        return jsonify({"message": "financialYears.notFound", "error_key": "financialYears.notFound"}), 404
    summary = _summary(year)
    if any(summary.values()):
        return jsonify({
            "message": "financialYears.hasTransactions",
            "error_key": "financialYears.hasTransactions",
            "summary": summary,
        }), 409
    name = year.name
    db.session.delete(year)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "financialYears.deleteFailed", "error_key": "financialYears.deleteFailed"}), 409
    log_action("delete", "financial_year", year_id, f"سنة مالية: {name}")
    return jsonify({"success": True})


@financial_years_bp.route("/<int:year_id>/close", methods=["POST"])
@require_api("financial_years", "edit")
def close_year(year_id):
    year = db.session.get(FinancialYear, year_id)
    if not year:
        return jsonify({"message": "financialYears.notFound", "error_key": "financialYears.notFound"}), 404
    year.is_closed = True
    year.is_active = False
    db.session.commit()
    log_action("update", "financial_year", year.id, f"إقفال سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)})


@financial_years_bp.route("/<int:year_id>/open", methods=["POST"])
@require_api("financial_years", "edit")
def open_year(year_id):
    year = db.session.get(FinancialYear, year_id)
    if not year:
        return jsonify({"message": "financialYears.notFound", "error_key": "financialYears.notFound"}), 404
    year.is_closed = False
    db.session.commit()
    log_action("update", "financial_year", year.id, f"إعادة فتح سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)})


@financial_years_bp.route("/<int:year_id>/activate", methods=["POST"])
@require_api("financial_years", "edit")
def activate_year(year_id):
    year = db.session.get(FinancialYear, year_id)
    if not year:
        return jsonify({"message": "financialYears.notFound", "error_key": "financialYears.notFound"}), 404
    _clear_active(year.company_id)
    year.is_active = True
    year.is_closed = False
    db.session.commit()
    log_action("update", "financial_year", year.id, f"تفعيل سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)})


def _clear_active(company_id, exclude=None):
    q = FinancialYear.query.filter_by(company_id=company_id, is_active=True)
    if exclude:
        q = q.filter(FinancialYear.id != exclude)
    for y in q.all():
        y.is_active = False


def financial_year_error(financial_year_id):
    """يعيد مفتاح خطأ إذا كانت السنة مقفلة، وإلا None."""
    if not financial_year_id:
        return None
    year = db.session.get(FinancialYear, financial_year_id)
    if year is None:
        return None
    if year.is_closed:
        return "financialYears.closed"
    return None

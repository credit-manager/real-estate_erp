from datetime import datetime
from flask import Blueprint, request, jsonify
from database import db
from models import FinancialYear, Company, Invoice, PurchaseOrder, RentalContract, PaymentPlan
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
    }


def _year_dict(year):
    data = year.to_dict()
    data.update(_summary(year))
    return data


def _validate(data, partial=False):
    if not partial or "company_id" in data:
        company = db.session.get(Company, data.get("company_id"))
        if not company:
            return "financialYears.companyRequired"
    if not partial or "name" in data:
        if not (data.get("name") or "").strip():
            return "financialYears.nameRequired"
    if not partial or "start_date" in data:
        if not _parse_date(data.get("start_date")):
            return "financialYears.datesRequired"
    if not partial or "end_date" in data:
        if not _parse_date(data.get("end_date")):
            return "financialYears.datesRequired"
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
    dup = FinancialYear.query.filter_by(
        company_id=data["company_id"], name=data["name"].strip()).first()
    if dup:
        return jsonify({"message": "financialYears.duplicate", "error_key": "financialYears.duplicate"}), 400
    year = FinancialYear(
        company_id=data["company_id"],
        name=data["name"].strip(),
        start_date=_parse_date(data.get("start_date")),
        end_date=_parse_date(data.get("end_date")),
        is_active=bool(data.get("is_active", False)),
        is_closed=bool(data.get("is_closed", False)),
    )
    if year.is_active:
        _clear_active(year.company_id)
    db.session.add(year)
    db.session.commit()
    log_action("create", "financial_year", year.id, f"سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)}), 201


@financial_years_bp.route("/<int:year_id>", methods=["PUT"])
@require_api("financial_years", "edit")
def update_year(year_id):
    year = FinancialYear.query.get_or_404(year_id)
    data = request.get_json(silent=True) or {}
    err = _validate(data, partial=True)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    if "company_id" in data:
        company = db.session.get(Company, data["company_id"])
        if not company:
            return jsonify({"message": "financialYears.companyRequired", "error_key": "financialYears.companyRequired"}), 400
        year.company_id = data["company_id"]
    if "name" in data:
        year.name = data["name"].strip()
    if "start_date" in data:
        year.start_date = _parse_date(data["start_date"])
    if "end_date" in data:
        year.end_date = _parse_date(data["end_date"])
    if "is_active" in data:
        year.is_active = bool(data["is_active"])
        if year.is_active:
            _clear_active(year.company_id, exclude=year.id)
    if "is_closed" in data:
        year.is_closed = bool(data["is_closed"])
    db.session.commit()
    log_action("update", "financial_year", year.id, f"سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)})


@financial_years_bp.route("/<int:year_id>", methods=["DELETE"])
@require_api("financial_years", "delete")
def delete_year(year_id):
    year = FinancialYear.query.get_or_404(year_id)
    name = year.name
    db.session.delete(year)
    db.session.commit()
    log_action("delete", "financial_year", year_id, f"سنة مالية: {name}")
    return jsonify({"success": True})


@financial_years_bp.route("/<int:year_id>/close", methods=["POST"])
@require_api("financial_years", "edit")
def close_year(year_id):
    year = FinancialYear.query.get_or_404(year_id)
    year.is_closed = True
    db.session.commit()
    log_action("update", "financial_year", year.id, f"إقفال سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)})


@financial_years_bp.route("/<int:year_id>/open", methods=["POST"])
@require_api("financial_years", "edit")
def open_year(year_id):
    year = FinancialYear.query.get_or_404(year_id)
    year.is_closed = False
    db.session.commit()
    log_action("update", "financial_year", year.id, f"إعادة فتح سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)})


@financial_years_bp.route("/<int:year_id>/activate", methods=["POST"])
@require_api("financial_years", "edit")
def activate_year(year_id):
    year = FinancialYear.query.get_or_404(year_id)
    _clear_active(year.company_id)
    year.is_active = True
    year.is_closed = False
    db.session.commit()
    log_action("update", "financial_year", year.id, f"تفعيل سنة مالية: {year.name}")
    return jsonify({"success": True, "year": _year_dict(year)})


def _clear_active(company_id, exclude=None):
    for y in FinancialYear.query.filter_by(company_id=company_id, is_active=True).all():
        if exclude and y.id == exclude:
            continue
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

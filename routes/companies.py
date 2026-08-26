from flask import Blueprint, request, jsonify
from database import db
from models import Company, Branch, Currency
from permissions import require_api
from auditlog import log_action

companies_bp = Blueprint("companies", __name__, url_prefix="/api/companies")


def _sync_base_currency(company):
    """إذا كان رمز عملة الشركة مطابقاً لعملة مسجلة، يعيّنها أساسية."""
    cur = Currency.query.filter_by(
        company_id=company.id, code=(company.currency or "").strip().upper()
    ).first()
    if not cur:
        return
    for other in Currency.query.filter_by(company_id=company.id, is_base=True).all():
        if other.id != cur.id:
            other.is_base = False
    cur.is_base = True


def _validate_company(data, partial=False):
    if not partial or "name" in data:
        if not (data.get("name") or "").strip():
            return "اسم الشركة مطلوب"
    return None


@companies_bp.route("", methods=["GET"])
@require_api("companies", "view")
def list_companies():
    companies = Company.query.order_by(Company.id).all()
    return jsonify({"companies": [c.to_dict() for c in companies]})


@companies_bp.route("/branches", methods=["GET"])
@require_api("companies", "view")
def list_branches():
    branches = Branch.query.order_by(Branch.id).all()
    return jsonify({"branches": [b.to_dict() for b in branches]})


@companies_bp.route("/meta", methods=["GET"])
@require_api("companies", "view")
def meta():
    companies = Company.query.all()
    branches = Branch.query.all()
    return jsonify({
        "companies_count": len(companies),
        "branches_count": len(branches),
        "active_companies": sum(1 for c in companies if c.is_active),
    })


@companies_bp.route("", methods=["POST"])
@require_api("companies", "create")
def create_company():
    data = request.get_json(silent=True) or {}
    err = _validate_company(data)
    if err:
        return jsonify({"message": err}), 400
    company = Company(
        name=data.get("name", "").strip(),
        legal_name=(data.get("legal_name") or "").strip(),
        tax_number=(data.get("tax_number") or "").strip(),
        commercial_registration=(data.get("commercial_registration") or "").strip(),
        address=(data.get("address") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        email=(data.get("email") or "").strip(),
        website=(data.get("website") or "").strip(),
        currency=(data.get("currency") or "EGP").strip(),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(company)
    db.session.commit()
    log_action("create", "company", company.id, f"شركة: {company.name}")
    return jsonify({"success": True, "company": company.to_dict()}), 201


@companies_bp.route("/<int:company_id>", methods=["PUT"])
@require_api("companies", "edit")
def update_company(company_id):
    company = Company.query.get_or_404(company_id)
    data = request.get_json(silent=True) or {}
    err = _validate_company(data, partial=True)
    if err:
        return jsonify({"message": err}), 400
    company.name = (data.get("name", company.name) or "").strip()
    company.legal_name = (data.get("legal_name", company.legal_name) or "").strip()
    company.tax_number = (data.get("tax_number", company.tax_number) or "").strip()
    company.commercial_registration = (
        data.get("commercial_registration", company.commercial_registration) or ""
    ).strip()
    company.address = (data.get("address", company.address) or "").strip()
    company.phone = (data.get("phone", company.phone) or "").strip()
    company.email = (data.get("email", company.email) or "").strip()
    company.website = (data.get("website", company.website) or "").strip()
    company.currency = (data.get("currency", company.currency) or "EGP").strip()
    if "is_active" in data:
        company.is_active = bool(data["is_active"])
    _sync_base_currency(company)
    db.session.commit()
    log_action("edit", "company", company.id, f"شركة: {company.name}")
    return jsonify({"success": True, "company": company.to_dict()})


@companies_bp.route("/<int:company_id>", methods=["DELETE"])
@require_api("companies", "delete")
def delete_company(company_id):
    company = Company.query.get_or_404(company_id)
    name = company.name
    db.session.delete(company)
    db.session.commit()
    log_action("delete", "company", company_id, f"شركة: {name}")
    return jsonify({"success": True})


@companies_bp.route("/<int:company_id>/branches", methods=["POST"])
@require_api("companies", "create")
def create_branch(company_id):
    company = Company.query.get_or_404(company_id)
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم الفرع مطلوب"}), 400
    branch = Branch(
        company_id=company.id,
        name=data.get("name", "").strip(),
        code=(data.get("code") or "").strip(),
        city=(data.get("city") or "").strip(),
        address=(data.get("address") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        manager_name=(data.get("manager_name") or "").strip(),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(branch)
    db.session.commit()
    log_action("create", "branch", branch.id, f"فرع: {branch.name}")
    return jsonify({"success": True, "branch": branch.to_dict()}), 201


@companies_bp.route("/branches/<int:branch_id>", methods=["PUT"])
@require_api("companies", "edit")
def update_branch(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    data = request.get_json(silent=True) or {}
    if "name" in data and not (data.get("name") or "").strip():
        return jsonify({"message": "اسم الفرع مطلوب"}), 400
    branch.name = (data.get("name", branch.name) or "").strip()
    branch.code = (data.get("code", branch.code) or "").strip()
    branch.city = (data.get("city", branch.city) or "").strip()
    branch.address = (data.get("address", branch.address) or "").strip()
    branch.phone = (data.get("phone", branch.phone) or "").strip()
    branch.manager_name = (data.get("manager_name", branch.manager_name) or "").strip()
    if "is_active" in data:
        branch.is_active = bool(data["is_active"])
    db.session.commit()
    log_action("edit", "branch", branch.id, f"فرع: {branch.name}")
    return jsonify({"success": True, "branch": branch.to_dict()})


@companies_bp.route("/branches/<int:branch_id>", methods=["DELETE"])
@require_api("companies", "delete")
def delete_branch(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    name = branch.name
    db.session.delete(branch)
    db.session.commit()
    log_action("delete", "branch", branch_id, f"فرع: {name}")
    return jsonify({"success": True})

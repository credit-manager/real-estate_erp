from flask import Blueprint, request, jsonify
from database import db
from models import Currency, Company
from permissions import require_api
from auditlog import log_action

currencies_bp = Blueprint("currencies", __name__, url_prefix="/api/currencies")


def _currency_dict(currency):
    return currency.to_dict()


@currencies_bp.route("", methods=["GET"])
@require_api("currencies", "view")
def list_currencies():
    company_id = request.args.get("company_id", type=int)
    query = Currency.query
    if company_id:
        query = query.filter_by(company_id=company_id)
    currencies = query.order_by(Currency.company_id, Currency.is_base.desc(), Currency.code).all()
    return jsonify({"currencies": [_currency_dict(c) for c in currencies]})


@currencies_bp.route("/options", methods=["GET"])
@require_api("currencies", "view")
def options():
    company_id = request.args.get("company_id", type=int)
    query = Currency.query.filter_by(is_active=True)
    if company_id:
        query = query.filter_by(company_id=company_id)
    currencies = query.order_by(Currency.company_id, Currency.is_base.desc(), Currency.code).all()
    return jsonify({"currencies": [_currency_dict(c) for c in currencies]})


def _validate(data, partial=False):
    if not partial or "company_id" in data:
        if not db.session.get(Company, data.get("company_id")):
            return "currencies.companyRequired"
    if not partial or "name" in data:
        if not (data.get("name") or "").strip():
            return "currencies.nameRequired"
    if not partial or "code" in data:
        if not (data.get("code") or "").strip():
            return "currencies.codeRequired"
    if "rate" in data and not partial:
        rate = data.get("rate")
        if rate in (None, ""):
            return "currencies.rateRequired"
        try:
            if float(rate) <= 0:
                return "currencies.rateInvalid"
        except (TypeError, ValueError):
            return "currencies.rateInvalid"
    return None


def _check_duplicate(company_id, code, exclude_id=None):
    q = Currency.query.filter_by(company_id=company_id, code=(code or "").strip().upper())
    if exclude_id:
        q = q.filter(Currency.id != exclude_id)
    return q.first() is not None


def _set_base(currency):
    """يجعل العملة هي الأساسية لشركتها ويلغي البقية، ويحدّث عملة الشركة."""
    for other in Currency.query.filter_by(company_id=currency.company_id, is_base=True).all():
        if other.id != currency.id:
            other.is_base = False
    currency.is_base = True
    if currency.company:
        currency.company.currency = currency.code


@currencies_bp.route("", methods=["POST"])
@require_api("currencies", "create")
def create_currency():
    data = request.get_json() or {}
    err = _validate(data)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    company_id = data["company_id"]
    code = (data["code"] or "").strip().upper()
    if _check_duplicate(company_id, code):
        return jsonify({"message": "currencies.duplicate", "error_key": "currencies.duplicate"}), 400
    currency = Currency(
        company_id=company_id,
        name=(data.get("name") or "").strip(),
        code=code,
        symbol=(data.get("symbol") or "").strip(),
        rate=float(data.get("rate", 1)),
        is_base=bool(data.get("is_base", False)),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(currency)
    db.session.flush()
    if currency.is_base:
        _set_base(currency)
    db.session.commit()
    log_action("create", "currency", currency.id, currency.code)
    return jsonify(_currency_dict(currency)), 201


@currencies_bp.route("/<int:currency_id>", methods=["PUT"])
@require_api("currencies", "edit")
def update_currency(currency_id):
    currency = Currency.query.get_or_404(currency_id)
    data = request.get_json() or {}
    err = _validate(data, partial=True)
    if err:
        return jsonify({"message": err, "error_key": err}), 400
    company_id = data.get("company_id", currency.company_id)
    if "company_id" in data and not db.session.get(Company, company_id):
        return jsonify({"message": "currencies.companyRequired", "error_key": "currencies.companyRequired"}), 400
    if "code" in data:
        code = (data["code"] or "").strip().upper()
        if not code:
            return jsonify({"message": "currencies.codeRequired", "error_key": "currencies.codeRequired"}), 400
        if _check_duplicate(company_id, code, exclude_id=currency.id):
            return jsonify({"message": "currencies.duplicate", "error_key": "currencies.duplicate"}), 400
        currency.code = code
    for field in ["company_id", "name", "symbol"]:
        if field in data:
            setattr(currency, field, data[field])
    if "rate" in data:
        rate = data["rate"]
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            return jsonify({"message": "currencies.rateInvalid", "error_key": "currencies.rateInvalid"}), 400
        if rate <= 0:
            return jsonify({"message": "currencies.rateInvalid", "error_key": "currencies.rateInvalid"}), 400
        currency.rate = rate
    if "is_active" in data:
        currency.is_active = bool(data["is_active"])
    if "is_base" in data:
        new_base = bool(data["is_base"])
        if new_base and currency.is_base:
            pass
        elif new_base:
            _set_base(currency)
        elif currency.is_base:
            return jsonify({"message": "currencies.cannotUnsetBase", "error_key": "currencies.cannotUnsetBase"}), 400
    db.session.commit()
    log_action("update", "currency", currency.id, currency.code)
    return jsonify(_currency_dict(currency))


@currencies_bp.route("/<int:currency_id>", methods=["DELETE"])
@require_api("currencies", "delete")
def delete_currency(currency_id):
    currency = Currency.query.get_or_404(currency_id)
    if currency.is_base:
        return jsonify({"message": "currencies.cannotDeleteBase", "error_key": "currencies.cannotDeleteBase"}), 400
    code = currency.code
    db.session.delete(currency)
    db.session.commit()
    log_action("delete", "currency", currency_id, code)
    return jsonify({"success": True})

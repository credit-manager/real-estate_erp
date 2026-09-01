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


# ══════════════════════════════════════════════════════════
# Exchange Rate History
# ══════════════════════════════════════════════════════════

from models.currency import ExchangeRateHistory
from datetime import datetime, date


@currencies_bp.route("/exchange-rate-history", methods=["GET"])
@require_api("currencies", "view")
def list_rate_history():
    """قائمة سجل أسعار الصرف — فلتر اختياري: currency_id, company_id"""
    q = ExchangeRateHistory.query
    cid = request.args.get("currency_id")
    company_id = request.args.get("company_id")
    if cid:
        q = q.filter_by(currency_id=int(cid))
    if company_id:
        q = q.filter_by(company_id=int(company_id))
    records = q.order_by(ExchangeRateHistory.rate_date.desc()).limit(200).all()
    return jsonify({"success": True, "history": [r.to_dict() for r in records]})


@currencies_bp.route("/exchange-rate-history", methods=["POST"])
@require_api("currencies", "edit")
def add_rate_history():
    """إضافة سجل سعر صرف جديد"""
    data = request.get_json() or {}
    currency_id = data.get("currency_id")
    rate_date_str = data.get("rate_date")
    mid_rate = data.get("mid_rate")

    if not currency_id or not rate_date_str or mid_rate is None:
        return jsonify({"message": "currency_id, rate_date, mid_rate required"}), 400

    try:
        rate_date = datetime.strptime(str(rate_date_str), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({"message": "invalid date format"}), 400

    mid_rate = float(mid_rate)
    if mid_rate <= 0:
        return jsonify({"message": "mid_rate must be positive"}), 400

    currency = Currency.query.get_or_404(currency_id)
    company_id = currency.company_id

    existing = ExchangeRateHistory.query.filter_by(
        currency_id=currency_id, rate_date=rate_date
    ).first()

    if existing:
        existing.buy_rate = float(data.get("buy_rate") or 0)
        existing.sell_rate = float(data.get("sell_rate") or 0)
        existing.mid_rate = mid_rate
        existing.source = data.get("source", "manual")
        existing.source_url = data.get("source_url")
        existing.notes = data.get("notes")
        record = existing
    else:
        record = ExchangeRateHistory(
            currency_id=currency_id,
            company_id=company_id,
            rate_date=rate_date,
            buy_rate=float(data.get("buy_rate") or 0),
            sell_rate=float(data.get("sell_rate") or 0),
            mid_rate=mid_rate,
            source=data.get("source", "manual"),
            source_url=data.get("source_url"),
            notes=data.get("notes"),
            created_by=session.get("user_id"),
        )
        db.session.add(record)

    currency.rate = mid_rate
    currency.exchange_rate_source = data.get("source", "manual")
    currency.exchange_rate_updated_at = datetime.utcnow()

    db.session.commit()
    log_action("create" if not existing else "update", "exchange_rate_history", record.id, f"{currency.code} {rate_date}")
    return jsonify({"success": True, "record": record.to_dict()}), 201


@currencies_bp.route("/exchange-rate-history/<int:record_id>", methods=["DELETE"])
@require_api("currencies", "delete")
def delete_rate_history(record_id):
    """حذف سجل سعر صرف"""
    record = ExchangeRateHistory.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    log_action("delete", "exchange_rate_history", record_id, "deleted")
    return jsonify({"success": True})


@currencies_bp.route("/latest-rate/<int:currency_id>", methods=["GET"])
@require_api("currencies", "view")
def latest_rate(currency_id):
    """آخر سعر صرف لعملة معينة"""
    record = ExchangeRateHistory.query.filter_by(currency_id=currency_id)\
        .order_by(ExchangeRateHistory.rate_date.desc()).first()
    if not record:
        return jsonify({"success": True, "rate": None})
    return jsonify({"success": True, "rate": record.to_dict()})

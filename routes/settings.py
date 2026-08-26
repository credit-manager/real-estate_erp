"""General Settings routes.

Page:  /general-settings
API:   GET  /api/general-settings          -> settings + options
       POST /api/general-settings          -> save settings
       GET  /api/general-settings/next-number?type=invoice|po|contract -> suggested next doc number
"""
import re

from flask import Blueprint, jsonify, render_template, request

from database import db
from models import (
    Company, Currency, FinancialYear, TaxType,
    Invoice, PurchaseOrder, RentalContract, RentalRenewal, RentalPayment,
)
from permissions import require_page, require_api, require_any_view
from auditlog import log_action
import utils.settings as settings


settings_bp = Blueprint("settings", __name__, url_prefix="/general-settings")


def _company_dict(c):
    return {
        "id": c.id, "name": c.name, "legal_name": c.legal_name,
        "tax_number": c.tax_number, "commercial_registration": c.commercial_registration,
        "address": c.address, "phone": c.phone, "email": c.email, "website": c.website,
    }


def _options():
    return {
        "companies": [_company_dict(c) for c in Company.query.order_by(Company.name).all()],
        "currencies": [
            {
                "id": c.id, "company_id": c.company_id,
                "company_name": c.company.name if c.company else None,
                "name": c.name, "code": c.code, "symbol": c.symbol,
                "is_base": bool(c.is_base), "is_active": bool(c.is_active),
            }
            for c in Currency.query.order_by(Currency.code).all()
        ],
        "financial_years": [
            {
                "id": y.id, "company_id": y.company_id,
                "company_name": y.company.name if y.company else None,
                "name": y.name, "start_date": y.start_date.isoformat() if y.start_date else None,
                "end_date": y.end_date.isoformat() if y.end_date else None,
                "is_active": bool(y.is_active), "is_closed": bool(y.is_closed),
            }
            for y in FinancialYear.query.order_by(FinancialYear.start_date.desc()).all()
        ],
        "tax_types": [
            {
                "id": t.id, "name": t.name, "rate": float(t.rate or 0),
                "is_active": bool(t.is_active), "is_default": bool(t.is_default),
            }
            for t in TaxType.query.order_by(TaxType.rate.desc()).all()
        ],
    }


def _validate(data):
    """Returns an error key or None."""
    decimals = data.get("number_decimals")
    if decimals not in (None, ""):
        try:
            if int(decimals) not in (0, 1, 2, 3):
                return "settings.numberDecimalsInvalid"
        except (TypeError, ValueError):
            return "settings.numberDecimalsInvalid"
    lang = data.get("default_lang")
    if lang not in (None, "", "ar", "en"):
        return "settings.langInvalid"
    theme = data.get("default_theme")
    if theme not in (None, "", "light", "dark"):
        return "settings.themeInvalid"
    date_fmt = data.get("date_format")
    if date_fmt not in (None, "", "dd/mm/yyyy", "yyyy-mm-dd"):
        return "settings.dateFormatInvalid"
    rate = data.get("doc_default_tax_rate")
    if rate not in (None, ""):
        try:
            r = float(rate)
        except (TypeError, ValueError):
            return "settings.taxRateInvalid"
        if r < 0 or r > 100:
            return "settings.taxRateInvalid"
    return None


@settings_bp.route("")
@require_page("settings")
def page():
    return render_template("general_settings.html")


@settings_bp.route("/api", methods=["GET"])
@require_api("settings", "view")
def get_settings():
    data = settings.get_all()
    payload = {
        k: settings.typed_value(k, v)
        for k, v in data.items()
    }
    return jsonify({
        "success": True,
        "settings": payload,
        "options": _options(),
    })


@settings_bp.route("/api", methods=["POST"])
@require_api("settings", "edit")
def save_settings():
    data = request.get_json(silent=True) or {}
    err = _validate(data)
    if err:
        return jsonify({"success": False, "message": err, "error_key": err}), 400
    settings.save(data)
    log_action("edit", "settings", None, "تعديل الإعدادات العامة")
    return jsonify({"success": True, "message": "settings.saved"})


_DOC_MODELS = {
    "invoice": (Invoice, "invoice_number"),
    "po": (PurchaseOrder, "po_number"),
    "contract": (RentalContract, "contract_number"),
    "renewal": (RentalRenewal, "renewal_number"),
    "payment": (RentalPayment, "payment_number"),
}


@settings_bp.route("/api/next-number", methods=["GET"])
@require_any_view
def next_number():
    doc_type = request.args.get("type", "invoice")
    if doc_type not in _DOC_MODELS:
        return jsonify({"success": False, "message": "invalid-type"}), 400
    model, field = _DOC_MODELS[doc_type]
    prefix = settings.get(doc_type + "_prefix", "")
    if not prefix:
        prefix = {"invoice": "INV-", "po": "PO-", "contract": "RC-", "renewal": "REN-", "payment": "COL-"}[doc_type]

    max_num = 0
    pattern = re.compile(r"(\d+)\s*$")
    for doc in model.query.all():
        value = getattr(doc, field, "") or ""
        if value.startswith(prefix):
            m = pattern.search(value[len(prefix):])
            if m:
                try:
                    max_num = max(max_num, int(m.group(1)))
                except ValueError:
                    pass
    next_num = max_num + 1
    return jsonify({"success": True, "number": f"{prefix}{next_num:04d}"})

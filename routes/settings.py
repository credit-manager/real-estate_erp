"""General Settings routes.

Page:  /general-settings
API:   GET  /api                      -> settings + options
       POST /api                      -> save all settings (legacy)
       POST /api/<section>            -> save a single section
       POST /api/company              -> save company data
       POST /api/layout               -> save layout preferences
       GET  /api/next-number?type=... -> next document number
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

# Sections that exist in the new design
_VALID_SECTIONS = set(settings.SECTION_KEYS) | {"company", "layout", "ai"}

# ── E-Invoicing valid values ──────────────────────────────────
_EINV_COUNTRIES = {"EG", "SA", "AE", "JO", "OM", "KW", "QA", "BH"}
_EINV_MODES = {"clearance", "reporting", "offline"}
_EINV_ENVS = {"preprod", "production"}


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


def _validate_section(section, data):
    """Returns an error key or None for a specific section."""
    if section == "appearance":
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
    elif section == "documents":
        rate = data.get("doc_default_tax_rate")
        if rate not in (None, ""):
            try:
                r = float(rate)
            except (TypeError, ValueError):
                return "settings.taxRateInvalid"
            if r < 0 or r > 100:
                return "settings.taxRateInvalid"
    elif section == "einvoice":
        ec = data.get("einv_country")
        if ec not in (None, "", *_EINV_COUNTRIES):
            return "settings.einvCountryInvalid"
        em = data.get("einv_mode")
        if em not in (None, "", *_EINV_MODES):
            return "settings.einvModeInvalid"
        ev = data.get("einv_environment")
        if ev not in (None, "", *_EINV_ENVS):
            return "settings.einvEnvInvalid"
    elif section == "realestate":
        for key in ("realestate_max_discount_percent", "realestate_vat_percent"):
            val = data.get(key)
            if val not in (None, ""):
                try:
                    f = float(val)
                    if f < 0 or f > 100:
                        return "settings.percentInvalid"
                except (TypeError, ValueError):
                    return "settings.percentInvalid"
    elif section == "rentals":
        val = data.get("rental_escalation_percent")
        if val not in (None, ""):
            try:
                f = float(val)
                if f < 0 or f > 100:
                    return "settings.percentInvalid"
            except (TypeError, ValueError):
                return "settings.percentInvalid"
    elif section == "sales":
        val = data.get("sales_commission_rate")
        if val not in (None, ""):
            try:
                f = float(val)
                if f < 0 or f > 100:
                    return "settings.percentInvalid"
            except (TypeError, ValueError):
                return "settings.percentInvalid"
    elif section == "mobile":
        for key in ("mobile_attendance_radius_meters", "mobile_gps_interval_seconds"):
            val = data.get(key)
            if val not in (None, ""):
                try:
                    f = float(val)
                    if f <= 0:
                        return "settings.radiusInvalid"
                except (TypeError, ValueError):
                    return "settings.radiusInvalid"
    elif section == "backup":
        for key in ("backup_auto_interval_days", "backup_auto_keep"):
            val = data.get(key)
            if val not in (None, ""):
                try:
                    i = int(val)
                    if i <= 0:
                        return "settings.percentInvalid"
                except (TypeError, ValueError):
                    return "settings.percentInvalid"
    return None


# ── Page ───────────────────────────────────────────────────────
@settings_bp.route("")
@require_page("settings")
def page():
    return render_template("general_settings.html")


# ── GET settings ──────────────────────────────────────────────
@settings_bp.route("/api", methods=["GET"])
@require_api("settings", "view")
def get_settings():
    data = settings.get_all()
    payload = {}
    for k, v in data.items():
        if k in settings.SECRET_KEYS:
            payload[k + "_set"] = settings.masked_get(k)
            continue
        payload[k] = settings.typed_value(k, v)
    return jsonify({
        "success": True,
        "settings": payload,
        "options": _options(),
    })


# ── POST save all (legacy) ────────────────────────────────────
@settings_bp.route("/api", methods=["POST"])
@require_api("settings", "edit")
def save_settings():
    data = request.get_json(silent=True) or {}
    settings.save(data)
    log_action("edit", "settings", None, "تعديل الإعدادات العامة")
    return jsonify({"success": True, "message": "settings.saved"})


# ── POST save section ─────────────────────────────────────────
@settings_bp.route("/api/<section>", methods=["POST"])
@require_api("settings", "edit")
def save_section_settings(section):
    if section not in _VALID_SECTIONS:
        return jsonify({"success": False, "message": "invalid-section"}), 400
    data = request.get_json(silent=True) or {}
    err = _validate_section(section, data)
    if err:
        return jsonify({"success": False, "message": err, "error_key": err}), 400
    section_keys = settings.SECTION_KEYS.get(section, set())
    settings.save_section(section_keys, data)
    log_action("edit", "settings", None, f"تعديل إعدادات: {section}")
    return jsonify({"success": True, "message": "settings.saved"})


# ── POST save company ─────────────────────────────────────────
@settings_bp.route("/api/company", methods=["POST"])
@require_api("settings", "edit")
def save_company():
    data = request.get_json(silent=True) or {}
    company_id = data.get("id")
    if not company_id:
        return jsonify({"success": False, "message": "missing-id"}), 400
    try:
        company = db.session.get(Company, int(company_id))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "invalid-id"}), 400
    if not company:
        return jsonify({"success": False, "message": "not-found"}), 404
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "companies.nameRequired"}), 400
    company.name = name
    company.legal_name = (data.get("legal_name") or "").strip()
    company.tax_number = (data.get("tax_number") or "").strip()
    company.commercial_registration = (data.get("commercial_registration") or "").strip()
    company.address = (data.get("address") or "").strip()
    company.phone = (data.get("phone") or "").strip()
    company.email = (data.get("email") or "").strip()
    company.website = (data.get("website") or "").strip()
    db.session.commit()
    log_action("edit", "company", company.id, f"تعديل بيانات الشركة: {company.name}")
    return jsonify({"success": True, "message": "companies.saved"})


# ── POST save layout ──────────────────────────────────────────
@settings_bp.route("/api/layout", methods=["POST"])
@require_api("settings", "edit")
def save_layout():
    data = request.get_json(silent=True) or {}
    layout = data.get("layout_style", "vertical")
    if layout not in ("vertical", "horizontal"):
        layout = "vertical"
    settings.set("layout_style", layout)
    settings.set("sidebar_width", str(data.get("sidebar_width", "258")))
    settings.set("compact_menu", "1" if data.get("compact_menu") else "0")
    settings.set("grouped_modules", "1" if data.get("grouped_modules") else "0")
    db.session.commit()
    return jsonify({"success": True, "message": "settings.saved"})


# ── GET next document number ──────────────────────────────────
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

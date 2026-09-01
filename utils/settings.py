"""Helpers for the General Settings key-value store."""
import time
from database import db
from models.setting import SystemSetting

DEFAULTS = {
    # ---- General ----
    "system_name": "Dynamic Pro ERP",
    "system_logo": "",
    "default_lang": "ar",
    "default_theme": "light",
    "number_decimals": "2",
    "date_format": "dd/mm/yyyy",
    # ---- Operational defaults ----
    "default_company_id": "",
    "default_currency_id": "",
    "default_financial_year_id": "",
    "default_tax_id": "",
    # ---- Printing / documents ----
    "invoice_prefix": "INV-",
    "po_prefix": "PO-",
    "contract_prefix": "RC-",
    "renewal_prefix": "REN-",
    "payment_prefix": "COL-",
    "doc_footer_text": "",
    "doc_default_tax_rate": "15",
    # ---- Sales ----
    "sales_commission_rate": "0",
    # ---- Real estate ----
    "realestate_max_discount_percent": "10",
    "realestate_vat_percent": "15",
    "realestate_contract_approval": "0",
    # ---- Rentals / escalation ----
    "rental_escalation_enabled": "0",
    "rental_escalation_percent": "5",
    # ---- Automatic backup ----
    "backup_auto_enabled": "0",
    "backup_auto_interval_days": "1",
    "backup_auto_folder": "",
    "backup_auto_keep": "10",
    "backup_auto_last": "",
    "backup_encryption_password": "",
    # ---- Mobile / Push notifications ----
    "fcm_server_key": "",
    "mobile_gps_interval_seconds": "30",
    "mobile_attendance_radius_meters": "200",
    "mobile_work_lat": "",
    "mobile_work_lng": "",
    # ---- Country / Currency ----
    "country": "EG",
    "country_name": "مصر",
    "base_currency": "EGP",
    "exchange_rate_source": "central_bank",
    "exchange_rate_api_url": "",
    # ---- E-Invoicing ----
    "einv_enabled": "0",
    "einv_country": "EG",
    "einv_mode": "",
    "einv_environment": "preprod",
    "einv_client_id": "",
    "einv_client_secret": "",
    "einv_api_key": "",
    "einv_provider_url": "",
    "einv_activity_code": "0000",
    # ---- Menu / Layout ----
    "layout_style": "vertical",
    "sidebar_width": "258",
    "compact_menu": "0",
    "grouped_modules": "1",
}

BOOLEAN_KEYS = {
    "backup_auto_enabled", "einv_enabled", "realestate_contract_approval",
    "rental_escalation_enabled", "compact_menu", "grouped_modules",
}
INTEGER_KEYS = {
    "number_decimals",
    "default_company_id",
    "default_currency_id",
    "default_financial_year_id",
    "default_tax_id",
    "backup_auto_interval_days",
    "backup_auto_keep",
    "mobile_gps_interval_seconds",
    "mobile_attendance_radius_meters",
    "sidebar_width",
}
FLOAT_KEYS = {
    "doc_default_tax_rate", "sales_commission_rate",
    "mobile_work_lat", "mobile_work_lng",
    "realestate_max_discount_percent", "realestate_vat_percent",
    "rental_escalation_percent",
}
SECRET_KEYS = {"einv_client_secret", "einv_api_key", "backup_encryption_password", "fcm_server_key"}

SECTION_KEYS = {
    "profile": {"system_name", "system_logo"},
    "appearance": {"default_theme", "default_lang", "number_decimals", "date_format"},
    "documents": {
        "invoice_prefix", "po_prefix", "contract_prefix",
        "renewal_prefix", "payment_prefix",
        "doc_default_tax_rate", "doc_footer_text",
    },
    "defaults": {
        "default_company_id", "default_currency_id",
        "default_financial_year_id", "default_tax_id",
    },
    "realestate": {
        "realestate_max_discount_percent", "realestate_vat_percent",
        "realestate_contract_approval",
    },
    "rentals": {"rental_escalation_enabled", "rental_escalation_percent"},
    "sales": {"sales_commission_rate"},
    "country_currency": {
        "country", "country_name", "base_currency",
        "exchange_rate_source", "exchange_rate_api_url",
    },
    "einvoice": {
        "einv_enabled", "einv_country", "einv_mode", "einv_environment",
        "einv_client_id", "einv_client_secret", "einv_api_key",
        "einv_provider_url", "einv_activity_code",
    },
    "backup": {
        "backup_auto_enabled", "backup_auto_interval_days",
        "backup_auto_keep", "backup_auto_folder",
        "backup_encryption_password",
    },
    "mobile": {
        "mobile_work_lat", "mobile_work_lng",
        "mobile_attendance_radius_meters", "mobile_gps_interval_seconds",
        "fcm_server_key",
    },
}

# ── In-memory cache ────────────────────────────────────────────
_cache = {"data": None, "ts": 0}
_CACHE_TTL = 30


def _invalidate():
    global _cache
    _cache = {"data": None, "ts": 0}


def get_all():
    """dict of all settings merged over DEFAULTS."""
    global _cache
    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL:
        return dict(_cache["data"])
    data = dict(DEFAULTS)
    try:
        rows = SystemSetting.query.all()
    except Exception:
        return data
    for r in rows:
        if r.key in data:
            data[r.key] = r.value if r.value is not None else ""
    _cache["data"] = data
    _cache["ts"] = now
    return dict(data)


def get(key, default=None):
    data = get_all()
    return data.get(key, default if default is not None else DEFAULTS.get(key, ""))


def get_int(key, default=None):
    try:
        return int(float(get(key)))
    except (TypeError, ValueError):
        return default


def get_float(key, default=None):
    try:
        return float(get(key))
    except (TypeError, ValueError):
        return default


def get_bool(key, default=False):
    raw = get(key)
    if isinstance(raw, bool):
        return raw
    if raw in ("1", "true", "True", "yes", "on", 1):
        return True
    return default


def set(key, value):
    row = SystemSetting.query.filter_by(key=key).first()
    if row:
        row.value = "" if value is None else str(value)
    else:
        db.session.add(SystemSetting(key=key, value="" if value is None else str(value)))
    _invalidate()


def save(mapping):
    """Persist only known keys from mapping."""
    for key, value in (mapping or {}).items():
        if key in DEFAULTS:
            set(key, value)
    db.session.commit()
    _invalidate()


def save_section(section_keys, mapping):
    """Persist only known keys from mapping for a specific section."""
    for key, value in (mapping or {}).items():
        if key in section_keys and key in DEFAULTS:
            set(key, value)
    db.session.commit()
    _invalidate()


def typed_value(key, raw):
    """Cast a raw string to the proper type for a key (for API responses)."""
    if key in INTEGER_KEYS:
        try:
            return int(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None
    if key in FLOAT_KEYS:
        try:
            return float(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None
    return raw


def masked_get(key):
    """Return True if the secret has a value, False otherwise."""
    raw = get(key)
    return bool(raw and str(raw).strip())

"""Helpers for the General Settings key-value store."""
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
    # ---- Mobile / Push notifications ----
    "fcm_server_key": "",
    "mobile_gps_interval_seconds": "30",
    "mobile_attendance_radius_meters": "200",
    "mobile_work_lat": "",
    "mobile_work_lng": "",
}

BOOLEAN_KEYS = {"backup_auto_enabled"}
INTEGER_KEYS = {
    "number_decimals",
    "default_company_id",
    "default_currency_id",
    "default_financial_year_id",
    "default_tax_id",
    "backup_auto_interval_days",
    "backup_auto_keep",
    "mobile_gps_interval_seconds",
}
FLOAT_KEYS = {"doc_default_tax_rate", "sales_commission_rate", "mobile_attendance_radius_meters", "mobile_work_lat", "mobile_work_lng", "realestate_max_discount_percent", "realestate_vat_percent", "rental_escalation_percent"}


def get_all():
    """dict of all settings merged over DEFAULTS."""
    data = dict(DEFAULTS)
    try:
        rows = SystemSetting.query.all()
    except Exception:
        return data
    for r in rows:
        if r.key in data:
            data[r.key] = r.value if r.value is not None else ""
    return data


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


def save(mapping):
    """Persist only known keys from mapping."""
    for key, value in (mapping or {}).items():
        if key in DEFAULTS:
            set(key, value)
    db.session.commit()


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

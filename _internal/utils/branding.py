# -*- coding: utf-8 -*-
"""Effective branding resolution (owner logo vs licensed-company logo).

The program logo defaults to the owner's logo (settings['system_logo']).
When the owner enables the branding override and a licensed company holds a
usable subscription (trial / active / grace — i.e. the contract period is
still running until the subscription's end date), the licensed company's own
logo is shown everywhere instead. As soon as the subscription ends (beyond its
grace window), the owner's logo returns automatically.
"""
from typing import Any, Dict, Optional

import utils.settings as settings

LOGO_MAX_LENGTH = 1_500_000  # 1.5 MB max for an inline logo payload


def _flag(raw: Any) -> bool:
    return str(raw) in ("1", "true", "True", "yes", "on", "checked")


def active_customer() -> Optional[Dict[str, Any]]:
    """Return the licensed company with the longest-running usable subscription.

    Returns None when the licensing tables are unavailable or no company has a
    usable subscription (expired, past grace, cancelled or never created).
    """
    try:
        from licensing.models import LicCompany
    except Exception:
        return None
    try:
        companies = LicCompany.query.filter_by(status="active").all()
    except Exception:
        return None

    best: Optional[Dict[str, Any]] = None
    for company in companies:
        sub = company.active_subscription
        if not sub or not sub.is_usable or not sub.end_date:
            continue
        entry: Dict[str, Any] = {
            "id": company.id,
            "name": company.name or company.name_ar or "#{}".format(company.id),
            "status": sub.check_status(),
            "valid_until": sub.end_date.isoformat(),
        }
        entry["_end"] = sub.end_date
        if best is None or entry["_end"] > best["_end"]:
            best = entry
    if best is not None:
        best.pop("_end", None)
    return best


def effective_logo() -> str:
    """Return the logo currently in effect (licensed company or owner)."""
    data = settings.get_all()  # raw merged values — no recursion
    if _flag(data.get("branding_override")):
        customer_logo = (data.get("branding_customer_logo") or "").strip()
        if customer_logo and active_customer():
            return customer_logo
    return (data.get("system_logo") or "").strip()


def info() -> Dict[str, Any]:
    """Describe the current branding state (settings page + API)."""
    data = settings.get_all()
    customer = active_customer()
    return {
        "override": _flag(data.get("branding_override")),
        "owner_logo": (data.get("system_logo") or "").strip(),
        "customer_logo": (data.get("branding_customer_logo") or "").strip(),
        "effective_logo": effective_logo(),
        "customer": customer,
    }


def valid_logo(value: Optional[str]) -> Optional[str]:
    """Validate a submitted logo value.

    Accepts an empty value (clears the logo), an http(s) URL or a data: URL.
    Returns an error message string, or None when the value is accepted.
    """
    value = (value or "").strip()
    if not value:
        return None
    if len(value) > LOGO_MAX_LENGTH:
        return "settings.logoTooLarge"
    if value.startswith("data:"):
        if "," not in value:
            return "settings.logoInvalid"
        if not value.split(",", 1)[0].lower().startswith(("data:image/", "data:image/svg")):
            return "settings.logoInvalid"
        return None
    if value.lower().startswith(("http://", "https://")):
        return None
    return "settings.logoInvalid"
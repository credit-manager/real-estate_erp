# -*- coding: utf-8 -*-
"""Input validation utilities for DynamicPro ERP."""
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# Maximum lengths for common field types
MAX_LENGTHS: Dict[str, int] = {
    "name": 200,
    "title": 200,
    "subject": 200,
    "full_name": 200,
    "username": 100,
    "email": 254,
    "phone": 50,
    "description": 5000,
    "notes": 5000,
    "comment": 5000,
    "address": 1000,
    "code": 100,
    "number": 50,
    "url": 2000,
}


def validate_field_length(
    data: Dict[str, Any],
    field: str,
    max_len: Optional[int] = None,
    required: bool = False,
) -> Optional[str]:
    """Validate a single field's length. Returns error message or None."""
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    if required and not value.strip():
        return f"{field} is required"
    limit: int = max_len or MAX_LENGTHS.get(field, 5000)
    if len(value) > limit:
        return f"{field} exceeds maximum length of {limit}"
    return None


def validate_input(
    data: Dict[str, Any],
    rules: List[Union[str, Tuple[str, Dict[str, Any]]]],
) -> Optional[str]:
    """Validate multiple fields. Returns first error message or None.

    rules: list of (field_name, kwargs) or just field_name strings.
    Example: validate_input(data, [("name", {"required": True}), "notes", ("title", {"max_len": 100})])
    """
    for rule in rules:
        if isinstance(rule, str):
            field = rule
            kwargs: Dict[str, Any] = {}
        else:
            field, kwargs = rule
        err = validate_field_length(data, field, **kwargs)
        if err:
            return err
    return None


def sanitize_text(value: Any, max_len: int = 5000) -> Any:
    """Truncate and strip a text value."""
    if not value or not isinstance(value, str):
        return value
    return value.strip()[:max_len]


def validate_email(email: str) -> bool:
    """Validate email format using regex."""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def validate_phone(phone: str) -> bool:
    """Validate phone number format (digits, spaces, dashes, plus)."""
    if not phone or not isinstance(phone, str):
        return False
    cleaned = phone.strip().replace(' ', '').replace('-', '')
    return bool(re.match(r'^\+?\d{7,15}$', cleaned))

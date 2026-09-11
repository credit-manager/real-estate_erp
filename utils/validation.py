# -*- coding: utf-8 -*-
"""Input validation utilities for DynamicPro ERP."""
import re

# Maximum lengths for common field types
MAX_LENGTHS = {
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


def validate_field_length(data, field, max_len=None, required=False):
    """Validate a single field's length. Returns error message or None."""
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    if required and not value.strip():
        return f"{field} is required"
    limit = max_len or MAX_LENGTHS.get(field, 5000)
    if len(value) > limit:
        return f"{field} exceeds maximum length of {limit}"
    return None


def validate_input(data, rules):
    """Validate multiple fields. Returns first error message or None.

    rules: list of (field_name, kwargs) or just field_name strings.
    Example: validate_input(data, [("name", {"required": True}), "notes", ("title", {"max_len": 100})])
    """
    for rule in rules:
        if isinstance(rule, str):
            field = rule
            kwargs = {}
        else:
            field, kwargs = rule
        err = validate_field_length(data, field, **kwargs)
        if err:
            return err
    return None


def sanitize_text(value, max_len=5000):
    """Truncate and strip a text value."""
    if not value or not isinstance(value, str):
        return value
    return value.strip()[:max_len]

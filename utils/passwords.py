# -*- coding: utf-8 -*-
"""Central password policy for DynamicPro ERP (commercial-grade).

Policy:
- Minimum 8 characters
- Must contain at least one letter and one digit
- Rejects common/weak passwords
"""
import secrets
import string

MIN_LENGTH = 8

WEAK_PASSWORDS = {
    "admin123", "admin@123", "password", "password123", "12345678",
    "qwerty123", "company123", "test1234", "welcome1", "changeme1",
}


def validate_password(password):
    """Return (ok, message). Message is Arabic UI-ready."""
    pw = (password or "").strip()
    if len(pw) < MIN_LENGTH:
        return False, "كلمة المرور يجب ألا تقل عن 8 أحرف"
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        return False, "كلمة المرور يجب أن تحتوي على حروف وأرقام"
    if pw.lower() in WEAK_PASSWORDS:
        return False, "كلمة المرور ضعيفة جداً، اختر كلمة مرور أقوى"
    return True, ""


def generate_strong_password(length=14):
    """Generate a strong random password (letters+digits)."""
    alphabet = string.ascii_letters + string.digits + "!@#%"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        ok, _ = validate_password(pw)
        if ok and pw.lower() not in WEAK_PASSWORDS:
            return pw

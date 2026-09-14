# -*- coding: utf-8 -*-
"""Central password policy for DynamicPro ERP (commercial-grade).

Policy:
- Minimum 8 characters
- Must contain at least one letter and one digit
- Rejects common/weak passwords
"""
import secrets
import string
from typing import Tuple

MIN_LENGTH: int = 8

WEAK_PASSWORDS: set = {
    "admin123", "admin@123", "password", "password123", "12345678",
    "qwerty123", "company123", "test1234", "welcome1", "changeme1",
}


def validate_password(password: str) -> Tuple[bool, str]:
    """Return (ok, message). Message is Arabic UI-ready."""
    pw = (password or "").strip()
    if len(pw) < MIN_LENGTH:
        return False, "كلمة المرور يجب ألا تقل عن 8 أحرف"
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        return False, "كلمة المرور يجب أن تحتوي على حروف وأرقام"
    if pw.lower() in WEAK_PASSWORDS:
        return False, "كلمة المرور ضعيفة جداً، اختر كلمة مرور أقوى"
    return True, ""


def generate_strong_password(length: int = 14) -> str:
    """Generate a strong random password (letters+digits)."""
    alphabet = string.ascii_letters + string.digits + "!@#%"
    for _ in range(1000):
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        ok, _ = validate_password(pw)
        if ok and pw.lower() not in WEAK_PASSWORDS:
            return pw
    raise RuntimeError("Failed to generate a strong password after 1000 attempts")


def check_password_strength(password: str) -> int:
    """Return password strength score (0-100)."""
    pw = (password or "").strip()
    score = 0
    
    if len(pw) >= 8:
        score += 20
    if len(pw) >= 12:
        score += 10
    if len(pw) >= 16:
        score += 10
    
    if any(c.islower() for c in pw):
        score += 10
    if any(c.isupper() for c in pw):
        score += 10
    if any(c.isdigit() for c in pw):
        score += 10
    if any(c in string.punctuation for c in pw):
        score += 15
    
    if pw.lower() in WEAK_PASSWORDS:
        score = 0
    
    return min(score, 100)

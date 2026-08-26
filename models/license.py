"""License & Activity models for DynamicPro ERP."""
from database import db
import secrets
import string
import hashlib
from datetime import datetime, timezone, timedelta


class License(db.Model):
    __tablename__ = "licenses"

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    company_name = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(120), nullable=False)
    contact_email = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(50))

    license_type = db.Column(db.String(20), nullable=False)  # trial, annual, biennial
    max_users = db.Column(db.Integer, default=10)
    issued_at = db.Column(db.DateTime, server_default=db.func.now())
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    def is_valid(self):
        return self.is_active and self.expires_at > datetime.now(timezone.utc)

    def days_remaining(self):
        if not self.is_valid():
            return 0
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    def to_dict(self):
        return {
            "id": self.id,
            "license_key": self.license_key,
            "company_name": self.company_name,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "license_type": self.license_type,
            "max_users": self.max_users,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "is_valid": self.is_valid(),
            "days_remaining": self.days_remaining(),
            "notes": self.notes,
            "created_by": self.created_by,
        }

    @staticmethod
    def generate_key():
        chars = string.ascii_uppercase + string.digits
        parts = []
        for _ in range(4):
            part = ''.join(secrets.choice(chars) for _ in range(4))
            parts.append(part)
        return '-'.join(parts)

    @staticmethod
    def get_duration(license_type):
        if license_type == "trial":
            return timedelta(days=30)
        elif license_type == "annual":
            return timedelta(days=365)
        elif license_type == "biennial":
            return timedelta(days=730)
        return timedelta(days=30)


class LicenseActivity(db.Model):
    __tablename__ = "license_activity"

    id = db.Column(db.Integer, primary_key=True)
    license_id = db.Column(db.Integer, db.ForeignKey("licenses.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    username = db.Column(db.String(80))
    action = db.Column(db.String(30))  # login, logout, view, create, edit, delete
    details = db.Column(db.String(300))
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "license_id": self.license_id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OwnerNotification(db.Model):
    __tablename__ = "owner_notifications"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(30))  # login, license_expiring, license_expired, user_action
    is_read = db.Column(db.Boolean, default=False)
    related_user = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "is_read": self.is_read,
            "related_user": self.related_user,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

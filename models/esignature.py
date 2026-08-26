"""Electronic Signature integration — DocuSign / Na3am / local signing."""
from database import db


class SignatureProvider(db.Model):
    """مزود خدمة التوقيع الإلكتروني."""
    __tablename__ = "signature_providers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # docusign, na3am, local
    display_name = db.Column(db.String(100), nullable=False)
    api_base_url = db.Column(db.String(255))
    client_id = db.Column(db.String(100))
    client_secret_encrypted = db.Column(db.Text)  # مخزن مشفر
    webhook_secret_encrypted = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    config_json = db.Column(db.Text)  # إعدادات إضافية
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "api_base_url": self.api_base_url,
            "is_active": self.is_active,
            "is_default": self.is_default,
        }


class SignatureRequest(db.Model):
    """طلب توقيع — وثيقة مرسلة للتوقيع."""
    __tablename__ = "signature_requests"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("signature_providers.id"), nullable=False, index=True)
    external_id = db.Column(db.String(100), index=True)  # ID من المزود (envelope_id في DocuSign)
    document_type = db.Column(db.String(30), nullable=False, index=True)  # sales_contract, rental_contract, etc.
    document_id = db.Column(db.Integer, nullable=False, index=True)  # ID الوثيقة في نظامنا
    document_number = db.Column(db.String(50))  # رقم العقد/الوثيقة
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="draft", index=True)  # draft, sent, delivered, signed, completed, declined, expired, voided
    signer_email = db.Column(db.String(120))
    signer_name = db.Column(db.String(150))
    signer_phone = db.Column(db.String(30))
    signing_url = db.Column(db.Text)  # رابط التوقيع
    completed_at = db.Column(db.DateTime)
    expired_at = db.Column(db.DateTime)
    callback_data = db.Column(db.Text)  # بيانات الويب هوك المستلمة
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    provider = db.relationship("SignatureProvider", backref="requests")

    def to_dict(self):
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "provider_name": self.provider.display_name if self.provider else None,
            "external_id": self.external_id,
            "document_type": self.document_type,
            "document_id": self.document_id,
            "document_number": self.document_number,
            "title": self.title,
            "message": self.message,
            "status": self.status,
            "signer_email": self.signer_email,
            "signer_name": self.signer_name,
            "signer_phone": self.signer_phone,
            "signing_url": self.signing_url,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expired_at": self.expired_at.isoformat() if self.expired_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SignatureAuditLog(db.Model):
    """سجل تدقيق أحداث التوقيع."""
    __tablename__ = "signature_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("signature_requests.id"), nullable=False, index=True)
    event_type = db.Column(db.String(30), nullable=False)  # created, sent, viewed, signed, completed, declined, expired, error
    event_data = db.Column(db.Text)  # JSON
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    request = db.relationship("SignatureRequest", backref="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "event_type": self.event_type,
            "event_data": self.event_data,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
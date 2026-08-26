"""نظام الإشعارات الموحد — SMS/Email/WhatsApp/Push/In-app."""
from database import db
from sqlalchemy import event


class NotificationChannel(db.Model):
    """قناة إشعار — SMS, Email, WhatsApp, Push, In-app."""
    __tablename__ = "notification_channels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)  # sms, email, whatsapp, push, inapp
    display_name = db.Column(db.String(100), nullable=False)
    provider = db.Column(db.String(50))  # twilio, ultramsg, sendgrid, fcm, local
    config_json = db.Column(db.Text)  # إعدادات المزود (API keys, sender ID, etc.)
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=10)  # أولوية القناة
    rate_limit_per_minute = db.Column(db.Integer, default=60)
    rate_limit_per_hour = db.Column(db.Integer, default=1000)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    templates = db.relationship("NotificationTemplate", backref="channel", cascade="all, delete-orphan")
    queue = db.relationship("NotificationQueue", backref="channel")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "provider": self.provider,
            "is_active": self.is_active,
            "priority": self.priority,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "rate_limit_per_hour": self.rate_limit_per_hour,
        }


class NotificationTemplate(db.Model):
    """قالب إشعار — مع متغيرات ديناميكية."""
    __tablename__ = "notification_templates"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("notification_channels.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)  # payment_due, contract_signed, maintenance_created
    subject_template = db.Column(db.Text)  # للبريد/الإشعارات ذات الموضوع
    body_template = db.Column(db.Text, nullable=False)  # Jinja2 template
    variables_json = db.Column(db.Text)  # وصف المتغيرات المتوقعة
    language = db.Column(db.String(10), default='ar')  # ar, en
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "channel_name": self.channel.display_name if self.channel else None,
            "name": self.name,
            "subject_template": self.subject_template,
            "body_template": self.body_template,
            "variables": self.variables_json,
            "language": self.language,
            "is_active": self.is_active,
        }


class NotificationQueue(db.Model):
    """طابور الإشعارات — للمعالجة غير المتزامنة."""
    __tablename__ = "notification_queue"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("notification_channels.id"), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("notification_templates.id"), index=True)

    recipient = db.Column(db.String(200), nullable=False)  # رقم هاتف، بريد، user_id للـ in-app
    recipient_type = db.Column(db.String(20), default='user')  # user, phone, email, topic
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)

    subject = db.Column(db.Text)
    body = db.Column(db.Text, nullable=False)
    data_json = db.Column(db.Text)  # بيانات إضافية للقالب

    status = db.Column(db.String(20), default='pending', index=True)  # pending, processing, sent, failed, cancelled
    priority = db.Column(db.Integer, default=5)  # 1=high, 5=normal, 10=low
    attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)

    scheduled_at = db.Column(db.DateTime, index=True)  # للجدولة المستقبلية
    sent_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)

    provider_response = db.Column(db.Text)  # استجابة المزود (JSON)
    external_id = db.Column(db.String(100))  # message_id من المزود

    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "channel_name": self.channel.display_name if self.channel else None,
            "template_id": self.template_id,
            "template_name": self.template.name if self.template else None,
            "recipient": self.recipient,
            "recipient_type": self.recipient_type,
            "subject": self.subject,
            "body": self.body,
            "status": self.status,
            "priority": self.priority,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error_message": self.error_message,
            "external_id": self.external_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NotificationPreference(db.Model):
    """تفضيلات الإشعارات للمستخدم."""
    __tablename__ = "notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    # إعدادات عامة
    email_enabled = db.Column(db.Boolean, default=True)
    sms_enabled = db.Column(db.Boolean, default=True)
    push_enabled = db.Column(db.Boolean, default=True)
    inapp_enabled = db.Column(db.Boolean, default=True)
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    # إعدادات لكل نوع إشعار
    preferences_json = db.Column(db.Text)  # {"payment_due": {"email": true, "sms": false}, ...}
    quiet_hours_start = db.Column(db.String(5))  # "22:00"
    quiet_hours_end = db.Column(db.String(5))  # "08:00"
    timezone = db.Column(db.String(50), default='Asia/Riyadh')
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_enabled": self.email_enabled,
            "sms_enabled": self.sms_enabled,
            "push_enabled": self.push_enabled,
            "inapp_enabled": self.inapp_enabled,
            "whatsapp_enabled": self.whatsapp_enabled,
            "preferences": self.preferences_json,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "timezone": self.timezone,
        }


class NotificationLog(db.Model):
    """سجل الإشعارات المرسلة — للتدقيق والتحليل."""
    __tablename__ = "notification_logs"

    id = db.Column(db.Integer, primary_key=True)
    queue_id = db.Column(db.Integer, db.ForeignKey("notification_queue.id"), index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("notification_channels.id"), index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("notification_templates.id"), index=True)

    recipient = db.Column(db.String(200))
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)

    subject = db.Column(db.Text)
    body = db.Column(db.Text)
    channel = db.Column(db.String(30))  # sms, email, whatsapp, push, inapp
    status = db.Column(db.String(20))  # sent, failed, delivered, read
    provider = db.Column(db.String(50))
    external_id = db.Column(db.String(100))
    error_message = db.Column(db.Text)
    cost = db.Column(db.Numeric(10, 4))  # تكلفة الإرسال

    sent_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    delivered_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "queue_id": self.queue_id,
            "channel": self.channel,
            "recipient": self.recipient,
            "subject": self.subject,
            "status": self.status,
            "provider": self.provider,
            "external_id": self.external_id,
            "error_message": self.error_message,
            "cost": float(self.cost) if self.cost else 0,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }
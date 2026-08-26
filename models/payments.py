"""تكامل بوابات الدفع — Moyasar / PayTabs / STC Pay."""
from database import db
from sqlalchemy import event


class PaymentGateway(db.Model):
    """بوابة دفع — Moyasar, PayTabs, STC Pay, Moyasar, HyperPay."""
    __tablename__ = "payment_gateways"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)  # moyasar, paytabs, stcpay, hyperpay
    display_name = db.Column(db.String(100), nullable=False)
    provider = db.Column(db.String(50))  # moyasar, paytabs, stcpay, hyperpay
    api_key_encrypted = db.Column(db.Text)  # مشفر
    secret_key_encrypted = db.Column(db.Text)  # مشفر
    merchant_id = db.Column(db.String(100))
    webhook_secret_encrypted = db.Column(db.Text)
    supported_currencies = db.Column(db.Text, default='SAR,USD')  # JSON array
    supported_cards = db.Column(db.Text, default='visa,mastercard,mada')  # JSON array
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    is_sandbox = db.Column(db.Boolean, default=True)
    config_json = db.Column(db.Text)  # إعدادات إضافية
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    transactions = db.relationship("PaymentTransaction", backref="gateway", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "provider": self.provider,
            "merchant_id": self.merchant_id,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "is_sandbox": self.is_sandbox,
            "supported_currencies": self.supported_currencies,
            "supported_cards": self.supported_cards,
        }


class PaymentTransaction(db.Model):
    """معاملة دفع — تتبع كامل لدورة حياة الدفع."""
    __tablename__ = "payment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    gateway_id = db.Column(db.Integer, db.ForeignKey("payment_gateways.id"), nullable=False, index=True)

    # المعرفات
    reference_id = db.Column(db.String(100), unique=True, nullable=False, index=True)  # مرجعنا الداخلي
    external_id = db.Column(db.String(100), index=True)  # معرف البوابة (payment_id في Moyasar)

    # المبالغ
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    currency = db.Column(db.String(10), default='SAR')
    fee = db.Column(db.Numeric(10, 2), default=0)  # رسوم البوابة
    net_amount = db.Column(db.Numeric(15, 2))  # المبلغ الصافي بعد الرسوم

    # حالة الدفع
    status = db.Column(db.String(30), default='initiated', index=True)  # initiated, pending, authorized, captured, failed, cancelled, refunded, partial_refunded
    payment_method = db.Column(db.String(30))  # visa, mastercard, mada, apple_pay, stcpay, tabby, tamara

    # الكيان المرتبط
    entity_type = db.Column(db.String(30), index=True)  # sales_contract, rental_contract, invoice, service_charge, installment, hoa_fee
    entity_id = db.Column(db.Integer, index=True)

    # بيانات العميل
    customer_name = db.Column(db.String(150))
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(30))
    customer_ip = db.Column(db.String(45))

    # بيانات البطاقة (مخفية/مجزأة)
    card_brand = db.Column(db.String(20))  # visa, mastercard, mada
    card_last4 = db.Column(db.String(4))
    card_exp_month = db.Column(db.Integer)
    card_exp_year = db.Column(db.Integer)

    # روابط و callback
    callback_url = db.Column(db.Text)
    return_url = db.Column(db.Text)
    webhook_url = db.Column(db.Text)

    # استجابة البوابة
    gateway_response = db.Column(db.Text)  # JSON response
    gateway_status = db.Column(db.String(50))  # حالة البوابة الأصلية

    # تواريخ
    initiated_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    authorized_at = db.Column(db.DateTime)
    captured_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    refunded_at = db.Column(db.DateTime)

    # استردادات
    refunded_amount = db.Column(db.Numeric(15, 2), default=0)
    refund_reason = db.Column(db.Text)

    # بيانات إضافية
    metadata_json = db.Column(db.Text)  # بيانات إضافية مخصصة
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # علاقات
    refunds = db.relationship("PaymentRefund", backref="transaction", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "gateway_id": self.gateway_id,
            "gateway_name": self.gateway.display_name if self.gateway else None,
            "reference_id": self.reference_id,
            "external_id": self.external_id,
            "amount": float(self.amount or 0),
            "currency": self.currency,
            "fee": float(self.fee or 0),
            "net_amount": float(self.net_amount or 0) if self.net_amount else float(self.amount or 0),
            "status": self.status,
            "payment_method": self.payment_method,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "customer_phone": self.customer_phone,
            "card_brand": self.card_brand,
            "card_last4": self.card_last4,
            "initiated_at": self.initiated_at.isoformat() if self.initiated_at else None,
            "authorized_at": self.authorized_at.isoformat() if self.authorized_at else None,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "refunded_amount": float(self.refunded_amount or 0),
        }

    @property
    def is_refundable(self):
        return self.status in ('captured', 'authorized') and float(self.refunded_amount or 0) < float(self.amount or 0)

    @property
    def refundable_amount(self):
        return float(self.amount or 0) - float(self.refunded_amount or 0)


class PaymentRefund(db.Model):
    """طلب استرداد — تتبع الاستردادات الجزئية والكاملة."""
    __tablename__ = "payment_refunds"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("payment_transactions.id"), nullable=False, index=True)
    reference_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    external_id = db.Column(db.String(100), index=True)  # معرف الاسترداد في البوابة

    amount = db.Column(db.Numeric(15, 2), nullable=False)
    currency = db.Column(db.String(10), default='SAR')
    reason = db.Column(db.Text)
    reason_code = db.Column(db.String(30))  # duplicate, fraudulent, customer_request, etc.

    status = db.Column(db.String(30), default='pending', index=True)  # pending, processing, completed, failed, cancelled
    gateway_response = db.Column(db.Text)
    gateway_status = db.Column(db.String(50))

    initiated_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    initiated_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    processed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "reference_id": self.reference_id,
            "external_id": self.external_id,
            "amount": float(self.amount or 0),
            "currency": self.currency,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "status": self.status,
            "initiated_at": self.initiated_at.isoformat() if self.initiated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class PaymentMethodToken(db.Model):
    """توكن طريقة دفع محفوظة — للـ recurring payments / saved cards."""
    __tablename__ = "payment_method_tokens"

    id = db.Column(db.Integer, primary_key=True)
    gateway_id = db.Column(db.Integer, db.ForeignKey("payment_gateways.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)  # للربط بـ Customer

    external_token = db.Column(db.String(200), nullable=False, index=True)  # token من البوابة
    payment_method = db.Column(db.String(30))  # visa, mastercard, mada, stcpay, apple_pay
    card_brand = db.Column(db.String(20))
    card_last4 = db.Column(db.String(4))
    card_exp_month = db.Column(db.Integer)
    card_exp_year = db.Column(db.Integer)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    nickname = db.Column(db.String(50))  # اسم مختصر للبطاقة

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "gateway_id": self.gateway_id,
            "external_token": self.external_token,
            "payment_method": self.payment_method,
            "card_brand": self.card_brand,
            "card_last4": self.card_last4,
            "card_exp_month": self.card_exp_month,
            "card_exp_year": self.card_exp_year,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "nickname": self.nickname,
        }


class PaymentPlanInstallment(db.Model):
    """ربط القسط بخطة دفع وبوابة — للـ auto-charge."""
    __tablename__ = "payment_plan_installments"

    id = db.Column(db.Integer, primary_key=True)
    installment_id = db.Column(db.Integer, db.ForeignKey("installments.id"), nullable=False, unique=True, index=True)
    gateway_id = db.Column(db.Integer, db.ForeignKey("payment_gateways.id"), index=True)
    payment_token_id = db.Column(db.Integer, db.ForeignKey("payment_method_tokens.id"), index=True)

    auto_charge = db.Column(db.Boolean, default=False)  # تحصيل تلقائي عند الاستحقاق
    charge_days_before_due = db.Column(db.Integer, default=1)  # قبل الاستحقاق بيوم
    max_retry_attempts = db.Column(db.Integer, default=3)
    retry_interval_hours = db.Column(db.Integer, default=24)

    last_charge_attempt = db.Column(db.DateTime)
    last_charge_status = db.Column(db.String(30))
    next_charge_at = db.Column(db.DateTime, index=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "installment_id": self.installment_id,
            "gateway_id": self.gateway_id,
            "payment_token_id": self.payment_token_id,
            "auto_charge": self.auto_charge,
            "charge_days_before_due": self.charge_days_before_due,
            "max_retry_attempts": self.max_retry_attempts,
            "retry_interval_hours": self.retry_interval_hours,
            "last_charge_attempt": self.last_charge_attempt.isoformat() if self.last_charge_attempt else None,
            "last_charge_status": self.last_charge_status,
            "next_charge_at": self.next_charge_at.isoformat() if self.next_charge_at else None,
        }
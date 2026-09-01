# -*- coding: utf-8 -*-
"""Master DB models for licensing & multi-tenant management.

All class names prefixed with 'Lic' to avoid conflicts with app models.
"""
from datetime import date, timedelta
from database import db


class LicPlan(db.Model):
    __tablename__ = "lic_plans"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    description_ar = db.Column(db.String(500))

    max_users = db.Column(db.Integer, nullable=False, default=5)
    max_projects = db.Column(db.Integer, nullable=False, default=10)
    max_storage_mb = db.Column(db.Integer, nullable=False, default=1024)

    modules = db.Column(db.JSON, nullable=False, default=dict)

    price_monthly = db.Column(db.Numeric(12, 2))
    price_yearly = db.Column(db.Numeric(12, 2))

    badge = db.Column(db.String(50))
    badge_color = db.Column(db.String(20))
    badge_bg = db.Column(db.String(20))
    icon = db.Column(db.String(10))
    gradient = db.Column(db.String(200))

    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id, "code": self.code, "name": self.name,
            "name_ar": self.name_ar,
            "description": self.description,
            "description_ar": self.description_ar,
            "max_users": self.max_users,
            "max_projects": self.max_projects, "max_storage_mb": self.max_storage_mb,
            "modules": self.modules or {},
            "price_monthly": float(self.price_monthly) if self.price_monthly else None,
            "price_yearly": float(self.price_yearly) if self.price_yearly else None,
            "badge": self.badge,
            "badge_color": self.badge_color,
            "badge_bg": self.badge_bg,
            "icon": self.icon,
            "gradient": self.gradient,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
        }


class LicCompany(db.Model):
    __tablename__ = "lic_companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200))
    tax_number = db.Column(db.String(50))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(30))
    address = db.Column(db.Text)

    db_name = db.Column(db.String(100), unique=True, nullable=False)
    db_host = db.Column(db.String(200), default="localhost")
    db_port = db.Column(db.Integer, default=5432)

    port = db.Column(db.Integer, default=2222)  # Server port for this company

    status = db.Column(db.String(20), default="active")  # active | suspended | deleted

    is_trial = db.Column(db.Boolean, default=False)
    trial_ends_at = db.Column(db.Date)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    @property
    def active_subscription(self):
        return LicSubscription.query.filter(
            LicSubscription.company_id == self.id,
            LicSubscription.status.in_(["trial", "active", "grace"]),
        ).order_by(LicSubscription.id.desc()).first()

    @property
    def active_license(self):
        return LicLicense.query.filter_by(
            company_id=self.id, status="active"
        ).order_by(LicLicense.id.desc()).first()

    def to_dict(self):
        lic = self.active_license
        sub = self.active_subscription
        return {
            "id": self.id, "name": self.name, "name_ar": self.name_ar,
            "tax_number": self.tax_number, "email": self.email,
            "phone": self.phone, "address": self.address,
            "db_name": self.db_name, "status": self.status,
            "port": self.port,
            "is_trial": self.is_trial,
            "trial_ends_at": self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            "subscription_status": sub.check_status() if sub else None,
            "subscription_end": sub.end_date.isoformat() if sub else None,
            "license_status": lic.status if lic else None,
            "license_expires": lic.expires_at.isoformat() if lic else None,
            "plan_code": sub.plan.code if sub and sub.plan else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LicSubscription(db.Model):
    __tablename__ = "lic_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("lic_companies.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("lic_plans.id"), nullable=False)

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    # trial | active | grace | expired | cancelled
    status = db.Column(db.String(20), default="active")

    auto_renew = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    plan = db.relationship("LicPlan", backref="subscriptions", lazy="joined")

    def check_status(self):
        today = date.today()
        if self.status == "cancelled":
            return "cancelled"
        if self.end_date >= today:
            return self.status
        grace = self.end_date + timedelta(days=7)
        if grace >= today:
            return "grace"
        return "expired"

    @property
    def is_usable(self):
        return self.check_status() in ("trial", "active", "grace")

    def to_dict(self):
        company = db.session.get(LicCompany, self.company_id)
        return {
            "id": self.id, "company_id": self.company_id,
            "company_name": company.name if company else None,
            "plan_id": self.plan_id,
            "plan_code": self.plan.code if self.plan else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "computed_status": self.check_status(),
            "auto_renew": self.auto_renew,
        }


class LicLicense(db.Model):
    __tablename__ = "lic_licenses"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("lic_companies.id"), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey("lic_subscriptions.id"))

    license_key = db.Column(db.String(50), unique=True, nullable=False)

    # active | suspended | revoked
    status = db.Column(db.String(20), default="active")

    issued_at = db.Column(db.Date, nullable=False)
    expires_at = db.Column(db.Date, nullable=False)

    last_validated = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def is_usable(self):
        return self.status == "active"

    def to_dict(self):
        company = db.session.get(LicCompany, self.company_id)
        return {
            "id": self.id, "company_id": self.company_id,
            "company_name": company.name if company else None,
            "subscription_id": self.subscription_id,
            "license_key": self.license_key, "status": self.status,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
        }


class LicPayment(db.Model):
    __tablename__ = "lic_payments"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("lic_companies.id"), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey("lic_subscriptions.id"))

    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default="EGP")

    payment_method = db.Column(db.String(30))
    reference_no = db.Column(db.String(100))

    status = db.Column(db.String(20), default="pending")  # pending | confirmed | failed | refunded

    paid_at = db.Column(db.DateTime)
    confirmed_by = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        company = db.session.get(LicCompany, self.company_id)
        return {
            "id": self.id, "company_id": self.company_id,
            "company_name": company.name if company else None,
            "subscription_id": self.subscription_id,
            "amount": float(self.amount), "currency": self.currency,
            "payment_method": self.payment_method, "reference_no": self.reference_no,
            "status": self.status,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "confirmed_by": self.confirmed_by,
        }


class LicMasterUser(db.Model):
    __tablename__ = "lic_master_users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150))

    role = db.Column(db.String(30), default="support")  # super_admin | admin | support | sales

    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id, "email": self.email, "full_name": self.full_name,
            "role": self.role, "is_active": self.is_active,
        }


class LicCompanyUser(db.Model):
    """Maps a company user email to their company in the master DB.

    This is the bridge that lets us identify which company a user belongs to
    from just their email address, without requiring the user to provide
    a database_id or company_id.
    """
    __tablename__ = "lic_company_users"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("lic_companies.id"), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150))

    role = db.Column(db.String(30), default="admin")  # admin | manager | employee

    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    company = db.relationship("LicCompany", backref="company_users", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("company_id", "email", name="uq_lic_company_users_company_email"),
    )

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id,
            "email": self.email, "full_name": self.full_name,
            "role": self.role, "is_active": self.is_active,
        }


class LicDatabaseRegistry(db.Model):
    __tablename__ = "lic_database_registry"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("lic_companies.id"), nullable=False)

    db_name = db.Column(db.String(100), nullable=False)
    db_host = db.Column(db.String(200), nullable=False)
    db_port = db.Column(db.Integer, default=5432)
    db_user = db.Column(db.String(100))
    db_password_enc = db.Column(db.String(255))

    schema_version = db.Column(db.String(20))
    last_migration = db.Column(db.DateTime)
    size_mb = db.Column(db.Numeric(10, 2))

    status = db.Column(db.String(20), default="active")
    # active | provisioning | migrating | archived

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id,
            "db_name": self.db_name, "db_host": self.db_host,
            "db_port": self.db_port, "schema_version": self.schema_version,
            "size_mb": float(self.size_mb) if self.size_mb else None,
            "status": self.status,
        }


class LicActivityLog(db.Model):
    __tablename__ = "lic_activity_log"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer)
    actor_email = db.Column(db.String(150))
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id, "actor_email": self.actor_email,
            "action": self.action, "target_type": self.target_type,
            "target_id": self.target_id, "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

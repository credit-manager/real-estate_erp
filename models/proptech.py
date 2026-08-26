"""Proptech extensions: snagging checklists, tenant screening (KYC), mortgages."""
from database import db


class DeliveryChecklistItem(db.Model):
    """بنود مطابقة التسليم (Snagging) — بند لكل نقطة فحص قبل التسليم."""
    __tablename__ = "delivery_checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey("unit_deliveries.id"), nullable=False, index=True)
    description = db.Column(db.String(250), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending | ok | issue | fixed
    notes = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    delivery = db.relationship("UnitDelivery", backref=db.backref(
        "checklist", cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "delivery_id": self.delivery_id,
            "description": self.description,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TenantScreening(db.Model):
    """فحص استادة المستأجرين (KYC) — الجدارة الائتمانية والقائمة السوداء."""
    __tablename__ = "tenant_screenings"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    monthly_income = db.Column(db.Numeric(15, 2), default=0)
    employer = db.Column(db.String(150))
    credit_status = db.Column(db.String(20), default="unknown")  # good | fair | bad | unknown
    blacklist = db.Column(db.Boolean, default=False)
    result = db.Column(db.String(20), default="pending")  # approved | rejected | pending
    notes = db.Column(db.Text)
    checked_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    checked_at = db.Column(db.DateTime, server_default=db.func.now())

    customer = db.relationship("Customer", backref="screenings")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "monthly_income": float(self.monthly_income or 0),
            "employer": self.employer,
            "credit_status": self.credit_status,
            "blacklist": bool(self.blacklist),
            "result": self.result,
            "notes": self.notes,
            "checked_by": self.checked_by,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }


class UnitMortgage(db.Model):
    """الرهون العقارية والتمويل — تتبع بنك ممول على وحدة مباعة."""
    __tablename__ = "unit_mortgages"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"), nullable=False, index=True)
    sales_contract_id = db.Column(db.Integer, db.ForeignKey("sales_contracts.id"))
    lender_name = db.Column(db.String(150), nullable=False)   # الجهة الممولة/البنك
    loan_amount = db.Column(db.Numeric(15, 2), default=0)
    ltv_percent = db.Column(db.Numeric(5, 2), default=0)      # نسبة القرض من قيمة الوحدة
    interest_rate = db.Column(db.Numeric(5, 2), default=0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    lien_number = db.Column(db.String(60))                     # رقم الرهن
    status = db.Column(db.String(20), default="active")        # active | settled | defaulted
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="mortgages")
    sales_contract = db.relationship("SalesContract", backref="mortgages")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "sales_contract_id": self.sales_contract_id,
            "lender_name": self.lender_name,
            "loan_amount": float(self.loan_amount or 0),
            "ltv_percent": float(self.ltv_percent or 0),
            "interest_rate": float(self.interest_rate or 0),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "lien_number": self.lien_number,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

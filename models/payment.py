from database import db


class PaymentPlan(db.Model):
    __tablename__ = "payment_plans"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"))
    total_amount = db.Column(db.Numeric(15, 2), default=0)
    down_payment = db.Column(db.Numeric(15, 2), default=0)
    monthly_amount = db.Column(db.Numeric(15, 2), default=0)
    start_date = db.Column(db.Date)
    months = db.Column(db.Integer, default=1)
    status = db.Column(db.String(30), default="active")  # active | completed | overdue
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="payment_plans")
    customer = db.relationship("Customer", backref="payment_plans")
    financial_year = db.relationship("FinancialYear", backref="payment_plans")
    installments = db.relationship(
        "Installment", backref="plan", cascade="all, delete-orphan",
        order_by="Installment.due_date",
    )

    def paid_total(self):
        return sum(float(i.paid_amount or 0) for i in self.installments) + float(self.down_payment or 0)

    def _base_currency(self):
        if self.financial_year and self.financial_year.company:
            company = self.financial_year.company
            for c in company.currencies:
                if c.is_base:
                    return c.to_dict()
            code = company.currency
            if code:
                return {"code": code, "symbol": code, "name": code}
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "customer_id": self.customer_id,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "currency": self._base_currency(),
            "total_amount": float(self.total_amount or 0),
            "down_payment": float(self.down_payment or 0),
            "monthly_amount": float(self.monthly_amount or 0),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "months": self.months,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid": self.paid_total(),
            "balance": float(self.total_amount or 0) - self.paid_total(),
            "installments": [i.to_dict() for i in self.installments],
        }


class Installment(db.Model):
    __tablename__ = "installments"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("payment_plans.id"))
    installment_number = db.Column(db.Integer, default=1)
    amount = db.Column(db.Numeric(15, 2), default=0)
    paid_amount = db.Column(db.Numeric(15, 2), default=0)
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="pending")  # pending | paid | partial | overdue

    def to_dict(self):
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "installment_number": self.installment_number,
            "amount": float(self.amount or 0),
            "paid_amount": float(self.paid_amount or 0),
            "balance": float((self.amount or 0) - (self.paid_amount or 0)),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "status": self.status,
        }

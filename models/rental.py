from database import db


class RentalContract(db.Model):
    __tablename__ = "rental_contracts"

    id = db.Column(db.Integer, primary_key=True)
    contract_number = db.Column(db.String(50), unique=True, nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"))
    monthly_rent = db.Column(db.Numeric(15, 2), default=0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="active")  # active | expired | terminated
    approval_status = db.Column(db.String(20), default="not_required")  # not_required | pending | approved | rejected
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="rental_contracts")
    customer = db.relationship("Customer", backref="rental_contracts")
    financial_year = db.relationship("FinancialYear", backref="rental_contracts")

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
            "contract_number": self.contract_number,
            "unit_id": self.unit_id,
            "customer_id": self.customer_id,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "currency": self._base_currency(),
            "monthly_rent": float(self.monthly_rent or 0),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "approval_status": self.approval_status or "not_required",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RentalRenewal(db.Model):
    """تجديد عقد إيجار (تمديد المدة و/أو تعديل الإيجار الشهري)."""
    __tablename__ = "rental_renewals"

    id = db.Column(db.Integer, primary_key=True)
    renewal_number = db.Column(db.String(50), unique=True, nullable=False)
    contract_id = db.Column(db.Integer, db.ForeignKey("rental_contracts.id"))
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"))
    previous_end_date = db.Column(db.Date)
    new_end_date = db.Column(db.Date)
    previous_monthly_rent = db.Column(db.Numeric(15, 2), default=0)
    new_monthly_rent = db.Column(db.Numeric(15, 2), default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    contract = db.relationship("RentalContract", backref="renewals")
    financial_year = db.relationship("FinancialYear", backref="rental_renewals")

    def to_dict(self):
        c = self.contract
        unit_code = c.unit.unit_code if c and c.unit else None
        customer_name = c.customer.full_name if c and c.customer else None
        return {
            "id": self.id,
            "renewal_number": self.renewal_number,
            "contract_id": self.contract_id,
            "contract_number": c.contract_number if c else None,
            "unit_code": unit_code,
            "customer_name": customer_name,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "previous_end_date": self.previous_end_date.isoformat() if self.previous_end_date else None,
            "new_end_date": self.new_end_date.isoformat() if self.new_end_date else None,
            "previous_monthly_rent": float(self.previous_monthly_rent or 0),
            "new_monthly_rent": float(self.new_monthly_rent or 0),
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RentalPayment(db.Model):
    """تحصيل إيجار (دفعة مستلمة مقابل عقد إيجار)."""
    __tablename__ = "rental_payments"

    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(50), unique=True, nullable=False)
    contract_id = db.Column(db.Integer, db.ForeignKey("rental_contracts.id"))
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"))
    amount = db.Column(db.Numeric(15, 2), default=0)
    payment_date = db.Column(db.Date)
    method = db.Column(db.String(30), default="cash")  # cash | bank | transfer
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    contract = db.relationship("RentalContract", backref="payments")
    financial_year = db.relationship("FinancialYear", backref="rental_payments")

    def to_dict(self):
        c = self.contract
        unit_code = c.unit.unit_code if c and c.unit else None
        customer_name = c.customer.full_name if c and c.customer else None
        return {
            "id": self.id,
            "payment_number": self.payment_number,
            "contract_id": self.contract_id,
            "contract_number": c.contract_number if c else None,
            "unit_code": unit_code,
            "customer_name": customer_name,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "amount": float(self.amount or 0),
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "method": self.method or "cash",
            "reference": self.reference,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

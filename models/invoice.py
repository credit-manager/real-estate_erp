from database import db


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_type = db.Column(db.String(30), default="sales")  # sales | purchase | expense
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), index=True)
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"), index=True)
    amount = db.Column(db.Numeric(15, 2), default=0)
    paid_amount = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(30), default="pending", index=True)  # pending | paid | partial | overdue
    approval_status = db.Column(db.String(20), default="not_required", index=True)  # not_required | pending | approved | rejected
    issue_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    description = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="invoices")
    supplier = db.relationship("Supplier", backref="invoices")
    project = db.relationship("Project", backref="invoices")
    financial_year = db.relationship("FinancialYear", backref="invoices")
    items = db.relationship(
        "InvoiceItem", backref="invoice", cascade="all, delete-orphan",
        order_by="InvoiceItem.id",
    )

    def items_total(self):
        if not self.items:
            return None
        return sum((float(i.quantity or 0) * float(i.unit_price or 0)
                    * (1 + float(i.tax_rate or 0) / 100)) for i in self.items)

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
            "invoice_number": self.invoice_number,
            "invoice_type": self.invoice_type,
            "customer_id": self.customer_id,
            "supplier_id": self.supplier_id,
            "project_id": self.project_id,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "currency": self._base_currency(),
            "amount": float(self.amount or 0),
            "paid_amount": float(self.paid_amount or 0),
            "balance": float((self.amount or 0) - (self.paid_amount or 0)),
            "status": self.status,
            "approval_status": self.approval_status or "not_required",
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=1)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    expiry_date = db.Column(db.Date)

    def to_dict(self):
        subtotal = float(self.quantity or 0) * float(self.unit_price or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "item_id": self.item_id,
            "warehouse_id": self.warehouse_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "tax_rate": float(self.tax_rate or 0),
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "total": round(subtotal + tax, 2),
        }

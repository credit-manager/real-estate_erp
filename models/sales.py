from database import db


class SalesOrder(db.Model):
    """أوامر البيع."""
    __tablename__ = "sales_orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    salesperson_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("crm_quotes.id"), index=True)
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"), index=True)
    order_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | confirmed | delivered | completed | cancelled
    approval_status = db.Column(db.String(20), default="not_required", index=True)  # not_required | pending | approved | rejected
    amount = db.Column(db.Numeric(15, 2), default=0)
    paid_amount = db.Column(db.Numeric(15, 2), default=0)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)  # soft-delete
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="sales_orders")
    salesperson = db.relationship("Employee", backref="sales_orders")
    quote = db.relationship("Quote", backref="sales_orders")
    financial_year = db.relationship("FinancialYear", backref="sales_orders")
    items = db.relationship(
        "SalesOrderItem", backref="order", cascade="all, delete-orphan",
        order_by="SalesOrderItem.id",
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
            "order_number": self.order_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "salesperson_id": self.salesperson_id,
            "salesperson_name": self.salesperson.full_name if self.salesperson else None,
            "quote_id": self.quote_id,
            "quote_number": self.quote.quote_number if self.quote else None,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "currency": self._base_currency(),
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "approval_status": self.approval_status or "not_required",
            "amount": float(self.amount or 0),
            "paid_amount": float(self.paid_amount or 0),
            "balance": float((self.amount or 0) - (self.paid_amount or 0)),
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class SalesOrderItem(db.Model):
    """بنود أوامر البيع."""
    __tablename__ = "sales_order_items"

    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey("sales_orders.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=1)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)

    def to_dict(self):
        subtotal = float(self.quantity or 0) * float(self.unit_price or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return {
            "id": self.id,
            "sales_order_id": self.sales_order_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "tax_rate": float(self.tax_rate or 0),
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "total": round(subtotal + tax, 2),
        }


class SalesReturn(db.Model):
    """مرتجعات المبيعات."""
    __tablename__ = "sales_returns"

    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"), index=True)
    return_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | processed | completed | rejected
    approval_status = db.Column(db.String(20), default="not_required", index=True)
    amount = db.Column(db.Numeric(15, 2), default=0)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    invoice = db.relationship("Invoice", backref="sales_returns")
    customer = db.relationship("Customer", backref="sales_returns")
    financial_year = db.relationship("FinancialYear", backref="sales_returns")
    items = db.relationship(
        "SalesReturnItem", backref="return_", cascade="all, delete-orphan",
        order_by="SalesReturnItem.id",
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
            "return_number": self.return_number,
            "invoice_id": self.invoice_id,
            "invoice_number": self.invoice.invoice_number if self.invoice else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "currency": self._base_currency(),
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "status": self.status,
            "approval_status": self.approval_status or "not_required",
            "amount": float(self.amount or 0),
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class SalesReturnItem(db.Model):
    """بنود مرتجعات المبيعات."""
    __tablename__ = "sales_return_items"

    id = db.Column(db.Integer, primary_key=True)
    sales_return_id = db.Column(db.Integer, db.ForeignKey("sales_returns.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=1)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    reason = db.Column(db.String(300))

    def to_dict(self):
        subtotal = float(self.quantity or 0) * float(self.unit_price or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return {
            "id": self.id,
            "sales_return_id": self.sales_return_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "tax_rate": float(self.tax_rate or 0),
            "reason": self.reason,
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "total": round(subtotal + tax, 2),
        }


class SalesCommission(db.Model):
    """عمولات المبيعات للمندوبين على أوامر/فواتير البيع."""
    __tablename__ = "sales_commissions"

    id = db.Column(db.Integer, primary_key=True)
    salesperson_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("sales_orders.id"), index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), index=True)
    commission_date = db.Column(db.Date)
    amount = db.Column(db.Numeric(15, 2), default=0)
    rate = db.Column(db.Numeric(5, 2), default=0)
    status = db.Column(db.String(20), default="pending", index=True)  # pending | approved | paid | cancelled
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    salesperson = db.relationship("Employee", backref="sales_commissions")
    order = db.relationship("SalesOrder", backref="commissions")
    invoice = db.relationship("Invoice", backref="sales_commissions")

    def to_dict(self):
        return {
            "id": self.id,
            "salesperson_id": self.salesperson_id,
            "salesperson_name": self.salesperson.full_name if self.salesperson else None,
            "order_id": self.order_id,
            "order_number": self.order.order_number if self.order else None,
            "invoice_id": self.invoice_id,
            "invoice_number": self.invoice.invoice_number if self.invoice else None,
            "commission_date": self.commission_date.isoformat() if self.commission_date else None,
            "amount": float(self.amount or 0),
            "rate": float(self.rate or 0),
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

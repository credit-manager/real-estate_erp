from database import db


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), index=True)
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"), index=True)
    items_description = db.Column(db.Text)
    total = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(30), default="pending", index=True)  # pending | approved | delivered | cancelled
    approval_status = db.Column(db.String(20), default="not_required", index=True)  # not_required | pending | approved | rejected
    order_date = db.Column(db.Date)
    delivery_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    supplier = db.relationship("Supplier", backref="purchase_orders")
    project = db.relationship("Project", backref="purchase_orders")
    financial_year = db.relationship("FinancialYear", backref="purchase_orders")
    items = db.relationship(
        "PurchaseOrderItem", backref="purchase_order", cascade="all, delete-orphan",
        order_by="PurchaseOrderItem.id",
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
            "po_number": self.po_number,
            "supplier_id": self.supplier_id,
            "project_id": self.project_id,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "currency": self._base_currency(),
            "items_description": self.items_description,
            "total": float(self.total or 0),
            "status": self.status,
            "approval_status": self.approval_status or "not_required",
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "delivery_date": self.delivery_date.isoformat() if self.delivery_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=1)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)

    def to_dict(self):
        subtotal = float(self.quantity or 0) * float(self.unit_price or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return {
            "id": self.id,
            "purchase_order_id": self.purchase_order_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "tax_rate": float(self.tax_rate or 0),
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "total": round(subtotal + tax, 2),
        }

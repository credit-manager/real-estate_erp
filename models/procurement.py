from database import db


class PurchaseRequest(db.Model):
    """طلب شراء."""
    __tablename__ = "purchase_requests"

    id = db.Column(db.Integer, primary_key=True)
    pr_number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200))
    requester = db.Column(db.String(120))
    department = db.Column(db.String(120))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), index=True)
    request_date = db.Column(db.Date)
    needed_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    total = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | submitted | approved | rejected
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    project = db.relationship("Project", backref="purchase_requests")
    items = db.relationship(
        "PurchaseRequestItem", backref="purchase_request", cascade="all, delete-orphan",
        order_by="PurchaseRequestItem.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "pr_number": self.pr_number,
            "title": self.title,
            "requester": self.requester,
            "department": self.department,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "request_date": self.request_date.isoformat() if self.request_date else None,
            "needed_date": self.needed_date.isoformat() if self.needed_date else None,
            "notes": self.notes,
            "total": float(self.total or 0),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class PurchaseRequestItem(db.Model):
    __tablename__ = "purchase_request_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey("purchase_requests.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=1)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)

    def to_dict(self):
        subtotal = float(self.quantity or 0) * float(self.unit_price or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return {
            "id": self.id,
            "purchase_request_id": self.purchase_request_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "tax_rate": float(self.tax_rate or 0),
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "total": round(subtotal + tax, 2),
        }


class RFQ(db.Model):
    """طلب عروض أسعار."""
    __tablename__ = "rfqs"

    id = db.Column(db.Integer, primary_key=True)
    rfq_number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), index=True)
    request_date = db.Column(db.Date)
    deadline = db.Column(db.Date)
    notes = db.Column(db.Text)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | sent | closed
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    project = db.relationship("Project", backref="rfqs")
    items = db.relationship(
        "RFQItem", backref="rfq", cascade="all, delete-orphan",
        order_by="RFQItem.id",
    )
    quotes = db.relationship(
        "RFQQuote", backref="rfq", cascade="all, delete-orphan",
        order_by="RFQQuote.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "rfq_number": self.rfq_number,
            "title": self.title,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "request_date": self.request_date.isoformat() if self.request_date else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "notes": self.notes,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
            "quotes_count": len(self.quotes),
        }


class RFQItem(db.Model):
    __tablename__ = "rfq_items"

    id = db.Column(db.Integer, primary_key=True)
    rfq_id = db.Column(db.Integer, db.ForeignKey("rfqs.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=1)

    def to_dict(self):
        return {
            "id": self.id,
            "rfq_id": self.rfq_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
        }


class RFQQuote(db.Model):
    """عرض مورد على طلب عروض أسعار."""
    __tablename__ = "rfq_quotes"

    id = db.Column(db.Integer, primary_key=True)
    rfq_id = db.Column(db.Integer, db.ForeignKey("rfqs.id"), index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), index=True)
    delivery_days = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    is_winner = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    supplier = db.relationship("Supplier", backref="rfq_quotes")
    items = db.relationship(
        "RFQQuoteItem", backref="quote", cascade="all, delete-orphan",
        order_by="RFQQuoteItem.id",
    )

    def total(self):
        return sum((float(i.unit_price or 0) * float(i.quantity or 0)
                    * (1 + float(i.tax_rate or 0) / 100)) for i in self.items)

    def to_dict(self):
        return {
            "id": self.id,
            "rfq_id": self.rfq_id,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.company_name if self.supplier else None,
            "delivery_days": self.delivery_days or 0,
            "notes": self.notes,
            "is_winner": bool(self.is_winner),
            "total": round(self.total(), 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class RFQQuoteItem(db.Model):
    __tablename__ = "rfq_quote_items"

    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("rfq_quotes.id"), index=True)
    rfq_item_id = db.Column(db.Integer, db.ForeignKey("rfq_items.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=1)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)

    def to_dict(self):
        subtotal = float(self.quantity or 0) * float(self.unit_price or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return {
            "id": self.id,
            "quote_id": self.quote_id,
            "rfq_item_id": self.rfq_item_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "tax_rate": float(self.tax_rate or 0),
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "total": round(subtotal + tax, 2),
        }


class PurchaseReceiving(db.Model):
    """استلام لأمر شراء."""
    __tablename__ = "purchase_receivings"

    id = db.Column(db.Integer, primary_key=True)
    receiving_number = db.Column(db.String(50), unique=True, nullable=False)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), index=True)
    received_date = db.Column(db.Date)
    warehouse = db.Column(db.String(120))
    notes = db.Column(db.Text)
    status = db.Column(db.String(30), default="received", index=True)  # received | returned
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    po = db.relationship("PurchaseOrder", backref="receivings")
    items = db.relationship(
        "PurchaseReceivingItem", backref="receiving", cascade="all, delete-orphan",
        order_by="PurchaseReceivingItem.id",
    )

    def total(self):
        return sum((float(i.quantity or 0) * float(i.unit_price or 0)
                    * (1 + float(i.tax_rate or 0) / 100)) for i in self.items)

    def to_dict(self):
        return {
            "id": self.id,
            "receiving_number": self.receiving_number,
            "po_id": self.po_id,
            "po_number": self.po.po_number if self.po else None,
            "supplier_id": self.po.supplier_id if self.po else None,
            "supplier_name": self.po.supplier.company_name if self.po and self.po.supplier else None,
            "received_date": self.received_date.isoformat() if self.received_date else None,
            "warehouse": self.warehouse,
            "notes": self.notes,
            "status": self.status,
            "total": round(self.total(), 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class PurchaseReceivingItem(db.Model):
    __tablename__ = "purchase_receiving_items"

    id = db.Column(db.Integer, primary_key=True)
    receiving_id = db.Column(db.Integer, db.ForeignKey("purchase_receivings.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=0)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)

    def to_dict(self):
        subtotal = float(self.quantity or 0) * float(self.unit_price or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return {
            "id": self.id,
            "receiving_id": self.receiving_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "tax_rate": float(self.tax_rate or 0),
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "total": round(subtotal + tax, 2),
        }


class PurchaseReturn(db.Model):
    """مرتجع شراء."""
    __tablename__ = "purchase_returns"

    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(50), unique=True, nullable=False)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), index=True)
    return_date = db.Column(db.Date)
    reason = db.Column(db.Text)
    total = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | processed | completed | rejected
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    po = db.relationship("PurchaseOrder", backref="returns")
    supplier = db.relationship("Supplier", backref="purchase_returns")
    items = db.relationship(
        "PurchaseReturnItem", backref="return_doc", cascade="all, delete-orphan",
        order_by="PurchaseReturnItem.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "return_number": self.return_number,
            "po_id": self.po_id,
            "po_number": self.po.po_number if self.po else None,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.company_name if self.supplier else None,
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "reason": self.reason,
            "total": float(self.total or 0),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class PurchaseReturnItem(db.Model):
    __tablename__ = "purchase_return_items"

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey("purchase_returns.id"), index=True)
    description = db.Column(db.String(300))
    quantity = db.Column(db.Numeric(12, 2), default=0)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)

    def to_dict(self):
        subtotal = float(self.quantity or 0) * float(self.unit_price or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return {
            "id": self.id,
            "return_id": self.return_id,
            "description": self.description,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "tax_rate": float(self.tax_rate or 0),
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "total": round(subtotal + tax, 2),
        }

from database import db


class Warehouse(db.Model):
    """مخزن."""
    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(200))
    manager_name = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "location": self.location,
            "manager_name": self.manager_name,
            "phone": self.phone,
            "notes": self.notes,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ItemCategory(db.Model):
    """تصنيف أصناف."""
    __tablename__ = "item_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    items = db.relationship("Item", back_populates="category")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items_count": len(self.items),
        }


class UnitOfMeasure(db.Model):
    """وحدة قياس."""
    __tablename__ = "units_of_measure"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    code = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    items = db.relationship("Item", back_populates="unit")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items_count": len(self.items),
        }


class Item(db.Model):
    """صنف."""
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("item_categories.id"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units_of_measure.id"), index=True)
    barcode = db.Column(db.String(80))
    description = db.Column(db.Text)
    cost_price = db.Column(db.Numeric(15, 2), default=0)
    sale_price = db.Column(db.Numeric(15, 2), default=0)
    reorder_level = db.Column(db.Numeric(15, 2), default=0)  # حد الطلب
    track_batch = db.Column(db.Boolean, default=False)
    track_serial = db.Column(db.Boolean, default=False)
    track_expiry = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    category = db.relationship("ItemCategory", back_populates="items", foreign_keys=[category_id])
    unit = db.relationship("UnitOfMeasure", back_populates="items", foreign_keys=[unit_id])
    stocks = db.relationship("ItemStock", backref="item", cascade="all, delete-orphan")

    def to_dict(self):
        total_qty = sum(float(s.quantity or 0) for s in self.stocks)
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "unit_id": self.unit_id,
            "unit_name": self.unit.name if self.unit else None,
            "barcode": self.barcode,
            "description": self.description,
            "cost_price": float(self.cost_price or 0),
            "sale_price": float(self.sale_price or 0),
            "reorder_level": float(self.reorder_level or 0),
            "track_batch": bool(self.track_batch),
            "track_serial": bool(self.track_serial),
            "track_expiry": bool(self.track_expiry),
            "is_active": bool(self.is_active),
            "quantity": round(total_qty, 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ItemStock(db.Model):
    """رصيد صنف داخل مخزن."""
    __tablename__ = "item_stocks"
    __table_args__ = (db.UniqueConstraint("item_id", "warehouse_id", name="uq_item_warehouse"),)

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    quantity = db.Column(db.Numeric(15, 2), default=0)
    avg_cost = db.Column(db.Numeric(15, 2), default=0)
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    warehouse = db.relationship("Warehouse", backref="stocks")

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "warehouse_id": self.warehouse_id,
            "warehouse_name": self.warehouse.name if self.warehouse else None,
            "quantity": float(self.quantity or 0),
            "avg_cost": float(self.avg_cost or 0),
        }


class StockBatch(db.Model):
    """دفعة (Batch) صنف داخل مخزن."""
    __tablename__ = "stock_batches"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    batch_number = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Numeric(15, 2), default=0)
    expiry_date = db.Column(db.Date)  # صلاحية المنتج
    received_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    item = db.relationship("Item", backref="batches")
    warehouse = db.relationship("Warehouse", backref="batches")

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "item_code": self.item.code if self.item else None,
            "item_name": self.item.name if self.item else None,
            "warehouse_id": self.warehouse_id,
            "warehouse_name": self.warehouse.name if self.warehouse else None,
            "batch_number": self.batch_number,
            "quantity": float(self.quantity or 0),
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "received_date": self.received_date.isoformat() if self.received_date else None,
            "is_expired": bool(self.expiry_date and self.expiry_date < __import__("datetime").date.today()),
        }


class StockSerial(db.Model):
    """رقم تسلسلي (Serial) لصنف."""
    __tablename__ = "stock_serials"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("stock_batches.id"), index=True)
    serial_number = db.Column(db.String(120), unique=True, nullable=False)
    status = db.Column(db.String(20), default="in_stock", index=True)  # in_stock | sold | scrapped
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    item = db.relationship("Item", backref="serials")
    warehouse = db.relationship("Warehouse", backref="serials")
    batch = db.relationship("StockBatch", backref="serials")

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "item_code": self.item.code if self.item else None,
            "item_name": self.item.name if self.item else None,
            "warehouse_id": self.warehouse_id,
            "warehouse_name": self.warehouse.name if self.warehouse else None,
            "batch_id": self.batch_id,
            "batch_number": self.batch.batch_number if self.batch else None,
            "serial_number": self.serial_number,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StockTransfer(db.Model):
    """تحويل أصناف بين المخازن."""
    __tablename__ = "stock_transfers"

    id = db.Column(db.Integer, primary_key=True)
    transfer_number = db.Column(db.String(50), unique=True, nullable=False)
    from_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    to_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    transfer_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="draft", index=True)  # draft | posted
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    from_warehouse = db.relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse = db.relationship("Warehouse", foreign_keys=[to_warehouse_id])
    items = db.relationship(
        "StockTransferItem", backref="transfer", cascade="all, delete-orphan",
        order_by="StockTransferItem.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "transfer_number": self.transfer_number,
            "from_warehouse_id": self.from_warehouse_id,
            "from_warehouse_name": self.from_warehouse.name if self.from_warehouse else None,
            "to_warehouse_id": self.to_warehouse_id,
            "to_warehouse_name": self.to_warehouse.name if self.to_warehouse else None,
            "transfer_date": self.transfer_date.isoformat() if self.transfer_date else None,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class StockTransferItem(db.Model):
    __tablename__ = "stock_transfer_items"

    id = db.Column(db.Integer, primary_key=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("stock_transfers.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(15, 2), default=0)
    batch_id = db.Column(db.Integer, db.ForeignKey("stock_batches.id"), index=True)

    item = db.relationship("Item", backref="transfer_items")
    batch = db.relationship("StockBatch", backref="transfer_items")

    def to_dict(self):
        return {
            "id": self.id,
            "transfer_id": self.transfer_id,
            "item_id": self.item_id,
            "item_code": self.item.code if self.item else None,
            "item_name": self.item.name if self.item else None,
            "quantity": float(self.quantity or 0),
            "batch_id": self.batch_id,
            "batch_number": self.batch.batch_number if self.batch else None,
        }


class StockTake(db.Model):
    """جرد مخزني."""
    __tablename__ = "stock_takes"

    id = db.Column(db.Integer, primary_key=True)
    take_number = db.Column(db.String(50), unique=True, nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    take_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="draft", index=True)  # draft | completed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    warehouse = db.relationship("Warehouse", backref="stock_takes")
    items = db.relationship(
        "StockTakeItem", backref="take", cascade="all, delete-orphan",
        order_by="StockTakeItem.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "take_number": self.take_number,
            "warehouse_id": self.warehouse_id,
            "warehouse_name": self.warehouse.name if self.warehouse else None,
            "take_date": self.take_date.isoformat() if self.take_date else None,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class StockTakeItem(db.Model):
    __tablename__ = "stock_take_items"

    id = db.Column(db.Integer, primary_key=True)
    take_id = db.Column(db.Integer, db.ForeignKey("stock_takes.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    system_qty = db.Column(db.Numeric(15, 2), default=0)
    counted_qty = db.Column(db.Numeric(15, 2), default=0)
    diff_qty = db.Column(db.Numeric(15, 2), default=0)
    notes = db.Column(db.String(300))

    item = db.relationship("Item", backref="stocktake_items")

    def to_dict(self):
        return {
            "id": self.id,
            "take_id": self.take_id,
            "item_id": self.item_id,
            "item_code": self.item.code if self.item else None,
            "item_name": self.item.name if self.item else None,
            "system_qty": float(self.system_qty or 0),
            "counted_qty": float(self.counted_qty or 0),
            "diff_qty": float(self.diff_qty or 0),
            "notes": self.notes,
        }


class StockMovement(db.Model):
    """حركة مخزنية (صادر/وارد/تحويل/تسوية)."""
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    movement_type = db.Column(db.String(30), default="in")  # in | out | transfer_in | transfer_out | adjust | stocktake | sale | purchase
    quantity = db.Column(db.Numeric(15, 2), default=0)
    batch_id = db.Column(db.Integer, db.ForeignKey("stock_batches.id"), index=True)
    reference_type = db.Column(db.String(40))
    reference_id = db.Column(db.Integer, index=True)
    notes = db.Column(db.String(300))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    item = db.relationship("Item", backref="movements")
    warehouse = db.relationship("Warehouse", backref="movements")
    batch = db.relationship("StockBatch", backref="movements")
    user = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "item_code": self.item.code if self.item else None,
            "item_name": self.item.name if self.item else None,
            "warehouse_id": self.warehouse_id,
            "warehouse_name": self.warehouse.name if self.warehouse else None,
            "movement_type": self.movement_type,
            "quantity": float(self.quantity or 0),
            "batch_id": self.batch_id,
            "batch_number": self.batch.batch_number if self.batch else None,
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
            "notes": self.notes,
            "created_by": self.created_by,
            "created_by_name": self.user.full_name if self.user else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

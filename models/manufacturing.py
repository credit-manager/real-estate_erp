from database import db


class WorkCenter(db.Model):
    """مركز عمل / خط إنتاج (التشغيل)."""
    __tablename__ = "work_centers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    wc_type = db.Column(db.String(20), default="machine")  # machine | labor | line
    hourly_cost = db.Column(db.Numeric(12, 2), default=0)
    capacity = db.Column(db.Numeric(12, 2), default=0)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    operations = db.relationship("ProductionOperation", backref="work_center")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "wc_type": self.wc_type,
            "hourly_cost": float(self.hourly_cost or 0),
            "capacity": float(self.capacity or 0),
            "is_active": bool(self.is_active),
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RawMaterial(db.Model):
    """مادة خام (ربط صنف مخزني بإعدادات التصنيع)."""
    __tablename__ = "raw_materials"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, unique=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))
    standard_cost = db.Column(db.Numeric(12, 2), default=0)
    reorder_level = db.Column(db.Numeric(15, 2), default=0)
    min_stock = db.Column(db.Numeric(15, 2), default=0)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    item = db.relationship("Item", foreign_keys=[item_id])
    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])

    def to_dict(self):
        total_qty = sum(float(s.quantity or 0) for s in self.item.stocks) if self.item else 0
        return {
            "id": self.id,
            "item_id": self.item_id,
            "item_code": self.item.code if self.item else None,
            "item_name": self.item.name if self.item else None,
            "unit_name": self.item.unit.name if self.item and self.item.unit else None,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.company_name if self.supplier else None,
            "standard_cost": float(self.standard_cost or 0),
            "reorder_level": float(self.reorder_level or 0),
            "min_stock": float(self.min_stock or 0),
            "is_active": bool(self.is_active),
            "notes": self.notes,
            "quantity": round(total_qty, 2),
            "is_low": bool(self.reorder_level and float(self.reorder_level) > 0 and total_qty <= float(self.reorder_level)),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Bom(db.Model):
    """قائمة مكونات (Bill of Materials)."""
    __tablename__ = "boms"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    product_item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    version = db.Column(db.String(20), default="1.0")
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    product_item = db.relationship("Item", foreign_keys=[product_item_id])
    lines = db.relationship(
        "BomLine", backref="bom", cascade="all, delete-orphan",
        order_by="BomLine.id",
    )

    def to_dict(self):
        total_cost = 0.0
        lines = []
        for ln in self.lines:
            d = ln.to_dict()
            total_cost += d.get("line_cost", 0)
            lines.append(d)
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "product_item_id": self.product_item_id,
            "product_code": self.product_item.code if self.product_item else None,
            "product_name": self.product_item.name if self.product_item else None,
            "version": self.version,
            "is_active": bool(self.is_active),
            "notes": self.notes,
            "lines": lines,
            "total_cost": round(total_cost, 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BomLine(db.Model):
    """سطر مكوّن داخل BOM."""
    __tablename__ = "bom_lines"

    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey("boms.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(15, 4), default=1)
    cost_estimate = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.String(300))

    item = db.relationship("Item", foreign_keys=[item_id])

    def to_dict(self):
        qty = float(self.quantity or 0)
        cost = float(self.cost_estimate or 0) if (self.cost_estimate or 0) > 0 else float(self.item.cost_price or 0) if self.item else 0
        return {
            "id": self.id,
            "bom_id": self.bom_id,
            "item_id": self.item_id,
            "item_code": self.item.code if self.item else None,
            "item_name": self.item.name if self.item else None,
            "unit_name": self.item.unit.name if self.item and self.item.unit else None,
            "quantity": qty,
            "cost_estimate": round(cost, 2),
            "line_cost": round(qty * cost, 2),
            "notes": self.notes,
        }


class ProductionOrder(db.Model):
    """أمر إنتاج."""
    __tablename__ = "production_orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    bom_id = db.Column(db.Integer, db.ForeignKey("boms.id"), nullable=False, index=True)
    product_item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(15, 2), default=0)
    produced_qty = db.Column(db.Numeric(15, 2), default=0)
    start_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    completed_at = db.Column(db.Date)
    status = db.Column(db.String(20), default="planned", index=True)  # planned | in_progress | completed | cancelled
    labor_cost = db.Column(db.Numeric(12, 2), default=0)
    overhead_cost = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    bom = db.relationship("Bom", foreign_keys=[bom_id])
    product_item = db.relationship("Item", foreign_keys=[product_item_id])
    warehouse = db.relationship("Warehouse", foreign_keys=[warehouse_id])
    operations = db.relationship(
        "ProductionOperation", backref="order", cascade="all, delete-orphan",
        order_by="ProductionOperation.id",
    )
    inspections = db.relationship(
        "QualityInspection", backref="order", cascade="all, delete-orphan",
        order_by="QualityInspection.id",
    )

    def progress(self):
        total = len(self.operations)
        done = sum(1 for o in self.operations if o.status == "completed")
        if self.status == "completed":
            return 100
        if self.status == "cancelled":
            return 0
        if total:
            return round(done * 100 / total, 0)
        qty = float(self.quantity or 0)
        if qty > 0:
            return round(min(100, float(self.produced_qty or 0) * 100 / qty), 0)
        return 0

    def material_estimate(self):
        total = 0.0
        for ln in self.bom.lines:
            total += float(ln.quantity or 0) * float(ln.to_dict().get("cost_estimate") or 0)
        return round(total * float(self.quantity or 0), 2)

    def to_dict(self):
        ops = [o.to_dict() for o in self.operations]
        insp = [i.to_dict() for i in self.inspections]
        op_cost = round(sum(o.get("operation_cost", 0) for o in ops), 2)
        material_est = self.material_estimate()
        return {
            "id": self.id,
            "order_number": self.order_number,
            "bom_id": self.bom_id,
            "bom_name": self.bom.name if self.bom else None,
            "product_item_id": self.product_item_id,
            "product_code": self.product_item.code if self.product_item else None,
            "product_name": self.product_item.name if self.product_item else None,
            "warehouse_id": self.warehouse_id,
            "warehouse_name": self.warehouse.name if self.warehouse else None,
            "quantity": float(self.quantity or 0),
            "produced_qty": float(self.produced_qty or 0),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "labor_cost": float(self.labor_cost or 0),
            "overhead_cost": float(self.overhead_cost or 0),
            "notes": self.notes,
            "progress": self.progress(),
            "material_cost_est": material_est,
            "operation_cost": op_cost,
            "total_cost": round(material_est + op_cost + float(self.overhead_cost or 0) + float(self.labor_cost or 0), 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "operations": ops,
            "inspections": insp,
        }


class ProductionOperation(db.Model):
    """عملية تصنيع على أمر إنتاج."""
    __tablename__ = "production_operations"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False, index=True)
    work_center_id = db.Column(db.Integer, db.ForeignKey("work_centers.id"), index=True)
    name = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    planned_hours = db.Column(db.Numeric(10, 2), default=0)
    actual_hours = db.Column(db.Numeric(10, 2), default=0)
    labor_cost = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(20), default="pending", index=True)  # pending | in_progress | completed
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    def to_dict(self):
        hours = float(self.actual_hours or 0)
        rate = float(self.work_center.hourly_cost or 0) if self.work_center else 0
        op_cost = round(hours * rate + float(self.labor_cost or 0), 2)
        return {
            "id": self.id,
            "order_id": self.order_id,
            "work_center_id": self.work_center_id,
            "work_center_name": self.work_center.name if self.work_center else None,
            "work_center_code": self.work_center.code if self.work_center else None,
            "name": self.name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "planned_hours": float(self.planned_hours or 0),
            "actual_hours": hours,
            "labor_cost": float(self.labor_cost or 0),
            "operation_cost": op_cost,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class QualityInspection(db.Model):
    """فحص جودة على أمر إنتاج."""
    __tablename__ = "quality_inspections"

    id = db.Column(db.Integer, primary_key=True)
    inspection_number = db.Column(db.String(50), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), index=True)
    inspector = db.Column(db.String(120))
    inspection_date = db.Column(db.Date)
    sample_size = db.Column(db.Numeric(15, 2), default=0)
    passed_qty = db.Column(db.Numeric(15, 2), default=0)
    failed_qty = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default="in_progress", index=True)  # in_progress | passed | failed
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    item = db.relationship("Item", foreign_keys=[item_id])

    def to_dict(self):
        return {
            "id": self.id,
            "inspection_number": self.inspection_number,
            "order_id": self.order_id,
            "order_number": self.order.order_number if self.order else None,
            "product_name": self.order.product_item.name if self.order and self.order.product_item else None,
            "item_id": self.item_id,
            "item_name": self.item.name if self.item else None,
            "inspector": self.inspector,
            "inspection_date": self.inspection_date.isoformat() if self.inspection_date else None,
            "sample_size": float(self.sample_size or 0),
            "passed_qty": float(self.passed_qty or 0),
            "failed_qty": float(self.failed_qty or 0),
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

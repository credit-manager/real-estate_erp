"""إدارة الأصول والمعدات: الأصول، المعدات، الصيانة، الحركة، العهدة، والإهلاك."""
from database import db


class AssetCategory(db.Model):
    """فئة الأصول/المعدات (تصنيف هرمي)."""
    __tablename__ = "asset_categories"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("asset_categories.id"))
    kind = db.Column(db.String(20), default="asset")  # asset | equipment
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    parent = db.relationship("AssetCategory", remote_side=[id], backref="children")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "parent_id": self.parent_id,
            "parent_name": self.parent.name if self.parent else None,
            "kind": self.kind,
            "is_active": bool(self.is_active),
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "asset_count": len(self.assets or []) if self.assets else 0,
        }


class AssetItem(db.Model):
    """بطاقة الأصل/المعدة — تفاصيل كاملة مع الإهلاك والصيانة والحركة والعهدة."""
    __tablename__ = "asset_items"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("asset_categories.id"), index=True)
    kind = db.Column(db.String(20), default="asset")  # asset | equipment
    asset_type = db.Column(db.String(80))  # نوع الأصل (سيارة، حاسوب، آلة...)
    serial_number = db.Column(db.String(100))
    brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    location_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), index=True)
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Numeric(15, 2), default=0)
    cost = db.Column(db.Numeric(15, 2), default=0)
    currency_code = db.Column(db.String(10))
    useful_life_years = db.Column(db.Integer, default=5)
    salvage_value = db.Column(db.Numeric(15, 2), default=0)
    depreciation_method = db.Column(db.String(20), default="straight")  # straight | declining
    monthly_depreciation = db.Column(db.Numeric(15, 2), default=0)
    accumulated_depreciation = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default="active", index=True)  # active | in_maintenance | disposed | retired
    condition = db.Column(db.String(20), default="good")  # new | good | fair | poor
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    expense_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    accumulated_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    warranty_until = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    category = db.relationship("AssetCategory", backref="assets")
    location = db.relationship("Warehouse", foreign_keys=[location_id])
    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])
    assigned_employee = db.relationship("Employee", foreign_keys=[assigned_employee_id])
    asset_account = db.relationship("Account", foreign_keys=[account_id])
    expense_account = db.relationship("Account", foreign_keys=[expense_account_id])
    accumulated_account = db.relationship("Account", foreign_keys=[accumulated_account_id])

    @property
    def net_book_value(self):
        return float(self.cost or 0) - float(self.accumulated_depreciation or 0)

    @property
    def is_equipment(self):
        return self.kind == "equipment"

    @property
    def active_custody(self):
        return AssetCustody.query.filter_by(
            asset_id=self.id, status="active").first()

    def compute_monthly(self):
        base = float(self.cost or 0) - float(self.salvage_value or 0)
        months = max(int(self.useful_life_years or 1) * 12, 1)
        if self.depreciation_method == "straight":
            return round(base / months, 2)
        rate = 2 / months
        return round(self.net_book_value * rate, 2)

    def to_dict(self):
        custody = self.active_custody
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "kind": self.kind,
            "asset_type": self.asset_type,
            "serial_number": self.serial_number,
            "brand": self.brand,
            "model": self.model,
            "location_id": self.location_id,
            "location_name": self.location.name if self.location else None,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.company_name if self.supplier else None,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "purchase_price": float(self.purchase_price or 0),
            "cost": float(self.cost or 0),
            "currency_code": self.currency_code,
            "useful_life_years": self.useful_life_years,
            "salvage_value": float(self.salvage_value or 0),
            "depreciation_method": self.depreciation_method,
            "monthly_depreciation": float(self.monthly_depreciation or 0),
            "accumulated_depreciation": float(self.accumulated_depreciation or 0),
            "net_book_value": self.net_book_value,
            "status": self.status,
            "condition": self.condition,
            "assigned_employee_id": self.assigned_employee_id,
            "assigned_employee_name": self.assigned_employee.full_name if self.assigned_employee else None,
            "account_id": self.account_id,
            "expense_account_id": self.expense_account_id,
            "accumulated_account_id": self.accumulated_account_id,
            "warranty_until": self.warranty_until.isoformat() if self.warranty_until else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "custody_employee_id": custody.employee_id if custody else None,
            "custody_employee_name": custody.employee.full_name if custody and custody.employee else None,
            "maintenance_active": self.status == "in_maintenance",
        }


class AssetMaintenance(db.Model):
    """سجل صيانة الأصول والمعدات."""
    __tablename__ = "asset_maintenance"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset_items.id"), nullable=False, index=True)
    maintenance_date = db.Column(db.Date, nullable=False)
    maintenance_type = db.Column(db.String(20), default="preventive")  # preventive | corrective | emergency
    cost = db.Column(db.Numeric(15, 2), default=0)
    vendor = db.Column(db.String(150))
    technician = db.Column(db.String(150))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="completed", index=True)  # scheduled | in_progress | completed | cancelled
    next_maintenance_date = db.Column(db.Date)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    asset = db.relationship("AssetItem", backref="maintenances")
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "asset_code": self.asset.code if self.asset else None,
            "asset_name": self.asset.name if self.asset else None,
            "maintenance_date": self.maintenance_date.isoformat() if self.maintenance_date else None,
            "maintenance_type": self.maintenance_type,
            "cost": float(self.cost or 0),
            "vendor": self.vendor,
            "technician": self.technician,
            "description": self.description,
            "status": self.status,
            "next_maintenance_date": self.next_maintenance_date.isoformat() if self.next_maintenance_date else None,
            "created_by": self.created_by,
            "created_by_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AssetMovement(db.Model):
    """حركة الأصول: استلام، نقل، تسليم، إرجاع، إعدام."""
    __tablename__ = "asset_movements"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset_items.id"), nullable=False, index=True)
    movement_date = db.Column(db.Date, nullable=False)
    movement_type = db.Column(db.String(20), nullable=False)  # received | transferred | returned | disposed
    from_location_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), index=True)
    to_location_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), index=True)
    from_employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    to_employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    asset = db.relationship("AssetItem", backref="movements")
    from_location = db.relationship("Warehouse", foreign_keys=[from_location_id])
    to_location = db.relationship("Warehouse", foreign_keys=[to_location_id])
    from_employee = db.relationship("Employee", foreign_keys=[from_employee_id])
    to_employee = db.relationship("Employee", foreign_keys=[to_employee_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "asset_code": self.asset.code if self.asset else None,
            "asset_name": self.asset.name if self.asset else None,
            "movement_date": self.movement_date.isoformat() if self.movement_date else None,
            "movement_type": self.movement_type,
            "from_location_id": self.from_location_id,
            "from_location_name": self.from_location.name if self.from_location else None,
            "to_location_id": self.to_location_id,
            "to_location_name": self.to_location.name if self.to_location else None,
            "from_employee_id": self.from_employee_id,
            "from_employee_name": self.from_employee.full_name if self.from_employee else None,
            "to_employee_id": self.to_employee_id,
            "to_employee_name": self.to_employee.full_name if self.to_employee else None,
            "reference": self.reference,
            "notes": self.notes,
            "created_by": self.created_by,
            "created_by_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AssetCustody(db.Model):
    """العهدة: تسليم أصل/معدة لموظف."""
    __tablename__ = "asset_custodies"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset_items.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    custody_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="active", index=True)  # active | returned
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    asset = db.relationship("AssetItem", backref="custodies")
    employee = db.relationship("Employee", foreign_keys=[employee_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "asset_code": self.asset.code if self.asset else None,
            "asset_name": self.asset.name if self.asset else None,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "custody_date": self.custody_date.isoformat() if self.custody_date else None,
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "status": self.status,
            "notes": self.notes,
            "created_by": self.created_by,
            "created_by_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
from database import db


class Building(db.Model):
    """المباني — مبنى تابع لمشروع عقاري."""
    __tablename__ = "real_estate_buildings"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    code = db.Column(db.String(50))
    name = db.Column(db.String(150), nullable=False)
    floors_count = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    status = db.Column(db.String(30), default="planning")  # planning | under_construction | completed | operational
    cost = db.Column(db.Numeric(15, 2), default=0)
    cost_center_id = db.Column(db.Integer, db.ForeignKey("cost_centers.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    project = db.relationship("Project", backref="buildings")
    cost_center = db.relationship("CostCenter", backref="buildings")
    floors = db.relationship(
        "Floor", backref="building", cascade="all, delete-orphan",
        order_by="Floor.number")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "code": self.code,
            "name": self.name,
            "floors_count": self.floors_count,
            "description": self.description,
            "status": self.status,
            "cost": float(self.cost or 0),
            "cost_center_id": self.cost_center_id,
            "units_count": len(self.units),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Floor(db.Model):
    """الطوابق — طابق تابع لمبنى."""
    __tablename__ = "real_estate_floors"

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("real_estate_buildings.id"))
    number = db.Column(db.Integer, default=1)
    name = db.Column(db.String(100))
    description = db.Column(db.String(200))
    cost = db.Column(db.Numeric(15, 2), default=0)
    cost_center_id = db.Column(db.Integer, db.ForeignKey("cost_centers.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    cost_center = db.relationship("CostCenter", backref="floors")

    def to_dict(self):
        return {
            "id": self.id,
            "building_id": self.building_id,
            "building_name": self.building.name if self.building else None,
            "number": self.number,
            "name": self.name,
            "description": self.description,
            "cost": float(self.cost or 0),
            "cost_center_id": self.cost_center_id,
            "units_count": len(self.units),
        }


class UnitType(db.Model):
    """أنواع الوحدات — قائمة قابلة للإدارة (شقة، فيلا، محل...)."""
    __tablename__ = "unit_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    name_ar = db.Column(db.String(80))
    code = db.Column(db.String(30))
    is_active = db.Column(db.Boolean, default=True)
    default_price_per_sqm = db.Column(db.Numeric(15, 2), default=0)
    default_rent_per_sqm = db.Column(db.Numeric(15, 2), default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_ar": self.name_ar,
            "code": self.code,
            "is_active": bool(self.is_active),
            "default_price_per_sqm": float(self.default_price_per_sqm or 0),
            "default_rent_per_sqm": float(self.default_rent_per_sqm or 0),
            "units_count": len(self.units),
        }


class Owner(db.Model):
    """الملاك — أصحاب العقارات (فرد/شركة)."""
    __tablename__ = "real_estate_owners"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    id_number = db.Column(db.String(60))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    type = db.Column(db.String(30), default="individual")  # individual | company
    nationality = db.Column(db.String(60))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "id_number": self.id_number,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "type": self.type,
            "nationality": self.nationality,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UnitPriceHistory(db.Model):
    """تسعير الوحدة — سجل تغييرات الأسعار."""
    __tablename__ = "unit_price_history"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    old_price = db.Column(db.Numeric(15, 2), default=0)
    new_price = db.Column(db.Numeric(15, 2), default=0)
    change_date = db.Column(db.Date)
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="price_history")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "old_price": float(self.old_price or 0),
            "new_price": float(self.new_price or 0),
            "change_date": self.change_date.isoformat() if self.change_date else None,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Reservation(db.Model):
    """الحجز — حجز وحدة لعميل (بعربون)."""
    __tablename__ = "unit_reservations"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    reserved_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    deposit = db.Column(db.Numeric(15, 2), default=0)  # العربون
    status = db.Column(db.String(20), default="active")  # active | converted | cancelled | expired
    notes = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="reservations")
    customer = db.relationship("Customer", backref="unit_reservations")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "reserved_date": self.reserved_date.isoformat() if self.reserved_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "deposit": float(self.deposit or 0),
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Allocation(db.Model):
    """التخصيص — تخصيص وحدة لعميل (تعميد)."""
    __tablename__ = "unit_allocations"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    allocated_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="active")  # active | converted | cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="allocations")
    customer = db.relationship("Customer", backref="unit_allocations")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "allocated_date": self.allocated_date.isoformat() if self.allocated_date else None,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Broker(db.Model):
    """السماسرة العقارية — وسطاء خارجيون باتفاقية عمولة (غير الموظفين)."""
    __tablename__ = "real_estate_brokers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    agency_name = db.Column(db.String(150))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    id_number = db.Column(db.String(60))
    default_rate = db.Column(db.Numeric(5, 2), default=0)  # نسبة الاتفاقية %
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "agency_name": self.agency_name,
            "phone": self.phone,
            "email": self.email,
            "id_number": self.id_number,
            "default_rate": float(self.default_rate or 0),
            "is_active": bool(self.is_active),
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SalesContract(db.Model):
    """عقد البيع — عقد بيع وحدة لعملية بيع (مرتبط بخطة الأقساط اختيارياً)."""
    __tablename__ = "sales_contracts"

    id = db.Column(db.Integer, primary_key=True)
    contract_number = db.Column(db.String(50), unique=True, nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    payment_plan_id = db.Column(db.Integer, db.ForeignKey("payment_plans.id"))
    total_amount = db.Column(db.Numeric(15, 2), default=0)
    discount = db.Column(db.Numeric(15, 2), default=0)
    net_amount = db.Column(db.Numeric(15, 2), default=0)
    vat_rate = db.Column(db.Float, default=0)      # نسبة ضريبة القيمة المضافة %
    vat_amount = db.Column(db.Numeric(15, 2), default=0)  # مبلغ الضريبة (على الصافي)
    contract_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="active")  # draft | active | completed | cancelled
    approval_status = db.Column(db.String(20), default="not_required")
    notes = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="sales_contracts")
    customer = db.relationship("Customer", backref="sales_contracts")
    payment_plan = db.relationship("PaymentPlan", backref="sales_contract")

    def _base_currency(self):
        if self.payment_plan and self.payment_plan.financial_year and self.payment_plan.financial_year.company:
            company = self.payment_plan.financial_year.company
            for cur in company.currencies:
                if cur.is_base:
                    return cur.to_dict()
            code = company.currency
            if code:
                return {"code": code, "symbol": code, "name": code}
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "contract_number": self.contract_number,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "payment_plan_id": self.payment_plan_id,
            "total_amount": float(self.total_amount or 0),
            "discount": float(self.discount or 0),
            "net_amount": float(self.net_amount or 0),
            "vat_rate": float(getattr(self, "vat_rate", 0) or 0),
            "vat_amount": float(getattr(self, "vat_amount", 0) or 0),
            "gross_with_vat": round(float(self.net_amount or 0) + float(getattr(self, "vat_amount", 0) or 0), 2),
            "contract_date": self.contract_date.isoformat() if self.contract_date else None,
            "status": self.status,
            "approval_status": self.approval_status or "not_required",
            "currency": self._base_currency(),
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Commission(db.Model):
    """العمولات — عمولات البيع للموظفين على عقود البيع."""
    __tablename__ = "commissions"

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("sales_contracts.id"))
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    broker_id = db.Column(db.Integer, db.ForeignKey("real_estate_brokers.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    rate = db.Column(db.Numeric(5, 2), default=0)  # نسبة %
    amount = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default="pending")  # pending | paid | cancelled
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)
    notes = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    contract = db.relationship("SalesContract", backref="commissions")
    unit = db.relationship("RealEstateUnit", backref="commissions")
    employee = db.relationship("Employee", backref="commissions")
    broker = db.relationship("Broker", backref="commissions")
    customer = db.relationship("Customer", backref="commissions")

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "contract_number": self.contract.contract_number if self.contract else None,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "broker_id": self.broker_id,
            "broker_name": (self.broker.name if self.broker else None),
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "rate": float(self.rate or 0),
            "amount": float(self.amount or 0),
            "status": self.status,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UnitDelivery(db.Model):
    """تسليم الوحدة — سجل تسليم الوحدة للمالك/العميل."""
    __tablename__ = "unit_deliveries"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    delivery_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="pending")  # pending | delivered | delayed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="deliveries")
    customer = db.relationship("Customer", backref="unit_deliveries")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "delivery_date": self.delivery_date.isoformat() if self.delivery_date else None,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MaintenanceRequest(db.Model):
    """الصيانة — طلبات صيانة الوحدات."""
    __tablename__ = "maintenance_requests"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    request_date = db.Column(db.Date)
    issue_type = db.Column(db.String(80))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="open")  # open | in_progress | done | cancelled
    cost = db.Column(db.Numeric(15, 2), default=0)
    assigned_to = db.Column(db.Integer, db.ForeignKey("employees.id"))
    resolved_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="maintenance_requests")
    customer = db.relationship("Customer", backref="maintenance_requests")
    assignee = db.relationship("Employee", backref="maintenance_tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "request_date": self.request_date.isoformat() if self.request_date else None,
            "issue_type": self.issue_type,
            "description": self.description,
            "status": self.status,
            "cost": float(self.cost or 0),
            "assigned_to": self.assigned_to,
            "assignee_name": self.assignee.full_name if self.assignee else None,
            "resolved_date": self.resolved_date.isoformat() if self.resolved_date else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UnitShare(db.Model):
    """الحصص العقارية — تملك الوحدة بحصص لعدة ملاك."""
    __tablename__ = "unit_shares"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("real_estate_owners.id"))
    share_percent = db.Column(db.Numeric(5, 2), default=0)
    notes = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="shares")
    owner = db.relationship("Owner", backref="shares")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "owner_id": self.owner_id,
            "owner_name": self.owner.full_name if self.owner else None,
            "share_percent": float(self.share_percent or 0),
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

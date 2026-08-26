from database import db
from sqlalchemy.orm import relationship


class ProjectPhase(db.Model):
    """مراحل المشروع"""
    __tablename__ = "project_phases"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="not_started", index=True)  # not_started | in_progress | completed | on_hold
    completion = db.Column(db.Integer, default=0)
    budget = db.Column(db.Numeric(15, 2), default=0)

    project = relationship("Project", backref="phases")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "completion": self.completion,
            "budget": float(self.budget or 0),
        }


class WBSItem(db.Model):
    """هيكل تقسيم العمل (WBS) / Breakdown Structure"""
    __tablename__ = "project_wbs_items"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("project_wbs_items.id"), index=True)
    code = db.Column(db.String(50))
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(30), default="work_package")  # phase | package | control_account | work_package
    description = db.Column(db.Text)

    project = relationship("Project", backref="wbs_items")
    children = relationship("WBSItem", backref=db.backref("parent", remote_side=[id]))

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "parent_id": self.parent_id,
            "code": self.code,
            "name": self.name,
            "type": self.type,
            "description": self.description,
        }


class BoqItem(db.Model):
    """بنود الأعمال / BOQ"""
    __tablename__ = "project_boq_items"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    wbs_id = db.Column(db.Integer, db.ForeignKey("project_wbs_items.id"), index=True)
    code = db.Column(db.String(50))
    description = db.Column(db.Text, nullable=False)
    unit = db.Column(db.String(30))
    quantity = db.Column(db.Numeric(15, 3), default=0)
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    category = db.Column(db.String(30), default="other")  # material | labor | equipment | subcontract | other
    status = db.Column(db.String(30), default="pending", index=True)  # pending | approved | rejected
    notes = db.Column(db.Text)

    project = relationship("Project", backref="boq_items")
    wbs = relationship("WBSItem", backref="boq_items")

    @property
    def total(self):
        return float((self.quantity or 0) * (self.unit_price or 0))

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "wbs_id": self.wbs_id,
            "code": self.code,
            "description": self.description,
            "unit": self.unit,
            "quantity": float(self.quantity or 0),
            "unit_price": float(self.unit_price or 0),
            "total": self.total,
            "category": self.category,
            "status": self.status,
            "notes": self.notes,
        }


class PriceAnalysisItem(db.Model):
    """تحليل الأسعار (مكونات بند BOQ)"""
    __tablename__ = "project_price_analysis"

    id = db.Column(db.Integer, primary_key=True)
    boq_id = db.Column(db.Integer, db.ForeignKey("project_boq_items.id"), nullable=False, index=True)
    description = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(30))
    quantity = db.Column(db.Numeric(15, 3), default=0)
    rate = db.Column(db.Numeric(15, 2), default=0)
    cost_type = db.Column(db.String(30), default="material")  # material | labor | equipment | overhead | profit

    boq = relationship("BoqItem", backref="price_analysis")

    @property
    def amount(self):
        return float((self.quantity or 0) * (self.rate or 0))

    def to_dict(self):
        return {
            "id": self.id,
            "boq_id": self.boq_id,
            "description": self.description,
            "unit": self.unit,
            "quantity": float(self.quantity or 0),
            "rate": float(self.rate or 0),
            "amount": self.amount,
            "cost_type": self.cost_type,
        }


class Subcontractor(db.Model):
    """مقاولو الباطن"""
    __tablename__ = "subcontractors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    specialty = db.Column(db.String(100))
    commercial_registration = db.Column(db.String(50))
    rating = db.Column(db.Integer, default=0)  # 1-5
    status = db.Column(db.String(30), default="active")  # active | inactive
    notes = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "specialty": self.specialty,
            "commercial_registration": self.commercial_registration,
            "rating": self.rating,
            "status": self.status,
            "notes": self.notes,
        }


class ProjectContract(db.Model):
    """العقود (عقود رئيسية أو مقاولي باطن)"""
    __tablename__ = "project_contracts"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    contract_no = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    contract_type = db.Column(db.String(30), default="main")  # main | subcontract
    party_name = db.Column(db.String(200))  # الطرف الآخر
    subcontractor_id = db.Column(db.Integer, db.ForeignKey("subcontractors.id"), index=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    contract_value = db.Column(db.Numeric(15, 2), default=0)
    advance_payment = db.Column(db.Numeric(15, 2), default=0)
    retention_pct = db.Column(db.Numeric(5, 2), default=10)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | signed | running | completed | terminated
    description = db.Column(db.Text)

    project = relationship("Project", backref="contracts")
    subcontractor = relationship("Subcontractor", backref="contracts")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "contract_no": self.contract_no,
            "title": self.title,
            "contract_type": self.contract_type,
            "party_name": self.party_name,
            "subcontractor_id": self.subcontractor_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "contract_value": float(self.contract_value or 0),
            "advance_payment": float(self.advance_payment or 0),
            "retention_pct": float(self.retention_pct or 0),
            "status": self.status,
            "description": self.description,
        }


class ProgressStatement(db.Model):
    """المستخلصات (اعتمادات الدفع للمقاول)"""
    __tablename__ = "progress_statements"

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("project_contracts.id"), nullable=False, index=True)
    statement_no = db.Column(db.String(50), nullable=False)
    statement_date = db.Column(db.Date)
    period_from = db.Column(db.Date)
    period_to = db.Column(db.Date)
    work_value = db.Column(db.Numeric(15, 2), default=0)  # أعمال هذا المستخلص
    advance_deduction = db.Column(db.Numeric(15, 2), default=0)  # خصم العهد
    retention_deduction = db.Column(db.Numeric(15, 2), default=0)  # خصم ضمان
    net_value = db.Column(db.Numeric(15, 2), default=0)
    cumulative_total = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | submitted | approved | rejected | paid
    notes = db.Column(db.Text)

    contract = relationship("ProjectContract", backref="statements")

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "statement_no": self.statement_no,
            "statement_date": self.statement_date.isoformat() if self.statement_date else None,
            "period_from": self.period_from.isoformat() if self.period_from else None,
            "period_to": self.period_to.isoformat() if self.period_to else None,
            "work_value": float(self.work_value or 0),
            "advance_deduction": float(self.advance_deduction or 0),
            "retention_deduction": float(self.retention_deduction or 0),
            "net_value": float(self.net_value or 0),
            "cumulative_total": float(self.cumulative_total or 0),
            "status": self.status,
            "notes": self.notes,
        }


class ChangeOrder(db.Model):
    """أوامر التغيير"""
    __tablename__ = "project_change_orders"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("project_contracts.id"), index=True)
    change_no = db.Column(db.String(50))
    description = db.Column(db.Text, nullable=False)
    reason = db.Column(db.String(200))
    change_type = db.Column(db.String(30), default="addition")  # addition | reduction | neutral
    amount = db.Column(db.Numeric(15, 2), default=0)
    change_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="pending", index=True)  # pending | approved | rejected | executed

    project = relationship("Project", backref="change_orders")
    contract = relationship("ProjectContract", backref="change_orders")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "contract_id": self.contract_id,
            "change_no": self.change_no,
            "description": self.description,
            "reason": self.reason,
            "change_type": self.change_type,
            "amount": float(self.amount or 0),
            "change_date": self.change_date.isoformat() if self.change_date else None,
            "status": self.status,
        }


class ProjectProgress(db.Model):
    """سجل نسب الإنجاز"""
    __tablename__ = "project_progress"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    boq_id = db.Column(db.Integer, db.ForeignKey("project_boq_items.id"), index=True)
    record_date = db.Column(db.Date)
    percentage = db.Column(db.Integer, default=0)
    note = db.Column(db.Text)

    project = relationship("Project", backref="progress_records")
    boq = relationship("BoqItem", backref="progress_records")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "boq_id": self.boq_id,
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "percentage": self.percentage,
            "note": self.note,
        }


class ExecutionLog(db.Model):
    """متابعة التنفيذ (سجل أنشطة)"""
    __tablename__ = "project_execution_logs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    log_date = db.Column(db.Date)
    activity = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    responsible = db.Column(db.String(120))
    status = db.Column(db.String(30), default="planned", index=True)  # planned | in_progress | done

    project = relationship("Project", backref="execution_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "log_date": self.log_date.isoformat() if self.log_date else None,
            "activity": self.activity,
            "description": self.description,
            "responsible": self.responsible,
            "status": self.status,
        }


class ProjectCost(db.Model):
    """إدارة التكاليف"""
    __tablename__ = "project_costs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    cost_date = db.Column(db.Date)
    category = db.Column(db.String(50), default="other")  # material | labor | equipment | subcontract | administrative | other
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(15, 2), default=0)
    reference = db.Column(db.String(50))
    notes = db.Column(db.Text)

    project = relationship("Project", backref="costs")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "cost_date": self.cost_date.isoformat() if self.cost_date else None,
            "category": self.category,
            "description": self.description,
            "amount": float(self.amount or 0),
            "reference": self.reference,
            "notes": self.notes,
        }


class ProjectRisk(db.Model):
    """إدارة المخاطر"""
    __tablename__ = "project_risks"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default="other")
    probability = db.Column(db.String(20), default="medium")  # low | medium | high
    impact = db.Column(db.String(20), default="medium")  # low | medium | high
    mitigation = db.Column(db.Text)
    owner = db.Column(db.String(120))
    status = db.Column(db.String(30), default="open", index=True)  # open | mitigated | closed

    project = relationship("Project", backref="risks")

    @property
    def level(self):
        levels = {"low": 1, "medium": 2, "high": 3}
        score = levels.get(self.probability, 2) * levels.get(self.impact, 2)
        if score >= 6:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "description": self.description,
            "category": self.category,
            "probability": self.probability,
            "impact": self.impact,
            "level": self.level,
            "mitigation": self.mitigation,
            "owner": self.owner,
            "status": self.status,
        }


class ProjectQuality(db.Model):
    """إدارة الجودة"""
    __tablename__ = "project_quality"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    check_date = db.Column(db.Date)
    check_type = db.Column(db.String(50), default="inspection")  # inspection | test | audit
    description = db.Column(db.Text, nullable=False)
    result = db.Column(db.String(20), default="pending")  # pass | fail | pending
    inspector = db.Column(db.String(120))
    corrective_action = db.Column(db.Text)
    status = db.Column(db.String(30), default="open", index=True)  # open | closed

    project = relationship("Project", backref="quality_checks")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "check_date": self.check_date.isoformat() if self.check_date else None,
            "check_type": self.check_type,
            "description": self.description,
            "result": self.result,
            "inspector": self.inspector,
            "corrective_action": self.corrective_action,
            "status": self.status,
        }


class SiteLog(db.Model):
    """إدارة المواقع (تقارير يومية)"""
    __tablename__ = "project_site_logs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    log_date = db.Column(db.Date)
    report_type = db.Column(db.String(30), default="daily")  # daily | site | meeting
    weather = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)

    project = relationship("Project", backref="site_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "log_date": self.log_date.isoformat() if self.log_date else None,
            "report_type": self.report_type,
            "weather": self.weather,
            "description": self.description,
            "notes": self.notes,
        }


class Equipment(db.Model):
    """المعدات"""
    __tablename__ = "equipment"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50))
    status = db.Column(db.String(30), default="available", index=True)  # available | in_use | under_maintenance | out_of_service
    location = db.Column(db.String(100))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), index=True)
    daily_cost = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.Text)

    project = relationship("Project", backref="equipment")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "location": self.location,
            "project_id": self.project_id,
            "daily_cost": float(self.daily_cost or 0),
            "notes": self.notes,
        }


class LaborAssignment(db.Model):
    """العمالة (تخصيص عمال للمشروع)"""
    __tablename__ = "labor_assignments"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    name = db.Column(db.String(120))
    trade = db.Column(db.String(80))  # المهنة/الحرفة
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    daily_rate = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(30), default="active", index=True)  # active | completed

    project = relationship("Project", backref="labor_assignments")
    employee = relationship("Employee", backref="labor_assignments")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "employee_id": self.employee_id,
            "name": self.name,
            "trade": self.trade,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "daily_rate": float(self.daily_rate or 0),
            "status": self.status,
        }

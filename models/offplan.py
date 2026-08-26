from database import db


class ConstructionMilestone(db.Model):
    """مراحل الإنجاز الإنشائي — مرتبطة بمشروع (للبيع على الخارطة)."""
    __tablename__ = "construction_milestones"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    target_date = db.Column(db.Date)
    completion_pct = db.Column(db.Numeric(5, 2), default=0)  # 0-100
    status = db.Column(db.String(20), default="pending", index=True)  # pending | in_progress | completed | delayed
    weight = db.Column(db.Numeric(5, 2), default=0)  # وزن المرحلة في الخطة الكلية %
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    project = db.relationship("Project", backref="milestones")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "name": self.name,
            "description": self.description,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "completion_pct": float(self.completion_pct or 0),
            "status": self.status,
            "weight": float(self.weight or 0),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DSPPlan(db.Model):
    """خطة الدفع المجدولة DSP — ربط كل قسط بمرحلة إنجاز (لا يُستحق إلا باكتمالها)."""
    __tablename__ = "dsp_plans"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey("construction_milestones.id"), index=True)
    name = db.Column(db.String(150), nullable=False)
    due_pct = db.Column(db.Numeric(5, 2), nullable=False)  # نسبة من إجمالي العقد %
    amount_formula = db.Column(db.String(50), default="pct")  # pct | fixed
    fixed_amount = db.Column(db.Numeric(15, 2), default=0)  # إن كان fixed
    due_days_after_milestone = db.Column(db.Integer, default=0)  # أيام بعد اكتمال المرحلة
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    project = db.relationship("Project", backref="dsp_plans")
    milestone = db.relationship("ConstructionMilestone", backref="dsp_entries")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "milestone_id": self.milestone_id,
            "milestone_name": self.milestone.name if self.milestone else None,
            "milestone_status": self.milestone.status if self.milestone else None,
            "name": self.name,
            "due_pct": float(self.due_pct or 0),
            "amount_formula": self.amount_formula,
            "fixed_amount": float(self.fixed_amount or 0),
            "due_days_after_milestone": self.due_days_after_milestone,
            "is_active": self.is_active,
            "is_due": self.is_due(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def is_due(self):
        """هل استحقت هذه الدفعة (المرحلة مكتملة)؟"""
        if not self.milestone:
            return True  # بلا مرحلة = مستحقة فوراً
        return self.milestone.status == "completed" or float(self.milestone.completion_pct or 0) >= 100


class TitleDeed(db.Model):
    """سند الملكية — تتبع تسلسل الملكية لكل وحدة."""
    __tablename__ = "title_deeds"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"), nullable=False, index=True)
    deed_number = db.Column(db.String(50), unique=True, nullable=False)
    owner_name = db.Column(db.String(150), nullable=False)
    owner_id_number = db.Column(db.String(30))
    issue_date = db.Column(db.Date)
    area = db.Column(db.Numeric(10, 2))
    deed_type = db.Column(db.String(30), default="freehold")  # freehold | usufruct | leasehold
    status = db.Column(db.String(20), default="active", index=True)  # active | transferred | cancelled
    previous_deed_id = db.Column(db.Integer, db.ForeignKey("title_deeds.id"))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    unit = db.relationship("RealEstateUnit", backref="title_deeds")
    previous_deed = db.relationship("TitleDeed", remote_side=[id], backref="next_deeds")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "deed_number": self.deed_number,
            "owner_name": self.owner_name,
            "owner_id_number": self.owner_id_number,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "area": float(self.area or 0),
            "deed_type": self.deed_type,
            "status": self.status,
            "previous_deed_id": self.previous_deed_id,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

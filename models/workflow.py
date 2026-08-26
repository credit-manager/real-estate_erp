from database import db


class WorkflowTemplate(db.Model):
    __tablename__ = "workflow_templates"

    id = db.Column(db.Integer, primary_key=True)
    doc_type = db.Column(db.String(30), nullable=False)  # invoice | po | rental_contract
    name = db.Column(db.String(120), nullable=False)
    min_amount = db.Column(db.Numeric(15, 2), nullable=True)  # سقف مالي: يُطبَّق عندما >= مبلغ المستند
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    steps = db.relationship(
        "WorkflowStep", backref="template", cascade="all, delete-orphan",
        order_by="WorkflowStep.position")

    def to_dict(self):
        return {
            "id": self.id,
            "doc_type": self.doc_type,
            "name": self.name,
            "is_active": bool(self.is_active),
            "steps": [s.to_dict() for s in self.steps],
        }


class WorkflowStep(db.Model):
    __tablename__ = "workflow_steps"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("workflow_templates.id"))
    position = db.Column(db.Integer, default=1)
    role = db.Column(db.String(60), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "template_id": self.template_id,
            "position": self.position,
            "role": self.role,
        }


class ApprovalRequest(db.Model):
    __tablename__ = "approval_requests"

    id = db.Column(db.Integer, primary_key=True)
    doc_type = db.Column(db.String(30), nullable=False)
    doc_id = db.Column(db.Integer, nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey("workflow_templates.id"))
    status = db.Column(db.String(20), default="pending")  # pending | approved | rejected | cancelled
    current_step = db.Column(db.Integer, default=1)
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    submitted_at = db.Column(db.DateTime, server_default=db.func.now())
    decided_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    decided_at = db.Column(db.DateTime)
    comment = db.Column(db.Text)

    template = db.relationship("WorkflowTemplate")
    submitter = db.relationship("User", foreign_keys=[submitted_by])
    decider = db.relationship("User", foreign_keys=[decided_by])
    steps = db.relationship(
        "ApprovalStepRecord", backref="request", cascade="all, delete-orphan",
        order_by="ApprovalStepRecord.position")

    def document(self):
        from utils.workflow import document_model
        model = document_model(self.doc_type)
        if not model:
            return None
        return db.session.get(model, self.doc_id)

    def current_role(self):
        for s in self.steps:
            if s.position == self.current_step:
                return s.role
        return None

    def to_dict(self):
        from utils.workflow import document_meta
        doc = self.document()
        doc_meta = document_meta(self.doc_type, doc) if doc is not None else {}
        return {
            "id": self.id,
            "doc_type": self.doc_type,
            "doc_id": self.doc_id,
            "template_id": self.template_id,
            "template_name": self.template.name if self.template else None,
            "status": self.status,
            "current_step": self.current_step,
            "current_role": self.current_role(),
            "submitted_by": self.submitted_by,
            "submitted_by_name": self.submitter.full_name if self.submitter else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "decided_by": self.decided_by,
            "decided_by_name": self.decider.full_name if self.decider else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "comment": self.comment,
            "doc": doc_meta,
            "steps": [s.to_dict() for s in self.steps],
        }


class ApprovalStepRecord(db.Model):
    __tablename__ = "approval_step_records"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("approval_requests.id"))
    step_id = db.Column(db.Integer, db.ForeignKey("workflow_steps.id"))
    position = db.Column(db.Integer, default=1)
    role = db.Column(db.String(60))
    status = db.Column(db.String(20), default="pending")  # pending | approved | rejected
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment = db.Column(db.Text)
    decided_at = db.Column(db.DateTime)

    approver = db.relationship("User", foreign_keys=[approver_id])

    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "step_id": self.step_id,
            "position": self.position,
            "role": self.role,
            "status": self.status,
            "approver_id": self.approver_id,
            "approver_name": self.approver.full_name if self.approver else None,
            "comment": self.comment,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }

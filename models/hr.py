from database import db


class Department(db.Model):
    """قسم تنظيمي."""
    __tablename__ = "hr_departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(30))
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    manager = db.relationship("Employee", foreign_keys=[manager_id])

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "manager_id": self.manager_id,
            "manager_name": self.manager.full_name if self.manager else None,
            "description": self.description,
            "is_active": bool(self.is_active),
            "employees_count": len(self.employees) if hasattr(self, "employees") else 0,
        }


class Position(db.Model):
    """مسمى وظيفي."""
    __tablename__ = "hr_positions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(30))
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "is_active": bool(self.is_active),
            "employees_count": len(self.employees) if hasattr(self, "employees") else 0,
        }


class EmploymentContract(db.Model):
    """عقد توظيف."""
    __tablename__ = "hr_contracts"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    contract_number = db.Column(db.String(50))
    contract_type = db.Column(db.String(30), default="full_time")  # full_time | part_time | fixed_term | probation
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    salary = db.Column(db.Numeric(12, 2), default=0)
    working_hours = db.Column(db.Numeric(5, 2), default=8)
    status = db.Column(db.String(30), default="active", index=True)  # active | expired | terminated | pending
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "contract_number": self.contract_number,
            "contract_type": self.contract_type,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "salary": float(self.salary or 0),
            "working_hours": float(self.working_hours or 0),
            "status": self.status,
            "notes": self.notes,
        }


class Recruitment(db.Model):
    """تعيين موظف (استقطاب وتوظيف)."""
    __tablename__ = "hr_recruitments"

    id = db.Column(db.Integer, primary_key=True)
    candidate_name = db.Column(db.String(120), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey("hr_positions.id"), index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("hr_departments.id"), index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    application_date = db.Column(db.Date)
    hire_date = db.Column(db.Date)
    salary = db.Column(db.Numeric(12, 2), default=0)
    source = db.Column(db.String(60))
    status = db.Column(db.String(30), default="applied", index=True)  # applied | interview | offered | hired | rejected
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    position = db.relationship("Position", foreign_keys=[position_id])
    department = db.relationship("Department", foreign_keys=[department_id])
    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_name": self.candidate_name,
            "position_id": self.position_id,
            "position_name": self.position.name if self.position else None,
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else None,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "phone": self.phone,
            "email": self.email,
            "application_date": self.application_date.isoformat() if self.application_date else None,
            "hire_date": self.hire_date.isoformat() if self.hire_date else None,
            "salary": float(self.salary or 0),
            "source": self.source,
            "status": self.status,
            "notes": self.notes,
        }


class AttendanceRecord(db.Model):
    """سجل حضور وانصراف."""
    __tablename__ = "hr_attendance"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    check_in = db.Column(db.String(8))
    check_out = db.Column(db.String(8))
    status = db.Column(db.String(30), default="present", index=True)  # present | absent | late | on_leave
    working_hours = db.Column(db.Numeric(5, 2), default=0)
    notes = db.Column(db.String(300))
    check_in_lat = db.Column(db.Float)
    check_in_lng = db.Column(db.Float)
    check_out_lat = db.Column(db.Float)
    check_out_lng = db.Column(db.Float)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "date": self.date.isoformat() if self.date else None,
            "check_in": self.check_in,
            "check_out": self.check_out,
            "status": self.status,
            "working_hours": float(self.working_hours or 0),
            "notes": self.notes,
            "check_in_lat": self.check_in_lat,
            "check_in_lng": self.check_in_lng,
            "check_out_lat": self.check_out_lat,
            "check_out_lng": self.check_out_lng,
        }


class LeaveRequest(db.Model):
    """طلب إجازة."""
    __tablename__ = "hr_leaves"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    leave_type = db.Column(db.String(30), default="annual")  # annual | sick | unpaid | emergency | maternity
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    days = db.Column(db.Numeric(5, 1), default=0)
    reason = db.Column(db.Text)
    status = db.Column(db.String(30), default="pending", index=True)  # pending | approved | rejected | cancelled
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "leave_type": self.leave_type,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "days": float(self.days or 0),
            "reason": self.reason,
            "status": self.status,
        }


class Penalty(db.Model):
    """جزاء/خصم."""
    __tablename__ = "hr_penalties"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    penalty_type = db.Column(db.String(80))
    amount = db.Column(db.Numeric(12, 2), default=0)
    penalty_date = db.Column(db.Date)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "penalty_type": self.penalty_type,
            "amount": float(self.amount or 0),
            "penalty_date": self.penalty_date.isoformat() if self.penalty_date else None,
            "reason": self.reason,
        }


class EmployeeAdvance(db.Model):
    """سلفة موظف."""
    __tablename__ = "hr_advances"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), default=0)
    advance_date = db.Column(db.Date)
    installments = db.Column(db.Integer, default=1)
    paid_amount = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(30), default="open", index=True)  # open | partial | settled
    reason = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        remaining = float(self.amount or 0) - float(self.paid_amount or 0)
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "amount": float(self.amount or 0),
            "advance_date": self.advance_date.isoformat() if self.advance_date else None,
            "installments": self.installments or 1,
            "paid_amount": float(self.paid_amount or 0),
            "remaining": round(remaining, 2),
            "status": self.status,
            "reason": self.reason,
        }


class EmployeeLoan(db.Model):
    """قرض موظف."""
    __tablename__ = "hr_loans"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), default=0)
    interest_rate = db.Column(db.Numeric(5, 2), default=0)
    loan_date = db.Column(db.Date)
    installments = db.Column(db.Integer, default=1)
    installment_amount = db.Column(db.Numeric(12, 2), default=0)
    paid_amount = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(30), default="open", index=True)  # open | partial | settled
    reason = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        total = float(self.amount or 0) + (float(self.amount or 0) * float(self.interest_rate or 0) / 100)
        remaining = total - float(self.paid_amount or 0)
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "amount": float(self.amount or 0),
            "interest_rate": float(self.interest_rate or 0),
            "total": round(total, 2),
            "loan_date": self.loan_date.isoformat() if self.loan_date else None,
            "installments": self.installments or 1,
            "installment_amount": float(self.installment_amount or 0),
            "paid_amount": float(self.paid_amount or 0),
            "remaining": round(remaining, 2),
            "status": self.status,
            "reason": self.reason,
        }


class PerformanceReview(db.Model):
    """تقييم أداء موظف."""
    __tablename__ = "hr_reviews"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    review_date = db.Column(db.Date)
    period = db.Column(db.String(60))
    rating = db.Column(db.Numeric(3, 1), default=0)  # 0-5
    reviewer = db.Column(db.String(120))
    strengths = db.Column(db.Text)
    weaknesses = db.Column(db.Text)
    goals = db.Column(db.Text)
    status = db.Column(db.String(30), default="completed", index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "review_date": self.review_date.isoformat() if self.review_date else None,
            "period": self.period,
            "rating": float(self.rating or 0),
            "reviewer": self.reviewer,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "goals": self.goals,
            "status": self.status,
        }


class TrainingProgram(db.Model):
    """برنامج تدريبي."""
    __tablename__ = "hr_trainings"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    provider = db.Column(db.String(120))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    cost = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(30), default="planned", index=True)  # planned | ongoing | completed | cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "provider": self.provider,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "cost": float(self.cost or 0),
            "status": self.status,
            "notes": self.notes,
            "trainees_count": len(self.enrollments) if hasattr(self, "enrollments") else 0,
        }


class TrainingEnrollment(db.Model):
    """تسجيل موظف في برنامج تدريبي."""
    __tablename__ = "hr_training_enrollments"

    id = db.Column(db.Integer, primary_key=True)
    training_id = db.Column(db.Integer, db.ForeignKey("hr_trainings.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    status = db.Column(db.String(30), default="enrolled", index=True)  # enrolled | completed | dropped
    completed_at = db.Column(db.Date)
    score = db.Column(db.Numeric(5, 2))
    notes = db.Column(db.String(300))

    training = db.relationship("TrainingProgram", backref="enrollments")
    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "training_id": self.training_id,
            "training_title": self.training.title if self.training else None,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "score": float(self.score or 0),
            "notes": self.notes,
        }

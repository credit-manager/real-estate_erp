from database import db


class PayrollSettings(db.Model):
    """إعدادات الرواتب: تأمينات، ضرائب، نهاية خدمة."""
    __tablename__ = "payroll_settings"

    id = db.Column(db.Integer, primary_key=True)
    insurance_employee_rate = db.Column(db.Numeric(5, 2), default=0)   # نسبة تأمين الموظف %
    insurance_employer_rate = db.Column(db.Numeric(5, 2), default=0)   # نسبة تأمين صاحب العمل %
    insurance_ceiling = db.Column(db.Numeric(12, 2), default=0)        # سقف التأمين (0 = بدون سقف)
    tax_exempt = db.Column(db.Numeric(12, 2), default=0)               # الإعفاء الضريبي الشهري
    gratuity_per_year_days = db.Column(db.Numeric(5, 1), default=21)   # أيام نهاية الخدمة لكل سنة (أول 5 سنوات)
    gratuity_after_five_days = db.Column(db.Numeric(5, 1), default=30) # أيام نهاية الخدمة لكل سنة بعد 5 سنوات
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "insurance_employee_rate": float(self.insurance_employee_rate or 0),
            "insurance_employer_rate": float(self.insurance_employer_rate or 0),
            "insurance_ceiling": float(self.insurance_ceiling or 0),
            "tax_exempt": float(self.tax_exempt or 0),
            "gratuity_per_year_days": float(self.gratuity_per_year_days or 0),
            "gratuity_after_five_days": float(self.gratuity_after_five_days or 0),
        }


class EmployeeSalary(db.Model):
    """هيكل راتب الموظف (الراتب الأساسي الفعّال — يدعم سجل التاريخ)."""
    __tablename__ = "payroll_salaries"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    base_salary = db.Column(db.Numeric(12, 2), default=0)
    effective_date = db.Column(db.Date)
    notes = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "base_salary": float(self.base_salary or 0),
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "notes": self.notes,
        }


class Allowance(db.Model):
    """بدل ثابت للموظف."""
    __tablename__ = "payroll_allowances"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(12, 2), default=0)
    is_percentage = db.Column(db.Boolean, default=False)
    percentage = db.Column(db.Numeric(5, 2), default=0)
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "name": self.name,
            "amount": float(self.amount or 0),
            "is_percentage": bool(self.is_percentage),
            "percentage": float(self.percentage or 0),
            "notes": self.notes,
        }


class PayrollDeduction(db.Model):
    """خصم ثابت من راتب الموظف."""
    __tablename__ = "payroll_deductions"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(12, 2), default=0)
    is_percentage = db.Column(db.Boolean, default=False)
    percentage = db.Column(db.Numeric(5, 2), default=0)
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "name": self.name,
            "amount": float(self.amount or 0),
            "is_percentage": bool(self.is_percentage),
            "percentage": float(self.percentage or 0),
            "notes": self.notes,
        }


class Bonus(db.Model):
    """مكافأة موظف (مرة واحدة)."""
    __tablename__ = "payroll_bonuses"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(12, 2), default=0)
    bonus_date = db.Column(db.Date)
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "name": self.name,
            "amount": float(self.amount or 0),
            "bonus_date": self.bonus_date.isoformat() if self.bonus_date else None,
            "notes": self.notes,
        }


class TaxBracket(db.Model):
    """شريحة ضريبية تصاعدية (شهرية)."""
    __tablename__ = "payroll_tax_brackets"

    id = db.Column(db.Integer, primary_key=True)
    from_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    to_amount = db.Column(db.Numeric(12, 2))  # NULL = حتى اللانهاية
    rate = db.Column(db.Numeric(5, 2), default=0, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "from_amount": float(self.from_amount or 0),
            "to_amount": float(self.to_amount) if self.to_amount is not None else None,
            "rate": float(self.rate or 0),
        }


class EndOfService(db.Model):
    """مكافأة نهاية الخدمة."""
    __tablename__ = "payroll_end_of_service"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    hire_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    service_years = db.Column(db.Numeric(6, 2), default=0)
    gratuity_days = db.Column(db.Numeric(8, 1), default=0)
    base_salary = db.Column(db.Numeric(12, 2), default=0)
    gratuity_amount = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | approved | paid
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "hire_date": self.hire_date.isoformat() if self.hire_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "service_years": float(self.service_years or 0),
            "gratuity_days": float(self.gratuity_days or 0),
            "base_salary": float(self.base_salary or 0),
            "gratuity_amount": float(self.gratuity_amount or 0),
            "status": self.status,
            "notes": self.notes,
        }


class PayrollRun(db.Model):
    """كشف مرتبات / دورة صرف رواتب لشهر."""
    __tablename__ = "payroll_runs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    month = db.Column(db.String(7))  # YYYY-MM
    from_date = db.Column(db.Date)
    to_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="draft", index=True)  # draft | finalized | paid
    total_gross = db.Column(db.Numeric(15, 2), default=0)
    total_deductions = db.Column(db.Numeric(15, 2), default=0)
    total_net = db.Column(db.Numeric(15, 2), default=0)
    employees_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "month": self.month,
            "from_date": self.from_date.isoformat() if self.from_date else None,
            "to_date": self.to_date.isoformat() if self.to_date else None,
            "status": self.status,
            "total_gross": float(self.total_gross or 0),
            "total_deductions": float(self.total_deductions or 0),
            "total_net": float(self.total_net or 0),
            "employees_count": self.employees_count or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PayrollLine(db.Model):
    """سطر موظف داخل كشف المرتبات."""
    __tablename__ = "payroll_lines"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("payroll_runs.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    base_salary = db.Column(db.Numeric(12, 2), default=0)
    allowances = db.Column(db.JSON, default=list)
    allowance_total = db.Column(db.Numeric(12, 2), default=0)
    bonuses = db.Column(db.JSON, default=list)
    bonus_total = db.Column(db.Numeric(12, 2), default=0)
    deductions = db.Column(db.JSON, default=list)
    deduction_total = db.Column(db.Numeric(12, 2), default=0)
    penalties_total = db.Column(db.Numeric(12, 2), default=0)
    loan_installment = db.Column(db.Numeric(12, 2), default=0)
    insurance = db.Column(db.Numeric(12, 2), default=0)
    tax = db.Column(db.Numeric(12, 2), default=0)
    gross = db.Column(db.Numeric(15, 2), default=0)
    total_deductions = db.Column(db.Numeric(15, 2), default=0)
    net = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(30), default="pending", index=True)  # pending | approved

    run = db.relationship("PayrollRun", backref="lines")
    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "department_name": self.employee.hr_department.name if self.employee and self.employee.hr_department else None,
            "position_name": self.employee.hr_position.name if self.employee and self.employee.hr_position else None,
            "base_salary": float(self.base_salary or 0),
            "allowances": self.allowances or [],
            "allowance_total": float(self.allowance_total or 0),
            "bonuses": self.bonuses or [],
            "bonus_total": float(self.bonus_total or 0),
            "deductions": self.deductions or [],
            "deduction_total": float(self.deduction_total or 0),
            "penalties_total": float(self.penalties_total or 0),
            "loan_installment": float(self.loan_installment or 0),
            "insurance": float(self.insurance or 0),
            "tax": float(self.tax or 0),
            "gross": float(self.gross or 0),
            "total_deductions": float(self.total_deductions or 0),
            "net": float(self.net or 0),
            "status": self.status,
        }

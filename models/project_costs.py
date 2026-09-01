from database import db


class ProjectCostItem(db.Model):
    """Individual cost line items for real estate projects"""
    __tablename__ = "project_cost_items"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    cost_date = db.Column(db.Date, server_default=db.func.current_date())
    category = db.Column(db.String(50), default="other")
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(15, 2), default=0)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    payment_method = db.Column(db.String(20), default="cash")
    supplier_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    reference = db.Column(db.String(50))
    notes = db.Column(db.Text)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey("journal_entries.id"), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    project = db.relationship("Project", backref="cost_items")
    account = db.relationship("Account", foreign_keys=[account_id])
    supplier_account = db.relationship("Account", foreign_keys=[supplier_account_id])
    journal_entry = db.relationship("JournalEntry", foreign_keys=[journal_entry_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "cost_date": self.cost_date.isoformat() if self.cost_date else None,
            "category": self.category,
            "description": self.description,
            "amount": float(self.amount or 0),
            "account_id": self.account_id,
            "account_name": self.account.name if self.account else None,
            "payment_method": self.payment_method,
            "supplier_account_id": self.supplier_account_id,
            "supplier_account_name": self.supplier_account.name if self.supplier_account else None,
            "reference": self.reference,
            "notes": self.notes,
            "journal_entry_id": self.journal_entry_id,
            "created_by": self.created_by,
            "creator_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CompanyExpense(db.Model):
    """General company operating expenses"""
    __tablename__ = "company_expenses"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    expense_date = db.Column(db.Date, server_default=db.func.current_date())
    category = db.Column(db.String(50), default="other")
    subcategory = db.Column(db.String(100))
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(15, 2), default=0)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    payment_method = db.Column(db.String(20), default="cash")
    payee_type = db.Column(db.String(20), default="employee")
    payee_id = db.Column(db.Integer, nullable=True)
    supplier_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    reference = db.Column(db.String(50))
    notes = db.Column(db.Text)
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_period = db.Column(db.String(20), default="monthly")  # monthly/quarterly/yearly
    journal_entry_id = db.Column(db.Integer, db.ForeignKey("journal_entries.id"), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    project = db.relationship("Project", backref="company_expenses")
    account = db.relationship("Account", foreign_keys=[account_id])
    supplier_account = db.relationship("Account", foreign_keys=[supplier_account_id])
    journal_entry = db.relationship("JournalEntry", foreign_keys=[journal_entry_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    employee = db.relationship("Employee", foreign_keys=[payee_id], primaryjoin="CompanyExpense.payee_id == Employee.id", viewonly=True)
    supplier = db.relationship("Supplier", foreign_keys=[payee_id], primaryjoin="CompanyExpense.payee_id == Supplier.id", viewonly=True)

    def to_dict(self):
        payee_name = None
        if self.payee_type == "employee" and self.employee:
            payee_name = self.employee.full_name
        elif self.payee_type == "supplier" and self.supplier:
            payee_name = self.supplier.company_name

        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "expense_date": self.expense_date.isoformat() if self.expense_date else None,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "amount": float(self.amount or 0),
            "account_id": self.account_id,
            "account_name": self.account.name if self.account else None,
            "payment_method": self.payment_method,
            "payee_type": self.payee_type,
            "payee_id": self.payee_id,
            "payee_name": payee_name,
            "supplier_account_id": self.supplier_account_id,
            "supplier_account_name": self.supplier_account.name if self.supplier_account else None,
            "reference": self.reference,
            "notes": self.notes,
            "is_recurring": self.is_recurring if hasattr(self, 'is_recurring') else False,
            "recurring_period": self.recurring_period if hasattr(self, 'recurring_period') else None,
            "journal_entry_id": self.journal_entry_id,
            "created_by": self.created_by,
            "creator_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

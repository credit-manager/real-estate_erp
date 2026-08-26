from database import db


class Account(db.Model):
    """دليل الحسابات - شجرة حسابات (قيد مزدوج)."""
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(20), default="asset")  # asset | liability | equity | revenue | expense
    parent_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    is_active = db.Column(db.Boolean, default=True)
    is_cash = db.Column(db.Boolean, default=False)
    is_bank = db.Column(db.Boolean, default=False)
    is_contra = db.Column(db.Boolean, default=False)
    bank_name = db.Column(db.String(150))
    account_number = db.Column(db.String(80))
    currency_code = db.Column(db.String(10))
    opening_balance = db.Column(db.Numeric(15, 2), default=0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    parent = db.relationship("Account", remote_side=[id], backref="children")

    @property
    def is_debit_normal(self):
        normal = self.type in ("asset", "expense")
        return not normal if self.is_contra else normal

    def to_dict(self, include_children=False):
        d = {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "type": self.type,
            "parent_id": self.parent_id,
            "is_active": bool(self.is_active),
            "is_cash": bool(self.is_cash),
            "is_bank": bool(self.is_bank),
            "is_contra": bool(self.is_contra),
            "bank_name": self.bank_name,
            "account_number": self.account_number,
            "currency_code": self.currency_code,
            "opening_balance": float(self.opening_balance or 0),
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "balance": 0.0,
        }
        if include_children:
            d["children"] = []
        return d


class CostCenter(db.Model):
    __tablename__ = "cost_centers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class JournalEntry(db.Model):
    __tablename__ = "journal_entries"

    id = db.Column(db.Integer, primary_key=True)
    entry_number = db.Column(db.String(30), nullable=False)
    date = db.Column(db.Date, nullable=False)
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"), index=True)
    description = db.Column(db.Text)
    source = db.Column(db.String(30), default="manual")  # manual | invoice | installment | cash | bank | asset | depreciation | reconcile | opening
    ref_type = db.Column(db.String(40))
    ref_id = db.Column(db.Integer, index=True)
    status = db.Column(db.String(20), default="posted", index=True)  # posted | draft
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    posted_at = db.Column(db.DateTime)
    reversed_of = db.Column(db.Integer)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)  # soft-delete

    financial_year = db.relationship("FinancialYear", backref="journal_entries")
    creator = db.relationship("User", foreign_keys=[created_by])
    lines = db.relationship(
        "JournalEntryLine", backref="entry", cascade="all, delete-orphan",
        order_by="JournalEntryLine.id",
    )

    @property
    def total_debit(self):
        return sum(float(l.debit or 0) for l in self.lines)

    @property
    def total_credit(self):
        return sum(float(l.credit or 0) for l in self.lines)

    @property
    def is_balanced(self):
        return abs(self.total_debit - self.total_credit) < 0.005

    def to_dict(self):
        return {
            "id": self.id,
            "entry_number": self.entry_number,
            "date": self.date.isoformat() if self.date else None,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "description": self.description,
            "source": self.source,
            "ref_type": self.ref_type,
            "ref_id": self.ref_id,
            "status": self.status,
            "created_by": self.created_by,
            "created_by_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "reversed_of": self.reversed_of,
            "total_debit": self.total_debit,
            "total_credit": self.total_credit,
            "balanced": self.is_balanced,
            "lines": [l.to_dict() for l in self.lines],
        }


class JournalEntryLine(db.Model):
    __tablename__ = "journal_entry_lines"

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("journal_entries.id"), index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), index=True)
    cost_center_id = db.Column(db.Integer, db.ForeignKey("cost_centers.id"), index=True)
    debit = db.Column(db.Numeric(15, 2), default=0)
    credit = db.Column(db.Numeric(15, 2), default=0)
    description = db.Column(db.Text)
    reconciled = db.Column(db.Boolean, default=False)
    reconciled_at = db.Column(db.DateTime)

    account = db.relationship("Account", foreign_keys=[account_id])
    cost_center = db.relationship("CostCenter", foreign_keys=[cost_center_id])

    def to_dict(self):
        return {
            "id": self.id,
            "entry_id": self.entry_id,
            "account_id": self.account_id,
            "account_code": self.account.code if self.account else None,
            "account_name": self.account.name if self.account else None,
            "cost_center_id": self.cost_center_id,
            "cost_center_name": self.cost_center.name if self.cost_center else None,
            "debit": float(self.debit or 0),
            "credit": float(self.credit or 0),
            "description": self.description,
            "reconciled": bool(self.reconciled),
        }


class FixedAsset(db.Model):
    __tablename__ = "fixed_assets"

    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80))
    purchase_date = db.Column(db.Date)
    cost = db.Column(db.Numeric(15, 2), default=0)
    useful_life_years = db.Column(db.Integer, default=5)
    salvage_value = db.Column(db.Numeric(15, 2), default=0)
    method = db.Column(db.String(20), default="straight")  # straight | declining
    monthly_depreciation = db.Column(db.Numeric(15, 2), default=0)
    accumulated_depreciation = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default="active")  # active | disposed
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    expense_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    accumulated_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    asset_account = db.relationship("Account", foreign_keys=[account_id])
    expense_account = db.relationship("Account", foreign_keys=[expense_account_id])
    accumulated_account = db.relationship("Account", foreign_keys=[accumulated_account_id])

    @property
    def net_book_value(self):
        return float(self.cost or 0) - float(self.accumulated_depreciation or 0)

    def compute_monthly(self):
        base = float(self.cost or 0) - float(self.salvage_value or 0)
        months = max(int(self.useful_life_years or 1) * 12, 1)
        if self.method == "straight":
            return round(base / months, 2)
        rate = 2 / months
        return round(self.net_book_value * rate, 2)

    def to_dict(self):
        return {
            "id": self.id,
            "asset_code": self.asset_code,
            "name": self.name,
            "category": self.category,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "cost": float(self.cost or 0),
            "useful_life_years": self.useful_life_years,
            "salvage_value": float(self.salvage_value or 0),
            "method": self.method,
            "monthly_depreciation": float(self.monthly_depreciation or 0),
            "accumulated_depreciation": float(self.accumulated_depreciation or 0),
            "net_book_value": self.net_book_value,
            "status": self.status,
            "account_id": self.account_id,
            "expense_account_id": self.expense_account_id,
            "accumulated_account_id": self.accumulated_account_id,
            "asset_account_name": self.asset_account.name if self.asset_account else None,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DepreciationRecord(db.Model):
    __tablename__ = "depreciation_records"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("fixed_assets.id"), index=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("journal_entries.id"), index=True)
    period = db.Column(db.String(20))  # YYYY-MM
    date = db.Column(db.Date)
    amount = db.Column(db.Numeric(15, 2), default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    asset = db.relationship("FixedAsset", backref="depreciation_records")
    entry = db.relationship("JournalEntry", foreign_keys=[entry_id])

    def to_dict(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "asset_name": self.asset.name if self.asset else None,
            "entry_id": self.entry_id,
            "period": self.period,
            "date": self.date.isoformat() if self.date else None,
            "amount": float(self.amount or 0),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BudgetLine(db.Model):
    __tablename__ = "budget_lines"

    id = db.Column(db.Integer, primary_key=True)
    financial_year_id = db.Column(db.Integer, db.ForeignKey("financial_years.id"))
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    amount = db.Column(db.Numeric(15, 2), default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("financial_year_id", "account_id", name="uq_budget_year_account"),
    )

    financial_year = db.relationship("FinancialYear", backref="budget_lines")
    account = db.relationship("Account", backref="budget_lines")

    def to_dict(self):
        return {
            "id": self.id,
            "financial_year_id": self.financial_year_id,
            "financial_year_name": self.financial_year.name if self.financial_year else None,
            "account_id": self.account_id,
            "account_code": self.account.code if self.account else None,
            "account_name": self.account.name if self.account else None,
            "amount": float(self.amount or 0),
        }

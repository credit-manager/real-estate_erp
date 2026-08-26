from database import db


class EscrowAccount(db.Model):
    """حساب الضمان — حساب بنكي مرتبط بمشروع عقاري لحفظ دفعات العملاء (وافي/Oqood)."""
    __tablename__ = "escrow_accounts"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    escrow_number = db.Column(db.String(50), unique=True, nullable=False)
    bank_name = db.Column(db.String(150), nullable=False)
    iban = db.Column(db.String(50))
    balance = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default="active", index=True)  # active | frozen | closed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    project = db.relationship("Project", backref="escrow_accounts")
    transactions = db.relationship("EscrowTransaction", backref="account", cascade="all, delete-orphan", order_by="EscrowTransaction.created_at.desc()")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "escrow_number": self.escrow_number,
            "bank_name": self.bank_name,
            "iban": self.iban,
            "balance": float(self.balance or 0),
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EscrowTransaction(db.Model):
    """حركة في حساب الضمان — إيداع/صرف/حجز/استرداد مرتبطة بعقد أو قسط."""
    __tablename__ = "escrow_transactions"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("escrow_accounts.id"), nullable=False, index=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("sales_contracts.id"), index=True)
    installment_id = db.Column(db.Integer, db.ForeignKey("installments.id"), index=True)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    type = db.Column(db.String(20), nullable=False, index=True)  # deposit | release | hold | refund
    status = db.Column(db.String(20), default="completed", index=True)  # pending | completed | cancelled
    description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    contract = db.relationship("SalesContract", backref="escrow_transactions")
    installment = db.relationship("Installment", backref="escrow_transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "escrow_number": self.account.escrow_number if self.account else None,
            "contract_id": self.contract_id,
            "contract_number": self.contract.contract_number if self.contract else None,
            "installment_id": self.installment_id,
            "amount": float(self.amount or 0),
            "type": self.type,
            "status": self.status,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

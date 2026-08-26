from database import db


class Currency(db.Model):
    __tablename__ = "currencies"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(10), nullable=False)
    symbol = db.Column(db.String(10))
    rate = db.Column(db.Float, nullable=False, default=1.0)
    is_base = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("company_id", "code", name="uq_currency_company_code"),
    )

    company = db.relationship("Company", backref="currencies")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "name": self.name,
            "code": self.code,
            "symbol": self.symbol,
            "rate": round(self.rate, 6) if self.rate is not None else None,
            "is_base": bool(self.is_base),
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

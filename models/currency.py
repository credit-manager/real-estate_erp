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
    exchange_rate_source = db.Column(db.String(50), default="")
    exchange_rate_updated_at = db.Column(db.DateTime, nullable=True)
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
            "exchange_rate_source": self.exchange_rate_source or "",
            "exchange_rate_updated_at": self.exchange_rate_updated_at.isoformat() if self.exchange_rate_updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ExchangeRateHistory(db.Model):
    """سجل تاريخ أسعار الصرف — يحفظ كل سعر صرف مستخدم في المعاملات"""
    __tablename__ = "exchange_rate_history"

    id = db.Column(db.Integer, primary_key=True)
    currency_id = db.Column(db.Integer, db.ForeignKey("currencies.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    rate_date = db.Column(db.Date, nullable=False)
    buy_rate = db.Column(db.Float, default=0)
    sell_rate = db.Column(db.Float, default=0)
    mid_rate = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), default="manual")  # manual | central_bank | api | fixed
    source_url = db.Column(db.String(500))
    notes = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    currency = db.relationship("Currency", backref="rate_history")
    company = db.relationship("Company", backref="rate_history")
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint("currency_id", "rate_date", name="uq_currency_rate_date"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "currency_id": self.currency_id,
            "currency_code": self.currency.code if self.currency else None,
            "currency_name": self.currency.name if self.currency else None,
            "company_id": self.company_id,
            "rate_date": self.rate_date.isoformat() if self.rate_date else None,
            "buy_rate": self.buy_rate,
            "sell_rate": self.sell_rate,
            "mid_rate": self.mid_rate,
            "source": self.source,
            "source_url": self.source_url,
            "notes": self.notes,
            "created_by": self.created_by,
            "creator_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

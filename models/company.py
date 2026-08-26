from database import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    legal_name = db.Column(db.String(200))
    tax_number = db.Column(db.String(50))
    commercial_registration = db.Column(db.String(50))
    address = db.Column(db.String(300))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(120))
    currency = db.Column(db.String(10), default="EGP")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    branches = db.relationship(
        "Branch", backref="company", cascade="all, delete-orphan",
        order_by="Branch.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "legal_name": self.legal_name,
            "tax_number": self.tax_number,
            "commercial_registration": self.commercial_registration,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "currency": self.currency,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "branches": [b.to_dict() for b in self.branches],
        }


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50))
    city = db.Column(db.String(100))
    address = db.Column(db.String(300))
    phone = db.Column(db.String(20))
    manager_name = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "name": self.name,
            "code": self.code,
            "city": self.city,
            "address": self.address,
            "phone": self.phone,
            "manager_name": self.manager_name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

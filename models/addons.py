"""إضافات عقارية: DMS + اتحاد ملاك + رسوم خدمات."""
from database import db


class UnitDocument(db.Model):
    """مستندات الوحدة — DMS (صك، عقد، هوية، مخطط، صور)."""
    __tablename__ = "unit_documents"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"), nullable=False, index=True)
    doc_type = db.Column(db.String(30), nullable=False, index=True)  # title_deed | contract | id_copy | plan | photo | other
    title = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    version = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)

    unit = db.relationship("RealEstateUnit", backref="documents")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "doc_type": self.doc_type,
            "title": self.title,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "version": self.version,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OwnerAssociation(db.Model):
    """اتحاد الملاك — لكل مشروع."""
    __tablename__ = "owner_associations"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, unique=True, index=True)
    name = db.Column(db.String(150), nullable=False)
    annual_fee_per_sqm = db.Column(db.Numeric(10, 2), default=0)  # رسوم سنوية للمتر
    collected_amount = db.Column(db.Numeric(15, 2), default=0)
    balance = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default="active")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    project = db.relationship("Project", backref="owner_association")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "name": self.name,
            "annual_fee_per_sqm": float(self.annual_fee_per_sqm or 0),
            "collected_amount": float(self.collected_amount or 0),
            "balance": float(self.balance or 0),
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ServiceCharge(db.Model):
    """رسوم خدمات — فاتورة دورية لاتحاد الملاك على وحدة."""
    __tablename__ = "service_charges"

    id = db.Column(db.Integer, primary_key=True)
    association_id = db.Column(db.Integer, db.ForeignKey("owner_associations.id"), nullable=False, index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"), nullable=False, index=True)
    period = db.Column(db.String(20), nullable=False)  # 2026-Q1 | 2026 | 2026-01
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    paid_amount = db.Column(db.Numeric(15, 2), default=0)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="pending", index=True)  # pending | paid | overdue | waived
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    association = db.relationship("OwnerAssociation", backref="charges")
    unit = db.relationship("RealEstateUnit", backref="service_charges")

    def to_dict(self):
        return {
            "id": self.id,
            "association_id": self.association_id,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "period": self.period,
            "amount": float(self.amount or 0),
            "paid_amount": float(self.paid_amount or 0),
            "balance": float((self.amount or 0) - (self.paid_amount or 0)),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

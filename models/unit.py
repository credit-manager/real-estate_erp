from database import db


class RealEstateUnit(db.Model):
    __tablename__ = "real_estate_units"

    id = db.Column(db.Integer, primary_key=True)
    unit_code = db.Column(db.String(50), unique=True, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    building_id = db.Column(db.Integer, db.ForeignKey("real_estate_buildings.id"))
    floor_id = db.Column(db.Integer, db.ForeignKey("real_estate_floors.id"))
    unit_type_id = db.Column(db.Integer, db.ForeignKey("unit_types.id"))
    owner_id = db.Column(db.Integer, db.ForeignKey("real_estate_owners.id"))
    unit_type = db.Column(db.String(50))  # Legacy field
    area = db.Column(db.Numeric(10, 2), default=0)
    floor = db.Column(db.String(20))  # Legacy field

    # Pricing
    price = db.Column(db.Numeric(15, 2), default=0)  # Sale price
    rent_price = db.Column(db.Numeric(15, 2), default=0)  # Monthly rent price
    price_per_sqm = db.Column(db.Numeric(15, 2), default=0)
    rent_per_sqm = db.Column(db.Numeric(15, 2), default=0)
    sale_method = db.Column(db.String(30), default="cash")  # cash | installment | both

    # Physical attributes
    frontage = db.Column(db.Numeric(8, 2))  # الواجهة بالمتر
    bedrooms = db.Column(db.Integer, default=1)
    bathrooms = db.Column(db.Integer, default=1)
    has_balcony = db.Column(db.Boolean, default=False)
    has_parking = db.Column(db.Boolean, default=False)
    floor_level = db.Column(db.String(30))  # basement | ground | upper | roof

    # Status
    status = db.Column(db.String(30), default="available")  # available | reserved | sold | rented | delivered

    # Financial tracking
    cost_center_id = db.Column(db.Integer, db.ForeignKey("cost_centers.id"), nullable=True)
    total_cost = db.Column(db.Numeric(15, 2), default=0)  # Allocated cost from project
    collected_amount = db.Column(db.Numeric(15, 2), default=0)
    receivable_amount = db.Column(db.Numeric(15, 2), default=0)

    # Soft delete
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    # Relationships
    project = db.relationship("Project", backref="units")
    building = db.relationship("Building", backref="units")
    floor_ref = db.relationship("Floor", backref="units", foreign_keys=[floor_id])
    unit_type_ref = db.relationship("UnitType", backref="units")
    owner = db.relationship("Owner", backref="units")
    cost_center = db.relationship("CostCenter", backref="units")

    def to_dict(self):
        return {
            "id": self.id,
            "unit_code": self.unit_code,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "building_id": self.building_id,
            "building_name": self.building.name if self.building else None,
            "floor_id": self.floor_id,
            "floor_label": (self.floor_ref.name if self.floor_ref else self.floor),
            "unit_type_id": self.unit_type_id,
            "unit_type_name": self.unit_type_ref.name if self.unit_type_ref else self.unit_type,
            "owner_id": self.owner_id,
            "owner_name": self.owner.full_name if self.owner else None,
            "unit_type": self.unit_type,
            "area": float(self.area or 0),
            "floor": self.floor,
            "price": float(self.price or 0),
            "rent_price": float(self.rent_price or 0),
            "price_per_sqm": float(self.price_per_sqm or 0),
            "rent_per_sqm": float(self.rent_per_sqm or 0),
            "sale_method": self.sale_method,
            "frontage": float(self.frontage) if self.frontage else None,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "has_balcony": bool(self.has_balcony),
            "has_parking": bool(self.has_parking),
            "floor_level": self.floor_level,
            "status": self.status,
            "cost_center_id": self.cost_center_id,
            "total_cost": float(self.total_cost or 0),
            "collected_amount": float(self.collected_amount or 0),
            "receivable_amount": float(self.receivable_amount or 0),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

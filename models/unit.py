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
    unit_type = db.Column(db.String(50))  # شقة | فيلا | بنتهاوس | محل
    area = db.Column(db.Numeric(10, 2), default=0)
    floor = db.Column(db.String(20))
    price = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(30), default="available")  # available | reserved | sold | rented
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)  # soft delete
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    project = db.relationship("Project", backref="units")
    building = db.relationship("Building", backref="units")
    floor_ref = db.relationship("Floor", backref="units", foreign_keys=[floor_id])
    unit_type_ref = db.relationship("UnitType", backref="units")
    owner = db.relationship("Owner", backref="units")

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
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

from database import db


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), default="")
    is_system = db.Column(db.Boolean, default=False)
    permissions = db.Column(db.JSON, default=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "is_system": bool(self.is_system),
            "permissions": self.permissions or {},
        }

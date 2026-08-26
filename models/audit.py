from database import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    username = db.Column(db.String(80))
    action = db.Column(db.String(30))  # create | update | delete | login | logout | payment
    entity = db.Column(db.String(50))  # unit | project | employee | customer | supplier | invoice | order | rental | plan | installment | user
    entity_id = db.Column(db.Integer)
    description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "entity": self.entity,
            "entity_id": self.entity_id,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

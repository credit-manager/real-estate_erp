from database import db


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    status = db.Column(db.String(50), default="active")  # active | finishing | completed | suspended
    priority = db.Column(db.String(20), default="medium")  # high | medium | low
    budget = db.Column(db.Numeric(15, 2), default=0)
    spent = db.Column(db.Numeric(15, 2), default=0)
    start_date = db.Column(db.Date)
    deadline = db.Column(db.Date)
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    completion = db.Column(db.Integer, default=0)  # نسبة الإنجاز 0-100
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    manager = db.relationship("Employee", backref="managed_projects")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "status": self.status,
            "priority": self.priority,
            "budget": float(self.budget or 0),
            "spent": float(self.spent or 0),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "manager_id": self.manager_id,
            "completion": self.completion,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

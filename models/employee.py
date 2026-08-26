from database import db


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    national_id = db.Column(db.String(20), unique=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    department = db.Column(db.String(80))
    position = db.Column(db.String(80))
    department_id = db.Column(db.Integer, db.ForeignKey("hr_departments.id"))
    position_id = db.Column(db.Integer, db.ForeignKey("hr_positions.id"))
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    gender = db.Column(db.String(10))
    birth_date = db.Column(db.Date)
    hire_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    employment_type = db.Column(db.String(30), default="full_time")  # full_time | part_time | fixed_term
    salary = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(30), default="active")  # active | on_leave | terminated
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    hr_department = db.relationship("Department", backref="employees", foreign_keys=[department_id])
    hr_position = db.relationship("Position", backref="employees", foreign_keys=[position_id])
    manager = db.relationship("Employee", remote_side=[id], backref="direct_reports")
    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "national_id": self.national_id,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "department": self.department,
            "position": self.position,
            "department_id": self.department_id,
            "department_name": self.hr_department.name if self.hr_department else None,
            "position_id": self.position_id,
            "position_name": self.hr_position.name if self.hr_position else None,
            "manager_id": self.manager_id,
            "manager_name": self.manager.full_name if self.manager else None,
            "gender": self.gender,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "hire_date": self.hire_date.isoformat() if self.hire_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "employment_type": self.employment_type or "full_time",
            "salary": float(self.salary or 0),
            "status": self.status,
            "user_id": self.user_id,
        }

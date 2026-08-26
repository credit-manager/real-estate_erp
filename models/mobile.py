from database import db


class FieldVisit(db.Model):
    """زيارة ميدانية (مندوب) لعملاء أو وحدات لمتابعة الإيجارات/المبيعات."""
    __tablename__ = "mobile_field_visits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    visit_number = db.Column(db.String(50))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("real_estate_units.id"), index=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("rental_contracts.id"), index=True)
    visit_type = db.Column(db.String(30), default="collection")  # collection | followup | inspection | new_lead
    scheduled_date = db.Column(db.Date)
    scheduled_time = db.Column(db.String(8))
    status = db.Column(db.String(30), default="planned", index=True)  # planned | done | cancelled | missed
    purpose = db.Column(db.String(300))
    notes = db.Column(db.Text)
    result = db.Column(db.String(300))
    amount_collected = db.Column(db.Numeric(15, 2), default=0)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    check_in_at = db.Column(db.DateTime)
    check_out_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    user = db.relationship("User", foreign_keys=[user_id])
    customer = db.relationship("Customer", foreign_keys=[customer_id])
    unit = db.relationship("RealEstateUnit", foreign_keys=[unit_id])
    contract = db.relationship("RentalContract", foreign_keys=[contract_id])

    def to_dict(self):
        return {
            "id": self.id,
            "visit_number": self.visit_number,
            "user_id": self.user_id,
            "delegate_name": self.user.full_name if self.user else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "customer_phone": self.customer.phone if self.customer else None,
            "unit_id": self.unit_id,
            "unit_code": self.unit.unit_code if self.unit else None,
            "contract_id": self.contract_id,
            "contract_number": self.contract.contract_number if self.contract else None,
            "visit_type": self.visit_type,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "scheduled_time": self.scheduled_time,
            "status": self.status,
            "purpose": self.purpose,
            "notes": self.notes,
            "result": self.result,
            "amount_collected": float(self.amount_collected or 0),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "check_in_at": self.check_in_at.isoformat() if self.check_in_at else None,
            "check_out_at": self.check_out_at.isoformat() if self.check_out_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GpsLocation(db.Model):
    """نقطة موقع GPS لحساب مستخدم (تتبع مباشر)."""
    __tablename__ = "mobile_gps_locations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float, default=0)
    speed = db.Column(db.Float, default=0)
    heading = db.Column(db.Float, default=0)
    source = db.Column(db.String(20), default="app")  # app | web
    recorded_at = db.Column(db.DateTime, default=db.func.now(), index=True)

    user = db.relationship("User", foreign_keys=[user_id])
    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.full_name if self.user else None,
            "employee_id": self.employee_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": float(self.accuracy or 0),
            "speed": float(self.speed or 0),
            "heading": float(self.heading or 0),
            "source": self.source,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }


class DeviceToken(db.Model):
    """رمز جهاز للتشغيل في إشعارات FCM."""
    __tablename__ = "mobile_device_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.Text, nullable=False)
    platform = db.Column(db.String(30), default="android")  # android | ios | web
    device_name = db.Column(db.String(120))
    last_seen = db.Column(db.DateTime, default=db.func.now())
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "platform": self.platform,
            "device_name": self.device_name,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class AppNotification(db.Model):
    """مركز إشعارات داخل النظام (لكل مستخدم)."""
    __tablename__ = "mobile_app_notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    category = db.Column(db.String(40), default="general")  # general | attendance | visits | rentals | finance | gps | system
    severity = db.Column(db.String(20), default="info")  # info | warning | danger | success
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "category": self.category,
            "severity": self.severity,
            "link": self.link,
            "is_read": bool(self.is_read),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

from database import db


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200))
    description = db.Column(db.Text)
    project_code = db.Column(db.String(50), unique=True)
    project_type = db.Column(db.String(50), default="residential")  # residential | commercial | industrial | mixed
    location = db.Column(db.String(200))
    land_owner = db.Column(db.String(200))
    status = db.Column(db.String(50), default="active")  # active | finishing | completed | suspended
    priority = db.Column(db.String(20), default="medium")  # high | medium | low
    currency = db.Column(db.String(10), default="EGP")
    cost_center_id = db.Column(db.Integer, db.ForeignKey("cost_centers.id"), nullable=True)

    budget = db.Column(db.Numeric(15, 2), default=0)
    spent = db.Column(db.Numeric(15, 2), default=0)
    start_date = db.Column(db.Date)
    deadline = db.Column(db.Date)
    expected_delivery_date = db.Column(db.Date)
    actual_delivery_date = db.Column(db.Date)
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    completion = db.Column(db.Integer, default=0)  # 0-100

    # Financial tracking
    land_cost = db.Column(db.Numeric(15, 2), default=0)
    papers_cost = db.Column(db.Numeric(15, 2), default=0)
    construction_cost = db.Column(db.Numeric(15, 2), default=0)
    other_costs = db.Column(db.Numeric(15, 2), default=0)
    total_invested = db.Column(db.Numeric(15, 2), default=0)
    total_revenue = db.Column(db.Numeric(15, 2), default=0)
    total_expenses = db.Column(db.Numeric(15, 2), default=0)
    forecast_remaining_cost = db.Column(db.Numeric(15, 2), default=0)
    forecast_total_cost = db.Column(db.Numeric(15, 2), default=0)

    # Budget tracking
    budget_land = db.Column(db.Numeric(15, 2), default=0)
    budget_papers = db.Column(db.Numeric(15, 2), default=0)
    budget_construction = db.Column(db.Numeric(15, 2), default=0)
    budget_marketing = db.Column(db.Numeric(15, 2), default=0)
    budget_admin = db.Column(db.Numeric(15, 2), default=0)
    budget_other = db.Column(db.Numeric(15, 2), default=0)

    # Revenue tracking
    revenue_sales = db.Column(db.Numeric(15, 2), default=0)
    revenue_rent = db.Column(db.Numeric(15, 2), default=0)
    collected_amount = db.Column(db.Numeric(15, 2), default=0)
    receivable_amount = db.Column(db.Numeric(15, 2), default=0)

    # Counts (cached)
    total_buildings = db.Column(db.Integer, default=0)
    total_floors = db.Column(db.Integer, default=0)
    total_units = db.Column(db.Integer, default=0)
    units_sold = db.Column(db.Integer, default=0)
    units_rented = db.Column(db.Integer, default=0)
    units_available = db.Column(db.Integer, default=0)
    units_reserved = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    manager = db.relationship("Employee", backref="managed_projects")
    cost_center = db.relationship("CostCenter", backref="projects")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_ar": self.name_ar,
            "description": self.description,
            "project_code": self.project_code,
            "project_type": self.project_type,
            "location": self.location,
            "land_owner": self.land_owner,
            "status": self.status,
            "priority": self.priority,
            "currency": self.currency,
            "cost_center_id": self.cost_center_id,
            "cost_center_name": self.cost_center.name if self.cost_center else None,
            "budget": float(self.budget or 0),
            "spent": float(self.spent or 0),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "expected_delivery_date": self.expected_delivery_date.isoformat() if self.expected_delivery_date else None,
            "actual_delivery_date": self.actual_delivery_date.isoformat() if self.actual_delivery_date else None,
            "manager_id": self.manager_id,
            "manager_name": self.manager.full_name if self.manager else None,
            "completion": self.completion,
            "land_cost": float(self.land_cost or 0),
            "papers_cost": float(self.papers_cost or 0),
            "construction_cost": float(self.construction_cost or 0),
            "other_costs": float(self.other_costs or 0),
            "total_invested": float(self.total_invested or 0),
            "total_revenue": float(self.total_revenue or 0),
            "total_expenses": float(self.total_expenses or 0),
            "forecast_remaining_cost": float(self.forecast_remaining_cost or 0),
            "forecast_total_cost": float(self.forecast_total_cost or 0),
            "budget_land": float(self.budget_land or 0),
            "budget_papers": float(self.budget_papers or 0),
            "budget_construction": float(self.budget_construction or 0),
            "budget_marketing": float(self.budget_marketing or 0),
            "budget_admin": float(self.budget_admin or 0),
            "budget_other": float(self.budget_other or 0),
            "budget_total": float(
                (self.budget_land or 0) + (self.budget_papers or 0) +
                (self.budget_construction or 0) + (self.budget_marketing or 0) +
                (self.budget_admin or 0) + (self.budget_other or 0)
            ),
            "revenue_sales": float(self.revenue_sales or 0),
            "revenue_rent": float(self.revenue_rent or 0),
            "collected_amount": float(self.collected_amount or 0),
            "receivable_amount": float(self.receivable_amount or 0),
            "total_buildings": self.total_buildings or 0,
            "total_floors": self.total_floors or 0,
            "total_units": self.total_units or 0,
            "units_sold": self.units_sold or 0,
            "units_rented": self.units_rented or 0,
            "units_available": self.units_available or 0,
            "units_reserved": self.units_reserved or 0,
            "expected_profit": float(
                (self.revenue_sales or 0) + (self.revenue_rent or 0) -
                (self.forecast_total_cost or 0)
            ),
            "actual_profit": float(
                (self.revenue_sales or 0) + (self.revenue_rent or 0) -
                (self.total_invested or 0)
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

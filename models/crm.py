from database import db


class CrmPipelineStage(db.Model):
    """مراحل أنبوب البيع (Pipeline) — جديد/مؤهل/عرض/تفاوض/مقبول."""
    __tablename__ = "crm_pipeline_stages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    position = db.Column(db.Integer, default=1)
    probability = db.Column(db.Numeric(5, 2), default=0)  # نسبة نجاح %
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "position": self.position,
            "probability": float(self.probability or 0),
            "is_active": bool(self.is_active),
            "opportunities_count": len([o for o in self.opportunities if o.status != "lost"]),
        }


class Lead(db.Model):
    """العملاء المحتملون — Leads."""
    __tablename__ = "crm_leads"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    company = db.Column(db.String(150))
    source = db.Column(db.String(50), default="other")  # website|facebook|call|walk_in|referral|other
    status = db.Column(db.String(20), default="new", index=True)  # new|contacted|qualified|unqualified|won|lost
    owner_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    budget = db.Column(db.Numeric(15, 2), default=0)
    city = db.Column(db.String(80))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    owner = db.relationship("Employee", backref="crm_leads")

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "phone": self.phone,
            "email": self.email,
            "company": self.company,
            "source": self.source,
            "status": self.status,
            "owner_id": self.owner_id,
            "owner_name": self.owner.full_name if self.owner else None,
            "budget": float(self.budget or 0),
            "city": self.city,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Opportunity(db.Model):
    """فرص البيع — Opportunities (مرتبطة بمرحلة Pipeline)."""
    __tablename__ = "crm_opportunities"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("crm_leads.id"), index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(15, 2), default=0)
    stage_id = db.Column(db.Integer, db.ForeignKey("crm_pipeline_stages.id"), index=True)
    probability = db.Column(db.Numeric(5, 2), default=0)
    expected_close_date = db.Column(db.Date)
    owner_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    status = db.Column(db.String(20), default="open", index=True)  # open|won|lost
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    lead = db.relationship("Lead", backref="opportunities")
    customer = db.relationship("Customer", backref="crm_opportunities")
    stage = db.relationship("CrmPipelineStage", backref="opportunities")
    owner = db.relationship("Employee", backref="crm_opportunities")

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "lead_name": self.lead.full_name if self.lead else None,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "title": self.title,
            "amount": float(self.amount or 0),
            "stage_id": self.stage_id,
            "stage_name": self.stage.name if self.stage else None,
            "stage_position": self.stage.position if self.stage else None,
            "probability": float(self.probability if self.probability is not None else (self.stage.probability if self.stage else 0)),
            "expected_close_date": self.expected_close_date.isoformat() if self.expected_close_date else None,
            "owner_id": self.owner_id,
            "owner_name": self.owner.full_name if self.owner else None,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CallLog(db.Model):
    """المكالمات — سجل المكالمات مع العملاء."""
    __tablename__ = "crm_calls"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("crm_leads.id"), index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    direction = db.Column(db.String(10), default="out")  # in|out
    duration = db.Column(db.Integer, default=0)  # بالثواني
    call_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="crm_calls")
    lead = db.relationship("Lead", backref="calls")
    employee = db.relationship("Employee", backref="crm_calls")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "lead_id": self.lead_id,
            "lead_name": self.lead.full_name if self.lead else None,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "direction": self.direction,
            "duration": self.duration,
            "call_date": self.call_date.isoformat() if self.call_date else None,
            "notes": self.notes,
            "follow_up_date": self.follow_up_date.isoformat() if self.follow_up_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Meeting(db.Model):
    """الاجتماعات — اجتماعات مع العملاء."""
    __tablename__ = "crm_meetings"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("crm_leads.id"), index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    title = db.Column(db.String(200), nullable=False)
    meeting_date = db.Column(db.DateTime)
    location = db.Column(db.String(150))
    status = db.Column(db.String(20), default="scheduled", index=True)  # scheduled|done|cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="crm_meetings")
    lead = db.relationship("Lead", backref="meetings")
    employee = db.relationship("Employee", backref="crm_meetings")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "lead_id": self.lead_id,
            "lead_name": self.lead.full_name if self.lead else None,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "title": self.title,
            "meeting_date": self.meeting_date.isoformat() if self.meeting_date else None,
            "location": self.location,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CrmTask(db.Model):
    """المهام — مهام المتابعة على العملاء."""
    __tablename__ = "crm_tasks"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("crm_leads.id"), index=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("crm_opportunities.id"), index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(10), default="medium")  # low|medium|high
    status = db.Column(db.String(20), default="pending", index=True)  # pending|in_progress|done|cancelled
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="crm_tasks")
    lead = db.relationship("Lead", backref="tasks")
    opportunity = db.relationship("Opportunity", backref="tasks")
    employee = db.relationship("Employee", backref="crm_tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "lead_id": self.lead_id,
            "lead_name": self.lead.full_name if self.lead else None,
            "opportunity_id": self.opportunity_id,
            "opportunity_title": self.opportunity.title if self.opportunity else None,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Campaign(db.Model):
    """الحملات التسويقية."""
    __tablename__ = "crm_campaigns"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    channel = db.Column(db.String(30), default="social")  # email|sms|social|call|other
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    budget = db.Column(db.Numeric(15, 2), default=0)
    owner_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    status = db.Column(db.String(20), default="planned", index=True)  # planned|active|completed|cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    owner = db.relationship("Employee", backref="crm_campaigns")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "channel": self.channel,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "budget": float(self.budget or 0),
            "owner_id": self.owner_id,
            "owner_name": self.owner.full_name if self.owner else None,
            "status": self.status,
            "leads_count": len(self.campaign_leads),
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CampaignLead(db.Model):
    """ربط العملاء المحتملين بالحملات."""
    __tablename__ = "crm_campaign_leads"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("crm_campaigns.id"), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("crm_leads.id"), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    campaign = db.relationship("Campaign", backref="campaign_leads")
    lead = db.relationship("Lead", backref="campaign_leads")

    def to_dict(self):
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign.name if self.campaign else None,
            "lead_id": self.lead_id,
            "lead_name": self.lead.full_name if self.lead else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FollowUp(db.Model):
    """المتابعة — مواعيد المتابعة المجدولة."""
    __tablename__ = "crm_follow_ups"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("crm_leads.id"), index=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("crm_opportunities.id"), index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    follow_up_date = db.Column(db.Date)
    action_type = db.Column(db.String(20), default="call")  # call|meeting|email|whatsapp|visit
    status = db.Column(db.String(20), default="pending", index=True)  # pending|done|overdue
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="crm_follow_ups")
    lead = db.relationship("Lead", backref="follow_ups")
    opportunity = db.relationship("Opportunity", backref="follow_ups")
    employee = db.relationship("Employee", backref="crm_follow_ups")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "lead_id": self.lead_id,
            "lead_name": self.lead.full_name if self.lead else None,
            "opportunity_id": self.opportunity_id,
            "opportunity_title": self.opportunity.title if self.opportunity else None,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "follow_up_date": self.follow_up_date.isoformat() if self.follow_up_date else None,
            "action_type": self.action_type,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Quote(db.Model):
    """العروض السعرية."""
    __tablename__ = "crm_quotes"

    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("crm_leads.id"), index=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("crm_opportunities.id"), index=True)
    title = db.Column(db.String(200))
    valid_until = db.Column(db.Date)
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    discount = db.Column(db.Numeric(15, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    status = db.Column(db.String(20), default="draft", index=True)  # draft|sent|accepted|rejected|expired
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="crm_quotes")
    lead = db.relationship("Lead", backref="quotes")
    opportunity = db.relationship("Opportunity", backref="quotes")

    def total(self):
        subtotal = float(self.subtotal or 0)
        discount = float(self.discount or 0)
        tax = subtotal * float(self.tax_rate or 0) / 100
        return round(subtotal - discount + tax, 2)

    def to_dict(self):
        return {
            "id": self.id,
            "quote_number": self.quote_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "lead_id": self.lead_id,
            "lead_name": self.lead.full_name if self.lead else None,
            "opportunity_id": self.opportunity_id,
            "opportunity_title": self.opportunity.title if self.opportunity else None,
            "title": self.title,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "subtotal": float(self.subtotal or 0),
            "discount": float(self.discount or 0),
            "tax_rate": float(self.tax_rate or 0),
            "tax_amount": round(float(self.subtotal or 0) * float(self.tax_rate or 0) / 100, 2),
            "total": self.total(),
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class QuoteItem(db.Model):
    """بنود العروض."""
    __tablename__ = "crm_quote_items"

    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("crm_quotes.id"), index=True)
    description = db.Column(db.String(250), nullable=False)
    qty = db.Column(db.Numeric(12, 2), default=1)
    unit_price = db.Column(db.Numeric(15, 2), default=0)

    quote = db.relationship("Quote", backref="items")

    def to_dict(self):
        return {
            "id": self.id,
            "quote_id": self.quote_id,
            "description": self.description,
            "qty": float(self.qty or 1),
            "unit_price": float(self.unit_price or 0),
            "total": round(float(self.qty or 1) * float(self.unit_price or 0), 2),
        }


class CrmContract(db.Model):
    """عقود CRM — عقود خدمات/مبيعات عامة."""
    __tablename__ = "crm_contracts"

    id = db.Column(db.Integer, primary_key=True)
    contract_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("crm_quotes.id"), index=True)
    title = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    value = db.Column(db.Numeric(15, 2), default=0)
    status = db.Column(db.String(20), default="draft", index=True)  # draft|active|completed|expired|terminated
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="crm_contracts")
    quote = db.relationship("Quote", backref="contracts")

    def to_dict(self):
        return {
            "id": self.id,
            "contract_number": self.contract_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "quote_id": self.quote_id,
            "quote_number": self.quote.quote_number if self.quote else None,
            "title": self.title,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "value": float(self.value or 0),
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Complaint(db.Model):
    """الشكاوى."""
    __tablename__ = "crm_complaints"

    id = db.Column(db.Integer, primary_key=True)
    complaint_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    priority = db.Column(db.String(10), default="medium")  # low|medium|high
    status = db.Column(db.String(20), default="open", index=True)  # open|in_progress|resolved|closed
    assigned_to = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    created_date = db.Column(db.Date)
    resolved_date = db.Column(db.Date)
    rating = db.Column(db.Integer, default=0)  # 1-5
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="crm_complaints")
    assignee = db.relationship("Employee", backref="crm_complaints")

    def to_dict(self):
        return {
            "id": self.id,
            "complaint_number": self.complaint_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "subject": self.subject,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "assignee_name": self.assignee.full_name if self.assignee else None,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "resolved_date": self.resolved_date.isoformat() if self.resolved_date else None,
            "rating": self.rating or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SupportTicket(db.Model):
    """تذاكر خدمة العملاء."""
    __tablename__ = "crm_tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), index=True)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    priority = db.Column(db.String(10), default="medium")  # low|medium|high
    status = db.Column(db.String(20), default="new", index=True)  # new|open|pending|resolved|closed
    assigned_to = db.Column(db.Integer, db.ForeignKey("employees.id"), index=True)
    created_date = db.Column(db.Date)
    resolved_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    customer = db.relationship("Customer", backref="crm_tickets")
    assignee = db.relationship("Employee", backref="crm_tickets")

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_number": self.ticket_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "subject": self.subject,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "assignee_name": self.assignee.full_name if self.assignee else None,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "resolved_date": self.resolved_date.isoformat() if self.resolved_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

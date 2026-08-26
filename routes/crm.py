from flask import Blueprint, request, jsonify
from datetime import datetime, date
from database import db
from models import (
    Customer, Employee,
    CrmPipelineStage, Lead, Opportunity, CallLog, Meeting,
    CrmTask, Campaign, CampaignLead, FollowUp,
    Quote, QuoteItem, CrmContract, Complaint, SupportTicket,
)
from permissions import require_api, require_api_any
from utils.pagination import paged_or_cap

crm_bp = Blueprint("crm_api", __name__, url_prefix="/api/crm")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:16], "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        return None


def parse_float(value, default=0):
    try:
        return float(value) if value not in (None, "") else default
    except (ValueError, TypeError):
        return default


def _log(action, entity, entity_id, description):
    from auditlog import log_action
    log_action(action, entity, entity_id, description)


def _next_number(model, prefix):
    from utils.docnum import seq_by_prefix
    year = datetime.now().year
    for c in ["quote_number", "contract_number", "complaint_number", "ticket_number"]:
        if hasattr(model, c):
            return seq_by_prefix(model, getattr(model, c), f"{prefix}-{year}-")
    return f"{prefix}-{year}-0001"


# ============ ملخص الوحدة ============

@crm_bp.route("/summary", methods=["GET"])
@require_api("crm", "view")
def summary():
    today = date.today()
    follow_ups = FollowUp.query.filter(FollowUp.status == "pending").all()
    overdue = sum(1 for f in follow_ups if f.follow_up_date and f.follow_up_date < today)
    due_today = sum(1 for f in follow_ups if f.follow_up_date == today)
    open_opps = Opportunity.query.filter_by(status="open").all()
    pipeline_total = sum(float(o.amount or 0) for o in open_opps)
    won_total = sum(
        float(o.amount or 0)
        for o in Opportunity.query.filter_by(status="won").all()
    )
    active_contracts = CrmContract.query.filter_by(status="active").all()
    return jsonify({
        "customers_count": Customer.query.count(),
        "leads_count": Lead.query.count(),
        "leads_open": Lead.query.filter(Lead.status.in_(["new", "contacted", "qualified"])).count(),
        "opportunities_count": Opportunity.query.count(),
        "opportunities_open": len(open_opps),
        "pipeline_total": round(pipeline_total, 2),
        "won_total": round(won_total, 2),
        "quotes_count": Quote.query.filter(Quote.status.in_(["draft", "sent"])).count(),
        "quotes_total": round(sum(q.total() for q in Quote.query.filter(Quote.status.in_(["draft", "sent"])).all()), 2),
        "contracts_count": len(active_contracts),
        "contracts_total": round(sum(float(c.value or 0) for c in active_contracts), 2),
        "complaints_open": Complaint.query.filter(Complaint.status.in_(["open", "in_progress"])).count(),
        "tickets_open": SupportTicket.query.filter(SupportTicket.status.in_(["new", "open", "pending"])).count(),
        "follow_ups_pending": len(follow_ups),
        "follow_ups_overdue": overdue,
        "follow_ups_today": due_today,
        "meetings_today": Meeting.query.filter(
            db.func.date(Meeting.meeting_date) == today,
            Meeting.status == "scheduled",
        ).count(),
    })


# ============ مراحل أنبوب البيع ============

@crm_bp.route("/stages", methods=["GET"])
@require_api("crm", "view")
def list_stages():
    stages = CrmPipelineStage.query.order_by(CrmPipelineStage.position).all()
    return jsonify([s.to_dict() for s in stages])


@crm_bp.route("/stages", methods=["POST"])
@require_api("crm", "create")
def create_stage():
    data = request.get_json() or {}
    stage = CrmPipelineStage(
        name=data.get("name"),
        position=int(data.get("position") or (CrmPipelineStage.query.count() + 1)),
        probability=parse_float(data.get("probability"), 0),
        is_active=data.get("is_active", True),
    )
    if not stage.name:
        return jsonify({"error": "invalid_name"}), 400
    db.session.add(stage)
    db.session.commit()
    _log("create", "pipeline_stage", stage.id, stage.name)
    return jsonify(stage.to_dict()), 201


@crm_bp.route("/stages/<int:stage_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_stage(stage_id):
    stage = CrmPipelineStage.query.get_or_404(stage_id)
    data = request.get_json() or {}
    for field in ["name", "position", "probability", "is_active"]:
        if field in data:
            setattr(stage, field, data[field])
    db.session.commit()
    _log("update", "pipeline_stage", stage.id, stage.name)
    return jsonify(stage.to_dict())


@crm_bp.route("/stages/<int:stage_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_stage(stage_id):
    stage = CrmPipelineStage.query.get_or_404(stage_id)
    if stage.opportunities:
        return jsonify({"error": "stage_has_opportunities"}), 400
    name = stage.name
    db.session.delete(stage)
    db.session.commit()
    _log("delete", "pipeline_stage", stage_id, name)
    return jsonify({"success": True})


# ============ العملاء المحتملون ============

@crm_bp.route("/leads", methods=["GET"])
@require_api("crm", "view")
def list_leads():
    q = Lead.query.order_by(Lead.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/leads", methods=["POST"])
@require_api("crm", "create")
def create_lead():
    data = request.get_json() or {}
    lead = Lead(
        full_name=data.get("full_name"),
        phone=data.get("phone"),
        email=data.get("email"),
        company=data.get("company"),
        source=data.get("source", "other"),
        status=data.get("status", "new"),
        owner_id=data.get("owner_id") or None,
        budget=parse_float(data.get("budget")),
        city=data.get("city"),
        notes=data.get("notes"),
    )
    if not lead.full_name:
        return jsonify({"error": "invalid_name"}), 400
    db.session.add(lead)
    db.session.commit()
    _log("create", "lead", lead.id, lead.full_name)
    return jsonify(lead.to_dict()), 201


@crm_bp.route("/leads/<int:lead_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json() or {}
    for field in ["full_name", "phone", "email", "company", "source", "status",
                  "owner_id", "budget", "city", "notes"]:
        if field in data:
            setattr(lead, field, data[field])
    db.session.commit()
    _log("update", "lead", lead.id, lead.full_name)
    return jsonify(lead.to_dict())


@crm_bp.route("/leads/<int:lead_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if lead.opportunities:
        return jsonify({"error": "lead_has_opportunities"}), 400
    if lead.quotes:
        return jsonify({"error": "lead_has_quotes"}), 400
    name = lead.full_name
    for cls in [CallLog, Meeting, CrmTask, FollowUp, CampaignLead]:
        for rel in cls.query.filter_by(lead_id=lead_id).all():
            db.session.delete(rel)
    db.session.delete(lead)
    db.session.commit()
    _log("delete", "lead", lead_id, name)
    return jsonify({"success": True})


@crm_bp.route("/leads/<int:lead_id>/convert", methods=["POST"])
@require_api("crm", "create")
def convert_lead(lead_id):
    """تحويل عميل محتمل إلى عميل + فرصة بيع في المرحلة الأولى."""
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json() or {}
    customer = None
    if data.get("customer_id"):
        customer = db.session.get(Customer, data.get("customer_id"))
    if not customer:
        customer = Customer(
            full_name=data.get("full_name") or lead.full_name,
            phone=data.get("phone") or lead.phone,
            email=data.get("email") or lead.email,
            company=data.get("company") or lead.company,
            address=data.get("address"),
            type=data.get("type", "individual"),
            notes=data.get("notes") or lead.notes,
        )
        db.session.add(customer)
        db.session.flush()
    stage = CrmPipelineStage.query.order_by(CrmPipelineStage.position).first()
    opportunity = Opportunity(
        lead_id=lead.id,
        customer_id=customer.id,
        title=data.get("title") or f"فرصة مع {lead.full_name}",
        amount=parse_float(data.get("amount"), lead.budget),
        stage_id=stage.id if stage else None,
        expected_close_date=parse_date(data.get("expected_close_date")),
        owner_id=data.get("owner_id") or lead.owner_id,
        status="open",
        notes=data.get("notes") or lead.notes,
    )
    db.session.add(opportunity)
    lead.status = "qualified"
    db.session.commit()
    _log("convert", "lead", lead.id, f"{lead.full_name} -> عميل + فرصة")
    return jsonify({"customer": customer.to_dict(), "opportunity": opportunity.to_dict()}), 201


# ============ فرص البيع ============

@crm_bp.route("/opportunities", methods=["GET"])
@require_api("crm", "view")
def list_opportunities():
    q = Opportunity.query.order_by(Opportunity.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/opportunities", methods=["POST"])
@require_api("crm", "create")
def create_opportunity():
    data = request.get_json() or {}
    stage_id = data.get("stage_id")
    stage = db.session.get(CrmPipelineStage, stage_id) if stage_id else None
    opportunity = Opportunity(
        lead_id=data.get("lead_id") or None,
        customer_id=data.get("customer_id") or None,
        title=data.get("title"),
        amount=parse_float(data.get("amount")),
        stage_id=stage.id if stage else None,
        probability=parse_float(
            data.get("probability"),
            float(stage.probability) if stage and stage.probability else 0,
        ),
        expected_close_date=parse_date(data.get("expected_close_date")),
        owner_id=data.get("owner_id") or None,
        status=data.get("status", "open"),
        notes=data.get("notes"),
    )
    if not opportunity.title:
        return jsonify({"error": "invalid_title"}), 400
    db.session.add(opportunity)
    db.session.commit()
    _log("create", "opportunity", opportunity.id, opportunity.title)
    return jsonify(opportunity.to_dict()), 201


@crm_bp.route("/opportunities/<int:opp_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_opportunity(opp_id):
    opportunity = Opportunity.query.get_or_404(opp_id)
    data = request.get_json() or {}
    for field in ["lead_id", "customer_id", "title", "amount", "stage_id",
                  "probability", "expected_close_date", "owner_id", "status", "notes"]:
        if field in data:
            setattr(opportunity, field, data[field])
    if "stage_id" in data and data["stage_id"]:
        stage = db.session.get(CrmPipelineStage, data["stage_id"])
        if stage and "probability" not in data:
            opportunity.probability = stage.probability
    db.session.commit()
    _log("update", "opportunity", opportunity.id, opportunity.title)
    return jsonify(opportunity.to_dict())


@crm_bp.route("/opportunities/<int:opp_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_opportunity(opp_id):
    opportunity = Opportunity.query.get_or_404(opp_id)
    if opportunity.quotes:
        return jsonify({"error": "opportunity_has_quotes"}), 400
    title = opportunity.title
    for cls in [CrmTask, FollowUp]:
        for rel in cls.query.filter_by(opportunity_id=opp_id).all():
            db.session.delete(rel)
    db.session.delete(opportunity)
    db.session.commit()
    _log("delete", "opportunity", opp_id, title)
    return jsonify({"success": True})


@crm_bp.route("/opportunities/<int:opp_id>/stage", methods=["POST"])
@require_api("crm", "edit")
def move_opportunity_stage(opp_id):
    opportunity = Opportunity.query.get_or_404(opp_id)
    data = request.get_json() or {}
    stage = CrmPipelineStage.query.get_or_404(data.get("stage_id"))
    opportunity.stage_id = stage.id
    opportunity.probability = stage.probability
    db.session.commit()
    _log("update", "opportunity", opportunity.id, f"تقدم للمرحلة: {stage.name}")
    return jsonify(opportunity.to_dict())


@crm_bp.route("/opportunities/<int:opp_id>/win", methods=["POST"])
@require_api("crm", "edit")
def win_opportunity(opp_id):
    opportunity = Opportunity.query.get_or_404(opp_id)
    opportunity.status = "won"
    opportunity.probability = 100
    if opportunity.lead:
        opportunity.lead.status = "won"
    db.session.commit()
    _log("update", "opportunity", opportunity.id, "فوز بالفرصة")
    return jsonify(opportunity.to_dict())


@crm_bp.route("/opportunities/<int:opp_id>/lose", methods=["POST"])
@require_api("crm", "edit")
def lose_opportunity(opp_id):
    opportunity = Opportunity.query.get_or_404(opp_id)
    opportunity.status = "lost"
    db.session.commit()
    _log("update", "opportunity", opportunity.id, "خسارة الفرصة")
    return jsonify(opportunity.to_dict())


# ============ المكالمات ============

@crm_bp.route("/calls", methods=["GET"])
@require_api("crm", "view")
def list_calls():
    q = CallLog.query.order_by(CallLog.call_date.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/calls", methods=["POST"])
@require_api("crm", "create")
def create_call():
    data = request.get_json() or {}
    call = CallLog(
        customer_id=data.get("customer_id") or None,
        lead_id=data.get("lead_id") or None,
        employee_id=data.get("employee_id") or None,
        direction=data.get("direction", "out"),
        duration=int(data.get("duration") or 0),
        call_date=parse_datetime(data.get("call_date")) or datetime.now(),
        notes=data.get("notes"),
        follow_up_date=parse_date(data.get("follow_up_date")),
    )
    if not call.customer_id and not call.lead_id:
        return jsonify({"error": "call_needs_party"}), 400
    db.session.add(call)
    if call.follow_up_date:
        db.session.add(FollowUp(
            customer_id=call.customer_id,
            lead_id=call.lead_id,
            employee_id=call.employee_id,
            follow_up_date=call.follow_up_date,
            action_type="call",
            status="pending",
            notes=f"متابعة مكالمة: {call.notes or ''}",
        ))
    db.session.commit()
    _log("create", "call", call.id, f"مكالمة مع {call.customer.full_name if call.customer else (call.lead.full_name if call.lead else '')}")
    return jsonify(call.to_dict()), 201


@crm_bp.route("/calls/<int:call_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_call(call_id):
    call = CallLog.query.get_or_404(call_id)
    data = request.get_json() or {}
    for field in ["customer_id", "lead_id", "employee_id", "direction", "duration",
                  "call_date", "notes", "follow_up_date"]:
        if field in data:
            setattr(call, field, data[field])
    db.session.commit()
    _log("update", "call", call.id, "تحديث مكالمة")
    return jsonify(call.to_dict())


@crm_bp.route("/calls/<int:call_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_call(call_id):
    call = CallLog.query.get_or_404(call_id)
    db.session.delete(call)
    db.session.commit()
    _log("delete", "call", call_id, "حذف مكالمة")
    return jsonify({"success": True})


# ============ الاجتماعات ============

@crm_bp.route("/meetings", methods=["GET"])
@require_api("crm", "view")
def list_meetings():
    q = Meeting.query.order_by(Meeting.meeting_date.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/meetings", methods=["POST"])
@require_api("crm", "create")
def create_meeting():
    data = request.get_json() or {}
    meeting = Meeting(
        customer_id=data.get("customer_id") or None,
        lead_id=data.get("lead_id") or None,
        employee_id=data.get("employee_id") or None,
        title=data.get("title"),
        meeting_date=parse_datetime(data.get("meeting_date")) or datetime.now(),
        location=data.get("location"),
        status=data.get("status", "scheduled"),
        notes=data.get("notes"),
    )
    if not meeting.title:
        return jsonify({"error": "invalid_title"}), 400
    db.session.add(meeting)
    db.session.commit()
    _log("create", "meeting", meeting.id, meeting.title)
    return jsonify(meeting.to_dict()), 201


@crm_bp.route("/meetings/<int:meeting_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_meeting(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    data = request.get_json() or {}
    for field in ["customer_id", "lead_id", "employee_id", "title", "meeting_date",
                  "location", "status", "notes"]:
        if field in data:
            setattr(meeting, field, data[field])
    db.session.commit()
    _log("update", "meeting", meeting.id, meeting.title)
    return jsonify(meeting.to_dict())


@crm_bp.route("/meetings/<int:meeting_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_meeting(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    db.session.delete(meeting)
    db.session.commit()
    _log("delete", "meeting", meeting_id, "حذف اجتماع")
    return jsonify({"success": True})


# ============ المهام ============

@crm_bp.route("/tasks", methods=["GET"])
@require_api("crm", "view")
def list_tasks():
    q = CrmTask.query.order_by(CrmTask.due_date.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/tasks", methods=["POST"])
@require_api("crm", "create")
def create_task():
    data = request.get_json() or {}
    task = CrmTask(
        customer_id=data.get("customer_id") or None,
        lead_id=data.get("lead_id") or None,
        opportunity_id=data.get("opportunity_id") or None,
        employee_id=data.get("employee_id") or None,
        title=data.get("title"),
        description=data.get("description"),
        due_date=parse_date(data.get("due_date")),
        priority=data.get("priority", "medium"),
        status=data.get("status", "pending"),
    )
    if not task.title:
        return jsonify({"error": "invalid_title"}), 400
    db.session.add(task)
    db.session.commit()
    _log("create", "task", task.id, task.title)
    return jsonify(task.to_dict()), 201


@crm_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_task(task_id):
    task = CrmTask.query.get_or_404(task_id)
    data = request.get_json() or {}
    for field in ["customer_id", "lead_id", "opportunity_id", "employee_id", "title",
                  "description", "due_date", "priority", "status"]:
        if field in data:
            setattr(task, field, data[field])
    db.session.commit()
    _log("update", "task", task.id, task.title)
    return jsonify(task.to_dict())


@crm_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_task(task_id):
    task = CrmTask.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    _log("delete", "task", task_id, "حذف مهمة")
    return jsonify({"success": True})


# ============ الحملات ============

@crm_bp.route("/campaigns", methods=["GET"])
@require_api("crm", "view")
def list_campaigns():
    q = Campaign.query.order_by(Campaign.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/campaigns", methods=["POST"])
@require_api("crm", "create")
def create_campaign():
    data = request.get_json() or {}
    campaign = Campaign(
        name=data.get("name"),
        description=data.get("description"),
        channel=data.get("channel", "social"),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        budget=parse_float(data.get("budget")),
        owner_id=data.get("owner_id") or None,
        status=data.get("status", "planned"),
        notes=data.get("notes"),
    )
    if not campaign.name:
        return jsonify({"error": "invalid_name"}), 400
    db.session.add(campaign)
    db.session.commit()
    _log("create", "campaign", campaign.id, campaign.name)
    return jsonify(campaign.to_dict()), 201


@crm_bp.route("/campaigns/<int:campaign_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    data = request.get_json() or {}
    for field in ["name", "description", "channel", "start_date", "end_date",
                  "budget", "owner_id", "status", "notes"]:
        if field in data:
            setattr(campaign, field, data[field])
    db.session.commit()
    _log("update", "campaign", campaign.id, campaign.name)
    return jsonify(campaign.to_dict())


@crm_bp.route("/campaigns/<int:campaign_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    name = campaign.name
    for rel in campaign.campaign_leads:
        db.session.delete(rel)
    db.session.delete(campaign)
    db.session.commit()
    _log("delete", "campaign", campaign_id, name)
    return jsonify({"success": True})


# ============ ربط الحملات بالعملاء المحتملين ============

@crm_bp.route("/campaign-leads", methods=["GET"])
@require_api("crm", "view")
def list_campaign_leads():
    q = CampaignLead.query.order_by(CampaignLead.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/campaign-leads", methods=["POST"])
@require_api("crm", "create")
def create_campaign_lead():
    data = request.get_json() or {}
    campaign = Campaign.query.get_or_404(data.get("campaign_id"))
    lead = Lead.query.get_or_404(data.get("lead_id"))
    existing = CampaignLead.query.filter_by(
        campaign_id=campaign.id, lead_id=lead.id
    ).first()
    if existing:
        return jsonify(existing.to_dict()), 200
    row = CampaignLead(campaign_id=campaign.id, lead_id=lead.id)
    db.session.add(row)
    db.session.commit()
    _log("create", "campaign_lead", row.id, f"{campaign.name} <- {lead.full_name}")
    return jsonify(row.to_dict()), 201


@crm_bp.route("/campaign-leads/<int:row_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_campaign_lead(row_id):
    row = CampaignLead.query.get_or_404(row_id)
    db.session.delete(row)
    db.session.commit()
    _log("delete", "campaign_lead", row_id, "فك ربط حملة بعميل محتمل")
    return jsonify({"success": True})


# ============ المتابعة ============

@crm_bp.route("/follow-ups", methods=["GET"])
@require_api("crm", "view")
def list_follow_ups():
    q = FollowUp.query.order_by(FollowUp.follow_up_date.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/follow-ups", methods=["POST"])
@require_api("crm", "create")
def create_follow_up():
    data = request.get_json() or {}
    row = FollowUp(
        customer_id=data.get("customer_id") or None,
        lead_id=data.get("lead_id") or None,
        opportunity_id=data.get("opportunity_id") or None,
        employee_id=data.get("employee_id") or None,
        follow_up_date=parse_date(data.get("follow_up_date")),
        action_type=data.get("action_type", "call"),
        status=data.get("status", "pending"),
        notes=data.get("notes"),
    )
    if not row.follow_up_date:
        return jsonify({"error": "follow_up_needs_date"}), 400
    db.session.add(row)
    db.session.commit()
    _log("create", "follow_up", row.id, f"متابعة في {row.follow_up_date}")
    return jsonify(row.to_dict()), 201


@crm_bp.route("/follow-ups/<int:follow_up_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_follow_up(follow_up_id):
    row = FollowUp.query.get_or_404(follow_up_id)
    data = request.get_json() or {}
    for field in ["customer_id", "lead_id", "opportunity_id", "employee_id",
                  "follow_up_date", "action_type", "status", "notes"]:
        if field in data:
            setattr(row, field, data[field])
    db.session.commit()
    _log("update", "follow_up", row.id, "تحديث متابعة")
    return jsonify(row.to_dict())


@crm_bp.route("/follow-ups/<int:follow_up_id>/done", methods=["POST"])
@require_api("crm", "edit")
def complete_follow_up(follow_up_id):
    row = FollowUp.query.get_or_404(follow_up_id)
    row.status = "done"
    db.session.commit()
    _log("update", "follow_up", row.id, "إنجاز المتابعة")
    return jsonify(row.to_dict())


@crm_bp.route("/follow-ups/<int:follow_up_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_follow_up(follow_up_id):
    row = FollowUp.query.get_or_404(follow_up_id)
    db.session.delete(row)
    db.session.commit()
    _log("delete", "follow_up", follow_up_id, "حذف متابعة")
    return jsonify({"success": True})


# ============ العروض ============

@crm_bp.route("/quotes", methods=["GET"])
@require_api_any("view", ["crm", "sales"])
def list_quotes():
    q = Quote.query.order_by(Quote.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/quotes", methods=["POST"])
@require_api_any("create", ["crm", "sales"])
def create_quote():
    data = request.get_json() or {}
    quote = Quote(
        quote_number=_next_number(Quote, "QT"),
        customer_id=data.get("customer_id") or None,
        lead_id=data.get("lead_id") or None,
        opportunity_id=data.get("opportunity_id") or None,
        title=data.get("title"),
        valid_until=parse_date(data.get("valid_until")),
        subtotal=parse_float(data.get("subtotal")),
        discount=parse_float(data.get("discount")),
        tax_rate=parse_float(data.get("tax_rate")),
        status=data.get("status", "draft"),
        notes=data.get("notes"),
    )
    db.session.add(quote)
    db.session.flush()
    for item in data.get("items", []) or []:
        if not item.get("description"):
            continue
        db.session.add(QuoteItem(
            quote_id=quote.id,
            description=item.get("description"),
            qty=parse_float(item.get("qty"), 1),
            unit_price=parse_float(item.get("unit_price")),
        ))
    _recalc_quote(quote)
    db.session.commit()
    _log("create", "quote", quote.id, quote.quote_number)
    return jsonify(quote.to_dict()), 201


@crm_bp.route("/quotes/<int:quote_id>", methods=["PUT"])
@require_api_any("edit", ["crm", "sales"])
def update_quote(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    data = request.get_json() or {}
    for field in ["customer_id", "lead_id", "opportunity_id", "title", "valid_until",
                  "subtotal", "discount", "tax_rate", "status", "notes"]:
        if field in data:
            setattr(quote, field, data[field])
    if "items" in data:
        for item in quote.items:
            db.session.delete(item)
        db.session.flush()
        for item in data.get("items", []) or []:
            if not item.get("description"):
                continue
            db.session.add(QuoteItem(
                quote_id=quote.id,
                description=item.get("description"),
                qty=parse_float(item.get("qty"), 1),
                unit_price=parse_float(item.get("unit_price")),
            ))
    _recalc_quote(quote)
    db.session.commit()
    _log("update", "quote", quote.id, quote.quote_number)
    return jsonify(quote.to_dict())


def _recalc_quote(quote):
    subtotal = sum(
        (float(i.qty or 1) * float(i.unit_price or 0)) for i in quote.items
    )
    quote.subtotal = round(subtotal, 2)


@crm_bp.route("/quotes/<int:quote_id>", methods=["DELETE"])
@require_api_any("delete", ["crm", "sales"])
def delete_quote(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    if quote.contracts:
        return jsonify({"error": "quote_has_contracts"}), 400
    number = quote.quote_number
    for item in quote.items:
        db.session.delete(item)
    db.session.delete(quote)
    db.session.commit()
    _log("delete", "quote", quote_id, number)
    return jsonify({"success": True})


@crm_bp.route("/quotes/<int:quote_id>/accept", methods=["POST"])
@require_api_any("edit", ["crm", "sales"])
def accept_quote(quote_id):
    """قبول عرض → إنشاء عقد + ربح الفرصة المرتبطة."""
    quote = Quote.query.get_or_404(quote_id)
    if not quote.customer_id:
        return jsonify({"error": "quote_needs_customer"}), 400
    if quote.contracts:
        return jsonify({"error": "quote_already_contracted"}), 400
    contract = CrmContract(
        contract_number=_next_number(CrmContract, "CT"),
        customer_id=quote.customer_id,
        quote_id=quote.id,
        title=quote.title or (quote.opportunity.title if quote.opportunity else "عقد"),
        start_date=date.today(),
        value=quote.total(),
        status="active",
        notes=quote.notes,
    )
    db.session.add(contract)
    quote.status = "accepted"
    if quote.opportunity:
        quote.opportunity.status = "won"
        quote.opportunity.probability = 100
        if quote.opportunity.lead:
            quote.opportunity.lead.status = "won"
    db.session.commit()
    _log("create", "contract", contract.id, contract.contract_number)
    return jsonify({"quote": quote.to_dict(), "contract": contract.to_dict()})


@crm_bp.route("/quotes/<int:quote_id>/reject", methods=["POST"])
@require_api("crm", "edit")
def reject_quote(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    quote.status = "rejected"
    db.session.commit()
    _log("update", "quote", quote.id, "رفض العرض")
    return jsonify(quote.to_dict())


# ============ العقود ============

@crm_bp.route("/contracts", methods=["GET"])
@require_api("crm", "view")
def list_contracts():
    q = CrmContract.query.order_by(CrmContract.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/contracts", methods=["POST"])
@require_api("crm", "create")
def create_contract():
    data = request.get_json() or {}
    contract = CrmContract(
        contract_number=data.get("contract_number") or _next_number(CrmContract, "CT"),
        customer_id=data.get("customer_id"),
        quote_id=data.get("quote_id") or None,
        title=data.get("title"),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        value=parse_float(data.get("value")),
        status=data.get("status", "draft"),
        notes=data.get("notes"),
    )
    if not contract.customer_id:
        return jsonify({"error": "contract_needs_customer"}), 400
    if not contract.title:
        return jsonify({"error": "invalid_title"}), 400
    db.session.add(contract)
    db.session.commit()
    _log("create", "contract", contract.id, contract.contract_number)
    return jsonify(contract.to_dict()), 201


@crm_bp.route("/contracts/<int:contract_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_contract(contract_id):
    contract = CrmContract.query.get_or_404(contract_id)
    data = request.get_json() or {}
    for field in ["customer_id", "quote_id", "title", "start_date", "end_date",
                  "value", "status", "notes"]:
        if field in data:
            setattr(contract, field, data[field])
    db.session.commit()
    _log("update", "contract", contract.id, contract.contract_number)
    return jsonify(contract.to_dict())


@crm_bp.route("/contracts/<int:contract_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_contract(contract_id):
    contract = CrmContract.query.get_or_404(contract_id)
    number = contract.contract_number
    db.session.delete(contract)
    db.session.commit()
    _log("delete", "contract", contract_id, number)
    return jsonify({"success": True})


# ============ الشكاوى ============

@crm_bp.route("/complaints", methods=["GET"])
@require_api("crm", "view")
def list_complaints():
    q = Complaint.query.order_by(Complaint.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/complaints", methods=["POST"])
@require_api("crm", "create")
def create_complaint():
    data = request.get_json() or {}
    complaint = Complaint(
        complaint_number=_next_number(Complaint, "CP"),
        customer_id=data.get("customer_id"),
        subject=data.get("subject"),
        description=data.get("description"),
        category=data.get("category"),
        priority=data.get("priority", "medium"),
        status=data.get("status", "open"),
        assigned_to=data.get("assigned_to") or None,
        created_date=parse_date(data.get("created_date")) or date.today(),
        rating=int(data.get("rating") or 0),
    )
    if not complaint.customer_id:
        return jsonify({"error": "complaint_needs_customer"}), 400
    if not complaint.subject:
        return jsonify({"error": "invalid_subject"}), 400
    db.session.add(complaint)
    db.session.commit()
    _log("create", "complaint", complaint.id, complaint.complaint_number)
    return jsonify(complaint.to_dict()), 201


@crm_bp.route("/complaints/<int:complaint_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    data = request.get_json() or {}
    for field in ["customer_id", "subject", "description", "category", "priority",
                  "status", "assigned_to", "created_date", "resolved_date", "rating"]:
        if field in data:
            setattr(complaint, field, data[field])
    if complaint.status in ("resolved", "closed") and not complaint.resolved_date:
        complaint.resolved_date = date.today()
    db.session.commit()
    _log("update", "complaint", complaint.id, complaint.complaint_number)
    return jsonify(complaint.to_dict())


@crm_bp.route("/complaints/<int:complaint_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    number = complaint.complaint_number
    db.session.delete(complaint)
    db.session.commit()
    _log("delete", "complaint", complaint_id, number)
    return jsonify({"success": True})


# ============ تذاكر خدمة العملاء ============

@crm_bp.route("/tickets", methods=["GET"])
@require_api("crm", "view")
def list_tickets():
    q = SupportTicket.query.order_by(SupportTicket.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@crm_bp.route("/tickets", methods=["POST"])
@require_api("crm", "create")
def create_ticket():
    data = request.get_json() or {}
    ticket = SupportTicket(
        ticket_number=_next_number(SupportTicket, "TK"),
        customer_id=data.get("customer_id"),
        subject=data.get("subject"),
        description=data.get("description"),
        category=data.get("category"),
        priority=data.get("priority", "medium"),
        status=data.get("status", "new"),
        assigned_to=data.get("assigned_to") or None,
        created_date=parse_date(data.get("created_date")) or date.today(),
    )
    if not ticket.customer_id:
        return jsonify({"error": "ticket_needs_customer"}), 400
    if not ticket.subject:
        return jsonify({"error": "invalid_subject"}), 400
    db.session.add(ticket)
    db.session.commit()
    _log("create", "ticket", ticket.id, ticket.ticket_number)
    return jsonify(ticket.to_dict()), 201


@crm_bp.route("/tickets/<int:ticket_id>", methods=["PUT"])
@require_api("crm", "edit")
def update_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    data = request.get_json() or {}
    for field in ["customer_id", "subject", "description", "category", "priority",
                  "status", "assigned_to", "created_date", "resolved_date"]:
        if field in data:
            setattr(ticket, field, data[field])
    if ticket.status in ("resolved", "closed") and not ticket.resolved_date:
        ticket.resolved_date = date.today()
    db.session.commit()
    _log("update", "ticket", ticket.id, ticket.ticket_number)
    return jsonify(ticket.to_dict())


@crm_bp.route("/tickets/<int:ticket_id>", methods=["DELETE"])
@require_api("crm", "delete")
def delete_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)
    number = ticket.ticket_number
    db.session.delete(ticket)
    db.session.commit()
    _log("delete", "ticket", ticket_id, number)
    return jsonify({"success": True})

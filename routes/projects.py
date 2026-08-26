import re
from datetime import datetime

from flask import Blueprint, request, jsonify
from sqlalchemy import Date as SqlDate

from database import db
from models import (
    Project, ProjectPhase, WBSItem, BoqItem, PriceAnalysisItem,
    Subcontractor, ProjectContract, ProgressStatement, ChangeOrder,
    ProjectProgress, ExecutionLog, ProjectCost, ProjectRisk,
    ProjectQuality, SiteLog, Equipment, LaborAssignment,
)
from permissions import require_api
from auditlog import log_action
from utils.pagination import paged_or_cap

projects_bp = Blueprint("projects", __name__, url_prefix="/api/projects")


def _clean_value(model, field, val):
    """Normalize incoming values (empty strings -> None, date strings -> date)."""
    if val is None:
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    col = model.__table__.columns.get(field)
    if col is not None and isinstance(col.type, SqlDate):
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    return val


def _commit_or_400(obj, action="save"):
    try:
        db.session.add(obj)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "فشل الحفظ، تحقق من البيانات"}), 400
    label = getattr(obj, "name", "") or getattr(obj, "description", "") or getattr(obj, "title", "") or str(obj.id or "")
    log_action(action, obj.__tablename__, obj.id, str(label))
    _recalc(obj)
    return None


def _recalc(obj):
    """Auto-update project spent/completion after related mutations."""
    if isinstance(obj, ProjectCost):
        pid = obj.project_id
        total = db.session.query(
            db.func.coalesce(db.func.sum(ProjectCost.amount), 0)
        ).filter_by(project_id=pid).scalar()
        proj = db.session.get(Project, pid)
        if proj:
            proj.spent = total
            db.session.commit()
    elif isinstance(obj, ProjectProgress):
        proj = db.session.get(Project, obj.project_id)
        if proj and obj.boq_id is None:
            proj.completion = obj.percentage or 0
            db.session.commit()


def register_crud(prefix, model, fields, parent_field=None):
    """Register generic list/create/update/delete routes for a model."""
    name = re.sub(r"[^A-Za-z0-9]+", "_", prefix.strip("/")).strip("_") or "item"

    def _list(**kw):
        q = model.query
        if parent_field and parent_field in kw:
            q = q.filter(getattr(model, parent_field) == kw[parent_field])
        items, envelope = paged_or_cap(q.order_by(model.id.desc()))
        return jsonify(envelope if envelope else items)

    def _create(**kw):
        data = request.get_json() or {}
        obj = model()
        for f in fields:
            if f in data:
                setattr(obj, f, _clean_value(model, f, data[f]))
        if parent_field and parent_field in kw:
            setattr(obj, parent_field, kw[parent_field])
        err = _commit_or_400(obj, "create")
        if err:
            return err
        return jsonify(obj.to_dict()), 201

    def _get(rid, **kw):
        return jsonify(model.query.get_or_404(rid).to_dict())

    def _update(rid, **kw):
        obj = model.query.get_or_404(rid)
        data = request.get_json() or {}
        for f in fields:
            if f in data:
                setattr(obj, f, _clean_value(model, f, data[f]))
        err = _commit_or_400(obj, "update")
        if err:
            return err
        return jsonify(obj.to_dict())

    def _delete(rid, **kw):
        obj = model.query.get_or_404(rid)
        try:
            db.session.delete(obj)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"message": "تعذر الحذف، قد يكون مرتبطاً ببيانات أخرى"}), 400
        log_action("delete", obj.__tablename__, rid, "")
        _recalc(obj)
        return jsonify({"success": True})

    _list.__name__ = f"{name}_list"
    _create.__name__ = f"{name}_create"
    _get.__name__ = f"{name}_get"
    _update.__name__ = f"{name}_update"
    _delete.__name__ = f"{name}_delete"

    projects_bp.add_url_rule(prefix, _list.__name__, require_api("projects", "view")(_list), methods=["GET"])
    projects_bp.add_url_rule(prefix, _create.__name__, require_api("projects", "create")(_create), methods=["POST"])
    projects_bp.add_url_rule(prefix + "/<int:rid>", _get.__name__, require_api("projects", "view")(_get), methods=["GET"])
    projects_bp.add_url_rule(prefix + "/<int:rid>", _update.__name__, require_api("projects", "edit")(_update), methods=["PUT"])
    projects_bp.add_url_rule(prefix + "/<int:rid>", _delete.__name__, require_api("projects", "delete")(_delete), methods=["DELETE"])


# ---- Basic project CRUD ----
@projects_bp.route("", methods=["GET"])
@require_api("projects", "view")
def list_projects():
    q = Project.query.order_by(Project.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@projects_bp.route("", methods=["POST"])
@require_api("projects", "create")
def create_project():
    data = request.get_json() or {}
    project = Project(
        name=data.get("name"),
        description=data.get("description"),
        location=data.get("location"),
        status=data.get("status", "active"),
        priority=data.get("priority", "medium"),
        budget=data.get("budget", 0),
        spent=data.get("spent", 0),
        manager_id=data.get("manager_id"),
        completion=data.get("completion", 0),
    )
    for f in ["start_date", "deadline"]:
        if data.get(f):
            setattr(project, f, _clean_value(Project, f, data[f]))
    db.session.add(project)
    db.session.commit()
    log_action("create", "project", project.id, project.name)
    return jsonify(project.to_dict()), 201


@projects_bp.route("/<int:project_id>", methods=["GET"])
@require_api("projects", "view")
def get_project(project_id):
    return jsonify(Project.query.get_or_404(project_id).to_dict())


@projects_bp.route("/<int:project_id>", methods=["PUT"])
@require_api("projects", "edit")
def update_project(project_id):
    project = Project.query.get_or_404(project_id)
    data = request.get_json() or {}
    for field in ["name", "description", "location", "status", "priority",
                  "budget", "spent", "manager_id", "completion", "start_date", "deadline"]:
        if field in data:
            setattr(project, field, _clean_value(Project, field, data[field]))
    db.session.commit()
    log_action("update", "project", project.id, project.name)
    return jsonify(project.to_dict())


def _cascade_delete_project(pid):
    """Delete all child rows of a project (FK-safe, order matters)."""
    boq_ids = [b[0] for b in db.session.query(BoqItem.id).filter_by(project_id=pid).all()]
    contract_ids = [c[0] for c in db.session.query(ProjectContract.id).filter_by(project_id=pid).all()]

    if boq_ids:
        PriceAnalysisItem.query.filter(PriceAnalysisItem.boq_id.in_(boq_ids)).delete(synchronize_session=False)
    if contract_ids:
        ProgressStatement.query.filter(ProgressStatement.contract_id.in_(contract_ids)).delete(synchronize_session=False)
    BoqItem.query.filter_by(project_id=pid).delete(synchronize_session=False)
    WBSItem.query.filter_by(project_id=pid).delete(synchronize_session=False)
    ProjectProgress.query.filter_by(project_id=pid).delete(synchronize_session=False)
    ChangeOrder.query.filter_by(project_id=pid).delete(synchronize_session=False)
    ProjectContract.query.filter_by(project_id=pid).delete(synchronize_session=False)
    ProjectPhase.query.filter_by(project_id=pid).delete(synchronize_session=False)
    ExecutionLog.query.filter_by(project_id=pid).delete(synchronize_session=False)
    ProjectCost.query.filter_by(project_id=pid).delete(synchronize_session=False)
    ProjectRisk.query.filter_by(project_id=pid).delete(synchronize_session=False)
    ProjectQuality.query.filter_by(project_id=pid).delete(synchronize_session=False)
    SiteLog.query.filter_by(project_id=pid).delete(synchronize_session=False)
    LaborAssignment.query.filter_by(project_id=pid).delete(synchronize_session=False)
    # equipment is shared globally -> just unassign
    for eq in Equipment.query.filter_by(project_id=pid).all():
        eq.project_id = None


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
@require_api("projects", "delete")
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    name = project.name
    try:
        _cascade_delete_project(project_id)
        db.session.delete(project)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "تعذر حذف المشروع لوجود بيانات مرتبطة"}), 400
    log_action("delete", "project", project_id, name)
    return jsonify({"success": True})


# ---- Project summary / workspace ----
@projects_bp.route("/<int:project_id>/statements", methods=["GET"])
@require_api("projects", "view")
def list_project_statements(project_id):
    rows = (
        db.session.query(ProgressStatement, ProjectContract)
        .join(ProjectContract, ProgressStatement.contract_id == ProjectContract.id)
        .filter(ProjectContract.project_id == project_id)
        .order_by(ProgressStatement.statement_date.desc(), ProgressStatement.id.desc())
        .all()
    )
    out = []
    for st, ct in rows:
        d = st.to_dict()
        d["contract_no"] = ct.contract_no
        d["contract_title"] = ct.title
        out.append(d)
    return jsonify(out)


@projects_bp.route("/<int:project_id>/schedule", methods=["GET"])
@require_api("projects", "view")
def project_schedule(project_id):
    """الجدولة الزمنية للمشروع (بيانات Gantt) + مؤشرات التأخر.

    يعيد: مراحل المشروع بأبعادها الزمنية، إجمالي المدة، التقدم الفعلي مقابل
    المتوقع بحساب اليوم (SV زمني)، وأي مرحلة متأخرة عن خطتها.
    """
    from datetime import datetime as _dt
    project = Project.query.get_or_404(project_id)
    today = _dt.now().date()

    phases = (ProjectPhase.query.filter_by(project_id=project_id)
              .order_by(ProjectPhase.order.asc(), ProjectPhase.id.asc()).all())
    rows, min_d, max_d = [], None, None
    for ph in phases:
        if ph.start_date and (min_d is None or ph.start_date < min_d):
            min_d = ph.start_date
        if ph.end_date and (max_d is None or ph.end_date > max_d):
            max_d = ph.end_date
        # المتوقع نظرياً: نسبة الوقت المنقضي من مدة المرحلة (مقيدة 0-100)
        expected = None
        if ph.start_date and ph.end_date:
            span = (ph.end_date - ph.start_date).days or 1
            elapsed = (min(today, ph.end_date) - ph.start_date).days
            expected = max(0, min(100, round(elapsed / span * 100)))
        late = bool(expected is not None and (ph.completion or 0) < expected - 10)
        rows.append({
            "id": ph.id,
            "name": ph.name,
            "order": ph.order,
            "start_date": ph.start_date.isoformat() if ph.start_date else None,
            "end_date": ph.end_date.isoformat() if ph.end_date else None,
            "status": ph.status,
            "completion": ph.completion or 0,
            "expected_completion": expected,
            "is_late": late,
        })

    total_days = ((max_d - min_d).days + 1) if (min_d and max_d) else None
    elapsed_days = ((min(today, max_d) - min_d).days + 1) if (min_d and max_d and today >= min_d) else 0
    overall_completion = round(sum(r["completion"] for r in rows) / len(rows)) if rows else 0
    timeline_expected = round(elapsed_days / total_days * 100) if total_days and project.start_date else None

    late_phases = [r["name"] for r in rows if r["is_late"]]
    return jsonify({
        "project_id": project_id,
        "project_start": project.start_date.isoformat() if project.start_date else None,
        "timeline_start": min_d.isoformat() if min_d else None,
        "timeline_end": max_d.isoformat() if max_d else None,
        "total_days": total_days,
        "elapsed_days": elapsed_days,
        "overall_completion": overall_completion,
        "timeline_expected_completion": timeline_expected,
        "schedule_variance": (overall_completion - timeline_expected) if timeline_expected is not None else None,
        "late_phases": late_phases,
        "on_track": not late_phases,
        "phases": rows,
    })


@projects_bp.route("/<int:project_id>/job-costing", methods=["GET"])
@require_api("projects", "view")
def project_job_costing(project_id):
    """تكلفة فعالة مقابل موازنة — لكل تصنيف ولكل بند BOQ.

    الفعالة من ProjectCost (بالتطابق مع تصنيفات BOQ) + نصيب البند من مستخلصات
    المقاولين. المخرجات: موازنة/فعالة/انحراف ونسبة استهلاك لكل فئة.
    """
    Project.query.get_or_404(project_id)

    cats = ["material", "labor", "equipment", "subcontract", "other"]

    def _sum(q, col):
        return float(db.session.query(db.func.coalesce(db.func.sum(col), 0)).filter(q).scalar() or 0)

    by_category = []
    total_budget = 0.0
    for cat in cats:
        budget = _sum(
            (BoqItem.project_id == project_id) & (BoqItem.category == cat),
            (BoqItem.quantity or 0) * (BoqItem.unit_price or 0),
        )
        actual = _sum(
            (ProjectCost.project_id == project_id)
            & (db.func.coalesce(ProjectCost.category, "other") == cat),
            ProjectCost.amount,
        )
        variance = round(budget - actual, 2)
        by_category.append({
            "category": cat,
            "budget": round(budget, 2),
            "actual": round(actual, 2),
            "variance": variance,
            "consumption_pct": round(actual / budget * 100, 1) if budget else None,
        })
        total_budget += budget

    # تفصيل على مستوى بنود BOQ مع نسبة التنفيذ من المستخلصات المعتمدة
    boq_items = BoqItem.query.filter_by(project_id=project_id).all()
    contract_ids = [c.id for c in ProjectContract.query.filter_by(project_id=project_id)]
    stmt_items_total = 0.0
    if contract_ids:
        stmt_items_total = float(db.session.query(
            db.func.coalesce(db.func.sum(ProgressStatement.work_value), 0)
        ).filter(
            ProgressStatement.contract_id.in_(contract_ids),
            ProgressStatement.status.in_(["approved", "paid"]),
        ).scalar() or 0)
    items_out = []
    for it in boq_items:
        budget = round(float((it.quantity or 0) * (it.unit_price or 0)), 2)
        items_out.append({
            "id": it.id,
            "code": it.code,
            "description": it.description,
            "category": it.category,
            "quantity": float(it.quantity or 0),
            "unit_price": float(it.unit_price or 0),
            "budget": budget,
            "status": it.status,
        })
    items_out.sort(key=lambda x: x["budget"], reverse=True)

    total_actual = sum(c["actual"] for c in by_category)
    return jsonify({
        "project_id": project_id,
        "by_category": by_category,
        "total_budget": round(total_budget, 2),
        "total_actual": round(total_actual, 2),
        "total_variance": round(total_budget - total_actual, 2),
        "statements_approved_total": round(stmt_items_total, 2),
        "items": items_out,
    })


@projects_bp.route("/<int:project_id>/summary", methods=["GET"])
@require_api("projects", "view")
def project_summary(project_id):
    p = Project.query.get_or_404(project_id)

    def _sum(q, col):
        return float(db.session.query(db.func.coalesce(db.func.sum(col), 0)).filter(q).scalar() or 0)

    costs_total = _sum(ProjectCost.project_id == project_id, ProjectCost.amount)
    boq_total = _sum(BoqItem.project_id == project_id, (BoqItem.quantity or 0) * (BoqItem.unit_price or 0))
    boq_approved = _sum(
        (BoqItem.project_id == project_id) & (BoqItem.status == "approved"),
        (BoqItem.quantity or 0) * (BoqItem.unit_price or 0),
    )
    contracts_total = _sum(ProjectContract.project_id == project_id, ProjectContract.contract_value)
    statements_paid = _sum(
        (ProgressStatement.contract_id.in_(
            db.session.query(ProjectContract.id).filter_by(project_id=project_id)
        )) & (ProgressStatement.status.in_(["approved", "paid"])),
        ProgressStatement.net_value,
    )
    change_orders = _sum(ChangeOrder.project_id == project_id, ChangeOrder.amount)

    phases = ProjectPhase.query.filter_by(project_id=project_id).all()
    phase_avg = round(sum(ph.completion or 0 for ph in phases) / len(phases)) if phases else 0
    progress_records = ProjectProgress.query.filter_by(project_id=project_id).order_by(ProjectProgress.record_date.desc()).all()
    wbs_count = WBSItem.query.filter_by(project_id=project_id).count()
    boq_count = BoqItem.query.filter_by(project_id=project_id).count()
    contracts_count = ProjectContract.query.filter_by(project_id=project_id).count()
    risks_open = ProjectRisk.query.filter_by(project_id=project_id, status="open").count()
    quality_fail = ProjectQuality.query.filter_by(project_id=project_id, result="fail").count()
    labor_active = LaborAssignment.query.filter_by(project_id=project_id, status="active").count()
    exec_done = ExecutionLog.query.filter_by(project_id=project_id, status="done").count()
    exec_total = ExecutionLog.query.filter_by(project_id=project_id).count()
    sites = SiteLog.query.filter_by(project_id=project_id).count()

    return jsonify({
        "project": p.to_dict(),
        "costs_total": costs_total,
        "boq_total": boq_total,
        "boq_approved": boq_approved,
        "contracts_total": contracts_total,
        "statements_paid": statements_paid,
        "change_orders": change_orders,
        "phase_avg": phase_avg,
        "phase_count": len(phases),
        "wbs_count": wbs_count,
        "boq_count": boq_count,
        "contracts_count": contracts_count,
        "risks_open": risks_open,
        "quality_fail": quality_fail,
        "labor_active": labor_active,
        "exec_done": exec_done,
        "exec_total": exec_total,
        "sites_count": sites,
        "progress_history": [r.to_dict() for r in progress_records[:30]],
    })


# ---- Sub-modules CRUD ----
register_crud("/<int:project_id>/phases", ProjectPhase,
              ["project_id", "name", "description", "order", "start_date", "end_date",
               "status", "completion", "budget"], parent_field="project_id")

register_crud("/<int:project_id>/wbs", WBSItem,
              ["project_id", "parent_id", "code", "name", "type", "description"], parent_field="project_id")

register_crud("/<int:project_id>/boq", BoqItem,
              ["project_id", "wbs_id", "code", "description", "unit", "quantity",
               "unit_price", "category", "status", "notes"], parent_field="project_id")

register_crud("/boq/<int:boq_id>/analysis", PriceAnalysisItem,
              ["boq_id", "description", "unit", "quantity", "rate", "cost_type"], parent_field="boq_id")

register_crud("/subcontractors", Subcontractor,
              ["name", "contact_person", "phone", "email", "address", "specialty",
               "commercial_registration", "rating", "status", "notes"])

register_crud("/<int:project_id>/contracts", ProjectContract,
              ["project_id", "contract_no", "title", "contract_type", "party_name",
               "subcontractor_id", "start_date", "end_date", "contract_value",
               "advance_payment", "retention_pct", "status", "description"], parent_field="project_id")

register_crud("/contracts/<int:contract_id>/statements", ProgressStatement,
              ["contract_id", "statement_no", "statement_date", "period_from", "period_to",
               "work_value", "advance_deduction", "retention_deduction",
               "net_value", "cumulative_total", "status", "notes"], parent_field="contract_id")

register_crud("/<int:project_id>/change-orders", ChangeOrder,
              ["project_id", "contract_id", "change_no", "description", "reason",
               "change_type", "amount", "change_date", "status"], parent_field="project_id")

register_crud("/<int:project_id>/progress", ProjectProgress,
              ["project_id", "boq_id", "record_date", "percentage", "note"], parent_field="project_id")

register_crud("/<int:project_id>/execution", ExecutionLog,
              ["project_id", "log_date", "activity", "description", "responsible", "status"],
              parent_field="project_id")

register_crud("/<int:project_id>/costs", ProjectCost,
              ["project_id", "cost_date", "category", "description", "amount",
               "reference", "notes"], parent_field="project_id")

register_crud("/<int:project_id>/risks", ProjectRisk,
              ["project_id", "description", "category", "probability", "impact",
               "mitigation", "owner", "status"], parent_field="project_id")

register_crud("/<int:project_id>/quality", ProjectQuality,
              ["project_id", "check_date", "check_type", "description", "result",
               "inspector", "corrective_action", "status"], parent_field="project_id")

register_crud("/<int:project_id>/site-logs", SiteLog,
              ["project_id", "log_date", "report_type", "weather", "description", "notes"],
              parent_field="project_id")

register_crud("/equipment", Equipment,
              ["code", "name", "type", "status", "location", "project_id", "daily_cost", "notes"])

register_crud("/<int:project_id>/labor", LaborAssignment,
              ["project_id", "employee_id", "name", "trade", "start_date", "end_date",
               "daily_rate", "status"], parent_field="project_id")

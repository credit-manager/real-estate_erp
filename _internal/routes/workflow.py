"""Workflow / approvals module: pages + API."""
from flask import Blueprint, render_template, request, jsonify, session

from database import db
from permissions import require_page, require_api
from auditlog import log_action
from models import WorkflowTemplate, WorkflowStep, ApprovalRequest, Role, User
from utils.workflow import (
    DOC_TYPES, user_is_approver, approve_request, reject_request, cancel_request,
)

workflow_bp = Blueprint("workflow", __name__, url_prefix="/workflow")


# ============ Pages ============

@workflow_bp.route("/approvals")
@require_page("workflow")
def approvals_page():
    return render_template("workflow_approvals.html")


@workflow_bp.route("/templates")
@require_page("workflow", "edit")
def templates_page():
    return render_template("workflow_templates.html")


@workflow_bp.route("/requests")
@require_page("workflow")
def requests_page():
    return render_template("workflow_requests.html")


# ============ Meta ============

@workflow_bp.route("/api/meta")
@require_api("workflow", "view")
def meta():
    roles = [r.name for r in Role.query.order_by(Role.name.asc()).all()]
    if "admin" not in roles:
        roles.insert(0, "admin")
    counts = {
        "pending": ApprovalRequest.query.filter_by(status="pending").count(),
        "approved": ApprovalRequest.query.filter_by(status="approved").count(),
        "rejected": ApprovalRequest.query.filter_by(status="rejected").count(),
    }
    my_role = session.get("role", "")
    my_pending = ApprovalRequest.query.filter_by(status="pending").count()
    if my_role != "admin":
        reqs = ApprovalRequest.query.filter_by(status="pending").all()
        my_pending = sum(1 for r in reqs if r.current_role() == my_role)
    return jsonify({
        "doc_types": list(DOC_TYPES.keys()),
        "roles": roles,
        "counts": counts,
        "my_pending": my_pending,
        "my_role": my_role,
    })


# ============ Approvals (pending) ============

@workflow_bp.route("/api/approvals")
@require_api("workflow", "view")
def list_pending():
    my_role = session.get("role", "")
    reqs = ApprovalRequest.query.filter_by(status="pending").order_by(
        ApprovalRequest.submitted_at.asc()).all()
    if my_role != "admin":
        reqs = [r for r in reqs if r.current_role() == my_role]
    return jsonify([r.to_dict() for r in reqs])


@workflow_bp.route("/api/requests")
@require_api("workflow", "view")
def list_requests():
    q = ApprovalRequest.query
    status = request.args.get("status")
    doc_type = request.args.get("doc_type")
    if status:
        q = q.filter_by(status=status)
    if doc_type:
        q = q.filter_by(doc_type=doc_type)
    reqs = q.order_by(ApprovalRequest.submitted_at.desc()).limit(200).all()
    return jsonify([r.to_dict() for r in reqs])


@workflow_bp.route("/api/requests/<int:req_id>/approve", methods=["POST"])
@require_api("workflow", "edit")
def request_approve(req_id):
    req = ApprovalRequest.query.get_or_404(req_id)
    if not user_is_approver(req):
        return jsonify({"success": False, "error_key": "workflow.notApprover"}), 403
    data = request.get_json() or {}
    ok = approve_request(req, data.get("comment", ""))
    if not ok:
        return jsonify({"success": False, "error_key": "workflow.notPending"}), 400
    return jsonify({"success": True, "request": req.to_dict()})


@workflow_bp.route("/api/requests/<int:req_id>/reject", methods=["POST"])
@require_api("workflow", "edit")
def request_reject(req_id):
    req = ApprovalRequest.query.get_or_404(req_id)
    if not user_is_approver(req):
        return jsonify({"success": False, "error_key": "workflow.notApprover"}), 403
    data = request.get_json() or {}
    comment = (data.get("comment", "") or "").strip()
    if not comment:
        return jsonify({"success": False, "error_key": "workflow.rejectCommentRequired"}), 400
    ok = reject_request(req, comment)
    if not ok:
        return jsonify({"success": False, "error_key": "workflow.notPending"}), 400
    return jsonify({"success": True, "request": req.to_dict()})


@workflow_bp.route("/api/requests/<int:req_id>/cancel", methods=["POST"])
@require_api("workflow", "edit")
def request_cancel(req_id):
    req = ApprovalRequest.query.get_or_404(req_id)
    uid = session.get("user_id")
    if session.get("role") != "admin" and req.submitted_by != uid:
        return jsonify({"success": False, "error_key": "workflow.notOwner"}), 403
    ok = cancel_request(req)
    if not ok:
        return jsonify({"success": False, "error_key": "workflow.notPending"}), 400
    return jsonify({"success": True, "request": req.to_dict()})


# ============ Templates ============

def _role_names():
    names = ["admin"] + [r.name for r in Role.query.all()]
    return set(names)


def _normalize_steps(steps_data):
    """يحوّل قائمة خطوات (أسماء أدوار) إلى كائنات WorkflowStep مرتبة."""
    names = _role_names()
    out = []
    idx = 1
    for step in (steps_data or []):
        if isinstance(step, dict):
            role = (step.get("role") or "").strip()
        else:
            role = str(step or "").strip()
        if not role or role not in names:
            continue
        out.append(WorkflowStep(position=idx, role=role))
        idx += 1
    return out


@workflow_bp.route("/api/templates")
@require_api("workflow", "view")
def list_templates():
    tmpls = WorkflowTemplate.query.order_by(WorkflowTemplate.doc_type.asc(), WorkflowTemplate.id.asc()).all()
    return jsonify([t.to_dict() for t in tmpls])


@workflow_bp.route("/api/templates", methods=["POST"])
@require_api("workflow", "edit")
def create_template():
    data = request.get_json() or {}
    doc_type = (data.get("doc_type") or "").strip()
    name = (data.get("name") or "").strip()
    if doc_type not in DOC_TYPES:
        return jsonify({"success": False, "error_key": "workflow.invalidDocType"}), 400
    if not name:
        return jsonify({"success": False, "error_key": "workflow.nameRequired"}), 400
    steps = _normalize_steps(data.get("steps"))
    if not steps:
        return jsonify({"success": False, "error_key": "workflow.stepsRequired"}), 400
    tpl = WorkflowTemplate(
        doc_type=doc_type,
        name=name,
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(tpl)
    for s in steps:
        tpl.steps.append(s)
    db.session.commit()
    log_action("create", "workflow", tpl.id, name)
    return jsonify(tpl.to_dict()), 201


@workflow_bp.route("/api/templates/<int:tpl_id>", methods=["PUT"])
@require_api("workflow", "edit")
def update_template(tpl_id):
    tpl = WorkflowTemplate.query.get_or_404(tpl_id)
    data = request.get_json() or {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "error_key": "workflow.nameRequired"}), 400
        tpl.name = name
    if "is_active" in data:
        tpl.is_active = bool(data.get("is_active"))
    if "doc_type" in data and data["doc_type"] in DOC_TYPES:
        tpl.doc_type = data["doc_type"]
    if "steps" in data:
        steps = _normalize_steps(data.get("steps"))
        if not steps:
            return jsonify({"success": False, "error_key": "workflow.stepsRequired"}), 400
        tpl.steps = []
        for s in steps:
            tpl.steps.append(s)
    db.session.commit()
    log_action("update", "workflow", tpl.id, tpl.name)
    return jsonify(tpl.to_dict())


@workflow_bp.route("/api/templates/<int:tpl_id>", methods=["DELETE"])
@require_api("workflow", "edit")
def delete_template(tpl_id):
    tpl = WorkflowTemplate.query.get_or_404(tpl_id)
    name = tpl.name
    ApprovalRequest.query.filter_by(template_id=tpl_id).update(
        {ApprovalRequest.template_id: None})
    db.session.delete(tpl)
    db.session.commit()
    log_action("delete", "workflow", tpl_id, name)
    return jsonify({"success": True})

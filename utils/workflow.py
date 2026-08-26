"""Workflow / approvals helpers."""
from datetime import datetime, timezone

from database import db
from flask import session

DOC_TYPES = {
    "invoice": "finance",
    "po": "procurement",
    "rental_contract": "rentals",
}


def document_model(doc_type):
    from models import Invoice, PurchaseOrder, RentalContract
    return {
        "invoice": Invoice,
        "po": PurchaseOrder,
        "rental_contract": RentalContract,
    }.get(doc_type)


def document_meta(doc_type, doc):
    """معلومات المستند لعرضها في الموافقات والسجل."""
    if doc is None:
        return {}
    href = {"invoice": "/finance", "po": "/procurement", "rental_contract": "/rentals"}.get(doc_type, "")
    cur = (doc._base_currency() or {}).get("code", "") if hasattr(doc, "_base_currency") else ""
    if doc_type == "invoice":
        return {
            "href": href,
            "number": doc.invoice_number,
            "title": (doc.description
                      or (doc.customer.full_name if doc.customer else "")
                      or "—"),
            "amount": float(doc.amount or 0),
            "currency": cur,
            "date": doc.issue_date.isoformat() if doc.issue_date else None,
            "status": doc.status,
        }
    if doc_type == "po":
        return {
            "href": href,
            "number": doc.po_number,
            "title": (doc.items_description
                      or (doc.supplier.company_name if doc.supplier else "")
                      or "—"),
            "amount": float(doc.total or 0),
            "currency": cur,
            "date": doc.order_date.isoformat() if doc.order_date else None,
            "status": doc.status,
        }
    if doc_type == "rental_contract":
        return {
            "href": href,
            "number": doc.contract_number,
            "title": (doc.customer.full_name if doc.customer else "") or "—",
            "amount": float(doc.monthly_rent or 0),
            "currency": cur,
            "date": doc.start_date.isoformat() if doc.start_date else None,
            "status": doc.status,
        }
    return {}


def _doc_amount(doc_type, doc):
    """المبلغ المالي للمستند (لسقوف الموافقات) — None إن لم يتوفر."""
    if doc is None:
        return None
    for attr in ("amount", "total", "net_value", "work_value"):
        v = getattr(doc, attr, None)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    meta = document_meta(doc_type, doc) or {}
    amt = meta.get("amount") or 0
    try:
        return float(amt) if amt else None
    except (TypeError, ValueError):
        return None


def active_template(doc_type, doc=None):
    """أعلى قالب موافقات مفعّل ينطبق على مستند.

    دعم سقوف مالية: القالب الذي قيمته min_amount أقل من أو تساوي مبلغ المستند
    يفوق القالب العام (بدون سقف). مثال: فواتير >500,000 تحتاج موافقة إضافية.
    """
    from models import WorkflowTemplate
    candidates = (WorkflowTemplate.query
                  .filter_by(doc_type=doc_type, is_active=True)
                  .order_by(WorkflowTemplate.id.asc()).all())
    if not candidates:
        return None
    amount = _doc_amount(doc_type, doc)
    best = None
    best_threshold = -1.0
    for t in candidates:
        thr = float(t.min_amount) if getattr(t, "min_amount", None) is not None else 0.0
        if amount is not None and thr <= amount and thr >= best_threshold:
            best, best_threshold = t, thr
        elif best is None and thr == 0.0:
            best = t
    return best or (candidates[0] if amount is None else best)


def user_is_approver(request):
    """هل المستخدم الحالي معتمد الخطوة الحالية؟ (الأدمن يعتمد أي خطوة)"""
    role = session.get("role", "")
    if role == "admin":
        return True
    return request.current_role() == role


def submit_document_for_approval(doc_type, doc_id):
    """إنشاء طلب موافقة لمستند جديد إن وُجد قالب مفعّل. يرجع الطلب أو None."""
    from auditlog import log_action
    from models import ApprovalRequest, ApprovalStepRecord
    tpl = active_template(doc_type, db.session.get(document_model(doc_type), doc_id) if document_model(doc_type) else None)
    if not tpl or not tpl.steps:
        return None
    existing = ApprovalRequest.query.filter_by(
        doc_type=doc_type, doc_id=doc_id, status="pending").first()
    if existing:
        return existing
    model = document_model(doc_type)
    doc = db.session.get(model, doc_id) if model else None
    req = ApprovalRequest(
        doc_type=doc_type,
        doc_id=doc_id,
        template_id=tpl.id,
        status="pending",
        current_step=1,
        submitted_by=session.get("user_id"),
    )
    db.session.add(req)
    for step in tpl.steps:
        db.session.add(ApprovalStepRecord(
            request=req, step_id=step.id, position=step.position,
            role=step.role, status="pending"))
    if doc is not None:
        doc.approval_status = "pending"
    db.session.commit()
    log_action("submit", "approval", req.id, "%s:%s" % (doc_type, doc_id))
    return req


def cancel_document_approval(doc_type, doc_id):
    """حذف طلبات الموافقة المرتبطة بمستند يُحذف من النظام."""
    from models import ApprovalRequest, ApprovalStepRecord
    reqs = ApprovalRequest.query.filter_by(doc_type=doc_type, doc_id=doc_id).all()
    if not reqs:
        return
    ids = [r.id for r in reqs]
    ApprovalStepRecord.query.filter(
        ApprovalStepRecord.request_id.in_(ids)
    ).delete(synchronize_session=False)
    for r in reqs:
        db.session.delete(r)


def approve_request(req, comment=""):
    """اعتماد الخطوة الحالية؛ عند انتهاء كل الخطوات يصبح الطلب معتمداً."""
    from auditlog import log_action
    if req.status != "pending":
        return False
    uid = session.get("user_id")
    now = datetime.now(timezone.utc)
    record = next((s for s in req.steps if s.position == req.current_step), None)
    if record:
        record.status = "approved"
        record.approver_id = uid
        record.comment = (comment or "").strip() or None
        record.decided_at = now
    nxt = req.current_step + 1
    if any(s.position == nxt for s in req.steps):
        req.current_step = nxt
    else:
        req.status = "approved"
        req.decided_by = uid
        req.decided_at = now
        req.comment = (comment or "").strip() or None
    doc = req.document()
    if doc is not None:
        doc.approval_status = "approved" if req.status == "approved" else "pending"
    db.session.commit()
    if req.status == "approved":
        from utils import accounting as acct
        try:
            if req.doc_type == "invoice":
                acct.post_invoice_entries(doc)
            elif req.doc_type == "po":
                acct.post_purchase_order_entries(doc)
            elif req.doc_type == "rental_contract":
                acct.post_contract_entries(doc)
        except Exception as e:
            log_action("error", "approval", req.id, "فشل الترحيل التلقائي: %s" % e)
    log_action("approve", "approval", req.id, "%s:%s" % (req.doc_type, req.doc_id))
    return True


def cancel_request(req):
    """إلغاء طلب موافقة معلّق من قبل مقدمه أو الأدمن."""
    from auditlog import log_action
    if req.status != "pending":
        return False
    uid = session.get("user_id")
    now = datetime.now(timezone.utc)
    for s in req.steps:
        if s.status == "pending":
            s.status = "cancelled"
            s.approver_id = uid
            s.decided_at = now
    req.status = "cancelled"
    req.decided_by = uid
    req.decided_at = now
    doc = req.document()
    if doc is not None:
        doc.approval_status = "not_required"
    db.session.commit()
    log_action("cancel", "approval", req.id, "%s:%s" % (req.doc_type, req.doc_id))
    return True


def reject_request(req, comment=""):
    """رفض الطلب وإيقاف كل الخطوات المعلقة."""
    from auditlog import log_action
    if req.status != "pending":
        return False
    uid = session.get("user_id")
    now = datetime.now(timezone.utc)
    for s in req.steps:
        if s.status == "pending":
            s.status = "rejected"
            s.approver_id = uid
            s.comment = (comment or "").strip() or None
            s.decided_at = now
    req.status = "rejected"
    req.decided_by = uid
    req.decided_at = now
    req.comment = (comment or "").strip() or None
    doc = req.document()
    if doc is not None:
        doc.approval_status = "rejected"
    db.session.commit()
    if req.doc_type == "invoice":
        from utils import accounting as acct
        acct.delete_source_entries("invoice", "invoice", req.doc_id)
    elif req.doc_type == "po":
        from utils import accounting as acct
        acct.delete_source_entries("po", "po", req.doc_id)
    elif req.doc_type == "rental_contract":
        from utils import accounting as acct
        acct.delete_source_entries("contract", "rental_contract", req.doc_id)
    log_action("reject", "approval", req.id, "%s:%s" % (req.doc_type, req.doc_id))
    return True

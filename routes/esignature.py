"""التوقيع الإلكتروني — DocuSign / Na3am / محلي."""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import IntegrityError

from database import db
from models import SignatureProvider, SignatureRequest, SignatureAuditLog, SalesContract, User
from permissions import require_api
from auditlog import log_action

esign_bp = Blueprint("esign", __name__, url_prefix="/api/esign")


# ==================== Providers ====================

@esign_bp.route("/providers", methods=["GET"])
@require_api("realestate", "view")
def list_providers():
    providers = SignatureProvider.query.filter_by(is_active=True).all()
    return jsonify([p.to_dict() for p in providers])


@esign_bp.route("/providers", methods=["POST"])
@require_api("realestate", "create")
def create_provider():
    data = request.get_json() or {}
    if not data.get("name") or not data.get("display_name"):
        return jsonify({"message": "الاسم والاسم المعروض مطلوبان"}), 400
    if SignatureProvider.query.filter_by(name=data["name"]).first():
        return jsonify({"message": "مزود بهذا الاسم موجود بالفعل"}), 409

    provider = SignatureProvider(
        name=data["name"],
        display_name=data["display_name"],
        api_base_url=data.get("api_base_url"),
        client_id=data.get("client_id"),
        client_secret_encrypted=data.get("client_secret"),  # TODO: تشفير
        webhook_secret_encrypted=data.get("webhook_secret"),
        is_active=data.get("is_active", True),
        is_default=data.get("is_default", False),
        config_json=data.get("config"),
    )
    db.session.add(provider)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "خطأ في الحفظ"}), 500
    log_action("create", "signature_provider", provider.id, provider.display_name)
    return jsonify(provider.to_dict()), 201


@esign_bp.route("/providers/<int:pid>", methods=["PUT"])
@require_api("realestate", "edit")
def update_provider(pid):
    provider = db.session.get(SignatureProvider, pid)
    if not provider:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("display_name", "api_base_url", "client_id", "is_active", "is_default"):
        if field in data:
            setattr(provider, field, data[field])
    if "client_secret" in data:
        provider.client_secret_encrypted = data["client_secret"]
    if "webhook_secret" in data:
        provider.webhook_secret_encrypted = data["webhook_secret"]
    if "config" in data:
        provider.config_json = data["config"]
    db.session.commit()
    log_action("update", "signature_provider", provider.id, provider.display_name)
    return jsonify(provider.to_dict())


@esign_bp.route("/providers/<int:pid>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_provider(pid):
    provider = db.session.get(SignatureProvider, pid)
    if not provider:
        return jsonify({"message": "غير موجود"}), 404
    if SignatureRequest.query.filter_by(provider_id=pid).first():
        return jsonify({"message": "لا يمكن حذف مزود له طلبات توقيع"}), 400
    db.session.delete(provider)
    db.session.commit()
    log_action("delete", "signature_provider", pid, provider.display_name)
    return jsonify({"success": True})


# ==================== Signature Requests ====================

def _get_default_provider():
    return SignatureProvider.query.filter_by(is_default=True, is_active=True).first() or \
           SignatureProvider.query.filter_by(is_active=True).first()


@esign_bp.route("/requests", methods=["GET"])
@require_api("realestate", "view")
def list_requests():
    q = SignatureRequest.query
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    doc_type = request.args.get("document_type")
    if doc_type:
        q = q.filter_by(document_type=doc_type)
    return jsonify([r.to_dict() for r in q.order_by(SignatureRequest.id.desc()).all()])


@esign_bp.route("/requests", methods=["POST"])
@require_api("realestate", "create")
def create_request():
    """إنشاء طلب توقيع لعقد بيع/إيجار."""
    data = request.get_json() or {}
    required = ("document_type", "document_id", "signer_email", "signer_name")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400

    # التحقق من وجود الوثيقة
    doc_type = data["document_type"]
    doc_id = data["document_id"]
    doc = None
    doc_number = ""
    if doc_type == "sales_contract":
        from models import SalesContract
        doc = db.session.get(SalesContract, doc_id)
        doc_number = doc.contract_number if doc else ""
    elif doc_type == "rental_contract":
        from models import RentalContract
        doc = db.session.get(RentalContract, doc_id)
        doc_number = doc.contract_number if doc else ""
    else:
        return jsonify({"message": "نوع وثيقة غير مدعوم"}), 400

    if not doc:
        return jsonify({"message": "الوثيقة غير موجودة"}), 404

    provider = _get_default_provider()
    if not provider:
        return jsonify({"message": "لا يوجد مزود توقيع مفعل"}), 400

    sig_req = SignatureRequest(
        provider_id=provider.id,
        document_type=doc_type,
        document_id=doc_id,
        document_number=doc_number,
        title=data.get("title") or f"توقيع {doc_number}",
        message=data.get("message"),
        signer_email=data["signer_email"],
        signer_name=data["signer_name"],
        signer_phone=data.get("signer_phone"),
        status="draft",
        created_by=request.environ.get("user_id"),
    )
    db.session.add(sig_req)
    db.session.commit()

    # Log audit
    audit = SignatureAuditLog(
        request_id=sig_req.id,
        event_type="created",
        event_data='{"source": "api"}',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(audit)
    db.session.commit()

    log_action("create", "signature_request", sig_req.id, sig_req.document_number)
    return jsonify(sig_req.to_dict()), 201


@esign_bp.route("/requests/<int:rid>/send", methods=["POST"])
@require_api("realestate", "edit")
def send_request(rid):
    """إرسال طلب التوقيع للمزود (DocuSign/Na3am/محلي)."""
    sig_req = db.session.get(SignatureRequest, rid)
    if not sig_req:
        return jsonify({"message": "غير موجود"}), 404
    if sig_req.status != "draft":
        return jsonify({"message": "لا يمكن الإرسال إلا للمسودات"}), 400

    provider = sig_req.provider
    if not provider:
        return jsonify({"message": "لا يوجد مزود مرتبط"}), 400

    # استدعاء المزود المناسب
    try:
        if provider.name == "docusign":
            result = _send_docusign(sig_req)
        elif provider.name == "na3am":
            result = _send_na3am(sig_req)
        else:
            result = _send_local(sig_req)
    except Exception as e:
        _log_audit(sig_req, "error", {"error": str(e)})
        return jsonify({"message": f"فشل الإرسال: {e}"}), 500

    if result.get("success"):
        sig_req.external_id = result.get("external_id")
        sig_req.signing_url = result.get("signing_url")
        sig_req.status = "sent"
        sig_req.expired_at = datetime.now() + timedelta(days=30)
        db.session.commit()
        _log_audit(sig_req, "sent", {"external_id": sig_req.external_id})
        log_action("send", "signature_request", sig_req.id, sig_req.document_number)
        return jsonify(sig_req.to_dict())
    else:
        _log_audit(sig_req, "error", {"error": result.get("error")})
        return jsonify({"message": result.get("error", "فشل الإرسال")}), 500


@esign_bp.route("/requests/<int:rid>", methods=["GET"])
@require_api("realestate", "view")
def get_request(rid):
    sig_req = db.session.get(SignatureRequest, rid)
    if not sig_req:
        return jsonify({"message": "غير موجود"}), 404
    return jsonify(sig_req.to_dict())


@esign_bp.route("/requests/<int:rid>/cancel", methods=["POST"])
@require_api("realestate", "edit")
def cancel_request(rid):
    sig_req = db.session.get(SignatureRequest, rid)
    if not sig_req:
        return jsonify({"message": "غير موجود"}), 404
    if sig_req.status not in ("draft", "sent", "delivered"):
        return jsonify({"message": "لا يمكن الإلغاء في هذه الحالة"}), 400
    sig_req.status = "voided"
    db.session.commit()
    _log_audit(sig_req, "voided", {})
    log_action("cancel", "signature_request", sig_req.id, sig_req.document_number)
    return jsonify(sig_req.to_dict())


@esign_bp.route("/webhook/<provider_name>", methods=["POST"])
def webhook(provider_name):
    """استقبال callback من DocuSign/Na3am."""
    data = request.get_json(silent=True) or {}
    # التحقق من التوقيع (TODO: التحقق من webhook secret)
    external_id = data.get("envelope_id") or data.get("external_id") or data.get("id")
    if not external_id:
        return jsonify({"success": False, "message": "معرف خارجي مفقود"}), 400

    sig_req = SignatureRequest.query.filter_by(external_id=external_id).first()
    if not sig_req:
        return jsonify({"success": False, "message": "طلب غير موجود"}), 404

    event = data.get("event") or data.get("status") or "unknown"
    status_map = {
        "sent": "sent", "delivered": "delivered", "signed": "signed",
        "completed": "completed", "declined": "declined", "expired": "expired",
        "voided": "voided"
    }
    new_status = status_map.get(event, "sent")

    sig_req.status = new_status
    sig_req.callback_data = json.dumps(data)
    if new_status == "completed":
        sig_req.completed_at = datetime.now()
    db.session.commit()

    _log_audit(sig_req, event, data)
    return jsonify({"success": True})


@esign_bp.route("/requests/<int:rid>/audit", methods=["GET"])
@require_api("realestate", "view")
def request_audit(rid):
    sig_req = db.session.get(SignatureRequest, rid)
    if not sig_req:
        return jsonify({"message": "غير موجود"}), 404
    logs = SignatureAuditLog.query.filter_by(request_id=rid).order_by(SignatureAuditLog.id.desc()).all()
    return jsonify([l.to_dict() for l in logs])


# ==================== Helpers ====================

def _send_docusign(sig_req):
    """إرسال عبر DocuSign API."""
    # TODO: تنفيذ DocuSign API الحقيقي
    # استخدام provider.api_base_url, client_id, client_secret
    # إنشاء envelope مع الوثيقة PDF
    return {"success": True, "external_id": f"docusign-{sig_req.id}", "signing_url": f"https://demo.docusign.net/signing/{sig_req.id}"}


def _send_na3am(sig_req):
    """إرسال عبر Na3am (مزود سعودي)."""
    # TODO: تنفيذ Na3am API
    return {"success": True, "external_id": f"na3am-{sig_req.id}", "signing_url": f"https://na3am.sa/sign/{sig_req.id}"}


def _send_local(sig_req):
    """توقيع محلي بسيط — إنشاء رابط توقيع داخلي."""
    # إنشاء رابط للتوقيع داخل النظام
    from flask import url_for
    signing_url = f"/portal/sign/{sig_req.id}"  # رابط داخلي
    return {"success": True, "external_id": f"local-{sig_req.id}", "signing_url": signing_url}


def _log_audit(sig_req, event_type, event_data):
    audit = SignatureAuditLog(
        request_id=sig_req.id,
        event_type=event_type,
        event_data=json.dumps(event_data, ensure_ascii=False),
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(audit)
    db.session.commit()
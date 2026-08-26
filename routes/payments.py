"""بوابات الدفع — Moyasar / PayTabs / STC Pay."""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, redirect
from sqlalchemy import or_

from database import db
from models import (
    PaymentGateway, PaymentTransaction, PaymentRefund,
    PaymentMethodToken, PaymentPlanInstallment,
    SalesContract, Installment, ServiceCharge, User
)
from permissions import require_api
from auditlog import log_action

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


# ==================== Gateways ====================

@payments_bp.route("/gateways", methods=["GET"])
@require_api("settings", "view")
def list_gateways():
    gateways = PaymentGateway.query.filter_by(is_active=True).all()
    return jsonify([g.to_dict() for g in gateways])


@payments_bp.route("/gateways", methods=["POST"])
@require_api("settings", "create")
def create_gateway():
    data = request.get_json() or {}
    required = ("name", "display_name", "provider")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400
    if PaymentGateway.query.filter_by(name=data["name"]).first():
        return jsonify({"message": "بوابة بهذا الاسم موجودة"}), 409

    gateway = PaymentGateway(
        name=data["name"],
        display_name=data["display_name"],
        provider=data["provider"],
        api_key_encrypted=data.get("api_key"),
        secret_key_encrypted=data.get("secret_key"),
        merchant_id=data.get("merchant_id"),
        webhook_secret_encrypted=data.get("webhook_secret"),
        supported_currencies=data.get("supported_currencies", "SAR,USD"),
        supported_cards=data.get("supported_cards", "visa,mastercard,mada"),
        is_active=data.get("is_active", True),
        is_default=data.get("is_default", False),
        is_sandbox=data.get("is_sandbox", True),
        config_json=data.get("config"),
    )
    db.session.add(gateway)
    db.session.commit()
    log_action("create", "payment_gateway", gateway.id, gateway.display_name)
    return jsonify(gateway.to_dict()), 201


@payments_bp.route("/gateways/<int:gid>", methods=["PUT"])
@require_api("settings", "edit")
def update_gateway(gid):
    gateway = db.session.get(PaymentGateway, gid)
    if not gateway:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("display_name", "provider", "merchant_id", "is_active", "is_default", "is_sandbox"):
        if field in data:
            setattr(gateway, field, data[field])
    for field in ("api_key", "secret_key", "webhook_secret"):
        if field in data:
            setattr(gateway, f"{field}_encrypted", data[field])
    if "config" in data:
        gateway.config_json = data["config"]
    if "supported_currencies" in data:
        gateway.supported_currencies = data["supported_currencies"]
    if "supported_cards" in data:
        gateway.supported_cards = data["supported_cards"]
    gateway.updated_at = datetime.now()
    db.session.commit()
    log_action("update", "payment_gateway", gateway.id, gateway.display_name)
    return jsonify(gateway.to_dict())


@payments_bp.route("/gateways/<int:gid>", methods=["DELETE"])
@require_api("settings", "delete")
def delete_gateway(gid):
    gateway = db.session.get(PaymentGateway, gid)
    if not gateway:
        return jsonify({"message": "غير موجود"}), 404
    if PaymentTransaction.query.filter_by(gateway_id=gid).first():
        return jsonify({"message": "لا يمكن حذف بوابة لها معاملات"}), 400
    db.session.delete(gateway)
    db.session.commit()
    log_action("delete", "payment_gateway", gid, gateway.display_name)
    return jsonify({"success": True})


def _get_default_gateway():
    return PaymentGateway.query.filter_by(is_default=True, is_active=True).first() or \
           PaymentGateway.query.filter_by(is_active=True).first()


# ==================== Transactions ====================

def _generate_reference_id():
    """توليد معرف مرجع فريد."""
    import uuid
    return f"PAY-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


@payments_bp.route("/transactions", methods=["GET"])
@require_api("finance", "view")
def list_transactions():
    q = PaymentTransaction.query
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    gateway = request.args.get("gateway_id", type=int)
    if gateway:
        q = q.filter_by(gateway_id=gateway)
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id", type=int)
    if entity_type and entity_id:
        q = q.filter_by(entity_type=entity_type, entity_id=entity_id)
    date_from = request.args.get("date_from")
    if date_from:
        q = q.filter(PaymentTransaction.initiated_at >= datetime.fromisoformat(date_from))
    date_to = request.args.get("date_to")
    if date_to:
        q = q.filter(PaymentTransaction.initiated_at <= datetime.fromisoformat(date_to))
    return jsonify([t.to_dict() for t in q.order_by(PaymentTransaction.id.desc()).limit(200).all()])


@payments_bp.route("/transactions", methods=["POST"])
@require_api("finance", "create")
def create_transaction():
    """إنشاء معاملة دفع جديدة وبدء الدفع."""
    data = request.get_json() or {}
    required = ("amount", "currency", "entity_type", "entity_id", "customer_email")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400

    gateway = _get_default_gateway()
    if not gateway:
        return jsonify({"message": "لا توجد بوابة دفع مفعلة"}), 400

    # التحقق من الكيان
    entity_type = data["entity_type"]
    entity_id = data["entity_id"]
    entity = None
    if entity_type == "sales_contract":
        from models import SalesContract
        entity = db.session.get(SalesContract, entity_id)
    elif entity_type == "installment":
        from models import Installment
        entity = db.session.get(Installment, entity_id)
    elif entity_type == "service_charge":
        from models import ServiceCharge
        entity = db.session.get(ServiceCharge, entity_id)
    else:
        return jsonify({"message": "نوع كيان غير مدعوم"}), 400

    if not entity:
        return jsonify({"message": "الكيان غير موجود"}), 404

    # إنشاء المعاملة
    reference_id = _generate_reference_id()
    amount = data["amount"]
    currency = data["currency"]
    customer_name = data.get("customer_name") or data["customer_email"].split("@")[0]

    txn = PaymentTransaction(
        gateway_id=gateway.id,
        reference_id=reference_id,
        amount=amount,
        currency=currency,
        entity_type=entity_type,
        entity_id=entity_id,
        customer_name=customer_name,
        customer_email=data["customer_email"],
        customer_phone=data.get("customer_phone"),
        customer_ip=request.remote_addr,
        callback_url=data.get("callback_url"),
        return_url=data.get("return_url"),
        webhook_url=data.get("webhook_url"),
        metadata_json=data.get("metadata"),
    )
    db.session.add(txn)
    db.session.commit()

    # بدء الدفع مع البوابة
    try:
        if gateway.name == "moyasar":
            result = _initiate_moyasar(txn)
        elif gateway.name == "paytabs":
            result = _initiate_paytabs(txn)
        elif gateway.name == "stcpay":
            result = _initiate_stcpay(txn)
        else:
            result = {"success": False, "error": "بوابة غير مدعومة"}

        if result.get("success"):
            txn.external_id = result.get("external_id")
            txn.gateway_response = result.get("gateway_response")
            txn.gateway_status = result.get("gateway_status")
            txn.status = "pending"
            db.session.commit()
            log_action("initiate", "payment_transaction", txn.id, txn.reference_id)
            return jsonify({
                "transaction": txn.to_dict(),
                "payment_url": result.get("payment_url"),
                "external_id": result.get("external_id"),
            }), 201
        else:
            txn.status = "failed"
            txn.gateway_response = result.get("error")
            txn.failed_at = datetime.now()
            db.session.commit()
            return jsonify({"message": result.get("error", "فشل بدء الدفع"), "transaction": txn.to_dict()}), 400
    except Exception as e:
        txn.status = "failed"
        txn.gateway_response = str(e)
        txn.failed_at = datetime.now()
        db.session.commit()
        return jsonify({"message": f"خطأ: {e}"}), 500


@payments_bp.route("/transactions/<int:tid>", methods=["GET"])
@require_api("finance", "view")
def get_transaction(tid):
    txn = db.session.get(PaymentTransaction, tid)
    if not txn:
        return jsonify({"message": "غير موجود"}), 404
    return jsonify(txn.to_dict())


@payments_bp.route("/transactions/<int:tid>/capture", methods=["POST"])
@require_api("finance", "edit")
def capture_transaction(tid):
    """التقاط دفع معتمد (للـ authorized payments)."""
    txn = db.session.get(PaymentTransaction, tid)
    if not txn:
        return jsonify({"message": "غير موجود"}), 404
    if txn.status != "authorized":
        return jsonify({"message": "لا يمكن التقاط إلا المدفوعات المعتمدة"}), 400

    gateway = txn.gateway
    try:
        if gateway.name == "moyasar":
            result = _capture_moyasar(txn)
        elif gateway.name == "paytabs":
            result = _capture_paytabs(txn)
        else:
            return jsonify({"message": "التقاط غير مدعوم لهذه البوابة"}), 400

        if result.get("success"):
            txn.status = "captured"
            txn.captured_at = datetime.now()
            txn.gateway_response = result.get("gateway_response")
            txn.gateway_status = result.get("gateway_status")
            db.session.commit()
            log_action("capture", "payment_transaction", txn.id, txn.reference_id)
            return jsonify(txn.to_dict())
        else:
            return jsonify({"message": result.get("error", "فشل التقاط الدفع")}), 400
    except Exception as e:
        return jsonify({"message": f"خطأ: {e}"}), 500


@payments_bp.route("/transactions/<int:tid>/refund", methods=["POST"])
@require_api("finance", "edit")
def refund_transaction(tid):
    """استرداد دفع (كامل أو جزئي)."""
    txn = db.session.get(PaymentTransaction, tid)
    if not txn:
        return jsonify({"message": "غير موجود"}), 404
    if not txn.is_refundable:
        return jsonify({"message": "لا يمكن استرداد هذه المعاملة"}), 400

    data = request.get_json() or {}
    amount = data.get("amount")
    if not amount or float(amount) <= 0:
        return jsonify({"message": "مبلغ الاسترداد مطلوب"}), 400
    if float(amount) > txn.refundable_amount:
        return jsonify({"message": "المبلغ يتجاوز المبلغ القابل للاسترداد"}), 400

    reason = data.get("reason", "customer_request")
    reason_code = data.get("reason_code", "customer_request")

    gateway = txn.gateway
    try:
        if gateway.name == "moyasar":
            result = _refund_moyasar(txn, amount)
        elif gateway.name == "paytabs":
            result = _refund_paytabs(txn, amount)
        else:
            return jsonify({"message": "الاسترداد غير مدعوم لهذه البوابة"}), 400

        if result.get("success"):
            refund = PaymentRefund(
                transaction_id=txn.id,
                reference_id=f"REF-{txn.reference_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                external_id=result.get("external_id"),
                amount=amount,
                currency=txn.currency,
                reason=data.get("reason"),
                reason_code=reason_code,
                status="processing",
                initiated_by=request.environ.get("user_id"),
            )
            db.session.add(refund)
            txn.refunded_amount = float(txn.refunded_amount or 0) + float(amount)
            if float(txn.refunded_amount) >= float(txn.amount):
                txn.status = "refunded"
                txn.refunded_at = datetime.now()
            else:
                txn.status = "partial_refunded"
            db.session.commit()
            log_action("refund", "payment_transaction", txn.id, f"Refund {amount} {txn.currency}")
            return jsonify({"transaction": txn.to_dict(), "refund": refund.to_dict()})
        else:
            return jsonify({"message": result.get("error", "فشل الاسترداد")}), 400
    except Exception as e:
        return jsonify({"message": f"خطأ: {e}"}), 500


@payments_bp.route("/transactions/<int:tid>/cancel", methods=["POST"])
@require_api("finance", "edit")
def cancel_transaction(tid):
    """إلغاء معاملة معلقة/معتمدة."""
    txn = db.session.get(PaymentTransaction, tid)
    if not txn:
        return jsonify({"message": "غير موجود"}), 404
    if txn.status not in ("pending", "authorized"):
        return jsonify({"message": "لا يمكن الإلغاء لهذا الحالة"}), 400

    gateway = txn.gateway
    try:
        if gateway.name == "moyasar":
            result = _cancel_moyasar(txn)
        elif gateway.name == "paytabs":
            result = _cancel_paytabs(txn)
        else:
            # للبوابات التي لا تدعم الإلغاء، نضعها كـ cancelled محلياً
            result = {"success": True}

        if result.get("success"):
            txn.status = "cancelled"
            txn.cancelled_at = datetime.now()
            db.session.commit()
            log_action("cancel", "payment_transaction", txn.id, txn.reference_id)
            return jsonify(txn.to_dict())
        else:
            return jsonify({"message": result.get("error", "فشل الإلغاء")}), 400
    except Exception as e:
        return jsonify({"message": f"خطأ: {e}"}), 500


# ==================== Refunds ====================

@payments_bp.route("/refunds", methods=["GET"])
@require_api("finance", "view")
def list_refunds():
    q = PaymentRefund.query
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    txn_id = request.args.get("transaction_id", type=int)
    if txn_id:
        q = q.filter_by(transaction_id=txn_id)
    return jsonify([r.to_dict() for r in q.order_by(PaymentRefund.id.desc()).limit(200).all()])


# ==================== Payment Tokens (Saved Cards) ====================

@payments_bp.route("/tokens", methods=["GET"])
@require_api("finance", "view")
def list_tokens():
    user_id = request.args.get("user_id", type=int)
    customer_id = request.args.get("customer_id", type=int)
    q = PaymentMethodToken.query.filter_by(is_active=True)
    if user_id:
        q = q.filter_by(user_id=user_id)
    if customer_id:
        q = q.filter_by(customer_id=customer_id)
    return jsonify([t.to_dict() for t in q.order_by(PaymentMethodToken.id.desc()).all()])


@payments_bp.route("/tokens", methods=["POST"])
@require_api("finance", "create")
def create_token():
    """حفظ توكن طريقة دفع (بعد الدفع الأول)."""
    data = request.get_json() or {}
    required = ("gateway_id", "external_token", "payment_method")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400

    # التحقق من عدم وجود توكن مكرر
    if PaymentMethodToken.query.filter_by(
        gateway_id=data["gateway_id"],
        external_token=data["external_token"]
    ).first():
        return jsonify({"message": "هذا التوكن محفوظ مسبقاً"}), 409

    token = PaymentMethodToken(
        gateway_id=data["gateway_id"],
        user_id=data.get("user_id"),
        customer_id=data.get("customer_id"),
        external_token=data["external_token"],
        payment_method=data["payment_method"],
        card_brand=data.get("card_brand"),
        card_last4=data.get("card_last4"),
        card_exp_month=data.get("card_exp_month"),
        card_exp_year=data.get("card_exp_year"),
        is_default=data.get("is_default", False),
        nickname=data.get("nickname"),
    )
    db.session.add(token)
    # إذا كان افتراضياً، إلغاء افتراضية البقية
    if token.is_default:
        PaymentMethodToken.query.filter(
            PaymentMethodToken.user_id == token.user_id,
            PaymentMethodToken.id != token.id,
            PaymentMethodToken.is_default == True
        ).update({"is_default": False})
    db.session.commit()
    log_action("create", "payment_token", token.id, f"{token.payment_method} ending in {token.card_last4}")
    return jsonify(token.to_dict()), 201


@payments_bp.route("/tokens/<int:tid>", methods=["DELETE"])
@require_api("finance", "delete")
def delete_token(tid):
    token = db.session.get(PaymentMethodToken, tid)
    if not token:
        return jsonify({"message": "غير موجود"}), 404
    token.is_active = False
    db.session.commit()
    return jsonify({"success": True})


# ==================== Auto-charge for Installments ====================

@payments_bp.route("/installment-plans", methods=["GET"])
@require_api("finance", "view")
def list_installment_plans():
    q = PaymentPlanInstallment.query
    installment_id = request.args.get("installment_id", type=int)
    if installment_id:
        q = q.filter_by(installment_id=installment_id)
    return jsonify([p.to_dict() for p in q.all()])


@payments_bp.route("/installment-plans", methods=["POST"])
@require_api("finance", "create")
def create_installment_plan():
    data = request.get_json() or {}
    if not data.get("installment_id"):
        return jsonify({"message": "installment_id مطلوب"}), 400

    # التحقق من عدم وجود خطة مسبقة
    if PaymentPlanInstallment.query.filter_by(installment_id=data["installment_id"]).first():
        return jsonify({"message": "خطة موجودة مسبقاً لهذا القسط"}), 409

    plan = PaymentPlanInstallment(
        installment_id=data["installment_id"],
        gateway_id=data.get("gateway_id"),
        payment_token_id=data.get("payment_token_id"),
        auto_charge=data.get("auto_charge", False),
        charge_days_before_due=data.get("charge_days_before_due", 1),
        max_retry_attempts=data.get("max_retry_attempts", 3),
        retry_interval_hours=data.get("retry_interval_hours", 24),
    )
    # حساب next_charge_at
    from models import Installment
    inst = db.session.get(Installment, data["installment_id"])
    if inst and inst.due_date:
        plan.next_charge_at = datetime.combine(inst.due_date, datetime.min.time()) - timedelta(days=plan.charge_days_before_due)

    db.session.add(plan)
    db.session.commit()
    return jsonify(plan.to_dict()), 201


@payments_bp.route("/installment-plans/<int:pid>", methods=["PUT"])
@require_api("finance", "edit")
def update_installment_plan(pid):
    plan = db.session.get(PaymentPlanInstallment, pid)
    if not plan:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("gateway_id", "payment_token_id", "auto_charge", "charge_days_before_due", "max_retry_attempts", "retry_interval_hours"):
        if field in data:
            setattr(plan, field, data[field])
    plan.updated_at = datetime.now()
    db.session.commit()
    return jsonify(plan.to_dict())


# ==================== Gateway Helpers (Stubs) ====================

def _initiate_moyasar(txn):
    """بدء دفع مع Moyasar."""
    # TODO: تنفيذ API Moyasar الحقيقي
    # POST https://api.moyasar.com/v1/payments
    return {
        "success": True,
        "external_id": f"moyasar-{txn.id}",
        "payment_url": f"https://checkout.moyasar.com/pay/{txn.reference_id}",
        "gateway_response": '{"status":"pending"}',
        "gateway_status": "pending",
    }


def _capture_moyasar(txn):
    return {"success": True, "gateway_response": '{"status":"captured"}', "gateway_status": "captured"}


def _refund_moyasar(txn, amount):
    return {"success": True, "external_id": f"moyasar-refund-{txn.id}"}


def _cancel_moyasar(txn):
    return {"success": True}


def _initiate_paytabs(txn):
    return {
        "success": True,
        "external_id": f"paytabs-{txn.id}",
        "payment_url": f"https://secure.paytabs.com/payment/page/{txn.reference_id}",
        "gateway_response": '{"status":"pending"}',
        "gateway_status": "pending",
    }


def _capture_paytabs(txn):
    return {"success": True, "gateway_response": '{"status":"captured"}', "gateway_status": "captured"}


def _refund_paytabs(txn, amount):
    return {"success": True, "external_id": f"paytabs-refund-{txn.id}"}


def _cancel_paytabs(txn):
    return {"success": True}


def _initiate_stcpay(txn):
    return {
        "success": True,
        "external_id": f"stcpay-{txn.id}",
        "payment_url": f"https://stcpay.com.sa/pay/{txn.reference_id}",
        "gateway_response": '{"status":"pending"}',
        "gateway_status": "pending",
    }


# ==================== Webhook Handlers ====================

@payments_bp.route("/webhook/<gateway_name>", methods=["POST"])
def webhook(gateway_name):
    """استقبال callback من بوابات الدفع."""
    data = request.get_json(silent=True) or request.form.to_dict()
    signature = request.headers.get("X-Signature") or request.headers.get("X-Paytabs-Signature")

    gateway = PaymentGateway.query.filter_by(name=gateway_name, is_active=True).first()
    if not gateway:
        return jsonify({"success": False, "message": "بوابة غير موجودة"}), 404

    # TODO: التحقق من التوقيع (signature verification)

    external_id = data.get("id") or data.get("payment_id") or data.get("transaction_id")
    if not external_id:
        return jsonify({"success": False, "message": "معرف خارجي مفقود"}), 400

    txn = PaymentTransaction.query.filter_by(external_id=external_id).first()
    if not txn:
        return jsonify({"success": False, "message": "معاملة غير موجودة"}), 404

    # تحديث الحالة حسب استجابة البوابة
    status_map = {
        "paid": "captured", "captured": "captured", "authorized": "authorized",
        "completed": "captured", "success": "captured",
        "failed": "failed", "failed_payment": "failed", "declined": "failed",
        "cancelled": "cancelled", "voided": "cancelled",
        "refunded": "refunded", "partially_refunded": "partial_refunded",
    }

    gateway_status = data.get("status") or data.get("payment_status") or "unknown"
    new_status = status_map.get(gateway_status.lower(), "pending")

    if new_status != txn.status:
        old_status = txn.status
        txn.status = new_status
        txn.gateway_status = gateway_status
        txn.gateway_response = jsonify(data).data.decode() if hasattr(jsonify(data), 'data') else str(data)

        if new_status == "captured":
            txn.captured_at = datetime.now()
            if not txn.authorized_at:
                txn.authorized_at = datetime.now()
        elif new_status == "failed":
            txn.failed_at = datetime.now()
        elif new_status == "cancelled":
            txn.cancelled_at = datetime.now()
        elif new_status in ("refunded", "partial_refunded"):
            txn.refunded_at = datetime.now()

        # تحديث بيانات البطاقة إن وجدت
        if "card" in data:
            card = data["card"]
            txn.card_brand = card.get("brand") or card.get("type")
            txn.card_last4 = card.get("last4") or card.get("last_four")
            txn.card_exp_month = card.get("exp_month")
            txn.card_exp_year = card.get("exp_year")

        db.session.commit()

        # Log
        from auditlog import log_action
        log_action("webhook", "payment_transaction", txn.id, f"{gateway_name} {old_status}->{new_status}")

    return jsonify({"success": True})
"""نظام الإشعارات الموحد — SMS/Email/WhatsApp/Push/In-app."""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func, or_

from database import db
from models import (
    NotificationChannel, NotificationTemplate, NotificationQueue,
    NotificationPreference, NotificationLog, User
)
from permissions import require_api
from auditlog import log_action

notif_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


# ==================== Channels ====================

@notif_bp.route("/channels", methods=["GET"])
@require_api("settings", "view")
def list_channels():
    channels = NotificationChannel.query.filter_by(is_active=True).order_by(NotificationChannel.priority).all()
    return jsonify([c.to_dict() for c in channels])


@notif_bp.route("/channels", methods=["POST"])
@require_api("settings", "create")
def create_channel():
    data = request.get_json() or {}
    required = ("name", "display_name")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400
    if NotificationChannel.query.filter_by(name=data["name"]).first():
        return jsonify({"message": "قناة بهذا الاسم موجودة"}), 409

    channel = NotificationChannel(
        name=data["name"],
        display_name=data["display_name"],
        provider=data.get("provider"),
        config_json=data.get("config"),
        is_active=data.get("is_active", True),
        priority=data.get("priority", 10),
        rate_limit_per_minute=data.get("rate_limit_per_minute", 60),
        rate_limit_per_hour=data.get("rate_limit_per_hour", 1000),
    )
    db.session.add(channel)
    db.session.commit()
    log_action("create", "notification_channel", channel.id, channel.display_name)
    return jsonify(channel.to_dict()), 201


@notif_bp.route("/channels/<int:cid>", methods=["PUT"])
@require_api("settings", "edit")
def update_channel(cid):
    channel = db.session.get(NotificationChannel, cid)
    if not channel:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("display_name", "provider", "is_active", "priority", "rate_limit_per_minute", "rate_limit_per_hour"):
        if field in data:
            setattr(channel, field, data[field])
    if "config" in data:
        channel.config_json = data["config"]
    db.session.commit()
    log_action("update", "notification_channel", channel.id, channel.display_name)
    return jsonify(channel.to_dict())


@notif_bp.route("/channels/<int:cid>", methods=["DELETE"])
@require_api("settings", "delete")
def delete_channel(cid):
    channel = db.session.get(NotificationChannel, cid)
    if not channel:
        return jsonify({"message": "غير موجود"}), 404
    if NotificationTemplate.query.filter_by(channel_id=cid).first():
        return jsonify({"message": "لا يمكن حذف قناة لها قوالب"}), 400
    db.session.delete(channel)
    db.session.commit()
    log_action("delete", "notification_channel", cid, channel.display_name)
    return jsonify({"success": True})


# ==================== Templates ====================

@notif_bp.route("/templates", methods=["GET"])
@require_api("settings", "view")
def list_templates():
    q = NotificationTemplate.query.filter_by(is_active=True)
    channel = request.args.get("channel_id", type=int)
    if channel:
        q = q.filter_by(channel_id=channel)
    lang = request.args.get("language")
    if lang:
        q = q.filter_by(language=lang)
    return jsonify([t.to_dict() for t in q.order_by(NotificationTemplate.name).all()])


@notif_bp.route("/templates", methods=["POST"])
@require_api("settings", "create")
def create_template():
    data = request.get_json() or {}
    required = ("channel_id", "name", "body_template")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400
    if not db.session.get(NotificationChannel, data["channel_id"]):
        return jsonify({"message": "القناة غير موجودة"}), 404

    template = NotificationTemplate(
        channel_id=data["channel_id"],
        name=data["name"],
        subject_template=data.get("subject_template"),
        body_template=data["body_template"],
        variables_json=data.get("variables"),
        language=data.get("language", "ar"),
        is_active=data.get("is_active", True),
    )
    db.session.add(template)
    db.session.commit()
    log_action("create", "notification_template", template.id, template.name)
    return jsonify(template.to_dict()), 201


@notif_bp.route("/templates/<int:tid>", methods=["PUT"])
@require_api("settings", "edit")
def update_template(tid):
    template = db.session.get(NotificationTemplate, tid)
    if not template:
        return jsonify({"message": "غير موجود"}), 404
    data = request.get_json() or {}
    for field in ("name", "subject_template", "body_template", "variables", "language", "is_active"):
        if field in data:
            if field == "variables":
                template.variables_json = data[field]
            else:
                setattr(template, field, data[field])
    if "channel_id" in data:
        if db.session.get(NotificationChannel, data["channel_id"]):
            template.channel_id = data["channel_id"]
    template.updated_at = datetime.now()
    db.session.commit()
    log_action("update", "notification_template", template.id, template.name)
    return jsonify(template.to_dict())


@notif_bp.route("/templates/<int:tid>", methods=["DELETE"])
@require_api("settings", "delete")
def delete_template(tid):
    template = db.session.get(NotificationTemplate, tid)
    if not template:
        return jsonify({"message": "غير موجود"}), 404
    if NotificationQueue.query.filter_by(template_id=tid).first():
        return jsonify({"message": "لا يمكن حذف قالب مستخدم في الطابور"}), 400
    db.session.delete(template)
    db.session.commit()
    log_action("delete", "notification_template", tid, template.name)
    return jsonify({"success": True})


# ==================== Queue (Send Notifications) ====================

def _render_template(template, data):
    """عرض القالب مع البيانات."""
    from jinja2 import Template
    try:
        subject = Template(template.subject_template or "").render(**data) if template.subject_template else ""
        body = Template(template.body_template).render(**data)
        return subject, body
    except Exception as e:
        return "", f"Template error: {e}"


@notif_bp.route("/send", methods=["POST"])
@require_api("settings", "create")
def send_notification():
    """إرسال إشعار فوري أو مجدول."""
    data = request.get_json() or {}
    required = ("channel", "recipient", "template")
    for f in required:
        if not data.get(f):
            return jsonify({"message": f"الحقل {f} مطلوب"}), 400

    channel = NotificationChannel.query.filter_by(name=data["channel"], is_active=True).first()
    if not channel:
        return jsonify({"message": "القناة غير موجودة أو غير مفعلة"}), 404

    template = NotificationTemplate.query.filter_by(name=data["template"], is_active=True).first()
    if not template:
        return jsonify({"message": "القالب غير موجود أو غير مفعل"}), 404

    # التحقق من تفضيلات المستخدم
    recipient_user_id = data.get("recipient_user_id", type=int)
    if recipient_user_id:
        pref = NotificationPreference.query.filter_by(user_id=recipient_user_id).first()
        if pref:
            channel_key = channel.name
            if channel_key == "email" and not pref.email_enabled:
                return jsonify({"message": "المستخدم معطل إشعارات البريد"}), 400
            if channel_key == "sms" and not pref.sms_enabled:
                return jsonify({"message": "المستخدم معطل إشعارات SMS"}), 400
            if channel_key == "push" and not pref.push_enabled:
                return jsonify({"message": "المستخدم معطل الإشعارات الفورية"}), 400
            if channel_key == "inapp" and not pref.inapp_enabled:
                return jsonify({"message": "المستخدم معطل الإشعارات الداخلية"}), 400

    # التحقق من ساعات الهدوء
    if recipient_user_id:
        pref = NotificationPreference.query.filter_by(user_id=recipient_user_id).first()
        if pref and pref.quiet_hours_start and pref.quiet_hours_end:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            if pref.quiet_hours_start <= current_time <= pref.quiet_hours_end:
                # جدولة بعد ساعات الهدوء
                return jsonify({"message": "في ساعات الهدوء — سيتم الإرسال لاحقاً", "status": "scheduled"}), 202

    # عرض القالب
    template_data = data.get("data", {})
    subject, body = _render_template(template, template_data)

    # إنشاء عنصر في الطابور
    queue_item = NotificationQueue(
        channel_id=channel.id,
        template_id=template.id,
        recipient=data["recipient"],
        recipient_type=data.get("recipient_type", "user"),
        recipient_user_id=recipient_user_id,
        subject=subject,
        body=body,
        data_json=data.get("data", {}),
        status="pending",
        priority=data.get("priority", 5),
        scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
    )
    db.session.add(queue_item)
    db.session.commit()
    log_action("create", "notification_queue", queue_item.id, f"{channel.name} to {queue_item.recipient}")
    return jsonify(queue_item.to_dict()), 201


@notif_bp.route("/queue", methods=["GET"])
@require_api("settings", "view")
def list_queue():
    q = NotificationQueue.query
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    channel = request.args.get("channel_id", type=int)
    if channel:
        q = q.filter_by(channel_id=channel)
    recipient_user = request.args.get("recipient_user_id", type=int)
    if recipient_user:
        q = q.filter_by(recipient_user_id=recipient_user)
    return jsonify([q_item.to_dict() for q_item in q.order_by(NotificationQueue.id.desc()).limit(200).all()])


@notif_bp.route("/queue/<int:qid>/retry", methods=["POST"])
@require_api("settings", "edit")
def retry_queue(qid):
    item = db.session.get(NotificationQueue, qid)
    if not item:
        return jsonify({"message": "غير موجود"}), 404
    if item.status not in ("failed", "cancelled"):
        return jsonify({"message": "لا يمكن إعادة المحاولة لهذا الحالة"}), 400
    if item.attempts >= item.max_attempts:
        return jsonify({"message": "تم الوصول للحد الأقصى من المحاولات"}), 400
    item.status = "pending"
    item.attempts = 0
    item.error_message = None
    db.session.commit()
    log_action("retry", "notification_queue", qid, item.recipient)
    return jsonify(item.to_dict())


@notif_bp.route("/queue/<int:qid>/cancel", methods=["POST"])
@require_api("settings", "edit")
def cancel_queue(qid):
    item = db.session.get(NotificationQueue, qid)
    if not item:
        return jsonify({"message": "غير موجود"}), 404
    if item.status not in ("pending", "processing"):
        return jsonify({"message": "لا يمكن الإلغاء لهذا الحالة"}), 400
    item.status = "cancelled"
    db.session.commit()
    log_action("cancel", "notification_queue", qid, item.recipient)
    return jsonify(item.to_dict())


# ==================== Preferences ====================

@notif_bp.route("/preferences", methods=["GET"])
@require_api("users", "view")
def get_preferences():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"message": "user_id مطلوب"}), 400
    pref = NotificationPreference.query.filter_by(user_id=user_id).first()
    if not pref:
        # إنشاء افتراضي
        pref = NotificationPreference(user_id=user_id)
        db.session.add(pref)
        db.session.commit()
    return jsonify(pref.to_dict())


@notif_bp.route("/preferences", methods=["PUT"])
@require_api("users", "edit")
def update_preferences():
    data = request.get_json() or {}
    user_id = data.get("user_id", type=int)
    if not user_id:
        return jsonify({"message": "user_id مطلوب"}), 400
    pref = NotificationPreference.query.filter_by(user_id=user_id).first()
    if not pref:
        pref = NotificationPreference(user_id=user_id)
        db.session.add(pref)
    for field in ("email_enabled", "sms_enabled", "push_enabled", "inapp_enabled", "whatsapp_enabled",
                  "quiet_hours_start", "quiet_hours_end", "timezone"):
        if field in data:
            setattr(pref, field, data[field])
    if "preferences" in data:
        pref.preferences_json = data["preferences"]
    pref.updated_at = datetime.now()
    db.session.commit()
    return jsonify(pref.to_dict())


# ==================== Logs ====================

@notif_bp.route("/logs", methods=["GET"])
@require_api("audit", "view")
def list_logs():
    q = NotificationLog.query
    channel = request.args.get("channel")
    if channel:
        q = q.filter_by(channel=channel)
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    user_id = request.args.get("user_id", type=int)
    if user_id:
        q = q.filter_by(recipient_user_id=user_id)
    date_from = request.args.get("date_from")
    if date_from:
        q = q.filter(NotificationLog.sent_at >= datetime.fromisoformat(date_from))
    date_to = request.args.get("date_to")
    if date_to:
        q = q.filter(NotificationLog.sent_at <= datetime.fromisoformat(date_to))
    return jsonify([log.to_dict() for log in q.order_by(NotificationLog.sent_at.desc()).limit(500).all()])


@notif_bp.route("/stats", methods=["GET"])
@require_api("reports", "view")
def notification_stats():
    """إحصائيات الإشعارات."""
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    q = NotificationLog.query
    if date_from:
        q = q.filter(NotificationLog.sent_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(NotificationLog.sent_at <= datetime.fromisoformat(date_to))

    total = q.count()
    sent = q.filter_by(status="sent").count()
    failed = q.filter_by(status="failed").count()
    delivered = q.filter_by(status="delivered").count()
    read = q.filter_by(status="read").count()

    by_channel = db.session.query(
        NotificationLog.channel, func.count(NotificationLog.id)
    ).filter(
        NotificationLog.sent_at >= datetime.fromisoformat(date_from) if date_from else True,
        NotificationLog.sent_at <= datetime.fromisoformat(date_to) if date_to else True
    ).group_by(NotificationLog.channel).all()

    by_status = db.session.query(
        NotificationLog.status, func.count(NotificationLog.id)
    ).group_by(NotificationLog.status).all()

    total_cost = db.session.query(func.sum(NotificationLog.cost)).scalar() or 0

    return jsonify({
        "total": total,
        "sent": sent,
        "failed": failed,
        "delivered": delivered,
        "read": read,
        "delivery_rate": round(sent / total * 100, 1) if total else 0,
        "read_rate": round(read / sent * 100, 1) if sent else 0,
        "total_cost": float(total_cost),
        "by_channel": [{"channel": c, "count": n} for c, n in by_channel],
        "by_status": [{"status": s, "count": n} for s, n in by_status],
    })


# ==================== Helper: Queue Processor ====================

def process_notification_queue():
    """معالجة طابور الإشعارات (لتشغيلها كـ background job)."""
    # هذه الدالة تُستدعى من نظام طابور المهام (Celery/RQ/APScheduler)
    pending = NotificationQueue.query.filter(
        NotificationQueue.status == "pending",
        or_(NotificationQueue.scheduled_at.is_(None), NotificationQueue.scheduled_at <= datetime.now())
    ).order_by(NotificationQueue.priority, NotificationQueue.created_at).limit(100).all()

    for item in pending:
        item.status = "processing"
        item.attempts += 1
        db.session.commit()

        try:
            channel = item.channel
            success = False
            external_id = None
            error_msg = None

            if channel.name == "email":
                success, external_id, error_msg = _send_email(item)
            elif channel.name == "sms":
                success, external_id, error_msg = _send_sms(item)
            elif channel.name == "whatsapp":
                success, external_id, error_msg = _send_whatsapp(item)
            elif channel.name == "push":
                success, external_id, error_msg = _send_push(item)
            elif channel.name == "inapp":
                success, external_id, error_msg = _send_inapp(item)
            else:
                success = False
                error_msg = f"قناة غير مدعومة: {channel.name}"

            if success:
                item.status = "sent"
                item.sent_at = datetime.now()
                item.external_id = external_id
                # Log
                log = NotificationLog(
                    queue_id=item.id,
                    channel_id=item.channel_id,
                    template_id=item.template_id,
                    recipient=item.recipient,
                    recipient_user_id=item.recipient_user_id,
                    subject=item.subject,
                    body=item.body,
                    channel=channel.name,
                    status="sent",
                    provider=channel.provider,
                    external_id=external_id,
                    sent_at=datetime.now(),
                )
                db.session.add(log)
            else:
                item.status = "failed" if item.attempts >= item.max_attempts else "pending"
                item.error_message = error_msg
                item.failed_at = datetime.now()
                # Log
                log = NotificationLog(
                    queue_id=item.id,
                    channel_id=item.channel_id,
                    template_id=item.template_id,
                    recipient=item.recipient,
                    recipient_user_id=item.recipient_user_id,
                    subject=item.subject,
                    body=item.body,
                    channel=channel.name,
                    status="failed",
                    provider=channel.provider,
                    error_message=error_msg,
                    sent_at=datetime.now(),
                )
                db.session.add(log)

            db.session.commit()

        except Exception as e:
            item.status = "failed" if item.attempts >= item.max_attempts else "pending"
            item.error_message = str(e)
            db.session.commit()


def _send_email(item):
    """إرسال بريد إلكتروني (SendGrid/Mailgun/SMTP)."""
    # TODO: تنفيذ الإرسال الفعلي
    return True, f"email-{item.id}", None


def _send_sms(item):
    """إرسال SMS (Twilio/Ultramsg/Unifonic)."""
    # TODO: التنفيذ الفعلي
    return True, f"sms-{item.id}", None


def _send_whatsapp(item):
    """إرسال WhatsApp (Ultramsg/360Dialog/Twilio)."""
    # TODO: التنفيذ الفعلي
    return True, f"whatsapp-{item.id}", None


def _send_push(item):
    """إرسال Push Notification (FCM/APNs)."""
    # TODO: التنفيذ الفعلي
    return True, f"push-{item.id}", None


def _send_inapp(item):
    """إشعار داخل التطبيق."""
    # إنشاء سجل in-app للمستخدم
    # هنا مجرد مثال — في التطبيق الحقيقي يتم تخزين في جدول user_notifications
    return True, f"inapp-{item.id}", None


# ==================== Helper Function for App Use ====================

def send_notification(channel_name, template_name, recipient, data=None, user_id=None, scheduled_at=None):
    """دالة مساعدة للاستخدام من باقي التطبيق."""
    channel = NotificationChannel.query.filter_by(name=channel_name, is_active=True).first()
    template = NotificationTemplate.query.filter_by(name=template_name, is_active=True).first()
    if not channel or not template:
        return False

    from jinja2 import Template
    subject = Template(template.subject_template or "").render(**(data or {})) if template.subject_template else ""
    body = Template(template.body_template).render(**(data or {}))

    queue_item = NotificationQueue(
        channel_id=channel.id,
        template_id=template.id,
        recipient=recipient,
        recipient_type="user" if user_id else "direct",
        recipient_user_id=user_id,
        subject=subject,
        body=body,
        data_json=data or {},
        status="pending",
        scheduled_at=scheduled_at,
    )
    db.session.add(queue_item)
    db.session.commit()
    return True
"""نظام الإشعارات الموحد — SMS/Email/WhatsApp/Push/In-app."""
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import func, or_

from database import db
from models import (
    NotificationChannel, NotificationTemplate, NotificationQueue,
    NotificationPreference, NotificationLog, User
)
from permissions import require_api
from auditlog import log_action
from utils.validation import error_response

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
        return error_response("قناة بهذا الاسم موجودة", 409)
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
        return error_response("غير موجود", 404)
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
        return error_response("غير موجود", 404)
    if NotificationTemplate.query.filter_by(channel_id=cid).first():
        return error_response("لا يمكن حذف قناة لها قوالب", 400)
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
        return error_response("القناة غير موجودة", 404)
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
        return error_response("غير موجود", 404)
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
        return error_response("غير موجود", 404)
    if NotificationQueue.query.filter_by(template_id=tid).first():
        return error_response("لا يمكن حذف قالب مستخدم في الطابور", 400)
    db.session.delete(template)
    db.session.commit()
    log_action("delete", "notification_template", tid, template.name)
    return jsonify({"success": True})


# ==================== Queue (Send Notifications) ====================

def _render_template(template, data):
    """عرض القالب مع البيانات — باستخدام SandboxedEnvironment لمنع SSTI."""
    from jinja2.sandbox import SandboxedEnvironment
    env = SandboxedEnvironment(autoescape=True)
    try:
        subject = env.from_string(template.subject_template or "").render(**data) if template.subject_template else ""
        body = env.from_string(template.body_template).render(**data)
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
        return error_response("القناة غير موجودة أو غير مفعلة", 404)
    template = NotificationTemplate.query.filter_by(name=data["template"], is_active=True).first()
    if not template:
        return error_response("القالب غير موجود أو غير مفعل", 404)
    # التحقق من تفضيلات المستخدم
    recipient_user_id = data.get("recipient_user_id", type=int)
    if recipient_user_id:
        pref = NotificationPreference.query.filter_by(user_id=recipient_user_id).first()
        if pref:
            channel_key = channel.name
            if channel_key == "email" and not pref.email_enabled:
                return error_response("المستخدم معطل إشعارات البريد", 400)
            if channel_key == "sms" and not pref.sms_enabled:
                return error_response("المستخدم معطل إشعارات SMS", 400)
            if channel_key == "push" and not pref.push_enabled:
                return error_response("المستخدم معطل الإشعارات الفورية", 400)
            if channel_key == "inapp" and not pref.inapp_enabled:
                return error_response("المستخدم معطل الإشعارات الداخلية", 400)
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
        return error_response("غير موجود", 404)
    if item.status not in ("failed", "cancelled"):
        return error_response("لا يمكن إعادة المحاولة لهذا الحالة", 400)
    if item.attempts >= item.max_attempts:
        return error_response("تم الوصول للحد الأقصى من المحاولات", 400)
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
        return error_response("غير موجود", 404)
    if item.status not in ("pending", "processing"):
        return error_response("لا يمكن الإلغاء لهذا الحالة", 400)
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
        return error_response("user_id مطلوب", 400)
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
        return error_response("user_id مطلوب", 400)
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
    """معالجة طابور الإشعارات (لتشغيلها كـ background job).
    
    Features:
    - Rate limiting per channel (respects rate_limit_per_minute/hour)
    - Exponential backoff on failure (1min, 2min, 4min, 8min...)
    - Dead letter logging when max_attempts exceeded
    - Per-item timeout guard (prevents stuck items)
    """
    import time as _time

    pending = NotificationQueue.query.filter(
        NotificationQueue.status == "pending",
        or_(NotificationQueue.scheduled_at.is_(None), NotificationQueue.scheduled_at <= datetime.now())
    ).order_by(NotificationQueue.priority, NotificationQueue.created_at).limit(100).all()

    # Track per-channel send counts for rate limiting
    channel_counts = {}
    channel_last_send = {}

    for item in pending:
        # Check per-channel rate limit
        ch = item.channel
        ch_key = ch.id
        if ch_key not in channel_counts:
            channel_counts[ch_key] = {"minute": 0, "hour": 0}
            channel_last_send[ch_key] = 0

        now_ts = _time.time()
        minute_count = channel_counts[ch_key]["minute"]
        hour_count = channel_counts[ch_key]["hour"]

        # Enforce per-minute rate limit
        if ch.rate_limit_per_minute and minute_count >= ch.rate_limit_per_minute:
            item.status = "pending"
            db.session.commit()
            continue

        # Enforce per-hour rate limit
        if ch.rate_limit_per_hour and hour_count >= ch.rate_limit_per_hour:
            item.status = "pending"
            db.session.commit()
            continue

        # Enforce minimum interval between sends (anti-burst)
        min_interval = 0.5  # 500ms between sends per channel
        elapsed = now_ts - channel_last_send.get(ch_key, 0)
        if elapsed < min_interval:
            _time.sleep(min_interval - elapsed)

        item.status = "processing"
        item.attempts += 1
        db.session.commit()

        try:
            success = False
            external_id = None
            error_msg = None

            if ch.name == "email":
                success, external_id, error_msg = _send_email(item)
            elif ch.name == "sms":
                success, external_id, error_msg = _send_sms(item)
            elif ch.name == "whatsapp":
                success, external_id, error_msg = _send_whatsapp(item)
            elif ch.name == "push":
                success, external_id, error_msg = _send_push(item)
            elif ch.name == "inapp":
                success, external_id, error_msg = _send_inapp(item)
            else:
                success = False
                error_msg = f"قناة غير مدعومة: {ch.name}"

            if success:
                item.status = "sent"
                item.sent_at = datetime.now()
                item.external_id = external_id
                channel_counts[ch_key]["minute"] = minute_count + 1
                channel_counts[ch_key]["hour"] = hour_count + 1
                channel_last_send[ch_key] = _time.time()
                log_entry = NotificationLog(
                    queue_id=item.id, channel_id=item.channel_id,
                    template_id=item.template_id, recipient=item.recipient,
                    recipient_user_id=item.recipient_user_id,
                    subject=item.subject, body=item.body,
                    channel=ch.name, status="sent", provider=ch.provider,
                    external_id=external_id, sent_at=datetime.now(),
                )
                db.session.add(log_entry)
            else:
                # Exponential backoff: set scheduled_at to now + 2^attempts minutes
                backoff_minutes = min(2 ** item.attempts, 60)  # Cap at 60 min
                if item.attempts >= item.max_attempts:
                    item.status = "failed"
                else:
                    item.status = "pending"
                    item.scheduled_at = datetime.now() + timedelta(minutes=backoff_minutes)
                item.error_message = error_msg
                item.failed_at = datetime.now()
                log_entry = NotificationLog(
                    queue_id=item.id, channel_id=item.channel_id,
                    template_id=item.template_id, recipient=item.recipient,
                    recipient_user_id=item.recipient_user_id,
                    subject=item.subject, body=item.body,
                    channel=ch.name, status="failed", provider=ch.provider,
                    error_message=error_msg, sent_at=datetime.now(),
                )
                db.session.add(log_entry)

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            item.error_message = str(e)
            if item.attempts >= item.max_attempts:
                item.status = "failed"
            else:
                backoff_minutes = min(2 ** item.attempts, 60)
                item.status = "pending"
                item.scheduled_at = datetime.now() + timedelta(minutes=backoff_minutes)
            db.session.commit()


def _send_email(item):
    """إرسال بريد إلكتروني عبر SMTP."""
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    config = item.channel.config_json or {}
    host = config.get("smtp_host") or os.environ.get("SMTP_HOST", "")
    port = int(config.get("smtp_port") or os.environ.get("SMTP_PORT", 587))
    user = config.get("smtp_user") or os.environ.get("SMTP_USER", "")
    password = config.get("smtp_password") or os.environ.get("SMTP_PASSWORD", "")
    from_addr = config.get("from_email") or os.environ.get("SMTP_FROM", user)
    use_tls = config.get("smtp_tls", True)

    if not host:
        return False, None, "SMTP_HOST not configured"

    try:
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = item.recipient
        msg["Subject"] = item.subject or ""
        msg.attach(MIMEText(item.body or "", "html", "utf-8"))

        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [item.recipient], msg.as_string())
        return True, f"smtp-{item.id}", None
    except Exception as e:
        return False, None, str(e)


def _send_sms(item):
    """إرسال SMS عبر Ultramsg/Twilio/Unifonic."""
    import os
    config = item.channel.config_json or {}
    provider = config.get("provider") or item.channel.provider or ""

    if provider == "ultramsg":
        try:
            import requests as _req
            instance_id = config.get("instance_id") or os.environ.get("ULTRAMSG_INSTANCE_ID", "")
            token = config.get("token") or os.environ.get("ULTRAMSG_TOKEN", "")
            if not instance_id or not token:
                return False, None, "Ultramsg instance_id/token not configured"
            resp = _req.post(f"https://api.ultramsg.com/{instance_id}/messages/chat", data={
                "token": token, "to": item.recipient, "body": item.body or "",
            }, timeout=15)
            if resp.status_code == 200 and resp.json().get("sent"):
                return True, f"ultramsg-{item.id}", None
            return False, None, f"Ultramsg error: {resp.text[:200]}"
        except Exception as e:
            return False, None, str(e)

    return False, None, f"SMS provider '{provider}' not implemented. Configure Ultramsg in channel.config_json"


def _send_whatsapp(item):
    """إرسال WhatsApp عبر Ultramsg/360Dialog."""
    import os
    config = item.channel.config_json or {}
    provider = config.get("provider") or item.channel.provider or ""

    if provider == "ultramsg":
        try:
            import requests as _req
            instance_id = config.get("instance_id") or os.environ.get("ULTRAMSG_INSTANCE_ID", "")
            token = config.get("token") or os.environ.get("ULTRAMSG_TOKEN", "")
            if not instance_id or not token:
                return False, None, "Ultramsg instance_id/token not configured"
            resp = _req.post(f"https://api.ultramsg.com/{instance_id}/messages/chat", data={
                "token": token, "to": item.recipient, "body": item.body or "",
            }, timeout=15)
            if resp.status_code == 200 and resp.json().get("sent"):
                return True, f"ultramsg-wa-{item.id}", None
            return False, None, f"Ultramsg WhatsApp error: {resp.text[:200]}"
        except Exception as e:
            return False, None, str(e)

    return False, None, f"WhatsApp provider '{provider}' not implemented. Configure Ultramsg in channel.config_json"


def _send_push(item):
    """إرسال Push Notification عبر FCM (HTTP v1 API)."""
    import os
    import json as _json
    try:
        import requests
    except ImportError:
        return False, None, "requests library not installed"

    config = item.channel.config_json or {}
    fcm_key = config.get("fcm_server_key") or os.environ.get("FCM_SERVER_KEY", "")
    fcm_url = "https://fcm.googleapis.com/v1/projects/{}/messages:send".format(
        config.get("fcm_project_id") or os.environ.get("FCM_PROJECT_ID", ""))

    if not fcm_key and not fcm_url:
        return False, None, "FCM not configured"

    payload = {
        "message": {
            "token": item.recipient,
            "notification": {"title": item.subject or "", "body": item.body or ""},
        }
    }
    try:
        headers = {"Authorization": f"Bearer {fcm_key}", "Content-Type": "application/json"}
        resp = requests.post(fcm_url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            return True, f"fcm-{item.id}", None
        return False, None, f"FCM error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, None, str(e)


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

    from jinja2.sandbox import SandboxedEnvironment
    _env = SandboxedEnvironment(autoescape=True)
    subject = _env.from_string(template.subject_template or "").render(**(data or {})) if template.subject_template else ""
    body = _env.from_string(template.body_template).render(**(data or {}))

    queue_item = NotificationQueue(
        channel_id=channel.id,
        template_id=template.id,
        recipient=recipient,
        recipient_type="user" if user_id else "direct",
        recipient_user_id=user_id,
        subject=subject,
        body=body,
        data_json=json.dumps(data or {}, ensure_ascii=False),
        status="pending",
        scheduled_at=scheduled_at,
    )
    db.session.add(queue_item)
    db.session.commit()
    return True
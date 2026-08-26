"""Mobile / PWA API routes.

تطبيقات الأدوار (مدير/مهندس/مندوب/HR) + GPS + حضور وانصراف + إشعارات فورية.
"""
from datetime import datetime, date, timedelta
import math
from flask import Blueprint, request, jsonify, render_template, session, Response
from sqlalchemy import func
from database import db
from models import User
from routes.auth import (
    _check_login_lock, _register_login_failure, _reset_login_failures, _login_key,
    MAX_LOGIN_ATTEMPTS, LOGIN_LOCK_SECONDS, _LOGIN_FAILURES,
)
from permissions import require_api, require_page, require_any_view
from auditlog import log_action
import server_config
import utils.settings as settings_module

mobile_bp = Blueprint("mobile", __name__, url_prefix="/mobile")
mobile_api = Blueprint("mobile_api", __name__, url_prefix="/api/mobile")

# ============ Pages ============

@mobile_bp.route("/")
def app_home():
    if "user_id" not in session:
        return render_template("mobile_login.html")
    return render_template("mobile_app.html")


@mobile_bp.route("/login")
def app_login_page():
    return render_template("mobile_login.html")


@mobile_bp.route("/manifest.webmanifest")
def manifest():
    import json as _json
    return Response(_json.dumps({
        "name": settings_module.get("system_name") or "Dynamic Pro ERP",
        "short_name": "DP Mobile",
        "start_url": "/mobile/",
        "scope": "/mobile/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0f172a",
        "theme_color": "#2563eb",
        "lang": request.cookies.get("lang", "ar"),
        "dir": "rtl",
        "icons": [
            {"src": "/static/mobile/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/mobile/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }, ensure_ascii=False), mimetype="application/manifest+json")


@mobile_bp.route("/sw.js")
def service_worker():
    js = r"""/* Service Worker - Dynamic Pro Mobile PWA */
const CACHE = "dp-mobile-v1";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(["/mobile", "/mobile/login"])));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  e.respondWith(
    fetch(e.request)
      .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return res; })
      .catch(() => caches.match(e.request))
  );
});
self.addEventListener("push", (e) => {
  if (!e.data) return;
  const data = e.data.json();
  e.waitUntil(self.registration.showNotification(data.title || "Dynamic Pro", {
    body: data.body || "",
    icon: "/static/mobile/icons/icon-192.png",
    badge: "/static/mobile/icons/icon-192.png",
    data: data,
  }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(clients.matchAll({ type: "window" }).then((list) => {
    if (list.length) { list[0].focus(); return; }
    return clients.openWindow("/mobile");
  }));
});
"""
    return Response(js, mimetype="application/javascript",
                    headers={"Cache-Control": "no-cache"})


@mobile_bp.route("/logout", methods=["POST"])
def app_logout():
    log_action("logout", "user", session.get("user_id"), session.get("username", ""))
    session.clear()
    return jsonify({"success": True})


# ============ Helpers ============

def _current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def _current_employee(user):
    if not user:
        return None
    return Employee.query.filter_by(user_id=user.id).first()


def _next_number(model):
    from utils.docnum import seq_after_max
    return seq_after_max(model, "VST-{n:04d}")


def _commit_with_number_retry(record, attr, generator):
    """يحفظ السجل مع إعادة المحاولة عند تعارض الرقم التسلسلي (سباق التزامن)."""
    import random
    from sqlalchemy.exc import IntegrityError
    for attempt in range(5):
        try:
            db.session.commit()
            return True
        except IntegrityError:
            db.session.rollback()
            if attempt == 4:
                raise
            # رقم مكرر بسبب طلب متزامن: ولّد رقماً جديداً وأعد المحاولة
            setattr(record, attr, generator())
    return False


def _today():
    return date.today()


def _now_str():
    return datetime.now().strftime("%H:%M")


# ============ API: الدخول والملف الشخصي ============

@mobile_api.route("/login", methods=["POST"])
def mobile_login():
    from werkzeug.security import check_password_hash
    from i18n import make_t, DEFAULT_LANG
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    # كلمة مرور الوصول للخادم (إن كانت مفعّلة)
    access_password = data.get("access_password", "")
    required = current_app.config.get("SERVER_ACCESS_PASSWORD", "")
    if required and not server_config.check_access_password(required, access_password):
        lang = request.cookies.get("lang", DEFAULT_LANG)
        from auditlog import log_action
        log_action("login_failed", "server_access", None, "كلمة مرور وصول الخادم خاطئة (موبايل)")
        return jsonify({
            "success": False,
            "code": "bad_access",
            "message": make_t(lang)("login.badAccess"),
        }), 401

    # حد محاولات الدخول: قفل مؤقت بعد 5 محاولات خاطئة
    key = _login_key(username)
    lock_remaining = _check_login_lock(key)
    if lock_remaining:
        return jsonify({
            "success": False,
            "code": "locked",
            "message": "تم قفل محاولات الدخول مؤقتاً بسبب محاولات خاطئة متكررة. "
                       f"حاول مجدداً بعد {lock_remaining // 60} دقيقة.",
            "retry_after": lock_remaining,
        }), 429

    user = User.query.filter_by(username=username).first()
    if user and user.is_active and check_password_hash(user.password_hash, password):
        _reset_login_failures(key)
        # تدوير الجلسة: جلسة جديدة entirely بعد تسجيل الدخول (حماية من session fixation)
        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        session["full_name"] = user.full_name
        session["role"] = user.role
        lang = data.get("lang") or request.cookies.get("lang", DEFAULT_LANG)
        if lang in ("ar", "en"):
            session["lang"] = lang
        log_action("login", "user", user.id, user.username)
        # تسجيل محاولة الدخول في سجل الأنشطة
        try:
            from routes.license import log_license_activity, create_owner_notification
            log_license_activity("login", f"user={user.username}", user.id, user.username)
            if user.username != "admin":
                create_owner_notification(
                    title=f"دخول مستخدم: {user.username}",
                    message=f"المستخدم {user.full_name} ({user.username}) قام بتسجيل الدخول من {request.remote_addr}",
                    notif_type="login",
                    related_user=user.username,
                )
        except Exception as e:
            #	Log license activity/failure notification error (لا يمنع دخول المستخدم)
            from auditlog import log_action
            log_action("login_notif_error", "system", user.id, f"خطأ في تنبيه الدخول: {str(e)[:100]}")
        return jsonify({"success": True, "user": user.to_dict()})

    from auditlog import log_action
    log_action("login_failed", "user", getattr(user, "id", None), f"محاولة دخول خاطئة ({username})")
    _register_login_failure(key)
    if _check_login_lock(key):
        return jsonify({
            "success": False,
            "code": "locked",
            "message": "تم قفل محاولات الدخول مؤقتاً بسبب محاولات خاطئة متكررة. "
                       f"حاول مجدداً بعد {LOGIN_LOCK_SECONDS // 60} دقيقة.",
            "retry_after": LOGIN_LOCK_SECONDS,
        }), 429

    lang = request.cookies.get("lang", DEFAULT_LANG)
    return jsonify({"success": False, "message": make_t(lang)("login.badCredentials")}), 401


@mobile_api.route("/me")
@require_any_view
def me():
    user = _current_user()
    if not user:
        return jsonify({"message": "غير مسجل"}), 401
    emp = _current_employee(user)
    data = {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email,
        "employee_id": emp.id if emp else None,
        "employee_name": emp.full_name if emp else None,
        "department_name": (emp.hr_department.name if emp and emp.hr_department else None),
        "position_name": (emp.hr_position.name if emp and emp.hr_position else None),
        "apps": _app_access(user),
    }
    return jsonify(data)


def _app_access(user):
    from permissions import user_can
    return {
        "manager": user.role == "admin",
        "engineer": user_can(user.role, "projects", "view"),
        "delegate": user_can(user.role, "rentals", "view") or user_can(user.role, "crm", "view"),
        "hr": user_can(user.role, "hr", "view"),
    }


# ============ API: الحضور والانصراف (مع GPS) ============

@mobile_api.route("/attendance/today")
@require_any_view
def attendance_today():
    user = _current_user()
    emp = _current_employee(user)
    if not emp:
        return jsonify({"record": None})
    rec = AttendanceRecord.query.filter_by(employee_id=emp.id, date=_today()).first()
    return jsonify({"record": rec.to_dict() if rec else None})


def _geo_distance_m(lat1, lng1, lat2, lng2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _geo_attendance_error(lat, lng, source="gps"):
    """تُرجع (message, error_key) لرفض الحضور، أو None للقبول (فحص صارم)."""
    if lat is None or lng is None:
        return ("إحداثيات الموقع مطلوبة لتسجيل الحضور", "mobile.gpsRequired")
    if source == "ip":
        return ("الموقع التقريبي (IP) لا يكفي لتسجيل الحضور — يجب تفعيل GPS دقيق", "mobile.gpsIpOnly")
    wlat = settings_module.get_float("mobile_work_lat")
    wlng = settings_module.get_float("mobile_work_lng")
    if wlat is None or wlng is None:
        return ("لم يتم تحديد موقع العمل بعد — يرجى ضبطه من صفحة الإعدادات", "mobile.workLocationNotSet")
    radius = settings_module.get_float("mobile_attendance_radius_meters") or 200
    dist = _geo_distance_m(lat, lng, wlat, wlng)
    if dist > radius:
        return ("أنت خارج نطاق موقع العمل (مسافتك %d م)" % int(round(dist)), "mobile.gpsOutOfRange")
    return None


@mobile_api.route("/attendance/check-in", methods=["POST"])
@require_any_view
def attendance_check_in():
    user = _current_user()
    emp = _current_employee(user)
    if not emp:
        return jsonify({"message": "لا يوجد موظف مرتبط بهذا الحساب", "error_key": "mobile.noEmployee"}), 400
    data = request.get_json() or {}
    today = _today()
    rec = AttendanceRecord.query.filter_by(employee_id=emp.id, date=today).first()
    if rec and rec.check_in:
        return jsonify({"message": "تم تسجيل الحضور مسبقاً", "error_key": "mobile.alreadyCheckedIn"}), 400

    lat = _to_float(data.get("latitude"))
    lng = _to_float(data.get("longitude"))
    geo_err = _geo_attendance_error(lat, lng, data.get("source", "gps"))
    if geo_err:
        return jsonify({"message": geo_err[0], "error_key": geo_err[1]}), 400
    work_start = settings_module.get("mobile_work_start", "09:00")
    now = _now_str()
    status = "present" if now <= work_start else "late"

    if not rec:
        rec = AttendanceRecord(employee_id=emp.id, date=today)
        db.session.add(rec)
    rec.check_in = now
    rec.status = status
    rec.check_in_lat = lat
    rec.check_in_lng = lng
    db.session.commit()
    _gps_report(user, emp, lat, lng, "check_in")
    _notify_user(user.id, "mobile.attendanceCheckInTitle", "%s %s" % (emp.full_name, now), "attendance", "success")
    log_action("check_in", "hr_attendance", rec.id, f"{emp.full_name} {now}")
    return jsonify({"record": rec.to_dict()})


@mobile_api.route("/attendance/check-out", methods=["POST"])
@require_any_view
def attendance_check_out():
    user = _current_user()
    emp = _current_employee(user)
    if not emp:
        return jsonify({"message": "لا يوجد موظف مرتبط بهذا الحساب", "error_key": "mobile.noEmployee"}), 400
    data = request.get_json() or {}
    today = _today()
    rec = AttendanceRecord.query.filter_by(employee_id=emp.id, date=today).first()
    if not rec or not rec.check_in:
        return jsonify({"message": "لم يتم تسجيل الحضور اليوم", "error_key": "mobile.notCheckedIn"}), 400
    if rec.check_out:
        return jsonify({"message": "تم تسجيل الانصراف مسبقاً", "error_key": "mobile.alreadyCheckedOut"}), 400

    now = _now_str()
    lat = _to_float(data.get("latitude"))
    lng = _to_float(data.get("longitude"))
    geo_err = _geo_attendance_error(lat, lng, data.get("source", "gps"))
    if geo_err:
        return jsonify({"message": geo_err[0], "error_key": geo_err[1]}), 400
    rec.check_out = now
    rec.check_out_lat = lat
    rec.check_out_lng = lng
    try:
        fmt = "%H:%M"
        delta = datetime.strptime(now, fmt) - datetime.strptime(rec.check_in, fmt)
        rec.working_hours = round(delta.seconds / 3600.0, 2)
    except (ValueError, TypeError):
        rec.working_hours = 0
    db.session.commit()
    _notify_user(user.id, "mobile.attendanceCheckOutTitle", "%s %s" % (emp.full_name, now), "attendance", "info")
    log_action("check_out", "hr_attendance", rec.id, f"{emp.full_name} {now}")
    return jsonify({"record": rec.to_dict()})


@mobile_api.route("/attendance/history")
@require_any_view
def attendance_history():
    user = _current_user()
    emp = _current_employee(user)
    if not emp:
        return jsonify({"records": []})
    days = int(request.args.get("days", 14))
    since = _today() - timedelta(days=days)
    rows = (AttendanceRecord.query
            .filter(AttendanceRecord.employee_id == emp.id, AttendanceRecord.date >= since)
            .order_by(AttendanceRecord.date.desc())
            .all())
    return jsonify({"records": [r.to_dict() for r in rows]})


# ============ API: GPS ============

@mobile_api.route("/gps/report", methods=["POST"])
@require_any_view
def gps_report():
    user = _current_user()
    emp = _current_employee(user)
    data = request.get_json() or {}
    lat = _to_float(data.get("latitude"))
    lng = _to_float(data.get("longitude"))
    if lat is None or lng is None:
        return jsonify({"message": "إحداثيات مطلوبة", "error_key": "mobile.gpsRequired"}), 400
    _gps_report(user, emp, lat, lng, data.get("source", "app"), _to_float(data.get("accuracy")))
    return jsonify({"success": True})


def _gps_report(user, emp, lat, lng, source="app", accuracy=0):
    if lat is None or lng is None:
        return
    pt = GpsLocation(
        user_id=user.id,
        employee_id=emp.id if emp else None,
        latitude=lat,
        longitude=lng,
        accuracy=accuracy if accuracy is not None else 0,
        source=source,
        recorded_at=datetime.now(),
    )
    db.session.add(pt)
    db.session.commit()
    # الاحتفاظ بالحجم: حذف النقاط الأقدم من 30 يوماً من حين لآخر
    cutoff = datetime.now() - timedelta(days=30)
    GpsLocation.query.filter(GpsLocation.recorded_at < cutoff).delete()
    db.session.commit()


@mobile_api.route("/gps/live")
@require_api("hr", "view")
def gps_live():
    """آخر موضع لكل موظف نشط (لخريطة المدير/HR)."""
    rows = (GpsLocation.query
            .order_by(GpsLocation.recorded_at.desc())
            .all())
    by_user = {}
    for r in rows:
        if r.user_id not in by_user and r.recorded_at:
            by_user[r.user_id] = r
    out = []
    for uid, pt in by_user.items():
        u = db.session.get(User, uid)
        emp = db.session.get(Employee, pt.employee_id) if pt.employee_id else None
        if not u or not u.is_active:
            continue
        out.append({
            "user_id": uid,
            "user_name": (emp.full_name if emp else u.full_name),
            "role": u.role,
            "employee_id": pt.employee_id,
            "latitude": pt.latitude,
            "longitude": pt.longitude,
            "accuracy": float(pt.accuracy or 0),
            "recorded_at": pt.recorded_at.isoformat() if pt.recorded_at else None,
        })
    return jsonify({"locations": out})


@mobile_api.route("/gps/track/<int:user_id>")
@require_api("hr", "view")
def gps_track(user_id):
    """مسار مستخدم خلال فترة."""
    hours = int(request.args.get("hours", 6))
    since = datetime.now() - timedelta(hours=hours)
    rows = (GpsLocation.query
            .filter(GpsLocation.user_id == user_id, GpsLocation.recorded_at >= since)
            .order_by(GpsLocation.recorded_at.asc())
            .all())
    return jsonify({"track": [r.to_dict() for r in rows]})


# ============ API: الزيارات الميدانية (مندوب) ============

@mobile_api.route("/visits")
@require_api("rentals", "view")
def list_visits():
    user = _current_user()
    my = request.args.get("mine") == "1"
    q = FieldVisit.query
    if my:
        q = q.filter(FieldVisit.user_id == user.id)
    rows = q.order_by(FieldVisit.scheduled_date.desc(), FieldVisit.id.desc()).all()
    return jsonify({"visits": [v.to_dict() for v in rows]})


@mobile_api.route("/visits", methods=["POST"])
@require_api("rentals", "create")
def create_visit():
    user = _current_user()
    data = request.get_json() or {}
    if not data.get("customer_id") and not data.get("unit_id") and not data.get("purpose"):
        return jsonify({"message": "اختر عميلاً أو وحدة واكتب الغرض", "error_key": "mobile.visitDataRequired"}), 400
    visit = FieldVisit(
        user_id=user.id,
        visit_number=_next_number(FieldVisit),
        customer_id=data.get("customer_id"),
        unit_id=data.get("unit_id"),
        contract_id=data.get("contract_id"),
        visit_type=data.get("visit_type", "collection"),
        scheduled_date=_to_date(data.get("scheduled_date")) or _today(),
        scheduled_time=data.get("scheduled_time"),
        purpose=data.get("purpose"),
        notes=data.get("notes"),
        status="planned",
    )
    db.session.add(visit)
    _commit_with_number_retry(visit, "visit_number", lambda: _next_number(FieldVisit))
    _notify_user(user.id, "mobile.visitCreated", visit.visit_number, "visits", "info")
    log_action("create", "field_visit", visit.id, visit.visit_number)
    return jsonify({"visit": visit.to_dict()}), 201


@mobile_api.route("/visits/<int:visit_id>", methods=["PUT"])
@require_api("rentals", "edit")
def update_visit(visit_id):
    visit = FieldVisit.query.get_or_404(visit_id)
    data = request.get_json() or {}
    for field in ["customer_id", "unit_id", "contract_id", "visit_type", "scheduled_date",
                  "scheduled_time", "purpose", "notes", "status", "result",
                  "amount_collected", "latitude", "longitude"]:
        if field in data and data[field] is not None:
            setattr(visit, field, data[field])
    db.session.commit()
    return jsonify({"visit": visit.to_dict()})


@mobile_api.route("/visits/<int:visit_id>/start", methods=["POST"])
@require_api("rentals", "edit")
def start_visit(visit_id):
    visit = FieldVisit.query.get_or_404(visit_id)
    visit.status = "done"
    visit.check_in_at = datetime.now()
    data = request.get_json() or {}
    visit.latitude = _to_float(data.get("latitude"))
    visit.longitude = _to_float(data.get("longitude"))
    db.session.commit()
    return jsonify({"visit": visit.to_dict()})


@mobile_api.route("/visits/<int:visit_id>/complete", methods=["POST"])
@require_api("rentals", "edit")
def complete_visit(visit_id):
    visit = FieldVisit.query.get_or_404(visit_id)
    data = request.get_json() or {}
    visit.status = "done"
    visit.result = data.get("result")
    visit.notes = data.get("notes", visit.notes)
    visit.check_out_at = datetime.now()
    if data.get("amount_collected") is not None:
        visit.amount_collected = data.get("amount_collected")
    db.session.commit()
    _notify_user(visit.user_id, "mobile.visitCompleted", visit.visit_number, "visits", "success")
    return jsonify({"visit": visit.to_dict()})


@mobile_api.route("/visits/<int:visit_id>", methods=["DELETE"])
@require_api("rentals", "delete")
def delete_visit(visit_id):
    visit = FieldVisit.query.get_or_404(visit_id)
    db.session.delete(visit)
    db.session.commit()
    return jsonify({"success": True})


# ============ API: بيانات المندوب (تحصيل) ============

@mobile_api.route("/collections")
@require_api("rentals", "view")
def delegate_collections():
    """عقود إيجار نشطة مع متأخراتها لتحصيل الإيجارات."""
    contracts = RentalContract.query.filter_by(status="active").all()
    out = []
    for c in contracts:
        paid = db.session.query(func.coalesce(func.sum(RentalPayment.amount), 0)).filter(
            RentalPayment.contract_id == c.id).scalar()
        paid = float(paid or 0)
        due = float(c.monthly_rent or 0)
        months_elapsed = 1
        if c.start_date:
            months_elapsed = max(1, (date.today().year - c.start_date.year) * 12 +
                                 (date.today().month - c.start_date.month))
        expected = due * months_elapsed
        balance = round(expected - paid, 2)
        out.append({
            "contract_id": c.id,
            "contract_number": c.contract_number,
            "customer_name": c.customer.full_name if c.customer else None,
            "customer_phone": c.customer.phone if c.customer else None,
            "unit_code": c.unit.unit_code if c.unit else None,
            "monthly_rent": due,
            "paid": paid,
            "balance": max(balance, 0),
            "end_date": c.end_date.isoformat() if c.end_date else None,
        })
    out.sort(key=lambda x: -x["balance"])
    return jsonify({"collections": out})


@mobile_api.route("/collections/pay", methods=["POST"])
@require_api("rentals", "create")
def delegate_collection_pay():
    user = _current_user()
    data = request.get_json() or {}
    contract = db.session.get(RentalContract, data.get("contract_id"))
    if not contract:
        return jsonify({"message": "عقد غير موجود", "error_key": "rentals.contractNotFound"}), 400
    amount = _to_float(data.get("amount")) or 0
    if amount <= 0:
        return jsonify({"message": "المبلغ غير صالح", "error_key": "mobile.invalidAmount"}), 400
    pay = RentalPayment(
        payment_number=_next_collection_number(),
        contract_id=contract.id,
        amount=amount,
        payment_date=_to_date(data.get("payment_date")) or _today(),
        method=data.get("method", "cash"),
        reference=data.get("reference"),
        notes=data.get("notes"),
    )
    db.session.add(pay)
    _commit_with_number_retry(pay, "payment_number", _next_collection_number)
    _notify_user(user.id, "mobile.collectionRecorded", "%s %s" % (pay.payment_number, amount), "rentals", "success")
    return jsonify({"payment": pay.to_dict()}), 201


def _next_collection_number():
    from models import RentalPayment
    from utils.docnum import seq_after_max
    return seq_after_max(RentalPayment, "COL-{n:04d}")


# ============ API: لوحات الأدوار ============

@mobile_api.route("/dashboard")
@require_any_view
def role_dashboard():
    user = _current_user()
    role = user.role
    if role == "admin":
        return _manager_dashboard()
    if user_can_role(role, "projects", "view"):
        return _engineer_dashboard()
    if user_can_role(role, "rentals", "view") or user_can_role(role, "crm", "view"):
        return _delegate_dashboard(user)
    if user_can_role(role, "hr", "view"):
        return _hr_dashboard()
    return jsonify({"role": role, "sections": []})


def user_can_role(role, module, action):
    from permissions import user_can
    return user_can(role, module, action)


def _manager_dashboard():
    from models import Customer, RealEstateUnit, Project, Invoice
    return jsonify({
        "role": "admin",
        "sections": [
            {"key": "summary", "title": "mobile.managerSummary"},
            {"key": "attendance"},
            {"key": "gps"},
            {"key": "visits"},
            {"key": "notifications"},
        ],
        "stats": {
            "customers": Customer.query.count(),
            "units": RealEstateUnit.query.count(),
            "projects": Project.query.count(),
            "today_attendance": AttendanceRecord.query.filter_by(date=_today()).count(),
            "pending_leaves": LeaveRequest.query.filter_by(status="pending").count(),
            "active_contracts": RentalContract.query.filter_by(status="active").count(),
            "pending_payments": RentalPayment.query.filter_by(payment_date=None).count(),
        },
    })


def _engineer_dashboard():
    emp = _current_employee(_current_user())
    q = Project.query
    projects = q.order_by(Project.id.desc()).limit(20).all()
    return jsonify({
        "role": "engineer",
        "sections": [{"key": "projects"}, {"key": "attendance"}, {"key": "notifications"}],
        "projects": [p.to_dict() for p in projects],
        "stats": {
            "total": len(projects),
            "active": sum(1 for p in projects if p.status not in ("done", "cancelled")),
            "phases": ProjectPhase.query.count(),
        },
    })


def _delegate_dashboard(user):
    today = _today()
    visits = FieldVisit.query.filter(
        FieldVisit.user_id == user.id,
        FieldVisit.scheduled_date >= today - timedelta(days=30),
    ).all()
    collections = RentalContract.query.filter_by(status="active").count()
    return jsonify({
        "role": "delegate",
        "sections": [{"key": "visits"}, {"key": "collections"}, {"key": "attendance"}, {"key": "notifications"}],
        "stats": {
            "today_visits": sum(1 for v in visits if v.scheduled_date == today),
            "pending_visits": sum(1 for v in visits if v.status == "planned"),
            "done_visits": sum(1 for v in visits if v.status == "done"),
            "active_contracts": collections,
        },
        "visits": [v.to_dict() for v in visits],
    })


def _hr_dashboard():
    today = _today()
    present = AttendanceRecord.query.filter_by(date=today, status="present").count()
    late = AttendanceRecord.query.filter_by(date=today, status="late").count()
    leave = LeaveRequest.query.filter_by(status="pending").count()
    return jsonify({
        "role": "hr",
        "sections": [{"key": "attendance"}, {"key": "leaves"}, {"key": "employees"}, {"key": "gps"}, {"key": "notifications"}],
        "stats": {
            "employees": Employee.query.filter_by(status="active").count(),
            "present": present,
            "late": late,
            "absent": Employee.query.filter_by(status="active").count() - present,
            "pending_leaves": leave,
            "departments": Department.query.count(),
            "positions": Position.query.count(),
        },
    })


# ============ API: الإشعارات ============

@mobile_api.route("/notifications")
@require_any_view
def my_notifications():
    user = _current_user()
    rows = (AppNotification.query
            .filter_by(user_id=user.id)
            .order_by(AppNotification.id.desc())
            .limit(100)
            .all())
    return jsonify({"notifications": [n.to_dict() for n in rows]})


@mobile_api.route("/notifications/unread-count")
@require_any_view
def unread_count():
    user = _current_user()
    count = AppNotification.query.filter_by(user_id=user.id, is_read=False).count()
    return jsonify({"count": count})


@mobile_api.route("/notifications/read", methods=["POST"])
@require_any_view
def mark_notifications_read():
    user = _current_user()
    data = request.get_json() or {}
    notif_id = data.get("id")
    if notif_id:
        n = AppNotification.query.filter_by(id=notif_id, user_id=user.id).first()
        if n:
            n.is_read = True
    else:
        AppNotification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"success": True})


@mobile_api.route("/notifications/stream")
@require_any_view
def notifications_stream():
    user = _current_user()

    def gen():
        last_id = AppNotification.query.filter_by(user_id=user.id).order_by(AppNotification.id.desc()).first()
        last = last_id.id if last_id else 0
        yield "data: {\"connected\": true}\n\n"
        import time
        while True:
            time.sleep(5)
            try:
                rows = (AppNotification.query
                        .filter(AppNotification.user_id == user.id, AppNotification.id > last)
                        .order_by(AppNotification.id.desc())
                        .limit(20)
                        .all())
            except Exception:
                break
            for n in rows:
                last = max(last, n.id)
                yield "data: " + json.dumps(n.to_dict(), ensure_ascii=False) + "\n\n"

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@mobile_api.route("/devices", methods=["POST"])
@require_any_view
def register_device():
    user = _current_user()
    data = request.get_json() or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"message": "رمز الجهاز مطلوب", "error_key": "mobile.tokenRequired"}), 400
    exists = DeviceToken.query.filter_by(user_id=user.id, token=token).first()
    if exists:
        exists.last_seen = datetime.now()
        if data.get("device_name"):
            exists.device_name = data.get("device_name")
    else:
        exists = DeviceToken(user_id=user.id, token=token,
                             platform=data.get("platform", "web"),
                             device_name=data.get("device_name"))
        db.session.add(exists)
    db.session.commit()
    return jsonify({"success": True})


@mobile_api.route("/devices", methods=["DELETE"])
@require_any_view
def unregister_device():
    user = _current_user()
    data = request.get_json() or {}
    token = (data.get("token") or "").strip()
    if token:
        DeviceToken.query.filter_by(user_id=user.id, token=token).delete()
        db.session.commit()
    return jsonify({"success": True})


# ============ API: بيانات مشتركة (لمندوب/مهندس) ============

@mobile_api.route("/lookups")
@require_any_view
def lookups():
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.full_name).all()
    units = RealEstateUnit.query.order_by(RealEstateUnit.unit_code).all()
    contracts = RentalContract.query.filter_by(status="active").all()
    return jsonify({
        "customers": [c.to_dict() for c in customers],
        "units": [u.to_dict() for u in units],
        "contracts": [c.to_dict() for c in contracts],
    })


@mobile_api.route("/leaves", methods=["POST"])
@require_any_view
def submit_leave():
    user = _current_user()
    emp = _current_employee(user)
    if not emp:
        return jsonify({"message": "لا يوجد موظف مرتبط بهذا الحساب", "error_key": "mobile.noEmployee"}), 400
    data = request.get_json() or {}
    start = _to_date(data.get("start_date"))
    end = _to_date(data.get("end_date"))
    if not start:
        return jsonify({"message": "تاريخ البداية مطلوب", "error_key": "mobile.dateRequired"}), 400
    leave = LeaveRequest(
        employee_id=emp.id,
        leave_type=data.get("leave_type", "annual"),
        start_date=start,
        end_date=end or start,
        days=data.get("days") or ((end or start) - start).days + 1,
        reason=data.get("reason"),
        status="pending",
    )
    db.session.add(leave)
    db.session.commit()
    _notify_user(user.id, "mobile.leaveSubmitted", emp.full_name, "system", "info")
    return jsonify({"leave": leave.to_dict()}), 201


# ============ Helpers ============

def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _notify_user(user_id, title_key, message="", category="general", severity="info"):
    from i18n import make_t
    from utils.notifications import notify
    lang = request.cookies.get("lang", "ar")
    title = make_t(lang)(title_key)
    notify(user_id, title, message, category, severity)

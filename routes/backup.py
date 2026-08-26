import base64
import glob
import json
import os
import threading
import time
from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, request, jsonify, Response
from sqlalchemy import Date, DateTime
from database import db
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from models import (
    User, Employee, Project, Customer, Supplier, RealEstateUnit,
    Invoice, InvoiceItem, PurchaseOrder, PurchaseOrderItem, RentalContract,
    PaymentPlan, Installment, AuditLog, Role, Company, Branch, FinancialYear,
    Currency, TaxType, SystemSetting,
    WorkflowTemplate, WorkflowStep, ApprovalRequest, ApprovalStepRecord,
    Account, CostCenter, JournalEntry, JournalEntryLine,
    FixedAsset, DepreciationRecord, BudgetLine,
    ProjectPhase, WBSItem, BoqItem, PriceAnalysisItem,
    Subcontractor, ProjectContract, ProgressStatement, ChangeOrder,
    ProjectProgress, ExecutionLog, ProjectCost, ProjectRisk,
    ProjectQuality, SiteLog, Equipment, LaborAssignment,
    Building, Floor, UnitType, Owner, UnitPriceHistory,
    Reservation, Allocation, SalesContract, Commission,
    UnitDelivery, MaintenanceRequest, UnitShare, Broker,
    CrmPipelineStage, Lead, Opportunity, CallLog, Meeting,
    CrmTask, Campaign, CampaignLead, FollowUp,
    Quote, QuoteItem, CrmContract, Complaint, SupportTicket,
    EscrowAccount, EscrowTransaction,
    ConstructionMilestone, DSPPlan, TitleDeed,
    UnitDocument, OwnerAssociation, ServiceCharge,
)
# PropTech (may not be in __init__ yet — import directly as fallback)
try:
    from models.proptech import DeliveryChecklistItem, TenantScreening, UnitMortgage
except ImportError:
    DeliveryChecklistItem = TenantScreening = UnitMortgage = None
from permissions import require_api
from auditlog import log_action

backup_bp = Blueprint("backup", __name__, url_prefix="/api/backup")


# الترتيب: أبناء قبل الآباء (حذف آمن مع قيود FK)، والاستعادة تعكسه.
_TABLES = [
    # --- PropTech / Escrow / OffPlan / Addons (أبناء أولاً) ---
    ("escrow_transactions", EscrowTransaction),
    ("title_deeds", TitleDeed),
    ("dsp_plans", DSPPlan),
    ("service_charges", ServiceCharge),
    ("unit_documents", UnitDocument),
    ("delivery_checklist_items", DeliveryChecklistItem) if DeliveryChecklistItem else None,
    ("tenant_screenings", TenantScreening) if TenantScreening else None,
    ("unit_mortgages", UnitMortgage) if UnitMortgage else None,
    ("escrow_accounts", EscrowAccount),
    ("construction_milestones", ConstructionMilestone),
    ("owner_associations", OwnerAssociation),
    ("real_estate_brokers", Broker),
]
# إزالة المدخلات الفارغة (إن فشل استيراد PropTech)
_TABLES = [t for t in _TABLES if t is not None and t[1] is not None]
_TABLES += [
    # --- وحدة CRM (أبناء أولاً: حذف آمن مع FK) ---
    ("crm_quote_items", QuoteItem),
    ("crm_contracts", CrmContract),
    ("crm_complaints", Complaint),
    ("crm_tickets", SupportTicket),
    ("crm_campaign_leads", CampaignLead),
    ("crm_follow_ups", FollowUp),
    ("crm_quotes", Quote),
    ("crm_tasks", CrmTask),
    ("crm_meetings", Meeting),
    ("crm_calls", CallLog),
    ("crm_opportunities", Opportunity),
    ("crm_leads", Lead),
    ("crm_campaigns", Campaign),
    ("crm_pipeline_stages", CrmPipelineStage),
    # --- وحدة الاستثمار العقاري (أبناء أولاً: حذف آمن مع FK) ---
    ("commissions", Commission),
    ("sales_contracts", SalesContract),
    ("unit_reservations", Reservation),
    ("unit_allocations", Allocation),
    ("unit_deliveries", UnitDelivery),
    ("maintenance_requests", MaintenanceRequest),
    ("unit_shares", UnitShare),
    ("unit_price_history", UnitPriceHistory),
    ("installments", Installment),
    ("payment_plans", PaymentPlan),
    ("rental_contracts", RentalContract),
    ("real_estate_units", RealEstateUnit),
    ("real_estate_floors", Floor),
    ("real_estate_buildings", Building),
    ("unit_types", UnitType),
    ("real_estate_owners", Owner),
    ("project_quality", ProjectQuality),
    ("purchase_order_items", PurchaseOrderItem),
    ("invoice_items", InvoiceItem),
    ("project_risks", ProjectRisk),
    ("project_execution_logs", ExecutionLog),
    ("branches", Branch),
    ("project_site_logs", SiteLog),
    ("budget_lines", BudgetLine),
    ("project_change_orders", ChangeOrder),
    ("progress_statements", ProgressStatement),
    ("project_contracts", ProjectContract),
    ("approval_step_records", ApprovalStepRecord),
    ("project_costs", ProjectCost),
    ("audit_logs", AuditLog),
    ("approval_requests", ApprovalRequest),
    ("invoices", Invoice),
    ("roles", Role),
    ("workflow_steps", WorkflowStep),
    ("workflow_templates", WorkflowTemplate),
    ("subcontractors", Subcontractor),
    ("project_phases", ProjectPhase),
    ("system_settings", SystemSetting),
    ("purchase_orders", PurchaseOrder),
    ("suppliers", Supplier),
    ("tax_types", TaxType),
    ("project_price_analysis", PriceAnalysisItem),
    ("depreciation_records", DepreciationRecord),
    ("labor_assignments", LaborAssignment),
    ("customers", Customer),
    ("fixed_assets", FixedAsset),
    ("project_progress", ProjectProgress),
    ("project_boq_items", BoqItem),
    ("project_wbs_items", WBSItem),
    ("currencies", Currency),
    ("equipment", Equipment),
    ("journal_entry_lines", JournalEntryLine),
    ("cost_centers", CostCenter),
    ("accounts", Account),
    ("journal_entries", JournalEntry),
    ("users", User),
    ("financial_years", FinancialYear),
    ("companies", Company),
    ("projects", Project),
    ("employees", Employee),
]


def _dump():
    out = {}
    for key, model in _TABLES:
        rows = []
        for obj in model.query.all():
            row = {}
            for col in model.__table__.columns:
                val = getattr(obj, col.name)
                if isinstance(val, (datetime, date)):
                    val = val.isoformat()
                elif isinstance(val, Decimal):
                    val = float(val)
                row[col.name] = val
            rows.append(row)
        out[key] = rows
    return out


def _sorted_rows(model, rows):
    """يرتب الصفوف داخل الجدول لضمان إدراج الآباء قبل الأبناء (إشارات ذاتية مثل accounts)."""
    cols = {c.name for c in model.__table__.columns}
    if "parent_id" not in cols or "id" not in cols:
        return rows
    id_map = {row.get("id"): row for row in rows if row.get("id") is not None}
    out, visited = [], set()

    def visit(row, stack):
        rid = row.get("id")
        if rid in visited or rid is None:
            return
        if rid in stack:
            return
        stack = stack | {rid}
        pid = row.get("parent_id")
        if pid is not None and pid in id_map:
            visit(id_map[pid], stack)
        visited.add(rid)
        out.append(row)

    for row in rows:
        visit(row, frozenset())
    return out


# ============ تشفير النسخ الاحتياطية (AES-256-GCM بكلمة مرور) ============
# يُشتق المفتاح من كلمة المرور عبر PBKDF2-SHA256، ويُعمَّل التشفير بـ AES-GCM
# (salt و nonce مختلفان لكل ملف لضمان مرونة عشوائية عالية حتى لنفس المحتوى).
_PBKDF2_ITERATIONS = 200_000
_BACKUP_FORMAT = "dynamicpro-backup-aes-gcm"


def _derive_key(password, salt):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _encrypt_payload(payload_bytes, password):
    """يُشفر محتوى النسخة الاحتياطية ويعيد حاوية JSON آمنة."""
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    ciphertext = encryptor.update(payload_bytes) + encryptor.finalize()
    return {
        "format": _BACKUP_FORMAT,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "tag": base64.b64encode(encryptor.tag).decode("ascii"),
        "data": base64.b64encode(ciphertext).decode("ascii"),
    }


def _decrypt_payload(container, password):
    """يفك تشفير حاوية النسخة الاحتياطية ويعيد البايتات الأصلية."""
    salt = base64.b64decode(container["salt"])
    nonce = base64.b64decode(container["nonce"])
    tag = base64.b64decode(container["tag"])
    ciphertext = base64.b64decode(container["data"])
    key = _derive_key(password, salt)
    decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def _restore(data):
    for key, model in _TABLES:
        db.session.query(model).delete()
    db.session.commit()

    for key, model in reversed(_TABLES):
        for row in _sorted_rows(model, data.get(key, [])):
            obj = model()
            for col in model.__table__.columns:
                name = col.name
                if name not in row or row[name] is None:
                    continue
                val = row[name]
                if isinstance(col.type, DateTime):
                    val = datetime.fromisoformat(val)
                elif isinstance(col.type, Date):
                    val = date.fromisoformat(val)
                setattr(obj, name, val)
            db.session.add(obj)
        db.session.commit()

    # إعادة تعيين تسلسل المعرفات (PostgreSQL sequences)
    try:
        for key, model in _TABLES:
            pk = model.__table__.primary_key.columns.keys()[0]
            max_id = db.session.query(db.func.max(getattr(model, pk))).scalar()
            if max_id:
                seq_name = f"{model.__tablename__}_{pk}_seq"
                db.session.execute(
                    db.text(
                        "SELECT setval(:seq, :n, true)"
                    ),
                    {"seq": seq_name, "n": int(max_id)},
                )
        db.session.commit()
    except Exception:
        db.session.rollback()


@backup_bp.route("/export")
@require_api("backup", "create")
def export_backup():
    data = {
        "app": "Dynamic Pro ERP",
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        **_dump(),
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # كلمة المرور تُقرأ من الهيدر فقط (لا تُمرَّر في الـ URL حتى لا تتسرب إلى السجلات)
    password = (request.headers.get("X-Backup-Password") or "").strip()
    if password:
        container = _encrypt_payload(
            json.dumps(data, ensure_ascii=False).encode("utf-8"), password
        )
        payload = json.dumps(container, ensure_ascii=False)
        filename = f"backup_{stamp}.dyncpro"
        mimetype = "application/octet-stream"
    else:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        filename = f"backup_{stamp}.json"
        mimetype = "application/json"
    resp = Response(payload, mimetype=mimetype)
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@backup_bp.route("/import", methods=["POST"])
@require_api("backup", "create")
def import_backup():
    # حد حجم الملف: 100MB كحد أقصى لمنع DoS
    MAX_BACKUP_SIZE = 100 * 1024 * 1024
    file = request.files.get("file")
    if not file:
        return jsonify({"message": "ملف مطلوب", "error_key": "backup.fileRequired"}), 400
    # تحقق من امتداد الملف
    fname = (file.filename or "").lower()
    if not (fname.endswith(".json") or fname.endswith(".dyncpro")):
        return jsonify({"message": "صيغة الملف غير مدعومة — استخدم .json أو .dyncpro", "error_key": "backup.invalidExtension"}), 400
    # قراءة مع حد الحجم
    file.seek(0, 2)
    fsize = file.tell()
    file.seek(0)
    if fsize > MAX_BACKUP_SIZE:
        return jsonify({"message": "حجم الملف كبير جداً (الحد 100MB)", "error_key": "backup.tooLarge"}), 413
    if fsize == 0:
        return jsonify({"message": "الملف فارغ", "error_key": "backup.emptyFile"}), 400
    raw = file.read(MAX_BACKUP_SIZE + 1)
    if len(raw) > MAX_BACKUP_SIZE:
        return jsonify({"message": "حجم الملف كبير جداً", "error_key": "backup.tooLarge"}), 413
    # كلمة مرور فك التشفير (تُقرأ من حقل النموذج أو الهيدر)
    password = (
        request.form.get("password")
        or request.headers.get("X-Backup-Password")
        or ""
    ).strip()
    try:
        container = json.loads(raw.decode("utf-8"))
    except Exception:
        container = None
    if isinstance(container, dict) and container.get("format") == _BACKUP_FORMAT:
        if not password:
            return jsonify({
                "message": "كلمة مرور التشفير مطلوبة",
                "error_key": "backup.passwordRequired",
            }), 400
        try:
            plain = _decrypt_payload(container, password)
            data = json.loads(plain.decode("utf-8"))
        except Exception:
            return jsonify({
                "message": "كلمة مرور غير صحيحة أو ملف تالف",
                "error_key": "backup.badPassword",
            }), 400
    else:
        data = container
    if not isinstance(data, dict) or "users" not in data:
        return jsonify({"message": "ملف غير صالح", "error_key": "backup.invalidFile"}), 400
    try:
        _restore(data)
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "message": "فشلت الاستعادة",
            "error_key": "backup.restoreFailed",
            "detail": str(e),
        }), 400
    return jsonify({"success": True})


# ============ النسخ الاحتياطي التلقائي ============

def _run_auto_backup_once(app):
    import utils.settings as settings
    if not settings.get_bool("backup_auto_enabled", False):
        return
    interval_days = settings.get_int("backup_auto_interval_days", 1) or 1
    last_raw = (settings.get("backup_auto_last", "") or "").strip()
    now = datetime.now()
    due = True
    if last_raw:
        try:
            last = datetime.fromisoformat(last_raw)
            due = (now - last).total_seconds() >= interval_days * 86400
        except ValueError:
            due = True
    if not due:
        return

    folder = (settings.get("backup_auto_folder", "") or "").strip()
    if not folder:
        folder = os.path.join(app.instance_path, "backups")
    # حماية من Path Traversal — السماح فقط داخل instance_path أو مسار صريح آمن
    try:
        folder_abs = os.path.abspath(folder)
        allowed_root = os.path.abspath(app.instance_path)
        # اسمح أيضاً بمجلد النسخ الافتراضي فقط خارج instance_path إذا كان صريحاً وموجوداً
        if not folder_abs.startswith(allowed_root):
            # تحقق من أن المسار لا يحتوي على .. وأنه مجلد موجود/قابل للإنشاء بأمان
            if ".." in folder or not os.path.isabs(folder_abs):
                folder = os.path.join(app.instance_path, "backups")
                folder_abs = os.path.abspath(folder)
            # إذا كان المسار مطلقاً خارج instance_path، تأكد أنه ليس جذر النظام
            if folder_abs in (os.path.abspath(os.sep), os.path.abspath("C:\\"), os.path.abspath("D:\\")):
                folder = os.path.join(app.instance_path, "backups")
                folder_abs = os.path.abspath(folder)
        folder = folder_abs
    except Exception:
        folder = os.path.join(app.instance_path, "backups")
    os.makedirs(folder, exist_ok=True)

    payload = json.dumps({
        "app": "Dynamic Pro ERP",
        "version": 1,
        "exported_at": now.isoformat(),
        **_dump(),
    }, ensure_ascii=False, indent=2)
    # تشفير النسخة التلقائية بكلمة مرور (إن كانت مضبوطة في الإعدادات)
    password = (settings.get("backup_encryption_password", "") or "").strip()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    if password:
        container = _encrypt_payload(payload.encode("utf-8"), password)
        filename = f"auto_backup_{stamp}.dyncpro"
        content = json.dumps(container, ensure_ascii=False)
    else:
        filename = f"auto_backup_{stamp}.json"
        content = payload
    with open(os.path.join(folder, filename), "w", encoding="utf-8") as fh:
        fh.write(content)

    keep = settings.get_int("backup_auto_keep", 10) or 10
    files = sorted(glob.glob(os.path.join(folder, "auto_backup_*")))
    for old in files[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass

    settings.set("backup_auto_last", now.isoformat())
    db.session.commit()


_scheduler_started = False


def schedule_auto_backup(app):
    """خيط خلفي يفحص كل دقيقة هل حان موعد النسخة التلقائية."""
    global _scheduler_started
    if _scheduler_started:
        return None
    _scheduler_started = True

    def worker():
        while True:
            try:
                with app.app_context():
                    _run_auto_backup_once(app)
            except Exception as e:
                try:
                    with app.app_context():
                        log_action("error", "backup", None,
                                   "خطأ في النسخ الاحتياطي التلقائي: %s" % e)
                        db.session.commit()
                except Exception:
                    pass
            time.sleep(60)

    t = threading.Thread(target=worker, daemon=True, name="auto-backup")
    t.start()
    return t


@backup_bp.route("/settings", methods=["GET"])
@require_api("backup", "view")
def get_backup_settings():
    import utils.settings as settings
    data = settings.get_all()
    enc_pw = data.get("backup_encryption_password", "")
    return jsonify({
        "success": True,
        "settings": {
            "backup_auto_enabled": settings.get_bool("backup_auto_enabled", False),
            "backup_auto_interval_days": settings.get_int("backup_auto_interval_days", 1),
            "backup_auto_folder": data.get("backup_auto_folder", ""),
            "backup_auto_keep": settings.get_int("backup_auto_keep", 10),
            "backup_auto_last": data.get("backup_auto_last", ""),
            "backup_encryption_password_set": bool(enc_pw),
            # لا نعيد كلمة المرور نفسها — فقط هل هي مضبوطة
        },
    })


@backup_bp.route("/settings", methods=["POST"])
@require_api("backup", "edit")
def save_backup_settings():
    import utils.settings as settings
    data = request.get_json(silent=True) or {}
    if "backup_auto_enabled" in data:
        settings.set("backup_auto_enabled", "1" if data["backup_auto_enabled"] else "0")
    if "backup_auto_interval_days" in data:
        try:
            interval = max(1, int(data["backup_auto_interval_days"]))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error_key": "backup.invalidInterval"}), 400
        settings.set("backup_auto_interval_days", interval)
    if "backup_auto_keep" in data:
        try:
            keep = max(1, int(data["backup_auto_keep"]))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error_key": "backup.invalidKeep"}), 400
        settings.set("backup_auto_keep", keep)
    if "backup_auto_folder" in data:
        raw_folder = (data["backup_auto_folder"] or "").strip()
        if raw_folder:
            # منع Path Traversal
            if ".." in raw_folder or raw_folder.startswith("\\\\"):
                return jsonify({"success": False, "error_key": "backup.invalidFolder"}), 400
            # منع المسارات الخطرة (جذر النظام)
            abs_check = os.path.abspath(raw_folder)
            if abs_check in (os.path.abspath(os.sep), os.path.abspath("C:\\"), os.path.abspath("D:\\")):
                return jsonify({"success": False, "error_key": "backup.invalidFolder"}), 400
        settings.set("backup_auto_folder", raw_folder)
    if "backup_encryption_password" in data:
        settings.set("backup_encryption_password", (data["backup_encryption_password"] or "").strip())
    db.session.commit()
    log_action("edit", "backup", None, "تعديل إعدادات النسخ الاحتياطي التلقائي")
    return jsonify({"success": True})

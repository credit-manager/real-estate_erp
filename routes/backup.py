import base64
import glob
import json
import os
import threading
import time
from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, request, jsonify, Response
from sqlalchemy import Date, DateTime, Numeric, text
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
try:
    from models.proptech import DeliveryChecklistItem, TenantScreening, UnitMortgage
except ImportError:
    DeliveryChecklistItem = TenantScreening = UnitMortgage = None
from permissions import require_api
from auditlog import log_action

backup_bp = Blueprint("backup", __name__, url_prefix="/api/backup")

_TABLES = [
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
_TABLES = [t for t in _TABLES if t is not None and t[1] is not None]
_TABLES += [
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
                    val = format(val, "f")
                row[col.name] = val
            rows.append(row)
        out[key] = rows
    return out


def _sorted_rows(model, rows):
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
    salt = base64.b64decode(container["salt"])
    nonce = base64.b64decode(container["nonce"])
    tag = base64.b64decode(container["tag"])
    ciphertext = base64.b64decode(container["data"])
    key = _derive_key(password, salt)
    decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def _restore(data):
    """Restore all tables in one transaction so failures roll back cleanly."""
    for _, model in _TABLES:
        db.session.query(model).delete()

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
                elif isinstance(col.type, Numeric):
                    val = Decimal(str(val))
                setattr(obj, name, val)
            db.session.add(obj)

    # Keep PostgreSQL sequences aligned after explicit primary-key restoration.
    try:
        for _, model in _TABLES:
            pk_columns = list(model.__table__.primary_key.columns)
            if not pk_columns:
                continue
            pk = pk_columns[0].name
            max_id = db.session.query(db.func.max(getattr(model, pk))).scalar()
            if max_id:
                seq_name = f"{model.__tablename__}_{pk}_seq"
                db.session.execute(text("SELECT setval(:seq, :n, true)"), {"seq": seq_name, "n": int(max_id)})
    except Exception:
        # SQLite has no PostgreSQL sequence catalogue; sequence reset is optional.
        pass

    db.session.commit()


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
    password = (request.headers.get("X-Backup-Password") or "").strip()
    if password:
        container = _encrypt_payload(json.dumps(data, ensure_ascii=False).encode("utf-8"), password)
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
    MAX_BACKUP_SIZE = 100 * 1024 * 1024
    file = request.files.get("file")
    if not file:
        return jsonify({"message": "ملف مطلوب", "error_key": "backup.fileRequired"}), 400
    fname = (file.filename or "").lower()
    if not (fname.endswith(".json") or fname.endswith(".dyncpro")):
        return jsonify({"message": "صيغة الملف غير مدعومة — استخدم .json أو .dyncpro", "error_key": "backup.invalidExtension"}), 400
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
    password = (request.form.get("password") or request.headers.get("X-Backup-Password") or "").strip()
    try:
        container = json.loads(raw.decode("utf-8"))
    except Exception:
        container = None
    if isinstance(container, dict) and container.get("format") == _BACKUP_FORMAT:
        if not password:
            return jsonify({"message": "كلمة مرور التشفير مطلوبة", "error_key": "backup.passwordRequired"}), 400
        try:
            raw = _decrypt_payload(container, password)
        except Exception:
            return jsonify({"message": "فشل فك تشفير النسخة الاحتياطية", "error_key": "backup.decryptFailed"}), 400
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return jsonify({"message": "محتوى النسخة الاحتياطية غير صالح", "error_key": "backup.invalidJson"}), 400
    if not isinstance(data, dict) or data.get("app") != "Dynamic Pro ERP":
        return jsonify({"message": "ملف النسخة الاحتياطية غير صالح", "error_key": "backup.invalidFormat"}), 400
    try:
        _restore(data)
    except Exception:
        db.session.rollback()
        log_action("backup_restore_failed", details={"filename": file.filename or "unknown"})
        return jsonify({"message": "فشلت استعادة النسخة الاحتياطية وتم التراجع عن التغييرات", "error_key": "backup.restoreFailed"}), 422
    log_action("backup_restored", details={"filename": file.filename or "unknown"})
    return jsonify({"success": True, "message": "تمت الاستعادة بنجاح"}), 200

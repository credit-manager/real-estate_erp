"""حسابات الضمان العقاري — Escrow Accounts (وافي/Oqood)."""
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, request, jsonify, session
from sqlalchemy.exc import IntegrityError

from database import db
from models import EscrowAccount, EscrowTransaction, Project, SalesContract
from permissions import require_api
from auditlog import log_action

escrow_bp = Blueprint("escrow", __name__, url_prefix="/api/escrow")


def _next_escrow_number():
    year = datetime.now().year
    prefix = f"ESC-{year}-"
    last = (EscrowAccount.query
            .filter(EscrowAccount.escrow_number.like(prefix + "%"))
            .order_by(EscrowAccount.id.desc()).first())
    seq = 1
    if last and last.escrow_number:
        try:
            seq = int(last.escrow_number.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            seq = EscrowAccount.query.count() + 1
    return f"{prefix}{seq:04d}"


# ============ Accounts ============

@escrow_bp.route("/accounts", methods=["GET"])
@require_api("realestate", "view")
def list_accounts():
    q = EscrowAccount.query.filter(EscrowAccount.deleted_at.is_(None))
    project_id = request.args.get("project_id", type=int)
    if project_id:
        q = q.filter(EscrowAccount.project_id == project_id)
    status = request.args.get("status")
    if status:
        q = q.filter(EscrowAccount.status == status)
    return jsonify([a.to_dict() for a in q.order_by(EscrowAccount.id.desc()).all()])


@escrow_bp.route("/accounts", methods=["POST"])
@require_api("realestate", "create")
def create_account():
    data = request.get_json() or {}
    project_id = data.get("project_id")
    bank_name = (data.get("bank_name") or "").strip()
    if not project_id:
        return jsonify({"message": "المشروع مطلوب", "error_key": "escrow.projectRequired"}), 400
    if not bank_name:
        return jsonify({"message": "اسم البنك مطلوب", "error_key": "escrow.bankRequired"}), 400
    if not db.session.get(Project, project_id):
        return jsonify({"message": "المشروع غير موجود", "error_key": "escrow.projectNotFound"}), 404

    acc = EscrowAccount(
        project_id=project_id,
        escrow_number=data.get("escrow_number") or _next_escrow_number(),
        bank_name=bank_name,
        iban=(data.get("iban") or "").strip(),
        status=data.get("status", "active"),
        notes=(data.get("notes") or "").strip(),
    )
    db.session.add(acc)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "رقم حساب الضمان مكرر", "error_key": "escrow.duplicateNumber"}), 409
    log_action("create", "escrow_account", acc.id, acc.escrow_number)
    return jsonify(acc.to_dict()), 201


@escrow_bp.route("/accounts/<int:acc_id>", methods=["PUT"])
@require_api("realestate", "edit")
def update_account(acc_id):
    acc = db.session.get(EscrowAccount, acc_id)
    if not acc or acc.deleted_at:
        return jsonify({"message": "غير موجود", "error_key": "escrow.notFound"}), 404
    data = request.get_json() or {}
    if "bank_name" in data:
        acc.bank_name = (data["bank_name"] or "").strip() or acc.bank_name
    if "iban" in data:
        acc.iban = (data["iban"] or "").strip()
    if "status" in data and data["status"] in ("active", "frozen", "closed"):
        acc.status = data["status"]
    if "notes" in data:
        acc.notes = (data["notes"] or "").strip()
    db.session.commit()
    log_action("update", "escrow_account", acc.id, acc.escrow_number)
    return jsonify(acc.to_dict())


@escrow_bp.route("/accounts/<int:acc_id>", methods=["DELETE"])
@require_api("realestate", "delete")
def delete_account(acc_id):
    acc = db.session.get(EscrowAccount, acc_id)
    if not acc or acc.deleted_at:
        return jsonify({"message": "غير موجود", "error_key": "escrow.notFound"}), 404
    if float(acc.balance or 0) != 0:
        return jsonify({"message": "لا يمكن حذف حساب به رصيد", "error_key": "escrow.hasBalance"}), 400
    acc.deleted_at = datetime.now()
    db.session.commit()
    log_action("delete", "escrow_account", acc.id, acc.escrow_number)
    return jsonify({"success": True})


# ============ Transactions ============

@escrow_bp.route("/accounts/<int:acc_id>/transactions", methods=["GET"])
@require_api("realestate", "view")
def list_transactions(acc_id):
    acc = db.session.get(EscrowAccount, acc_id)
    if not acc:
        return jsonify({"message": "غير موجود", "error_key": "escrow.notFound"}), 404
    txs = EscrowTransaction.query.filter_by(account_id=acc_id).order_by(EscrowTransaction.id.desc()).all()
    return jsonify([t.to_dict() for t in txs])


@escrow_bp.route("/accounts/<int:acc_id>/transactions", methods=["POST"])
@require_api("realestate", "create")
def create_transaction(acc_id):
    # قفل الصف لمنع race condition
    acc = db.session.query(EscrowAccount).filter_by(id=acc_id).with_for_update().first()
    if not acc or acc.deleted_at:
        return jsonify({"message": "غير موجود", "error_key": "escrow.notFound"}), 404
    if acc.status == "closed":
        return jsonify({"message": "الحساب مغلق", "error_key": "escrow.accountClosed"}), 400
    if acc.status == "frozen":
        return jsonify({"message": "الحساب مجمّد", "error_key": "escrow.accountFrozen"}), 400

    data = request.get_json() or {}
    try:
        amount = Decimal(str(data.get("amount") or 0))
    except Exception:
        return jsonify({"message": "المبلغ غير صالح", "error_key": "escrow.amountRequired"}), 400
    if amount <= 0 or amount > Decimal("1000000000"):
        return jsonify({"message": "المبلغ غير صالح", "error_key": "escrow.amountRequired"}), 400
    tx_type = (data.get("type") or "").strip()
    if tx_type not in ("deposit", "release", "hold", "refund"):
        return jsonify({"message": "نوع الحركة غير صالح", "error_key": "escrow.invalidType"}), 400
    # تحقق FK
    if data.get("contract_id") and not db.session.get(SalesContract, data["contract_id"]):
        return jsonify({"message": "العقد غير موجود", "error_key": "escrow.contractNotFound"}), 404

    # تحقق من الرصيد عند الصرف/الاسترداد
    if tx_type in ("release", "refund"):
        if Decimal(str(acc.balance or 0)) < amount:
            return jsonify({"message": "الرصيد غير كافٍ", "error_key": "escrow.insufficientBalance"}), 400

    tx = EscrowTransaction(
        account_id=acc_id,
        contract_id=data.get("contract_id"),
        installment_id=data.get("installment_id"),
        amount=amount,
        type=tx_type,
        status="completed",
        description=(data.get("description") or "").strip(),
        created_by=session.get("user_id"),
    )
    # تحديث الرصيد
    if tx_type in ("deposit", "hold"):
        acc.balance = Decimal(str(acc.balance or 0)) + Decimal(str(amount))
    else:
        acc.balance = Decimal(str(acc.balance or 0)) - Decimal(str(amount))

    db.session.add(tx)
    db.session.commit()
    log_action("create", "escrow_transaction", tx.id, f"{acc.escrow_number} {tx_type} {amount}")
    return jsonify(tx.to_dict()), 201


@escrow_bp.route("/summary", methods=["GET"])
@require_api("realestate", "view")
def escrow_summary():
    """ملخص أرصدة الضمان لكل مشروع."""
    from sqlalchemy import func
    rows = (db.session.query(
        EscrowAccount.project_id,
        func.sum(EscrowAccount.balance),
        func.count(EscrowAccount.id),
    ).filter(EscrowAccount.deleted_at.is_(None))
     .group_by(EscrowAccount.project_id).all())
    result = []
    for pid, total, cnt in rows:
        proj = db.session.get(Project, pid) if pid else None
        result.append({
            "project_id": pid,
            "project_name": proj.name if proj else None,
            "total_balance": float(total or 0),
            "accounts_count": cnt,
        })
    overall = sum(r["total_balance"] for r in result)
    return jsonify({"overall_balance": overall, "per_project": result})

"""إدارة الأصول والمعدات: الأصول، المعدات، الصيانة، الحركة، العهدة، والإهلاك."""
import datetime

from flask import Blueprint, render_template, request, jsonify, session
from database import db
from permissions import require_page, require_api
from auditlog import log_action
from models import (
    AssetCategory, AssetItem, AssetMaintenance, AssetMovement, AssetCustody,
    Account, Employee, Warehouse, Supplier, FinancialYear,
)
import utils.accounting as acct
from utils.pagination import paged_or_cap

assets_bp = Blueprint("assets", __name__, url_prefix="/assets")


def _d(s):
    if not s:
        return None
    try:
        return datetime.datetime.strptime(str(s), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _log(action, entity, entity_id, description):
    log_action(action, entity, entity_id, description)


def _default_fy_and_date():
    from utils.settings import get_int
    year_id = get_int("default_financial_year_id")
    year = db.session.get(FinancialYear, year_id) if year_id else None
    if not year:
        year = FinancialYear.query.filter_by(is_active=True, is_closed=False) \
            .order_by(FinancialYear.start_date.desc()).first()
    if year and not year.is_closed:
        return year.id, (year.start_date or datetime.date.today())
    return None, datetime.date.today()


# ==================== صفحات ====================

@assets_bp.route("/")
@require_page("accounting")
def dashboard():
    return render_template("assets.html")


@assets_bp.route("/assets")
@require_page("accounting")
def assets_page():
    return render_template("assets_registry.html")


@assets_bp.route("/equipment")
@require_page("accounting")
def equipment_page():
    return render_template("assets_equipment.html")


@assets_bp.route("/maintenance")
@require_page("accounting")
def maintenance_page():
    return render_template("assets_maintenance.html")


@assets_bp.route("/movements")
@require_page("accounting")
def movements_page():
    return render_template("assets_movements.html")


@assets_bp.route("/custody")
@require_page("accounting")
def custody_page():
    return render_template("assets_custody.html")


@assets_bp.route("/depreciation")
@require_page("accounting")
def depreciation_page():
    return render_template("assets_depreciation.html")


# ==================== بيانات عامة ====================

@assets_bp.route("/api/meta")
@require_api("accounting", "view")
def meta():
    categories = [c.to_dict() for c in AssetCategory.query.order_by(AssetCategory.code.asc()).all()]
    employees = [{"id": e.id, "name": e.full_name} for e in Employee.query.order_by(Employee.full_name.asc()).limit(500).all()]
    warehouses = [{"id": w.id, "name": w.name} for w in Warehouse.query.order_by(Warehouse.name.asc()).all()]
    suppliers = [{"id": s.id, "name": s.company_name} for s in Supplier.query.order_by(Supplier.company_name.asc()).limit(500).all()]
    accounts = [a.to_dict() for a in Account.query.order_by(Account.code.asc()).all()]
    defaults = {}
    for key in acct.DEFAULT_ACCOUNT_MAP:
        defaults[key] = acct.default_account_id(key)
    return jsonify({
        "categories": categories,
        "employees": employees,
        "warehouses": warehouses,
        "suppliers": suppliers,
        "accounts": accounts,
        "defaults": defaults,
    })


# ==================== الفئات ====================

@assets_bp.route("/api/categories")
@require_api("accounting", "view")
def list_categories():
    return jsonify([c.to_dict() for c in AssetCategory.query.order_by(AssetCategory.code.asc()).all()])


@assets_bp.route("/api/categories", methods=["POST"])
@require_api("accounting", "create")
def create_category():
    data = request.get_json(force=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        return jsonify({"message": "common.required"}), 400
    if AssetCategory.query.filter_by(code=code).first():
        return jsonify({"message": "accounting.codeExists"}), 400
    cat = AssetCategory(
        code=code,
        name=name,
        parent_id=data.get("parent_id") or None,
        kind=data.get("kind", "asset"),
        is_active=bool(data.get("is_active", True)),
        description=(data.get("description") or "").strip() or None,
    )
    db.session.add(cat)
    db.session.commit()
    _log("create", "asset_category", cat.id, f"إنشاء فئة أصول: {cat.code} - {cat.name}")
    return jsonify({"success": True, "category": cat.to_dict()})


@assets_bp.route("/api/categories/<int:cat_id>", methods=["PUT"])
@require_api("accounting", "edit")
def update_category(cat_id):
    cat = db.session.get(AssetCategory, cat_id)
    if not cat:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    dup = AssetCategory.query.filter(AssetCategory.code == code, AssetCategory.id != cat_id).first()
    if dup:
        return jsonify({"message": "accounting.codeExists"}), 400
    if code:
        cat.code = code
    if name:
        cat.name = name
    if "parent_id" in data:
        cat.parent_id = data.get("parent_id") or None
    if "kind" in data:
        cat.kind = data.get("kind", cat.kind)
    if "is_active" in data:
        cat.is_active = bool(data.get("is_active"))
    if "description" in data:
        cat.description = (data.get("description") or "").strip() or None
    db.session.commit()
    _log("update", "asset_category", cat.id, f"تعديل فئة أصول: {cat.code}")
    return jsonify({"success": True, "category": cat.to_dict()})


@assets_bp.route("/api/categories/<int:cat_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_category(cat_id):
    cat = db.session.get(AssetCategory, cat_id)
    if not cat:
        return jsonify({"message": "common.notFound"}), 404
    if AssetItem.query.filter_by(category_id=cat_id).first():
        return jsonify({"message": "assets.categoryHasAssets"}), 400
    if AssetCategory.query.filter_by(parent_id=cat_id).first():
        return jsonify({"message": "assets.categoryHasChildren"}), 400
    db.session.delete(cat)
    db.session.commit()
    _log("delete", "asset_category", cat_id, f"حذف فئة أصول: {cat.code}")
    return jsonify({"success": True})


# ==================== الأصول والمعدات ====================

def _item_dict(a):
    return a.to_dict()


@assets_bp.route("/api/items")
@require_api("accounting", "view")
def list_items():
    kind = request.args.get("kind")
    status = request.args.get("status")
    q = AssetItem.query
    if kind:
        q = q.filter_by(kind=kind)
    if status:
        q = q.filter_by(status=status)
    items, envelope = paged_or_cap(q.order_by(AssetItem.code.asc()), _item_dict)
    return jsonify(envelope if envelope else items)


@assets_bp.route("/api/items", methods=["POST"])
@require_api("accounting", "create")
def create_item():
    data = request.get_json(force=True) or {}
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        return jsonify({"message": "common.required"}), 400
    if AssetItem.query.filter_by(code=code).first():
        return jsonify({"message": "accounting.codeExists"}), 400
    cost = float(data.get("cost") or 0)
    kind = data.get("kind", "asset")
    item = AssetItem(
        code=code,
        name=name,
        category_id=data.get("category_id") or None,
        kind=kind,
        asset_type=(data.get("asset_type") or "").strip() or None,
        serial_number=(data.get("serial_number") or "").strip() or None,
        brand=(data.get("brand") or "").strip() or None,
        model=(data.get("model") or "").strip() or None,
        location_id=data.get("location_id") or None,
        supplier_id=data.get("supplier_id") or None,
        purchase_date=_d(data.get("purchase_date")),
        purchase_price=float(data.get("purchase_price") or 0),
        cost=cost,
        currency_code=(data.get("currency_code") or "").strip() or None,
        useful_life_years=int(data.get("useful_life_years") or 5),
        salvage_value=float(data.get("salvage_value") or 0),
        depreciation_method=data.get("depreciation_method", "straight"),
        status=data.get("status", "active"),
        condition=data.get("condition", "good"),
        assigned_employee_id=data.get("assigned_employee_id") or None,
        account_id=data.get("account_id") or None,
        expense_account_id=data.get("expense_account_id") or None,
        accumulated_account_id=data.get("accumulated_account_id") or None,
        warranty_until=_d(data.get("warranty_until")),
        notes=(data.get("notes") or "").strip() or None,
    )
    item.monthly_depreciation = item.compute_monthly()
    db.session.add(item)
    db.session.commit()
    _post_purchase(item, cost, data)
    _log("create", "asset", item.id, f"إضافة {kind}: {item.code} - {item.name}")
    return jsonify({"success": True, "item": _item_dict(item)})


def _post_purchase(item, cost, data):
    """ترحيل شراء الأصل/المعدة: مدين حساب الأصل / دائن صندوق أو ذمم."""
    if cost <= 0:
        return
    if not acct.default_account_id("acc_default_asset"):
        return
    funding = data.get("funding", "credit")
    if funding in ("cash", "bank"):
        counter = data.get("cash_account_id") or acct.default_account_id(
            "acc_default_cash" if funding == "cash" else "acc_default_bank")
    else:
        counter = data.get("counterpart_account_id") or acct.default_account_id("acc_default_payable")
    if not counter:
        return
    year_id, _ = _default_fy_and_date()
    try:
        acct.make_entry(
            [
                {"account_id": item.account_id or acct.default_account_id("acc_default_asset"),
                 "debit": cost, "credit": 0, "description": f"شراء {item.name}"},
                {"account_id": int(counter), "debit": 0, "credit": cost, "description": f"شراء {item.name}"},
            ],
            date=item.purchase_date or datetime.date.today(),
            description=f"شراء {item.kind} {item.code}",
            financial_year_id=year_id,
            source="asset", ref_type="asset", ref_id=item.id)
    except Exception:
        db.session.rollback()


@assets_bp.route("/api/items/<int:item_id>", methods=["PUT"])
@require_api("accounting", "edit")
def update_item(item_id):
    item = db.session.get(AssetItem, item_id)
    if not item:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    code = str(data.get("code") or "").strip()
    dup = AssetItem.query.filter(AssetItem.code == code, AssetItem.id != item_id).first()
    if dup:
        return jsonify({"message": "accounting.codeExists"}), 400
    if code:
        item.code = code
    if data.get("name"):
        item.name = data["name"]
    if "category_id" in data:
        item.category_id = data.get("category_id") or None
    if "kind" in data:
        item.kind = data.get("kind", item.kind)
    if "asset_type" in data:
        item.asset_type = (data.get("asset_type") or "").strip() or None
    if "serial_number" in data:
        item.serial_number = (data.get("serial_number") or "").strip() or None
    if "brand" in data:
        item.brand = (data.get("brand") or "").strip() or None
    if "model" in data:
        item.model = (data.get("model") or "").strip() or None
    if "location_id" in data:
        item.location_id = data.get("location_id") or None
    if "supplier_id" in data:
        item.supplier_id = data.get("supplier_id") or None
    if "purchase_date" in data:
        item.purchase_date = _d(data.get("purchase_date"))
    if "purchase_price" in data:
        item.purchase_price = float(data.get("purchase_price") or 0)
    if "cost" in data:
        item.cost = float(data.get("cost") or 0)
    if "currency_code" in data:
        item.currency_code = (data.get("currency_code") or "").strip() or None
    if "useful_life_years" in data:
        item.useful_life_years = int(data.get("useful_life_years") or 5)
    if "salvage_value" in data:
        item.salvage_value = float(data.get("salvage_value") or 0)
    if "depreciation_method" in data:
        item.depreciation_method = data.get("depreciation_method", "straight")
    if "status" in data:
        item.status = data.get("status", "active")
    if "condition" in data:
        item.condition = data.get("condition", "good")
    if "assigned_employee_id" in data:
        item.assigned_employee_id = data.get("assigned_employee_id") or None
    if "account_id" in data:
        item.account_id = data.get("account_id") or None
    if "expense_account_id" in data:
        item.expense_account_id = data.get("expense_account_id") or None
    if "accumulated_account_id" in data:
        item.accumulated_account_id = data.get("accumulated_account_id") or None
    if "warranty_until" in data:
        item.warranty_until = _d(data.get("warranty_until"))
    if "notes" in data:
        item.notes = (data.get("notes") or "").strip() or None
    item.monthly_depreciation = item.compute_monthly()
    db.session.commit()
    _log("update", "asset", item.id, f"تعديل {item.kind}: {item.code}")
    return jsonify({"success": True, "item": _item_dict(item)})


@assets_bp.route("/api/items/<int:item_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_item(item_id):
    item = db.session.get(AssetItem, item_id)
    if not item:
        return jsonify({"message": "common.notFound"}), 404
    if AssetMaintenance.query.filter_by(asset_id=item_id).first() or \
       AssetMovement.query.filter_by(asset_id=item_id).first() or \
       AssetCustody.query.filter_by(asset_id=item_id).first():
        return jsonify({"message": "assets.itemHasRecords"}), 400
    acct.delete_source_entries("asset", "asset", item_id)
    db.session.delete(item)
    db.session.commit()
    _log("delete", "asset", item_id, f"حذف {item.kind}: {item.code}")
    return jsonify({"success": True})


# ==================== الإهلاك ====================

@assets_bp.route("/api/items/<int:item_id>/depreciate", methods=["POST"])
@require_api("accounting", "create")
def depreciate(item_id):
    item = db.session.get(AssetItem, item_id)
    if not item:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    period = str(data.get("period") or datetime.date.today().strftime("%Y-%m"))
    date = _d(data.get("date")) or datetime.date.today()
    from models import DepreciationRecord
    if DepreciationRecord.query.filter_by(asset_id=item_id, period=period).first():
        return jsonify({"message": "accounting.periodAlready"}), 400
    if item.net_book_value <= 0 or item.status not in ("active", "in_maintenance"):
        return jsonify({"message": "accounting.fullyDepreciated"}), 400
    exp_acc = item.expense_account_id or acct.default_account_id("acc_default_depreciation")
    acc_acc = item.accumulated_account_id or acct.default_account_id("acc_default_accumulated")
    if not (exp_acc and acc_acc):
        return jsonify({"message": "accounting.deprAccountsRequired"}), 400
    amount = float(item.monthly_depreciation or item.compute_monthly())
    if amount > item.net_book_value:
        amount = item.net_book_value
    fy_id = data.get("financial_year_id")
    try:
        entry = acct.make_entry(
            [
                {"account_id": int(exp_acc), "debit": amount, "credit": 0, "description": f"إهلاك {item.name}"},
                {"account_id": int(acc_acc), "debit": 0, "credit": amount, "description": f"إهلاك {item.name}"},
            ],
            date=date,
            description=f"إهلاك {item.kind} {item.code} - {period}",
            financial_year_id=int(fy_id) if fy_id not in (None, "", 0) else None,
            source="depreciation", ref_type="asset", ref_id=item.id)
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    item.accumulated_depreciation = float(item.accumulated_depreciation or 0) + amount
    db.session.add(DepreciationRecord(
        asset_id=item.id, entry_id=entry.id, period=period, date=date, amount=amount))
    db.session.commit()
    _log("create", "journal", entry.id, f"إهلاك {item.code} {period}")
    return jsonify({"success": True, "item": _item_dict(item), "amount": amount})


# ==================== الصيانة ====================

@assets_bp.route("/api/maintenance")
@require_api("accounting", "view")
def list_maintenance():
    asset_id = request.args.get("asset_id")
    q = AssetMaintenance.query
    if asset_id:
        q = q.filter_by(asset_id=int(asset_id))
    items, envelope = paged_or_cap(q.order_by(AssetMaintenance.maintenance_date.desc()))
    return jsonify(envelope if envelope else items)


@assets_bp.route("/api/maintenance", methods=["POST"])
@require_api("accounting", "create")
def create_maintenance():
    data = request.get_json(force=True) or {}
    asset_id = data.get("asset_id")
    maintenance_date = _d(data.get("maintenance_date"))
    if not asset_id or not maintenance_date:
        return jsonify({"message": "common.required"}), 400
    asset = db.session.get(AssetItem, int(asset_id))
    if not asset:
        return jsonify({"message": "common.notFound"}), 400
    rec = AssetMaintenance(
        asset_id=int(asset_id),
        maintenance_date=maintenance_date,
        maintenance_type=data.get("maintenance_type", "preventive"),
        cost=float(data.get("cost") or 0),
        vendor=(data.get("vendor") or "").strip() or None,
        technician=(data.get("technician") or "").strip() or None,
        description=(data.get("description") or "").strip() or None,
        status=data.get("status", "completed"),
        next_maintenance_date=_d(data.get("next_maintenance_date")),
        created_by=session.get("user_id"),
    )
    db.session.add(rec)
    if rec.status == "in_progress" and asset.status != "in_maintenance":
        asset.status = "in_maintenance"
    if rec.status == "completed" and asset.status == "in_maintenance":
        asset.status = "active"
    db.session.commit()
    _log("create", "asset_maintenance", rec.id, f"صيانة {asset.code}")
    return jsonify({"success": True, "maintenance": rec.to_dict(), "asset": _item_dict(asset)})


@assets_bp.route("/api/maintenance/<int:rec_id>", methods=["PUT"])
@require_api("accounting", "edit")
def update_maintenance(rec_id):
    rec = db.session.get(AssetMaintenance, rec_id)
    if not rec:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    if "maintenance_date" in data:
        rec.maintenance_date = _d(data.get("maintenance_date")) or rec.maintenance_date
    if "maintenance_type" in data:
        rec.maintenance_type = data.get("maintenance_type", rec.maintenance_type)
    if "cost" in data:
        rec.cost = float(data.get("cost") or 0)
    if "vendor" in data:
        rec.vendor = (data.get("vendor") or "").strip() or None
    if "technician" in data:
        rec.technician = (data.get("technician") or "").strip() or None
    if "description" in data:
        rec.description = (data.get("description") or "").strip() or None
    if "status" in data:
        rec.status = data.get("status", rec.status)
    if "next_maintenance_date" in data:
        rec.next_maintenance_date = _d(data.get("next_maintenance_date"))
    asset = rec.asset
    if rec.status == "in_progress" and asset and asset.status != "in_maintenance":
        asset.status = "in_maintenance"
    if rec.status == "completed" and asset and asset.status == "in_maintenance":
        asset.status = "active"
    db.session.commit()
    _log("update", "asset_maintenance", rec.id, f"تعديل صيانة {rec.asset.code if rec.asset else ''}")
    return jsonify({"success": True, "maintenance": rec.to_dict(), "asset": _item_dict(asset) if asset else None})


@assets_bp.route("/api/maintenance/<int:rec_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_maintenance(rec_id):
    rec = db.session.get(AssetMaintenance, rec_id)
    if not rec:
        return jsonify({"message": "common.notFound"}), 404
    asset = rec.asset
    db.session.delete(rec)
    db.session.commit()
    _log("delete", "asset_maintenance", rec_id, f"حذف صيانة {asset.code if asset else ''}")
    return jsonify({"success": True})


# ==================== الحركة ====================

@assets_bp.route("/api/movements")
@require_api("accounting", "view")
def list_movements():
    asset_id = request.args.get("asset_id")
    q = AssetMovement.query
    if asset_id:
        q = q.filter_by(asset_id=int(asset_id))
    items, envelope = paged_or_cap(q.order_by(AssetMovement.movement_date.desc()))
    return jsonify(envelope if envelope else items)


@assets_bp.route("/api/movements", methods=["POST"])
@require_api("accounting", "create")
def create_movement():
    data = request.get_json(force=True) or {}
    asset_id = data.get("asset_id")
    movement_date = _d(data.get("movement_date"))
    movement_type = data.get("movement_type")
    if not asset_id or not movement_date or not movement_type:
        return jsonify({"message": "common.required"}), 400
    asset = db.session.get(AssetItem, int(asset_id))
    if not asset:
        return jsonify({"message": "common.notFound"}), 400
    mov = AssetMovement(
        asset_id=int(asset_id),
        movement_date=movement_date,
        movement_type=movement_type,
        from_location_id=data.get("from_location_id") or None,
        to_location_id=data.get("to_location_id") or None,
        from_employee_id=data.get("from_employee_id") or None,
        to_employee_id=data.get("to_employee_id") or None,
        reference=(data.get("reference") or "").strip() or None,
        notes=(data.get("notes") or "").strip() or None,
        created_by=session.get("user_id"),
    )
    db.session.add(mov)
    if movement_type == "transferred" and data.get("to_location_id"):
        asset.location_id = data.get("to_location_id")
    if movement_type == "returned":
        asset.location_id = None
        asset.assigned_employee_id = None
    if movement_type == "disposed":
        asset.status = "disposed"
    db.session.commit()
    _log("create", "asset_movement", mov.id, f"حركة {asset.code} - {movement_type}")
    return jsonify({"success": True, "movement": mov.to_dict(), "asset": _item_dict(asset)})


@assets_bp.route("/api/movements/<int:mov_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_movement(mov_id):
    mov = db.session.get(AssetMovement, mov_id)
    if not mov:
        return jsonify({"message": "common.notFound"}), 404
    asset = mov.asset
    db.session.delete(mov)
    db.session.commit()
    _log("delete", "asset_movement", mov_id, f"حذف حركة {asset.code if asset else ''}")
    return jsonify({"success": True})


# ==================== العهدة ====================

@assets_bp.route("/api/custody")
@require_api("accounting", "view")
def list_custody():
    asset_id = request.args.get("asset_id")
    status = request.args.get("status")
    q = AssetCustody.query
    if asset_id:
        q = q.filter_by(asset_id=int(asset_id))
    if status:
        q = q.filter_by(status=status)
    items, envelope = paged_or_cap(q.order_by(AssetCustody.custody_date.desc()))
    return jsonify(envelope if envelope else items)


@assets_bp.route("/api/custody", methods=["POST"])
@require_api("accounting", "create")
def create_custody():
    data = request.get_json(force=True) or {}
    asset_id = data.get("asset_id")
    employee_id = data.get("employee_id")
    custody_date = _d(data.get("custody_date"))
    if not asset_id or not employee_id or not custody_date:
        return jsonify({"message": "common.required"}), 400
    asset = db.session.get(AssetItem, int(asset_id))
    if not asset:
        return jsonify({"message": "common.notFound"}), 400
    active = AssetCustody.query.filter_by(asset_id=int(asset_id), status="active").first()
    if active:
        active.status = "returned"
        active.return_date = custody_date
    rec = AssetCustody(
        asset_id=int(asset_id),
        employee_id=int(employee_id),
        custody_date=custody_date,
        status="active",
        notes=(data.get("notes") or "").strip() or None,
        created_by=session.get("user_id"),
    )
    db.session.add(rec)
    asset.assigned_employee_id = int(employee_id)
    db.session.commit()
    _log("create", "asset_custody", rec.id, f"عهدة {asset.code} إلى {rec.employee.full_name if rec.employee else ''}")
    return jsonify({"success": True, "custody": rec.to_dict(), "asset": _item_dict(asset)})


@assets_bp.route("/api/custody/<int:rec_id>/return", methods=["POST"])
@require_api("accounting", "edit")
def return_custody(rec_id):
    rec = db.session.get(AssetCustody, rec_id)
    if not rec:
        return jsonify({"message": "common.notFound"}), 404
    data = request.get_json(force=True) or {}
    return_date = _d(data.get("return_date")) or datetime.date.today()
    rec.status = "returned"
    rec.return_date = return_date
    asset = rec.asset
    if asset:
        asset.assigned_employee_id = None
    db.session.commit()
    _log("update", "asset_custody", rec.id, f"إرجاع عهدة {rec.asset.code if rec.asset else ''}")
    return jsonify({"success": True, "custody": rec.to_dict(), "asset": _item_dict(asset) if asset else None})


@assets_bp.route("/api/custody/<int:rec_id>", methods=["DELETE"])
@require_api("accounting", "delete")
def delete_custody(rec_id):
    rec = db.session.get(AssetCustody, rec_id)
    if not rec:
        return jsonify({"message": "common.notFound"}), 404
    asset = rec.asset
    db.session.delete(rec)
    db.session.commit()
    _log("delete", "asset_custody", rec_id, f"حذف عهدة {asset.code if asset else ''}")
    return jsonify({"success": True})
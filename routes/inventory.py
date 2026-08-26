from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from database import db
from models import (
    Warehouse, ItemCategory, UnitOfMeasure, Item, ItemStock,
    StockBatch, StockSerial, StockTransfer, StockTransferItem,
    StockTake, StockTakeItem, StockMovement,
)
from permissions import require_api, require_page
from auditlog import log_action

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")
pages_bp = Blueprint("inventory_pages", __name__)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _log(action, entity, entity_id, description):
    log_action(action, entity, entity_id, description)


def _next_number(prefix, model, field):
    from utils.docnum import seq_after_max
    return seq_after_max(model, prefix + "-{n:04d}")


def _record_movement(item_id, warehouse_id, movement_type, quantity, batch_id=None,
                     reference_type=None, reference_id=None, notes=""):
    try:
        db.session.add(StockMovement(
            item_id=item_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=quantity,
            batch_id=batch_id,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=(notes or "")[:300],
        ))
    except Exception:
        db.session.rollback()


def _adjust_stock(item_id, warehouse_id, delta, cost=0):
    """يحدّث رصيد الصنف في المخزن بقيمة delta (موجبة زيادة / سالبة نقص)."""
    stock = ItemStock.query.filter_by(item_id=item_id, warehouse_id=warehouse_id).first()
    if not stock:
        stock = ItemStock(item_id=item_id, warehouse_id=warehouse_id, quantity=0, avg_cost=0)
        db.session.add(stock)
    new_qty = float(stock.quantity or 0) + delta
    stock.quantity = max(0, new_qty)
    if cost and delta > 0:
        old_total = float(stock.quantity or 0) * float(stock.avg_cost or 0)
        new_total = old_total + (delta * cost)
        stock.avg_cost = new_total / stock.quantity if stock.quantity else 0
    return stock


# ============ صفحات (Pages) ============

@pages_bp.route("/inventory")
@require_page("inventory")
def inventory_home():
    return render_template("inventory.html")


@pages_bp.route("/inventory/warehouses")
@require_page("inventory")
def warehouses():
    return render_template("inventory_warehouses.html")


@pages_bp.route("/inventory/items")
@require_page("inventory")
def items():
    return render_template("inventory_items.html")


@pages_bp.route("/inventory/categories")
@require_page("inventory")
def categories():
    return render_template("inventory_categories.html")


@pages_bp.route("/inventory/units")
@require_page("inventory")
def units():
    return render_template("inventory_units.html")


@pages_bp.route("/inventory/stock")
@require_page("inventory")
def stock():
    return render_template("inventory_stock.html")


@pages_bp.route("/inventory/batches")
@require_page("inventory")
def batches():
    return render_template("inventory_batches.html")


@pages_bp.route("/inventory/serials")
@require_page("inventory")
def serials():
    return render_template("inventory_serials.html")


@pages_bp.route("/inventory/transfers")
@require_page("inventory")
def transfers():
    return render_template("inventory_transfers.html")


@pages_bp.route("/inventory/stocktakes")
@require_page("inventory")
def stocktakes():
    return render_template("inventory_stocktakes.html")


@pages_bp.route("/inventory/suppliers")
@require_page("inventory")
def suppliers():
    return render_template("inventory_suppliers.html")


@pages_bp.route("/inventory/reports")
@require_page("inventory")
def reports():
    return render_template("inventory_reports.html")


# ============ البيانات الأساسية (Meta) ============

@inventory_bp.route("/meta", methods=["GET"])
@require_api("inventory", "view")
def meta():
    warehouses = Warehouse.query.filter_by(is_active=True).all()
    categories = ItemCategory.query.filter_by(is_active=True).all()
    units = UnitOfMeasure.query.filter_by(is_active=True).all()
    items = Item.query.all()
    low_stock = [i.to_dict() for i in items
                 if i.reorder_level and float(i.reorder_level) > 0
                 and float(i.to_dict().get("quantity") or 0) <= float(i.reorder_level)]
    expired = StockBatch.query.filter(StockBatch.expiry_date.isnot(None),
                                      StockBatch.expiry_date < datetime.now().date()).all()
    return jsonify({
        "warehouses": [w.to_dict() for w in warehouses],
        "categories": [c.to_dict() for c in categories],
        "units": [u.to_dict() for u in units],
        "items_count": len(items),
        "warehouses_count": len(warehouses),
        "categories_count": len(categories),
        "units_count": len(units),
        "stock_value": round(sum(float(s.quantity or 0) * float(s.avg_cost or 0)
                                 for s in ItemStock.query.all()), 2),
        "low_stock_count": len(low_stock),
        "expired_batches_count": len(expired),
        "movements_count": StockMovement.query.count(),
    })


# ============ المخازن (Warehouses) ============

@inventory_bp.route("/warehouses", methods=["GET"])
@require_api("inventory", "view")
def list_warehouses():
    warehouses = Warehouse.query.order_by(Warehouse.code).all()
    return jsonify({"warehouses": [w.to_dict() for w in warehouses]})


@inventory_bp.route("/warehouses", methods=["POST"])
@require_api("inventory", "create")
def create_warehouse():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم المخزن مطلوب"}), 400
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"message": "رمز المخزن مطلوب"}), 400
    if Warehouse.query.filter_by(code=code).first():
        return jsonify({"message": "رمز المخزن موجود مسبقاً"}), 400
    wh = Warehouse(
        code=code,
        name=data.get("name", "").strip(),
        location=(data.get("location") or "").strip(),
        manager_name=(data.get("manager_name") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        notes=data.get("notes"),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(wh)
    db.session.commit()
    _log("create", "warehouse", wh.id, f"مخزن: {wh.name}")
    return jsonify({"success": True, "warehouse": wh.to_dict()}), 201


@inventory_bp.route("/warehouses/<int:warehouse_id>", methods=["PUT"])
@require_api("inventory", "edit")
def update_warehouse(warehouse_id):
    wh = Warehouse.query.get_or_404(warehouse_id)
    data = request.get_json(silent=True) or {}
    if "name" in data and not (data.get("name") or "").strip():
        return jsonify({"message": "اسم المخزن مطلوب"}), 400
    code = (data.get("code") or wh.code).strip()
    existing = Warehouse.query.filter_by(code=code).first()
    if existing and existing.id != wh.id:
        return jsonify({"message": "رمز المخزن موجود مسبقاً"}), 400
    wh.code = code
    wh.name = (data.get("name", wh.name) or "").strip()
    wh.location = (data.get("location", wh.location) or "").strip()
    wh.manager_name = (data.get("manager_name", wh.manager_name) or "").strip()
    wh.phone = (data.get("phone", wh.phone) or "").strip()
    wh.notes = data.get("notes", wh.notes)
    if "is_active" in data:
        wh.is_active = bool(data["is_active"])
    db.session.commit()
    _log("edit", "warehouse", wh.id, f"مخزن: {wh.name}")
    return jsonify({"success": True, "warehouse": wh.to_dict()})


@inventory_bp.route("/warehouses/<int:warehouse_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_warehouse(warehouse_id):
    wh = Warehouse.query.get_or_404(warehouse_id)
    if ItemStock.query.filter_by(warehouse_id=warehouse_id).first() or \
            StockBatch.query.filter_by(warehouse_id=warehouse_id).first():
        return jsonify({"message": "لا يمكن حذف مخزن عليه أرصدة أو دفعات"}), 400
    name = wh.name
    db.session.delete(wh)
    db.session.commit()
    _log("delete", "warehouse", warehouse_id, f"مخزن: {name}")
    return jsonify({"success": True})


# ============ التصنيفات (Categories) ============

@inventory_bp.route("/categories", methods=["GET"])
@require_api("inventory", "view")
def list_categories():
    cats = ItemCategory.query.order_by(ItemCategory.name).all()
    return jsonify({"categories": [c.to_dict() for c in cats]})


@inventory_bp.route("/categories", methods=["POST"])
@require_api("inventory", "create")
def create_category():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم التصنيف مطلوب"}), 400
    cat = ItemCategory(
        name=data.get("name", "").strip(),
        description=(data.get("description") or "").strip(),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(cat)
    db.session.commit()
    _log("create", "item_category", cat.id, f"تصنيف: {cat.name}")
    return jsonify({"success": True, "category": cat.to_dict()}), 201


@inventory_bp.route("/categories/<int:category_id>", methods=["PUT"])
@require_api("inventory", "edit")
def update_category(category_id):
    cat = ItemCategory.query.get_or_404(category_id)
    data = request.get_json(silent=True) or {}
    if "name" in data and not (data.get("name") or "").strip():
        return jsonify({"message": "اسم التصنيف مطلوب"}), 400
    cat.name = (data.get("name", cat.name) or "").strip()
    cat.description = (data.get("description", cat.description) or "").strip()
    if "is_active" in data:
        cat.is_active = bool(data["is_active"])
    db.session.commit()
    _log("edit", "item_category", cat.id, f"تصنيف: {cat.name}")
    return jsonify({"success": True, "category": cat.to_dict()})


@inventory_bp.route("/categories/<int:category_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_category(category_id):
    cat = ItemCategory.query.get_or_404(category_id)
    if Item.query.filter_by(category_id=category_id).first():
        return jsonify({"message": "لا يمكن حذف تصنيف يحتوي أصنافاً"}), 400
    name = cat.name
    db.session.delete(cat)
    db.session.commit()
    _log("delete", "item_category", category_id, f"تصنيف: {name}")
    return jsonify({"success": True})


# ============ الوحدات (Units) ============

@inventory_bp.route("/units", methods=["GET"])
@require_api("inventory", "view")
def list_units():
    units = UnitOfMeasure.query.order_by(UnitOfMeasure.name).all()
    return jsonify({"units": [u.to_dict() for u in units]})


@inventory_bp.route("/units", methods=["POST"])
@require_api("inventory", "create")
def create_unit():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم الوحدة مطلوب"}), 400
    unit = UnitOfMeasure(
        name=data.get("name", "").strip(),
        code=(data.get("code") or "").strip(),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(unit)
    db.session.commit()
    _log("create", "unit_of_measure", unit.id, f"وحدة: {unit.name}")
    return jsonify({"success": True, "unit": unit.to_dict()}), 201


@inventory_bp.route("/units/<int:unit_id>", methods=["PUT"])
@require_api("inventory", "edit")
def update_unit(unit_id):
    unit = UnitOfMeasure.query.get_or_404(unit_id)
    data = request.get_json(silent=True) or {}
    if "name" in data and not (data.get("name") or "").strip():
        return jsonify({"message": "اسم الوحدة مطلوب"}), 400
    unit.name = (data.get("name", unit.name) or "").strip()
    unit.code = (data.get("code", unit.code) or "").strip()
    if "is_active" in data:
        unit.is_active = bool(data["is_active"])
    db.session.commit()
    _log("edit", "unit_of_measure", unit.id, f"وحدة: {unit.name}")
    return jsonify({"success": True, "unit": unit.to_dict()})


@inventory_bp.route("/units/<int:unit_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_unit(unit_id):
    unit = UnitOfMeasure.query.get_or_404(unit_id)
    if Item.query.filter_by(unit_id=unit_id).first():
        return jsonify({"message": "لا يمكن حذف وحدة مستخدمة في أصناف"}), 400
    name = unit.name
    db.session.delete(unit)
    db.session.commit()
    _log("delete", "unit_of_measure", unit_id, f"وحدة: {name}")
    return jsonify({"success": True})


# ============ الأصناف (Items) ============

@inventory_bp.route("/items", methods=["GET"])
@require_api("inventory", "view")
def list_items():
    items = Item.query.order_by(Item.code).all()
    return jsonify({"items": [i.to_dict() for i in items]})


@inventory_bp.route("/items", methods=["POST"])
@require_api("inventory", "create")
def create_item():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم الصنف مطلوب"}), 400
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"message": "كود الصنف مطلوب"}), 400
    if Item.query.filter_by(code=code).first():
        return jsonify({"message": "كود الصنف موجود مسبقاً"}), 400
    item = Item(
        code=code,
        name=data.get("name", "").strip(),
        category_id=data.get("category_id") or None,
        unit_id=data.get("unit_id") or None,
        barcode=(data.get("barcode") or "").strip(),
        description=data.get("description"),
        cost_price=data.get("cost_price") or 0,
        sale_price=data.get("sale_price") or 0,
        reorder_level=data.get("reorder_level") or 0,
        track_batch=bool(data.get("track_batch")),
        track_serial=bool(data.get("track_serial")),
        track_expiry=bool(data.get("track_expiry")),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(item)
    db.session.commit()
    _log("create", "item", item.id, f"صنف: {item.name}")
    return jsonify({"success": True, "item": item.to_dict()}), 201


@inventory_bp.route("/items/<int:item_id>", methods=["PUT"])
@require_api("inventory", "edit")
def update_item(item_id):
    item = Item.query.get_or_404(item_id)
    data = request.get_json(silent=True) or {}
    if "name" in data and not (data.get("name") or "").strip():
        return jsonify({"message": "اسم الصنف مطلوب"}), 400
    code = (data.get("code") or item.code).strip()
    existing = Item.query.filter_by(code=code).first()
    if existing and existing.id != item.id:
        return jsonify({"message": "كود الصنف موجود مسبقاً"}), 400
    item.code = code
    item.name = (data.get("name", item.name) or "").strip()
    item.category_id = data.get("category_id", item.category_id) or None
    item.unit_id = data.get("unit_id", item.unit_id) or None
    item.barcode = (data.get("barcode", item.barcode) or "").strip()
    item.description = data.get("description", item.description)
    if "cost_price" in data:
        item.cost_price = data["cost_price"] or 0
    if "sale_price" in data:
        item.sale_price = data["sale_price"] or 0
    if "reorder_level" in data:
        item.reorder_level = data["reorder_level"] or 0
    for flag in ("track_batch", "track_serial", "track_expiry"):
        if flag in data:
            setattr(item, flag, bool(data[flag]))
    if "is_active" in data:
        item.is_active = bool(data["is_active"])
    db.session.commit()
    _log("edit", "item", item.id, f"صنف: {item.name}")
    return jsonify({"success": True, "item": item.to_dict()})


@inventory_bp.route("/items/<int:item_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    if ItemStock.query.filter_by(item_id=item_id).first():
        return jsonify({"message": "لا يمكن حذف صنف عليه رصيد"}), 400
    name = item.name
    db.session.delete(item)
    db.session.commit()
    _log("delete", "item", item_id, f"صنف: {name}")
    return jsonify({"success": True})


# ============ الأرصدة (Stock) ============

@inventory_bp.route("/stock", methods=["GET"])
@require_api("inventory", "view")
def list_stock():
    warehouse_id = request.args.get("warehouse_id", type=int)
    q = ItemStock.query
    if warehouse_id:
        q = q.filter_by(warehouse_id=warehouse_id)
    rows = q.order_by(ItemStock.item_id, ItemStock.warehouse_id).all()
    result = []
    for s in rows:
        d = s.to_dict()
        it = s.item
        if it:
            d["item_code"] = it.code
            d["item_name"] = it.name
            d["unit_name"] = it.unit.name if it.unit else None
            d["reorder_level"] = float(it.reorder_level or 0)
        result.append(d)
    return jsonify({"stock": result})


@inventory_bp.route("/stock/low", methods=["GET"])
@require_api("inventory", "view")
def low_stock():
    items = Item.query.all()
    rows = []
    for i in items:
        total = sum(float(s.quantity or 0) for s in i.stocks)
        if i.reorder_level and float(i.reorder_level) > 0 and total <= float(i.reorder_level):
            d = i.to_dict()
            d["quantity"] = round(total, 2)
            rows.append(d)
    return jsonify({"items": rows})


@inventory_bp.route("/stock/expiring", methods=["GET"])
@require_api("inventory", "view")
def expiring_batches():
    days = request.args.get("days", default=90, type=int)
    today = datetime.now().date()
    from datetime import timedelta
    horizon = today + timedelta(days=days)
    batches = StockBatch.query.filter(StockBatch.expiry_date.isnot(None)).all()
    rows = [b.to_dict() for b in batches
            if b.expiry_date and today <= b.expiry_date <= horizon and float(b.quantity or 0) > 0]
    rows.sort(key=lambda b: b.get("expiry_date") or "")
    return jsonify({"batches": rows})


# ============ الدفعات (Batches) ============

@inventory_bp.route("/batches", methods=["GET"])
@require_api("inventory", "view")
def list_batches():
    batches = StockBatch.query.order_by(StockBatch.expiry_date.asc().nullslast()).all()
    return jsonify({"batches": [b.to_dict() for b in batches]})


@inventory_bp.route("/batches", methods=["POST"])
@require_api("inventory", "create")
def create_batch():
    data = request.get_json(silent=True) or {}
    if not (data.get("batch_number") or "").strip():
        return jsonify({"message": "رقم الدفعة مطلوب"}), 400
    item_id = data.get("item_id")
    warehouse_id = data.get("warehouse_id")
    if not item_id or not warehouse_id:
        return jsonify({"message": "الصنف والمخزن مطلوبان"}), 400
    item = Item.query.get_or_404(item_id)
    batch = StockBatch(
        item_id=item_id,
        warehouse_id=warehouse_id,
        batch_number=data.get("batch_number", "").strip(),
        quantity=data.get("quantity") or 0,
        expiry_date=parse_date(data.get("expiry_date")),
        received_date=parse_date(data.get("received_date")) or datetime.now().date(),
    )
    db.session.add(batch)
    _adjust_stock(item_id, warehouse_id, float(batch.quantity or 0))
    _record_movement(item_id, warehouse_id, "in", float(batch.quantity or 0),
                     batch_id=batch.id, reference_type="batch", reference_id=batch.id,
                     notes=f"إضافة دفعة {batch.batch_number}")
    db.session.commit()
    _log("create", "stock_batch", batch.id, f"دفعة: {batch.batch_number}")
    return jsonify({"success": True, "batch": batch.to_dict()}), 201


@inventory_bp.route("/batches/<int:batch_id>", methods=["PUT"])
@require_api("inventory", "edit")
def update_batch(batch_id):
    batch = StockBatch.query.get_or_404(batch_id)
    data = request.get_json(silent=True) or {}
    old_qty = float(batch.quantity or 0)
    new_qty = float(data.get("quantity", old_qty) or 0)
    if "quantity" in data and new_qty != old_qty:
        delta = new_qty - old_qty
        _adjust_stock(batch.item_id, batch.warehouse_id, delta)
        _record_movement(batch.item_id, batch.warehouse_id,
                         "in" if delta > 0 else "out", abs(delta),
                         batch_id=batch.id, reference_type="batch",
                         reference_id=batch.id, notes="تعديل كمية دفعة")
    batch.batch_number = (data.get("batch_number", batch.batch_number) or "").strip()
    batch.quantity = new_qty
    if "expiry_date" in data:
        batch.expiry_date = parse_date(data.get("expiry_date"))
    db.session.commit()
    _log("edit", "stock_batch", batch.id, f"دفعة: {batch.batch_number}")
    return jsonify({"success": True, "batch": batch.to_dict()})


@inventory_bp.route("/batches/<int:batch_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_batch(batch_id):
    batch = StockBatch.query.get_or_404(batch_id)
    if float(batch.quantity or 0) > 0:
        return jsonify({"message": "لا يمكن حذف دفعة عليها كمية"}), 400
    number = batch.batch_number
    db.session.delete(batch)
    db.session.commit()
    _log("delete", "stock_batch", batch_id, f"دفعة: {number}")
    return jsonify({"success": True})


# ============ الأرقام التسلسلية (Serials) ============

@inventory_bp.route("/serials", methods=["GET"])
@require_api("inventory", "view")
def list_serials():
    serials = StockSerial.query.order_by(StockSerial.created_at.desc()).all()
    return jsonify({"serials": [s.to_dict() for s in serials]})


@inventory_bp.route("/serials", methods=["POST"])
@require_api("inventory", "create")
def create_serial():
    data = request.get_json(silent=True) or {}
    if not (data.get("serial_number") or "").strip():
        return jsonify({"message": "الرقم التسلسلي مطلوب"}), 400
    serial_number = data.get("serial_number", "").strip()
    if StockSerial.query.filter_by(serial_number=serial_number).first():
        return jsonify({"message": "الرقم التسلسلي موجود مسبقاً"}), 400
    item_id = data.get("item_id")
    warehouse_id = data.get("warehouse_id")
    if not item_id or not warehouse_id:
        return jsonify({"message": "الصنف والمخزن مطلوبان"}), 400
    serial = StockSerial(
        item_id=item_id,
        warehouse_id=warehouse_id,
        batch_id=data.get("batch_id") or None,
        serial_number=serial_number,
        status=data.get("status") or "in_stock",
    )
    db.session.add(serial)
    _adjust_stock(item_id, warehouse_id, 1)
    _record_movement(item_id, warehouse_id, "in", 1,
                     batch_id=serial.batch_id, reference_type="serial",
                     reference_id=serial.id, notes=f"إضافة رقم تسلسلي {serial_number}")
    db.session.commit()
    _log("create", "stock_serial", serial.id, f"رقم تسلسلي: {serial_number}")
    return jsonify({"success": True, "serial": serial.to_dict()}), 201


@inventory_bp.route("/serials/<int:serial_id>", methods=["PUT"])
@require_api("inventory", "edit")
def update_serial(serial_id):
    serial = StockSerial.query.get_or_404(serial_id)
    data = request.get_json(silent=True) or {}
    new_status = data.get("status", serial.status)
    if new_status != serial.status:
        if new_status == "sold" and serial.status == "in_stock":
            _adjust_stock(serial.item_id, serial.warehouse_id, -1)
            _record_movement(serial.item_id, serial.warehouse_id, "out", 1,
                             batch_id=serial.batch_id, reference_type="serial",
                             reference_id=serial.id, notes=f"بيع رقم تسلسلي {serial.serial_number}")
        elif new_status == "in_stock" and serial.status == "sold":
            _adjust_stock(serial.item_id, serial.warehouse_id, 1)
            _record_movement(serial.item_id, serial.warehouse_id, "in", 1,
                             batch_id=serial.batch_id, reference_type="serial",
                             reference_id=serial.id, notes=f"إعادة رقم تسلسلي {serial.serial_number}")
    serial.status = new_status
    if "batch_id" in data:
        serial.batch_id = data.get("batch_id") or None
    db.session.commit()
    _log("edit", "stock_serial", serial.id, f"رقم تسلسلي: {serial.serial_number}")
    return jsonify({"success": True, "serial": serial.to_dict()})


@inventory_bp.route("/serials/<int:serial_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_serial(serial_id):
    serial = StockSerial.query.get_or_404(serial_id)
    if serial.status == "in_stock":
        _adjust_stock(serial.item_id, serial.warehouse_id, -1)
    number = serial.serial_number
    db.session.delete(serial)
    db.session.commit()
    _log("delete", "stock_serial", serial_id, f"رقم تسلسلي: {number}")
    return jsonify({"success": True})


# ============ التحويلات (Transfers) ============

@inventory_bp.route("/transfers", methods=["GET"])
@require_api("inventory", "view")
def list_transfers():
    transfers = StockTransfer.query.order_by(StockTransfer.created_at.desc()).all()
    return jsonify({"transfers": [t.to_dict() for t in transfers]})


@inventory_bp.route("/transfers", methods=["POST"])
@require_api("inventory", "create")
def create_transfer():
    data = request.get_json(silent=True) or {}
    from_wh = data.get("from_warehouse_id")
    to_wh = data.get("to_warehouse_id")
    if not from_wh or not to_wh:
        return jsonify({"message": "مخزن المصدر والوجهة مطلوبان"}), 400
    if from_wh == to_wh:
        return jsonify({"message": "مخزن المصدر والوجهة لا يمكن أن يكونا متطابقين"}), 400
    lines = data.get("items") or []
    if not lines:
        return jsonify({"message": "أضف صنفاً واحداً على الأقل"}), 400
    transfer = StockTransfer(
        transfer_number=_next_number("TRF", StockTransfer, "transfer_number"),
        from_warehouse_id=from_wh,
        to_warehouse_id=to_wh,
        transfer_date=parse_date(data.get("transfer_date")) or datetime.now().date(),
        status="posted",
        notes=data.get("notes"),
    )
    db.session.add(transfer)
    db.session.flush()
    for line in lines:
        item_id = line.get("item_id")
        qty = float(line.get("quantity") or 0)
        if not item_id or qty <= 0:
            continue
        src = ItemStock.query.filter_by(item_id=item_id, warehouse_id=from_wh).first()
        src_qty = float(src.quantity or 0) if src else 0
        if src_qty < qty:
            db.session.rollback()
            return jsonify({"message": f"الرصيد غير كافٍ في المخزن المصدر لصنف الرقم {item_id}"}), 400
        _adjust_stock(item_id, from_wh, -qty)
        _adjust_stock(item_id, to_wh, qty)
        batch_id = line.get("batch_id") or None
        if batch_id:
            batch = db.session.get(StockBatch, batch_id)
            if batch and float(batch.quantity or 0) >= qty:
                batch.quantity = float(batch.quantity or 0) - qty
                new_batch = StockBatch(
                    item_id=item_id, warehouse_id=to_wh,
                    batch_number=batch.batch_number,
                    quantity=qty,
                    expiry_date=batch.expiry_date,
                    received_date=batch.received_date,
                )
                db.session.add(new_batch)
                db.session.flush()
                batch_id = new_batch.id
        t_item = StockTransferItem(
            transfer_id=transfer.id, item_id=item_id,
            quantity=qty, batch_id=batch_id,
        )
        db.session.add(t_item)
        _record_movement(item_id, from_wh, "transfer_out", qty, batch_id=batch_id,
                         reference_type="transfer", reference_id=transfer.id,
                         notes=f"تحويل إلى {transfer.to_warehouse.name if transfer.to_warehouse else ''}")
        _record_movement(item_id, to_wh, "transfer_in", qty, batch_id=batch_id,
                         reference_type="transfer", reference_id=transfer.id,
                         notes=f"تحويل من {transfer.from_warehouse.name if transfer.from_warehouse else ''}")
    db.session.commit()
    _log("create", "stock_transfer", transfer.id, f"تحويل: {transfer.transfer_number}")
    return jsonify({"success": True, "transfer": transfer.to_dict()}), 201


@inventory_bp.route("/transfers/<int:transfer_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_transfer(transfer_id):
    transfer = StockTransfer.query.get_or_404(transfer_id)
    if transfer.status != "posted":
        db.session.delete(transfer)
        db.session.commit()
        return jsonify({"success": True})
    for line in transfer.items:
        _adjust_stock(line.item_id, transfer.from_warehouse_id, float(line.quantity or 0))
        _adjust_stock(line.item_id, transfer.to_warehouse_id, -float(line.quantity or 0))
        _record_movement(line.item_id, transfer.from_warehouse_id, "in", float(line.quantity or 0),
                         reference_type="transfer", reference_id=transfer.id, notes="تراجع تحويل")
    number = transfer.transfer_number
    db.session.delete(transfer)
    db.session.commit()
    _log("delete", "stock_transfer", transfer_id, f"تحويل: {number}")
    return jsonify({"success": True})


# ============ الجرد (Stock Takes) ============

@inventory_bp.route("/stocktakes", methods=["GET"])
@require_api("inventory", "view")
def list_stocktakes():
    takes = StockTake.query.order_by(StockTake.created_at.desc()).all()
    return jsonify({"stocktakes": [t.to_dict() for t in takes]})


@inventory_bp.route("/stocktakes", methods=["POST"])
@require_api("inventory", "create")
def create_stocktake():
    data = request.get_json(silent=True) or {}
    warehouse_id = data.get("warehouse_id")
    if not warehouse_id:
        return jsonify({"message": "المخزن مطلوب"}), 400
    take = StockTake(
        take_number=_next_number("ST", StockTake, "take_number"),
        warehouse_id=warehouse_id,
        take_date=parse_date(data.get("take_date")) or datetime.now().date(),
        status="draft",
        notes=data.get("notes"),
    )
    db.session.add(take)
    db.session.flush()
    items = ItemStock.query.filter_by(warehouse_id=warehouse_id).all()
    if not items:
        db.session.rollback()
        return jsonify({"message": "لا توجد أرصدة في هذا المخزن للجرد"}), 400
    for s in items:
        db.session.add(StockTakeItem(
            take_id=take.id,
            item_id=s.item_id,
            system_qty=float(s.quantity or 0),
            counted_qty=float(s.quantity or 0),
            diff_qty=0,
        ))
    db.session.commit()
    _log("create", "stock_take", take.id, f"جرد: {take.take_number}")
    return jsonify({"success": True, "stocktake": take.to_dict()}), 201


@inventory_bp.route("/stocktakes/<int:take_id>", methods=["PUT"])
@require_api("inventory", "edit")
def update_stocktake(take_id):
    take = StockTake.query.get_or_404(take_id)
    data = request.get_json(silent=True) or {}
    if "status" in data and data.get("status") == "completed" and take.status == "draft":
        for line in take.items:
            diff = float(line.counted_qty or 0) - float(line.system_qty or 0)
            line.diff_qty = diff
            if abs(diff) > 0.0001:
                _adjust_stock(line.item_id, take.warehouse_id, diff)
                _record_movement(line.item_id, take.warehouse_id,
                                 "stocktake", diff,
                                 reference_type="stocktake", reference_id=take.id,
                                 notes="تسوية جرد مخزني")
        take.status = "completed"
    elif "counted_qty" in data:
        for line in take.items:
            if line.id == data.get("item_id"):
                line.counted_qty = data.get("counted_qty") or 0
                line.diff_qty = float(line.counted_qty or 0) - float(line.system_qty or 0)
    take.notes = data.get("notes", take.notes)
    db.session.commit()
    _log("edit", "stock_take", take.id, f"جرد: {take.take_number}")
    return jsonify({"success": True, "stocktake": take.to_dict()})


@inventory_bp.route("/stocktakes/<int:take_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_stocktake(take_id):
    take = StockTake.query.get_or_404(take_id)
    if take.status == "completed":
        return jsonify({"message": "لا يمكن حذف جرد مكتمل"}), 400
    number = take.take_number
    db.session.delete(take)
    db.session.commit()
    _log("delete", "stock_take", take_id, f"جرد: {number}")
    return jsonify({"success": True})


# ============ الحركة المخزنية (Movements) ============

@inventory_bp.route("/movements", methods=["GET"])
@require_api("inventory", "view")
def list_movements():
    item_id = request.args.get("item_id", type=int)
    warehouse_id = request.args.get("warehouse_id", type=int)
    q = StockMovement.query
    if item_id:
        q = q.filter_by(item_id=item_id)
    if warehouse_id:
        q = q.filter_by(warehouse_id=warehouse_id)
    moves = q.order_by(StockMovement.created_at.desc()).limit(200).all()
    return jsonify({"movements": [m.to_dict() for m in moves]})


# ============ الموردون (Suppliers) ============

@inventory_bp.route("/suppliers", methods=["GET"])
@require_api("inventory", "view")
def list_suppliers():
    from models import Supplier
    suppliers = Supplier.query.order_by(Supplier.company_name).all()
    return jsonify({"suppliers": [s.to_dict() for s in suppliers]})


@inventory_bp.route("/suppliers", methods=["POST"])
@require_api("inventory", "create")
def create_supplier():
    from models import Supplier
    data = request.get_json(silent=True) or {}
    if not (data.get("company_name") or "").strip():
        return jsonify({"message": "اسم الشركة الموردة مطلوب"}), 400
    supplier = Supplier(
        company_name=data.get("company_name", "").strip(),
        contact_name=(data.get("contact_name") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        email=(data.get("email") or "").strip(),
        address=(data.get("address") or "").strip(),
        category=(data.get("category") or "").strip(),
    )
    db.session.add(supplier)
    db.session.commit()
    _log("create", "supplier", supplier.id, f"مورد: {supplier.company_name}")
    return jsonify({"success": True, "supplier": supplier.to_dict()}), 201


@inventory_bp.route("/suppliers/<int:supplier_id>", methods=["PUT"])
@require_api("inventory", "edit")
def update_supplier(supplier_id):
    from models import Supplier
    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json(silent=True) or {}
    if "company_name" in data and not (data.get("company_name") or "").strip():
        return jsonify({"message": "اسم الشركة الموردة مطلوب"}), 400
    supplier.company_name = (data.get("company_name", supplier.company_name) or "").strip()
    supplier.contact_name = (data.get("contact_name", supplier.contact_name) or "").strip()
    supplier.phone = (data.get("phone", supplier.phone) or "").strip()
    supplier.email = (data.get("email", supplier.email) or "").strip()
    supplier.address = (data.get("address", supplier.address) or "").strip()
    supplier.category = (data.get("category", supplier.category) or "").strip()
    db.session.commit()
    _log("edit", "supplier", supplier.id, f"مورد: {supplier.company_name}")
    return jsonify({"success": True, "supplier": supplier.to_dict()})


@inventory_bp.route("/suppliers/<int:supplier_id>", methods=["DELETE"])
@require_api("inventory", "delete")
def delete_supplier(supplier_id):
    from models import Supplier
    supplier = Supplier.query.get_or_404(supplier_id)
    name = supplier.company_name
    db.session.delete(supplier)
    db.session.commit()
    _log("delete", "supplier", supplier_id, f"مورد: {name}")
    return jsonify({"success": True})


# ============ تقارير المخزون ============

@inventory_bp.route("/reports", methods=["GET"])
@require_api("inventory", "view")
def stock_reports():
    """تقارير مخزنية: القيمة بالتكلفة، التقارير، الحركات، الصلاحية، الموردين."""
    today = datetime.now().date()
    report = request.args.get("report", "stock_value")
    warehouse_id = request.args.get("warehouse_id", type=int)
    category_id = request.args.get("category_id", type=int)
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    warehouses = [w.to_dict() for w in Warehouse.query.filter_by(is_active=True).all()]
    categories = [c.to_dict() for c in ItemCategory.query.filter_by(is_active=True).all()]

    def _stock_query():
        q = ItemStock.query
        if warehouse_id:
            q = q.filter(ItemStock.warehouse_id == warehouse_id)
        return q

    if report == "stock_value":
        rows = []
        total_value = 0.0
        total_cost = 0.0
        for s in _stock_query().all():
            if float(s.quantity or 0) <= 0:
                continue
            item = s.item
            if category_id and item.category_id != category_id:
                continue
            value = float(s.quantity or 0) * float(s.avg_cost or item.cost_price or 0)
            total_value += value
            total_cost += float(s.avg_cost or item.cost_price or 0)
            rows.append({
                "item_id": item.id,
                "item_code": item.code,
                "item_name": item.name,
                "category_name": item.category.name if item.category else None,
                "warehouse_id": s.warehouse_id,
                "warehouse_name": s.warehouse.name if s.warehouse else None,
                "quantity": float(s.quantity or 0),
                "unit_name": item.unit.name if item.unit else None,
                "avg_cost": float(s.avg_cost or 0),
                "value": round(value, 2),
            })
        rows.sort(key=lambda r: r["value"], reverse=True)
        return jsonify({
            "report": "stock_value",
            "warehouses": warehouses,
            "categories": categories,
            "rows": rows,
            "summary": {
                "total_value": round(total_value, 2),
                "total_cost": round(total_cost, 2),
                "items_count": len(rows),
            },
        })

    if report == "movements":
        q = StockMovement.query
        if warehouse_id:
            q = q.filter(StockMovement.warehouse_id == warehouse_id)
        if month and year:
            q = q.filter(db.extract("month", StockMovement.created_at) == month,
                         db.extract("year", StockMovement.created_at) == year)
        rows = [m.to_dict() for m in q.order_by(StockMovement.created_at.desc()).limit(1000).all()]
        return jsonify({
            "report": "movements",
            "warehouses": warehouses,
            "rows": rows,
        })

    if report == "expiry":
        rows = []
        q = StockBatch.query.filter(StockBatch.expiry_date.isnot(None))
        if warehouse_id:
            q = q.filter(StockBatch.warehouse_id == warehouse_id)
        for b in q.all():
            item = b.item
            if category_id and item.category_id != category_id:
                continue
            days = (b.expiry_date - today).days if b.expiry_date else None
            rows.append({
                "id": b.id,
                "batch_number": b.batch_number,
                "item_id": item.id,
                "item_code": item.code,
                "item_name": item.name,
                "warehouse_name": b.warehouse.name if b.warehouse else None,
                "quantity": float(b.quantity or 0),
                "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
                "received_date": b.received_date.isoformat() if b.received_date else None,
                "days_left": days,
                "status": "expired" if days is not None and days < 0 else
                          "expiring" if days is not None and days <= 60 else "ok",
            })
        rows.sort(key=lambda r: (r["days_left"] is None, r["days_left"] or 10**9))
        return jsonify({
            "report": "expiry",
            "warehouses": warehouses,
            "categories": categories,
            "rows": rows,
        })

    if report == "suppliers":
        from models import Supplier, Invoice, InvoiceItem
        rows = []
        for sup in Supplier.query.order_by(Supplier.company_name).all():
            items = {}
            total_purchased = 0.0
            for inv in Invoice.query.filter_by(supplier_id=sup.id, invoice_type="purchase").all():
                for it in inv.items:
                    total_purchased += float(it.quantity or 0) * float(it.unit_price or 0)
                    if it.item_id:
                        items.setdefault(it.item_id, {
                            "item_id": it.item_id,
                            "item_code": it.item.code if it.item else None,
                            "item_name": it.item.name if it.item else None,
                            "qty": 0.0,
                            "value": 0.0,
                        })
                        items[it.item_id]["qty"] += float(it.quantity or 0)
                        items[it.item_id]["value"] += float(it.quantity or 0) * float(it.unit_price or 0)
            rows.append({
                "id": sup.id,
                "company_name": sup.company_name,
                "contact_name": sup.contact_name,
                "phone": sup.phone,
                "total_purchased": round(total_purchased, 2),
                "items": sorted(items.values(), key=lambda x: x["value"], reverse=True),
            })
        rows.sort(key=lambda r: r["total_purchased"], reverse=True)
        return jsonify({
            "report": "suppliers",
            "rows": rows,
        })

    return jsonify({"message": "تقرير غير مدعوم"}), 400

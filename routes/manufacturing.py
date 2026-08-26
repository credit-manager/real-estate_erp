from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, date
from database import db
from models import (
    Item, Warehouse, Supplier,
    WorkCenter, RawMaterial, Bom, BomLine,
    ProductionOrder, ProductionOperation, QualityInspection,
    StockMovement, ItemStock,
)
from permissions import require_api, require_page
from auditlog import log_action
from utils.pagination import paged_or_cap

mf_bp = Blueprint("mf", __name__, url_prefix="/api/mf")
mf_pages_bp = Blueprint("mf_pages", __name__)


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


def _record_movement(item_id, warehouse_id, movement_type, quantity,
                     reference_type=None, reference_id=None, notes=""):
    db.session.add(StockMovement(
        item_id=item_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=(notes or "")[:300],
    ))


def _adjust_stock(item_id, warehouse_id, delta, cost=0):
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


def _component_unit_cost(item_id, warehouse_id):
    """تكلفة وحدة المكوّن الفعلية (متوسط تكلفة الرصيد في المخزن أو تكلفة الصنف)."""
    stock = ItemStock.query.filter_by(item_id=item_id, warehouse_id=warehouse_id).first()
    if stock and float(stock.avg_cost or 0) > 0:
        return float(stock.avg_cost)
    item = db.session.get(Item, item_id)
    return float(item.cost_price or 0) if item else 0


def _order_costing(order):
    """تفصيل تكلفة أمر إنتاج (تقديري وفعلي)."""
    material_est = 0.0
    material_actual = 0.0
    components = []
    if order.bom:
        for ln in order.bom.lines:
            qty = float(ln.quantity or 0)
            unit_est = float(ln.to_dict().get("cost_estimate") or 0)
            unit_act = _component_unit_cost(ln.item_id, order.warehouse_id)
            material_est += qty * unit_est
            material_actual += qty * unit_act
            components.append({
                "item_name": ln.item.name if ln.item else None,
                "item_code": ln.item.code if ln.item else None,
                "qty_per_unit": qty,
                "unit_est": round(unit_est, 2),
                "unit_act": round(unit_act, 2),
            })
    ordered_qty = float(order.quantity or 0)
    produced_qty = float(order.produced_qty or 0) or ordered_qty
    material_est = round(material_est * ordered_qty, 2)
    material_actual = round(material_actual * produced_qty, 2)
    operation_cost = 0.0
    for op in order.operations:
        if op.status != "cancelled":
            operation_cost += float(op.to_dict().get("operation_cost", 0))
    operation_cost = round(operation_cost, 2)
    labor = round(float(order.labor_cost or 0), 2)
    overhead = round(float(order.overhead_cost or 0), 2)
    total = round(material_actual + operation_cost + labor + overhead, 2)
    unit_cost = round(total / produced_qty, 2) if produced_qty else 0
    return {
        "components": components,
        "material_est": material_est,
        "material_actual": material_actual,
        "operation_cost": operation_cost,
        "labor": labor,
        "overhead": overhead,
        "total": total,
        "unit_cost": unit_cost,
        "variance": round(total - (order.material_estimate() + operation_cost + labor + overhead), 2),
    }


# ============ صفحات (Pages) ============

@mf_pages_bp.route("/mf/work-centers")
@require_page("manufacturing")
def page_work_centers():
    return render_template("mf_work_centers.html")


@mf_pages_bp.route("/mf/raw-materials")
@require_page("manufacturing")
def page_raw_materials():
    return render_template("mf_raw_materials.html")


@mf_pages_bp.route("/mf/bom")
@require_page("manufacturing")
def page_bom():
    return render_template("mf_bom.html")


@mf_pages_bp.route("/mf/orders")
@require_page("manufacturing")
def page_orders():
    return render_template("mf_orders.html")


@mf_pages_bp.route("/mf/operations")
@require_page("manufacturing")
def page_operations():
    return render_template("mf_operations.html")


@mf_pages_bp.route("/mf/quality")
@require_page("manufacturing")
def page_quality():
    return render_template("mf_quality.html")


@mf_pages_bp.route("/mf/tracking")
@require_page("manufacturing")
def page_tracking():
    return render_template("mf_tracking.html")


@mf_pages_bp.route("/mf/costing")
@require_page("manufacturing")
def page_costing():
    return render_template("mf_costing.html")


# ============ خيارات القوائم ============

@mf_bp.route("/options", methods=["GET"])
@require_api("manufacturing", "view")
def options():
    items = [{"id": i.id, "code": i.code, "name": i.name, "cost_price": float(i.cost_price or 0)}
             for i in Item.query.filter_by(is_active=True).order_by(Item.name).all()]
    warehouses = [{"id": w.id, "name": w.name} for w in Warehouse.query.filter_by(is_active=True).all()]
    suppliers = [{"id": s.id, "company_name": s.company_name} for s in Supplier.query.all()]
    work_centers = [{"id": wc.id, "code": wc.code, "name": wc.name, "hourly_cost": float(wc.hourly_cost or 0)}
                    for wc in WorkCenter.query.filter_by(is_active=True).all()]
    boms = [{"id": b.id, "code": b.code, "name": b.name, "product_item_id": b.product_item_id,
             "product_name": b.product_item.name if b.product_item else None} for b in Bom.query.all()]
    orders = [{"id": o.id, "order_number": o.order_number, "product_name": o.product_item.name if o.product_item else None,
               "status": o.status} for o in ProductionOrder.query.order_by(ProductionOrder.id.desc()).all()]
    return jsonify({
        "items": items, "warehouses": warehouses, "suppliers": suppliers,
        "work_centers": work_centers, "boms": boms, "orders": orders,
    })


# ============ المواد الخام ============

@mf_bp.route("/raw-materials", methods=["GET"])
@require_api("manufacturing", "view")
def list_raw_materials():
    q = RawMaterial.query.order_by(RawMaterial.item_id)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@mf_bp.route("/raw-materials", methods=["POST"])
@require_api("manufacturing", "create")
def create_raw_material():
    data = request.get_json(silent=True) or {}
    if not data.get("item_id"):
        return jsonify({"message": "الصنف مطلوب", "error_key": "mf.itemRequired"}), 400
    if RawMaterial.query.filter_by(item_id=data.get("item_id")).first():
        return jsonify({"message": "هذا الصنف مضاف بالفعل كمواد خام", "error_key": "mf.rawExists"}), 400
    rm = RawMaterial(
        item_id=data.get("item_id"),
        supplier_id=data.get("supplier_id") or None,
        standard_cost=float(data.get("standard_cost") or 0),
        reorder_level=float(data.get("reorder_level") or 0),
        min_stock=float(data.get("min_stock") or 0),
        is_active=bool(data.get("is_active", True)),
        notes=data.get("notes") or "",
    )
    db.session.add(rm)
    db.session.commit()
    _log("create", "raw_material", rm.id, f"مادة خام: {rm.item.name if rm.item else ''}")
    return jsonify(rm.to_dict()), 201


@mf_bp.route("/raw-materials/<int:rm_id>", methods=["PUT"])
@require_api("manufacturing", "edit")
def update_raw_material(rm_id):
    rm = RawMaterial.query.get_or_404(rm_id)
    data = request.get_json(silent=True) or {}
    for field in ["supplier_id", "standard_cost", "reorder_level", "min_stock", "is_active", "notes"]:
        if field in data:
            if field == "is_active":
                rm.is_active = bool(data[field])
            elif field in ("standard_cost", "reorder_level", "min_stock"):
                setattr(rm, field, float(data[field] or 0))
            else:
                setattr(rm, field, data[field] or None if field == "supplier_id" else data[field])
    db.session.commit()
    _log("edit", "raw_material", rm.id, "raw material updated")
    return jsonify(rm.to_dict())


@mf_bp.route("/raw-materials/<int:rm_id>", methods=["DELETE"])
@require_api("manufacturing", "delete")
def delete_raw_material(rm_id):
    rm = RawMaterial.query.get_or_404(rm_id)
    db.session.delete(rm)
    db.session.commit()
    _log("delete", "raw_material", rm_id, "raw material deleted")
    return jsonify({"success": True})


# ============ مراكز العمل (التشغيل) ============

@mf_bp.route("/work-centers", methods=["GET"])
@require_api("manufacturing", "view")
def list_work_centers():
    return jsonify([wc.to_dict() for wc in WorkCenter.query.order_by(WorkCenter.name).all()])


@mf_bp.route("/work-centers", methods=["POST"])
@require_api("manufacturing", "create")
def create_work_center():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم مركز العمل مطلوب", "error_key": "mf.nameRequired"}), 400
    code = (data.get("code") or "").strip() or _next_number("WC", WorkCenter, "code")
    if WorkCenter.query.filter_by(code=code).first():
        return jsonify({"message": "كود مركز العمل موجود مسبقاً", "error_key": "mf.codeExists"}), 400
    wc = WorkCenter(
        code=code,
        name=data.get("name").strip(),
        wc_type=data.get("wc_type") or "machine",
        hourly_cost=float(data.get("hourly_cost") or 0),
        capacity=float(data.get("capacity") or 0),
        is_active=bool(data.get("is_active", True)),
        notes=data.get("notes") or "",
    )
    db.session.add(wc)
    db.session.commit()
    _log("create", "work_center", wc.id, f"مركز عمل: {wc.name}")
    return jsonify(wc.to_dict()), 201


@mf_bp.route("/work-centers/<int:wc_id>", methods=["PUT"])
@require_api("manufacturing", "edit")
def update_work_center(wc_id):
    wc = WorkCenter.query.get_or_404(wc_id)
    data = request.get_json(silent=True) or {}
    if "name" in data and data.get("name"):
        wc.name = data["name"].strip()
    if "code" in data and data.get("code"):
        code = data["code"].strip()
        if code != wc.code and WorkCenter.query.filter_by(code=code).first():
            return jsonify({"message": "كود مركز العمل موجود مسبقاً", "error_key": "mf.codeExists"}), 400
        wc.code = code
    for field in ["wc_type", "notes"]:
        if field in data:
            setattr(wc, field, data[field])
    for field in ["hourly_cost", "capacity"]:
        if field in data:
            setattr(wc, field, float(data[field] or 0))
    if "is_active" in data:
        wc.is_active = bool(data["is_active"])
    db.session.commit()
    _log("edit", "work_center", wc.id, "work center updated")
    return jsonify(wc.to_dict())


@mf_bp.route("/work-centers/<int:wc_id>", methods=["DELETE"])
@require_api("manufacturing", "delete")
def delete_work_center(wc_id):
    wc = WorkCenter.query.get_or_404(wc_id)
    if ProductionOperation.query.filter_by(work_center_id=wc_id).first():
        return jsonify({"message": "لا يمكن حذف مركز عمل مستخدم في عمليات إنتاج", "error_key": "mf.wcInUse"}), 400
    db.session.delete(wc)
    db.session.commit()
    _log("delete", "work_center", wc_id, "work center deleted")
    return jsonify({"success": True})


# ============ قوائم المكونات (BOM) ============

@mf_bp.route("/boms", methods=["GET"])
@require_api("manufacturing", "view")
def list_boms():
    q = Bom.query.order_by(Bom.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@mf_bp.route("/boms", methods=["POST"])
@require_api("manufacturing", "create")
def create_bom():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم BOM مطلوب", "error_key": "mf.nameRequired"}), 400
    if not data.get("product_item_id"):
        return jsonify({"message": "الصنف المنتج مطلوب", "error_key": "mf.itemRequired"}), 400
    code = (data.get("code") or "").strip() or _next_number("BOM", Bom, "code")
    if Bom.query.filter_by(code=code).first():
        return jsonify({"message": "كود BOM موجود مسبقاً", "error_key": "mf.codeExists"}), 400
    bom = Bom(
        code=code,
        name=data.get("name").strip(),
        product_item_id=data.get("product_item_id"),
        version=(data.get("version") or "1.0").strip() or "1.0",
        is_active=bool(data.get("is_active", True)),
        notes=data.get("notes") or "",
    )
    db.session.add(bom)
    db.session.flush()
    for ln in data.get("lines") or []:
        if not ln.get("item_id"):
            continue
        qty = float(ln.get("quantity") or 0)
        if qty <= 0:
            continue
        db.session.add(BomLine(
            bom_id=bom.id,
            item_id=ln.get("item_id"),
            quantity=qty,
            cost_estimate=float(ln.get("cost_estimate") or 0),
            notes=ln.get("notes") or "",
        ))
    db.session.commit()
    _log("create", "bom", bom.id, f"BOM: {bom.name}")
    return jsonify(bom.to_dict()), 201


@mf_bp.route("/boms/<int:bom_id>", methods=["GET"])
@require_api("manufacturing", "view")
def get_bom(bom_id):
    return jsonify(Bom.query.get_or_404(bom_id).to_dict())


@mf_bp.route("/boms/<int:bom_id>", methods=["PUT"])
@require_api("manufacturing", "edit")
def update_bom(bom_id):
    bom = Bom.query.get_or_404(bom_id)
    data = request.get_json(silent=True) or {}
    if "name" in data and data.get("name"):
        bom.name = data["name"].strip()
    if "code" in data and data.get("code"):
        code = data["code"].strip()
        if code != bom.code and Bom.query.filter_by(code=code).first():
            return jsonify({"message": "كود BOM موجود مسبقاً", "error_key": "mf.codeExists"}), 400
        bom.code = code
    if "product_item_id" in data and data.get("product_item_id"):
        bom.product_item_id = data["product_item_id"]
    if "version" in data:
        bom.version = (data.get("version") or "").strip() or bom.version
    if "is_active" in data:
        bom.is_active = bool(data["is_active"])
    if "notes" in data:
        bom.notes = data.get("notes") or ""
    if "lines" in data:
        # إعادة بناء السطور
        for ln in list(bom.lines):
            db.session.delete(ln)
        db.session.flush()
        for ln in data.get("lines") or []:
            if not ln.get("item_id"):
                continue
            qty = float(ln.get("quantity") or 0)
            if qty <= 0:
                continue
            db.session.add(BomLine(
                bom_id=bom.id,
                item_id=ln.get("item_id"),
                quantity=qty,
                cost_estimate=float(ln.get("cost_estimate") or 0),
                notes=ln.get("notes") or "",
            ))
    db.session.commit()
    _log("edit", "bom", bom.id, "BOM updated")
    return jsonify(bom.to_dict())


@mf_bp.route("/boms/<int:bom_id>", methods=["DELETE"])
@require_api("manufacturing", "delete")
def delete_bom(bom_id):
    bom = Bom.query.get_or_404(bom_id)
    if ProductionOrder.query.filter_by(bom_id=bom_id).first():
        return jsonify({"message": "لا يمكن حذف BOM مستخدم في أوامر إنتاج", "error_key": "mf.bomInUse"}), 400
    for ln in list(bom.lines):
        db.session.delete(ln)
    db.session.delete(bom)
    db.session.commit()
    _log("delete", "bom", bom_id, "BOM deleted")
    return jsonify({"success": True})


# ============ أوامر الإنتاج ============

@mf_bp.route("/orders", methods=["GET"])
@require_api("manufacturing", "view")
def list_orders():
    q = ProductionOrder.query.order_by(ProductionOrder.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@mf_bp.route("/orders", methods=["POST"])
@require_api("manufacturing", "create")
def create_order():
    data = request.get_json(silent=True) or {}
    if not data.get("bom_id"):
        return jsonify({"message": "BOM مطلوب", "error_key": "mf.bomRequired"}), 400
    if not data.get("warehouse_id"):
        return jsonify({"message": "المخزن مطلوب", "error_key": "mf.warehouseRequired"}), 400
    qty = float(data.get("quantity") or 0)
    if qty <= 0:
        return jsonify({"message": "الكمية يجب أن تكون أكبر من صفر", "error_key": "mf.qtyRequired"}), 400
    bom = Bom.query.get_or_404(data.get("bom_id"))
    order = ProductionOrder(
        order_number=_next_number("PO", ProductionOrder, "order_number"),
        bom_id=bom.id,
        product_item_id=bom.product_item_id,
        warehouse_id=data.get("warehouse_id"),
        quantity=qty,
        produced_qty=float(data.get("produced_qty") or 0),
        start_date=parse_date(data.get("start_date")),
        due_date=parse_date(data.get("due_date")),
        status="planned",
        labor_cost=float(data.get("labor_cost") or 0),
        overhead_cost=float(data.get("overhead_cost") or 0),
        notes=data.get("notes") or "",
    )
    db.session.add(order)
    db.session.commit()
    _log("create", "production_order", order.id, f"أمر إنتاج: {order.order_number}")
    return jsonify(order.to_dict()), 201


@mf_bp.route("/orders/<int:order_id>", methods=["GET"])
@require_api("manufacturing", "view")
def get_order(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    d = order.to_dict()
    d["costing"] = _order_costing(order)
    return jsonify(d)


@mf_bp.route("/orders/<int:order_id>", methods=["PUT"])
@require_api("manufacturing", "edit")
def update_order(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    if order.status in ("completed", "cancelled"):
        return jsonify({"message": "لا يمكن تعديل أمر منتهٍ أو ملغي", "error_key": "mf.orderClosed"}), 400
    data = request.get_json(silent=True) or {}
    for field in ["quantity", "produced_qty", "labor_cost", "overhead_cost"]:
        if field in data:
            setattr(order, field, float(data[field] or 0))
    for field in ["start_date", "due_date"]:
        if field in data:
            setattr(order, field, parse_date(data[field]))
    if "warehouse_id" in data and data.get("warehouse_id"):
        order.warehouse_id = data["warehouse_id"]
    if "notes" in data:
        order.notes = data.get("notes") or ""
    db.session.commit()
    _log("edit", "production_order", order.id, "production order updated")
    return jsonify(order.to_dict())


@mf_bp.route("/orders/<int:order_id>", methods=["DELETE"])
@require_api("manufacturing", "delete")
def delete_order(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    if order.status == "completed":
        return jsonify({"message": "لا يمكن حذف أمر إنتاج منتهٍ", "error_key": "mf.orderClosed"}), 400
    for op in list(order.operations):
        db.session.delete(op)
    for ins in list(order.inspections):
        db.session.delete(ins)
    db.session.delete(order)
    db.session.commit()
    _log("delete", "production_order", order_id, "production order deleted")
    return jsonify({"success": True})


@mf_bp.route("/orders/<int:order_id>/start", methods=["POST"])
@require_api("manufacturing", "edit")
def start_order(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    if order.status not in ("planned", "in_progress"):
        return jsonify({"message": "لا يمكن بدء أمر بهذه الحالة", "error_key": "mf.badStatus"}), 400
    order.status = "in_progress"
    if not order.start_date:
        order.start_date = date.today()
    db.session.commit()
    _log("edit", "production_order", order.id, "order started")
    return jsonify(order.to_dict())


@mf_bp.route("/orders/<int:order_id>/produce", methods=["POST"])
@require_api("manufacturing", "edit")
def produce_order(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    if order.status not in ("planned", "in_progress"):
        return jsonify({"message": "لا يمكن تسجيل إنتاج لأمر منتهٍ أو ملغي", "error_key": "mf.badStatus"}), 400
    data = request.get_json(silent=True) or {}
    qty = float(data.get("qty") or 0)
    if qty <= 0:
        return jsonify({"message": "الكمية المنتجة يجب أن تكون أكبر من صفر", "error_key": "mf.qtyRequired"}), 400
    order.produced_qty = float(order.produced_qty or 0) + qty
    order.status = "in_progress"
    db.session.commit()
    _log("edit", "production_order", order.id, f"إنتاج {qty}")
    return jsonify(order.to_dict())


@mf_bp.route("/orders/<int:order_id>/complete", methods=["POST"])
@require_api("manufacturing", "edit")
def complete_order(order_id):
    """إتمام أمر الإنتاج: صرف المواد الخام وإضافة المنتج النهائي للمخزن."""
    order = ProductionOrder.query.get_or_404(order_id)
    if order.status in ("completed", "cancelled"):
        return jsonify({"message": "الأمر منتهٍ أو ملغي بالفعل", "error_key": "mf.orderClosed"}), 400
    produced = float(order.produced_qty or 0) or float(order.quantity or 0)
    bom = order.bom
    if not bom or not bom.lines:
        return jsonify({"message": "BOM بلا مكونات — لا يمكن إتمام الأمر", "error_key": "mf.bomNoLines"}), 400

    # فحص توفر المواد الخام
    missing = []
    needed_map = []
    for ln in bom.lines:
        need = float(ln.quantity or 0) * produced
        stock = ItemStock.query.filter_by(item_id=ln.item_id, warehouse_id=order.warehouse_id).first()
        avail = float(stock.quantity or 0) if stock else 0
        needed_map.append((ln.item_id, need, avail, ln.item.name if ln.item else None))
        if avail < need:
            missing.append(f"{ln.item.name if ln.item else ln.item_id} (المطلوب {need:.2f}، المتوفر {avail:.2f})")
    if missing:
        return jsonify({
            "message": "مواد خام غير كافية: " + "، ".join(missing),
            "error_key": "mf.insufficientMaterial",
            "missing": missing,
        }), 400

    # صرف المواد
    for item_id, need, _, name in needed_map:
        _adjust_stock(item_id, order.warehouse_id, -need)
        _record_movement(item_id, order.warehouse_id, "production_out", need,
                         reference_type="production_order", reference_id=order.id,
                         notes=f"صرف مواد لأمر إنتاج {order.order_number}")

    # إضافة المنتج النهائي بتكلفة إجمالية
    costing = _order_costing(order)
    unit_cost = costing["unit_cost"] if costing["unit_cost"] else float(order.product_item.cost_price or 0) if order.product_item else 0
    _adjust_stock(order.product_item_id, order.warehouse_id, produced, cost=unit_cost)
    _record_movement(order.product_item_id, order.warehouse_id, "production_in", produced,
                     reference_type="production_order", reference_id=order.id,
                     notes=f"إنتاج {order.order_number}")

    order.produced_qty = produced
    order.status = "completed"
    order.completed_at = date.today()
    db.session.commit()
    _log("complete", "production_order", order.id, f"إتمام أمر إنتاج {order.order_number}")
    return jsonify(order.to_dict())


@mf_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@require_api("manufacturing", "edit")
def cancel_order(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    if order.status in ("completed", "cancelled"):
        return jsonify({"message": "الأمر منتهٍ أو ملغي بالفعل", "error_key": "mf.orderClosed"}), 400
    order.status = "cancelled"
    db.session.commit()
    _log("cancel", "production_order", order.id, "order cancelled")
    return jsonify(order.to_dict())


# ============ عمليات التشغيل ============

@mf_bp.route("/operations", methods=["GET"])
@require_api("manufacturing", "view")
def list_operations():
    def _op_dict(op):
        d = op.to_dict()
        d["order_number"] = op.order.order_number if op.order else None
        d["product_name"] = op.order.product_item.name if op.order and op.order.product_item else None
        return d

    q = ProductionOperation.query.order_by(ProductionOperation.id.desc())
    items, envelope = paged_or_cap(q, _op_dict)
    return jsonify(envelope if envelope else items)


@mf_bp.route("/orders/<int:order_id>/operations", methods=["POST"])
@require_api("manufacturing", "create")
def create_operation(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    if order.status in ("completed", "cancelled"):
        return jsonify({"message": "لا يمكن إضافة عمليات لأمر منتهٍ أو ملغي", "error_key": "mf.orderClosed"}), 400
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم العملية مطلوب", "error_key": "mf.nameRequired"}), 400
    op = ProductionOperation(
        order_id=order.id,
        work_center_id=data.get("work_center_id") or None,
        name=data.get("name").strip(),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        planned_hours=float(data.get("planned_hours") or 0),
        actual_hours=float(data.get("actual_hours") or 0),
        labor_cost=float(data.get("labor_cost") or 0),
        status=data.get("status") or "pending",
        notes=data.get("notes") or "",
    )
    db.session.add(op)
    db.session.commit()
    order.status = "in_progress"
    db.session.commit()
    _log("create", "production_operation", op.id, f"عملية: {op.name}")
    return jsonify(op.to_dict()), 201


@mf_bp.route("/operations/<int:op_id>", methods=["PUT"])
@require_api("manufacturing", "edit")
def update_operation(op_id):
    op = ProductionOperation.query.get_or_404(op_id)
    if op.order.status in ("completed", "cancelled"):
        return jsonify({"message": "لا يمكن تعديل عمليات أمر منتهٍ أو ملغي", "error_key": "mf.orderClosed"}), 400
    data = request.get_json(silent=True) or {}
    for field in ["name", "status", "notes"]:
        if field in data:
            setattr(op, field, data[field])
    if "work_center_id" in data:
        op.work_center_id = data.get("work_center_id") or None
    for field in ["planned_hours", "actual_hours", "labor_cost"]:
        if field in data:
            setattr(op, field, float(data[field] or 0))
    for field in ["start_date", "end_date"]:
        if field in data:
            setattr(op, field, parse_date(data[field]))
    db.session.commit()
    _log("edit", "production_operation", op.id, "operation updated")
    return jsonify(op.to_dict())


@mf_bp.route("/operations/<int:op_id>", methods=["DELETE"])
@require_api("manufacturing", "delete")
def delete_operation(op_id):
    op = ProductionOperation.query.get_or_404(op_id)
    if op.order.status in ("completed", "cancelled"):
        return jsonify({"message": "لا يمكن حذف عمليات أمر منتهٍ أو ملغي", "error_key": "mf.orderClosed"}), 400
    db.session.delete(op)
    db.session.commit()
    _log("delete", "production_operation", op_id, "operation deleted")
    return jsonify({"success": True})


# ============ الجودة ============

@mf_bp.route("/inspections", methods=["GET"])
@require_api("manufacturing", "view")
def list_inspections():
    q = QualityInspection.query.order_by(QualityInspection.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@mf_bp.route("/inspections", methods=["POST"])
@require_api("manufacturing", "create")
def create_inspection():
    data = request.get_json(silent=True) or {}
    if not data.get("order_id"):
        return jsonify({"message": "أمر الإنتاج مطلوب", "error_key": "mf.orderRequired"}), 400
    order = ProductionOrder.query.get_or_404(data.get("order_id"))
    ins = QualityInspection(
        inspection_number=_next_number("QI", QualityInspection, "inspection_number"),
        order_id=order.id,
        item_id=data.get("item_id") or order.product_item_id,
        inspector=(data.get("inspector") or "").strip(),
        inspection_date=parse_date(data.get("inspection_date")) or date.today(),
        sample_size=float(data.get("sample_size") or 0),
        passed_qty=float(data.get("passed_qty") or 0),
        failed_qty=float(data.get("failed_qty") or 0),
        status=data.get("status") or "in_progress",
        notes=data.get("notes") or "",
    )
    db.session.add(ins)
    db.session.commit()
    _log("create", "quality_inspection", ins.id, f"فحص جودة: {ins.inspection_number}")
    return jsonify(ins.to_dict()), 201


@mf_bp.route("/inspections/<int:ins_id>", methods=["PUT"])
@require_api("manufacturing", "edit")
def update_inspection(ins_id):
    ins = QualityInspection.query.get_or_404(ins_id)
    data = request.get_json(silent=True) or {}
    for field in ["inspector", "status", "notes"]:
        if field in data:
            setattr(ins, field, data[field])
    for field in ["sample_size", "passed_qty", "failed_qty"]:
        if field in data:
            setattr(ins, field, float(data[field] or 0))
    if "inspection_date" in data:
        ins.inspection_date = parse_date(data["inspection_date"])
    if "item_id" in data and data.get("item_id"):
        ins.item_id = data["item_id"]
    db.session.commit()
    _log("edit", "quality_inspection", ins.id, "inspection updated")
    return jsonify(ins.to_dict())


@mf_bp.route("/inspections/<int:ins_id>", methods=["DELETE"])
@require_api("manufacturing", "delete")
def delete_inspection(ins_id):
    ins = QualityInspection.query.get_or_404(ins_id)
    db.session.delete(ins)
    db.session.commit()
    _log("delete", "quality_inspection", ins_id, "inspection deleted")
    return jsonify({"success": True})


# ============ متابعة الإنتاج ============

@mf_bp.route("/tracking", methods=["GET"])
@require_api("manufacturing", "view")
def tracking():
    orders = ProductionOrder.query.order_by(ProductionOrder.id.desc()).all()
    result = []
    for o in orders:
        d = o.to_dict()
        d["costing"] = _order_costing(o)
        result.append(d)
    totals = {
        "total": len(orders),
        "planned": sum(1 for o in orders if o.status == "planned"),
        "in_progress": sum(1 for o in orders if o.status == "in_progress"),
        "completed": sum(1 for o in orders if o.status == "completed"),
        "cancelled": sum(1 for o in orders if o.status == "cancelled"),
        "total_produced": round(sum(float(o.produced_qty or 0) for o in orders), 2),
        "total_qty": round(sum(float(o.quantity or 0) for o in orders), 2),
    }
    return jsonify({"orders": result, "totals": totals})


# ============ تكلفة الإنتاج ============

@mf_bp.route("/costing", methods=["GET"])
@require_api("manufacturing", "view")
def costing():
    orders = ProductionOrder.query.order_by(ProductionOrder.id.desc()).all()
    result = []
    t_material = t_operation = t_labor = t_overhead = t_total = 0.0
    for o in orders:
        c = _order_costing(o)
        d = o.to_dict()
        d["costing"] = c
        result.append(d)
        if o.status != "cancelled":
            t_material += c["material_actual"]
            t_operation += c["operation_cost"]
            t_labor += c["labor"]
            t_overhead += c["overhead"]
            t_total += c["total"]
    totals = {
        "material": round(t_material, 2),
        "operation": round(t_operation, 2),
        "labor": round(t_labor, 2),
        "overhead": round(t_overhead, 2),
        "total": round(t_total, 2),
    }
    return jsonify({"orders": result, "totals": totals})

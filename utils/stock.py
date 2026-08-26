"""Stock linkage helpers: apply/reverse a purchase invoice on inventory.

A purchase invoice (invoice_type == "purchase") whose line items carry an
item_id and a warehouse_id will, when saved:
  - create a StockBatch (batch number = INV-<invoice.id>),
  - increase the item stock in the target warehouse,
  - record a "purchase" StockMovement linked to the invoice.

When the invoice is deleted/edited, the same lines are reversed.
"""
from database import db


def apply_purchase_invoice(invoice):
    """Post a purchase invoice onto stock (batches, balances, movements)."""
    if getattr(invoice, "invoice_type", None) != "purchase":
        return
    from models import StockBatch, StockMovement, ItemStock

    for it in invoice.items:
        item_id = getattr(it, "item_id", None)
        warehouse_id = getattr(it, "warehouse_id", None)
        qty = float(getattr(it, "quantity", None) or 0)
        if not item_id or not warehouse_id or qty <= 0:
            continue
        unit_cost = float(getattr(it, "unit_price", None) or 0)

        batch = StockBatch(
            item_id=item_id,
            warehouse_id=warehouse_id,
            batch_number="INV-%d" % invoice.id,
            quantity=qty,
            received_date=getattr(invoice, "issue_date", None) or None,
            expiry_date=getattr(it, "expiry_date", None) or None,
        )
        db.session.add(batch)
        db.session.flush()

        stock = ItemStock.query.filter_by(item_id=item_id, warehouse_id=warehouse_id).first()
        if not stock:
            stock = ItemStock(item_id=item_id, warehouse_id=warehouse_id, quantity=0, avg_cost=0)
            db.session.add(stock)
        old_qty = float(stock.quantity or 0)
        old_total = old_qty * float(stock.avg_cost or 0)
        stock.quantity = old_qty + qty
        stock.avg_cost = (old_total + qty * unit_cost) / stock.quantity if stock.quantity else 0

        db.session.add(StockMovement(
            item_id=item_id,
            warehouse_id=warehouse_id,
            movement_type="purchase",
            quantity=qty,
            batch_id=batch.id,
            reference_type="invoice",
            reference_id=invoice.id,
            notes=invoice.invoice_number,
        ))
    db.session.commit()


def reverse_purchase_invoice(invoice):
    """Undo the stock effects of a purchase invoice."""
    if getattr(invoice, "invoice_type", None) != "purchase":
        return
    from models import StockBatch, StockMovement, ItemStock

    movements = StockMovement.query.filter_by(
        reference_type="invoice", reference_id=invoice.id, movement_type="purchase"
    ).all()
    for m in movements:
        stock = ItemStock.query.filter_by(item_id=m.item_id, warehouse_id=m.warehouse_id).first()
        if stock:
            stock.quantity = max(0, float(stock.quantity or 0) - float(m.quantity or 0))
        db.session.delete(m)

    batch_number = "INV-%d" % invoice.id
    for b in StockBatch.query.filter(StockBatch.batch_number == batch_number).all():
        db.session.delete(b)

    db.session.commit()

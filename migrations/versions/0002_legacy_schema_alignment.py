"""Align databases created by pre-Alembic application versions.

This migration makes schema changes that historically lived inside application
startup explicit and repeatable. It is intentionally additive and idempotent so
existing installations can be upgraded without destructive data changes.
"""

from alembic import op
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, Numeric, String, Text, inspect


revision = "0002_legacy_schema_alignment"
down_revision = "0001_accounting_integrity"
branch_labels = None
depends_on = None


def _has_table(table):
    return table in inspect(op.get_bind()).get_table_names()


def _add(table, name, column):
    inspector = inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns(table)}
    if name not in columns:
        op.add_column(table, column)


def _index(table, name, columns):
    inspector = inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return
    existing = {idx["name"] for idx in inspector.get_indexes(table) if idx.get("name")}
    if name not in existing:
        op.create_index(name, table, columns)


def upgrade():
    # Financial/document fields historically added by app.py at startup.
    _add("invoices", "financial_year_id", Column("financial_year_id", Integer))
    _add("invoices", "approval_status", Column("approval_status", String(20), server_default="not_required"))
    _add("invoices", "deleted_at", Column("deleted_at", DateTime, nullable=True))
    _add("invoices", "einv_status", Column("einv_status", String(20)))
    _add("invoices", "einv_reference", Column("einv_reference", String(120)))
    _add("invoices", "einv_qr", Column("einv_qr", Text))
    _add("invoices", "einv_submitted_at", Column("einv_submitted_at", DateTime))
    _add("invoices", "einv_message", Column("einv_message", Text))
    _index("invoices", "ix_invoices_deleted_at", ["deleted_at"])

    for table in ("purchase_orders", "rental_contracts"):
        _add(table, "financial_year_id", Column("financial_year_id", Integer))
        _add(table, "approval_status", Column("approval_status", String(20), server_default="not_required"))

    _add("payment_plans", "financial_year_id", Column("financial_year_id", Integer))

    for table in ("sales_orders", "journal_entries", "real_estate_units", "unit_reservations", "sales_contracts"):
        _add(table, "deleted_at", Column("deleted_at", DateTime, nullable=True))
        _index(table, f"ix_{table}_deleted_at", ["deleted_at"])

    for name, typ in (
        ("building_id", Integer),
        ("floor_id", Integer),
        ("unit_type_id", Integer),
        ("owner_id", Integer),
    ):
        _add("real_estate_units", name, Column(name, typ))

    _add("sales_contracts", "vat_rate", Column("vat_rate", Float, server_default="0"))
    _add("sales_contracts", "vat_amount", Column("vat_amount", Numeric(15, 2), server_default="0"))
    _add("commissions", "broker_id", Column("broker_id", Integer))

    _add("workflow_templates", "min_amount", Column("min_amount", Numeric(15, 2)))

    for name, typ, kwargs in (
        ("department_id", Integer, {}),
        ("position_id", Integer, {}),
        ("manager_id", Integer, {}),
        ("gender", String(10), {}),
        ("birth_date", Date, {}),
        ("end_date", Date, {}),
        ("employment_type", String(30), {"server_default": "full_time"}),
        ("user_id", Integer, {}),
    ):
        _add("employees", name, Column(name, typ, **kwargs))

    for name, typ in (("company", String(255)), ("notes", String(255))):
        _add("customers", name, Column(name, typ))
    _add("customers", "is_active", Column("is_active", Boolean, server_default="true"))

    for name, typ in (
        ("item_id", Integer),
        ("warehouse_id", Integer),
    ):
        _add("invoice_items", name, Column(name, typ))
    _add("invoice_items", "expiry_date", Column("expiry_date", Date))

    for name in ("check_in_lat", "check_in_lng", "check_out_lat", "check_out_lng"):
        _add("hr_attendance", name, Column(name, Float))

    for table in ("invoices", "purchase_orders", "rental_contracts"):
        _index(table, f"ix_{table}_financial_year_id", ["financial_year_id"])


def downgrade():
    # Deliberately conservative: these compatibility columns may contain data
    # written by upgraded installations. Retaining them avoids destructive loss.
    pass

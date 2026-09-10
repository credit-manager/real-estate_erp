"""Add database-level safety checks for financial master data.

Revision ID: 0003_financial_safety_checks
Revises: 0002_legacy_schema_alignment
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "0003_financial_safety_checks"
down_revision = "0002_legacy_schema_alignment"
branch_labels = None
depends_on = None

_CHECKS = {
    "budget_lines": {
        "ck_budget_line_amount_nonnegative": "amount >= 0",
    },
    "fixed_assets": {
        "ck_fixed_asset_cost_nonnegative": "cost >= 0",
        "ck_fixed_asset_useful_life_positive": "useful_life_years > 0",
        "ck_fixed_asset_salvage_nonnegative": "salvage_value >= 0",
        "ck_fixed_asset_accumulated_nonnegative": "accumulated_depreciation >= 0",
    },
    "depreciation_records": {
        "ck_depreciation_amount_nonnegative": "amount >= 0",
    },
}


def _validate_existing_rows(bind, table, constraint_name):
    predicates = {
        "ck_budget_line_amount_nonnegative": "amount < 0",
        "ck_fixed_asset_cost_nonnegative": "cost < 0",
        "ck_fixed_asset_useful_life_positive": "useful_life_years <= 0",
        "ck_fixed_asset_salvage_nonnegative": "salvage_value < 0",
        "ck_fixed_asset_accumulated_nonnegative": "accumulated_depreciation < 0",
        "ck_depreciation_amount_nonnegative": "amount < 0",
    }
    predicate = predicates[constraint_name]
    count = bind.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {predicate}")).scalar_one()
    if count:
        raise RuntimeError(
            f"Cannot install {constraint_name}: {count} existing rows in {table} violate the rule."
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table, constraints in _CHECKS.items():
        if table not in inspector.get_table_names():
            continue
        existing = {
            c["name"]
            for c in inspector.get_check_constraints(table)
            if c.get("name")
        }
        for name in constraints:
            if name in existing:
                continue
            _validate_existing_rows(bind, table, name)
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name, expression in constraints.items():
                if name not in existing:
                    batch_op.create_check_constraint(name, expression)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table, constraints in _CHECKS.items():
        if table not in inspector.get_table_names():
            continue
        existing = {
            c["name"]
            for c in inspector.get_check_constraints(table)
            if c.get("name")
        }
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name in constraints:
                if name in existing:
                    batch_op.drop_constraint(name, type_="check")

"""Add database invariants for financial-year integrity.

Revision ID: 0005_financial_year_integrity
Revises: 0004_journal_cancelled_status
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "0005_financial_year_integrity"
down_revision = "0004_journal_cancelled_status"
branch_labels = None
depends_on = None

CHECK_NAME = "ck_financial_year_date_range"
ACTIVE_INDEX = "uq_financial_year_one_active_per_company"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "financial_years" not in inspector.get_table_names():
        return

    checks = {
        c["name"]
        for c in inspector.get_check_constraints("financial_years")
        if c.get("name")
    }

    invalid = bind.execute(
        text("SELECT COUNT(*) FROM financial_years WHERE end_date <= start_date")
    ).scalar_one()
    if invalid:
        raise RuntimeError(
            f"Cannot install {CHECK_NAME}: {invalid} financial years have an invalid date range."
        )

    if CHECK_NAME not in checks:
        with op.batch_alter_table("financial_years", schema=None) as batch_op:
            batch_op.create_check_constraint(
                CHECK_NAME,
                "end_date > start_date",
            )

    duplicate_active = bind.execute(text(
        "SELECT company_id FROM financial_years "
        "WHERE is_active = TRUE GROUP BY company_id HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate_active:
        raise RuntimeError(
            "Cannot install uq_financial_year_one_active_per_company: "
            f"company {duplicate_active[0]} has multiple active financial years."
        )

    existing_indexes = {
        idx["name"]
        for idx in inspect(bind).get_indexes("financial_years")
        if idx.get("name")
    }
    if ACTIVE_INDEX not in existing_indexes:
        op.create_index(
            ACTIVE_INDEX,
            "financial_years",
            ["company_id"],
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "financial_years" not in inspector.get_table_names():
        return

    indexes = {
        idx["name"]
        for idx in inspector.get_indexes("financial_years")
        if idx.get("name")
    }
    if ACTIVE_INDEX in indexes:
        op.drop_index(ACTIVE_INDEX, table_name="financial_years")

    checks = {
        c["name"]
        for c in inspect(bind).get_check_constraints("financial_years")
        if c.get("name")
    }
    if CHECK_NAME in checks:
        with op.batch_alter_table("financial_years", schema=None) as batch_op:
            batch_op.drop_constraint(CHECK_NAME, type_="check")

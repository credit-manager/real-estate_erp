"""Add database-level accounting line integrity checks.

Revision ID: 0001_accounting_integrity
Revises:
Create Date: 2026-09-09
"""

from alembic import op
from sqlalchemy import inspect


revision = "0001_accounting_integrity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "journal_entry_lines" not in inspector.get_table_names():
        raise RuntimeError(
            "journal_entry_lines table is missing; initialize the application schema "
            "before applying accounting integrity migrations."
        )

    existing = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("journal_entry_lines")
        if constraint.get("name")
    }

    with op.batch_alter_table("journal_entry_lines", schema=None) as batch_op:
        if "ck_journal_line_debit_nonnegative" not in existing:
            batch_op.create_check_constraint(
                "ck_journal_line_debit_nonnegative", "debit >= 0"
            )
        if "ck_journal_line_credit_nonnegative" not in existing:
            batch_op.create_check_constraint(
                "ck_journal_line_credit_nonnegative", "credit >= 0"
            )
        if "ck_journal_line_one_side_only" not in existing:
            batch_op.create_check_constraint(
                "ck_journal_line_one_side_only", "debit = 0 OR credit = 0"
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "journal_entry_lines" not in inspector.get_table_names():
        return

    existing = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("journal_entry_lines")
        if constraint.get("name")
    }

    with op.batch_alter_table("journal_entry_lines", schema=None) as batch_op:
        for name in (
            "ck_journal_line_one_side_only",
            "ck_journal_line_credit_nonnegative",
            "ck_journal_line_debit_nonnegative",
        ):
            if name in existing:
                batch_op.drop_constraint(name, type_="check")

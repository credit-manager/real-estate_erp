"""Align the journal-entry status constraint with audited soft deletion.

Revision ID: 0004_journal_cancelled_status
Revises: 0003_financial_safety_checks
"""

from alembic import op
from sqlalchemy import inspect

revision = "0004_journal_cancelled_status"
down_revision = "0003_financial_safety_checks"
branch_labels = None
depends_on = None

OLD_NAME = "ck_journal_entry_status"
NEW_NAME = "ck_journal_entry_status"
EXPRESSION = "status IN ('posted', 'draft', 'cancelled')"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "journal_entries" not in inspector.get_table_names():
        return
    existing = {
        c["name"]
        for c in inspector.get_check_constraints("journal_entries")
        if c.get("name")
    }
    with op.batch_alter_table("journal_entries", schema=None) as batch_op:
        if OLD_NAME in existing:
            batch_op.drop_constraint(OLD_NAME, type_="check")
        batch_op.create_check_constraint(NEW_NAME, EXPRESSION)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "journal_entries" not in inspector.get_table_names():
        return
    existing = {
        c["name"]
        for c in inspector.get_check_constraints("journal_entries")
        if c.get("name")
    }
    with op.batch_alter_table("journal_entries", schema=None) as batch_op:
        if NEW_NAME in existing:
            batch_op.drop_constraint(NEW_NAME, type_="check")
        batch_op.create_check_constraint(
            OLD_NAME, "status IN ('posted', 'draft')"
        )

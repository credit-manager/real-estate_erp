"""Close remaining database bypasses around immutable journals.

Revision ID: 0007_harden_journal_delete_guards
Revises: 0006_journal_entry_immutability
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "0007_harden_journal_delete_guards"
down_revision = "0006_journal_entry_immutability"
branch_labels = None
depends_on = None

_ENTRY_DELETE_TRIGGER = "trg_prevent_journal_delete"
_LINE_TRIGGER = "trg_prevent_posted_journal_line_mutation"
_ENTRY_DELETE_FUNCTION = "prevent_journal_delete"
_LINE_FUNCTION = "prevent_posted_journal_line_mutation"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = set(inspect(bind).get_table_names())
    if "journal_entries" not in tables or "journal_entry_lines" not in tables:
        return

    op.execute(text(f"""
        CREATE OR REPLACE FUNCTION {_ENTRY_DELETE_FUNCTION}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'Journal entries are never physically deleted; use the audited cancellation/reversal workflow.'
                USING ERRCODE = '23514';
        END;
        $$;
    """))

    op.execute(text(f"""
        DROP TRIGGER IF EXISTS {_ENTRY_DELETE_TRIGGER} ON journal_entries;
        CREATE TRIGGER {_ENTRY_DELETE_TRIGGER}
        BEFORE DELETE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION {_ENTRY_DELETE_FUNCTION}();
    """))

    op.execute(text(f"""
        CREATE OR REPLACE FUNCTION {_LINE_FUNCTION}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            old_status TEXT;
            new_status TEXT;
        BEGIN
            IF TG_OP = 'DELETE' OR TG_OP = 'UPDATE' THEN
                SELECT status INTO old_status FROM journal_entries WHERE id = OLD.entry_id;
            END IF;
            IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
                SELECT status INTO new_status FROM journal_entries WHERE id = NEW.entry_id;
            END IF;

            IF old_status = 'posted' OR new_status = 'posted' THEN
                RAISE EXCEPTION 'Posted journal lines are immutable; use the reversal/cancellation workflow.'
                    USING ERRCODE = '23514';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$;
    """))

    op.execute(text(f"""
        DROP TRIGGER IF EXISTS {_LINE_TRIGGER} ON journal_entry_lines;
        CREATE TRIGGER {_LINE_TRIGGER}
        BEFORE INSERT OR UPDATE OR DELETE ON journal_entry_lines
        FOR EACH ROW EXECUTE FUNCTION {_LINE_FUNCTION}();
    """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = set(inspect(bind).get_table_names())
    if "journal_entries" in tables:
        op.execute(text(f"DROP TRIGGER IF EXISTS {_ENTRY_DELETE_TRIGGER} ON journal_entries"))
    if "journal_entry_lines" in tables:
        op.execute(text(f"DROP TRIGGER IF EXISTS {_LINE_TRIGGER} ON journal_entry_lines"))
    op.execute(text(f"DROP FUNCTION IF EXISTS {_ENTRY_DELETE_FUNCTION}()"))
    op.execute(text(f"DROP FUNCTION IF EXISTS {_LINE_FUNCTION}()"))

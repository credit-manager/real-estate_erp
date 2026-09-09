"""Protect posted journal entries from direct mutation.

Revision ID: 0006_journal_entry_immutability
Revises: 0005_financial_year_integrity
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "0006_journal_entry_immutability"
down_revision = "0005_financial_year_integrity"
branch_labels = None
depends_on = None

_ENTRY_TRIGGER = "trg_prevent_posted_journal_mutation"
_LINE_TRIGGER = "trg_prevent_posted_journal_line_mutation"
_ENTRY_FUNCTION = "prevent_posted_journal_mutation"
_LINE_FUNCTION = "prevent_posted_journal_line_mutation"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = set(inspect(bind).get_table_names())
    if "journal_entries" not in tables or "journal_entry_lines" not in tables:
        return

    op.execute(text(f"""
        CREATE OR REPLACE FUNCTION {_ENTRY_FUNCTION}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'posted' THEN
                IF NEW.status = 'cancelled'
                   AND NEW.entry_number IS NOT DISTINCT FROM OLD.entry_number
                   AND NEW.date IS NOT DISTINCT FROM OLD.date
                   AND NEW.financial_year_id IS NOT DISTINCT FROM OLD.financial_year_id
                   AND NEW.description IS NOT DISTINCT FROM OLD.description
                   AND NEW.source IS NOT DISTINCT FROM OLD.source
                   AND NEW.ref_type IS NOT DISTINCT FROM OLD.ref_type
                   AND NEW.ref_id IS NOT DISTINCT FROM OLD.ref_id
                   AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
                   AND NEW.posted_at IS NOT DISTINCT FROM OLD.posted_at
                   AND NEW.reversed_of IS NOT DISTINCT FROM OLD.reversed_of
                   AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at
                THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Posted journal entries are immutable; use the reversal/cancellation workflow.'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
    """))

    op.execute(text(f"""
        DROP TRIGGER IF EXISTS {_ENTRY_TRIGGER} ON journal_entries;
        CREATE TRIGGER {_ENTRY_TRIGGER}
        BEFORE UPDATE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION {_ENTRY_FUNCTION}();
    """))

    op.execute(text(f"""
        CREATE OR REPLACE FUNCTION {_LINE_FUNCTION}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            entry_status TEXT;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                SELECT status INTO entry_status FROM journal_entries WHERE id = OLD.entry_id;
            ELSE
                SELECT status INTO entry_status FROM journal_entries WHERE id = NEW.entry_id;
            END IF;

            IF entry_status = 'posted' THEN
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
        op.execute(text(f"DROP TRIGGER IF EXISTS {_ENTRY_TRIGGER} ON journal_entries"))
    if "journal_entry_lines" in tables:
        op.execute(text(f"DROP TRIGGER IF EXISTS {_LINE_TRIGGER} ON journal_entry_lines"))
    op.execute(text(f"DROP FUNCTION IF EXISTS {_ENTRY_FUNCTION}()"))
    op.execute(text(f"DROP FUNCTION IF EXISTS {_LINE_FUNCTION}()"))

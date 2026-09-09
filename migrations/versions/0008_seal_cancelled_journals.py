"""Seal cancelled journals and their lines as immutable audit records.

Revision ID: 0008_seal_cancelled_journals
Revises: 0007_harden_journal_delete_guards
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "0008_seal_cancelled_journals"
down_revision = "0007_harden_journal_delete_guards"
branch_labels = None
depends_on = None

_ENTRY_FUNCTION = "prevent_posted_or_cancelled_journal_mutation"
_LINE_FUNCTION = "prevent_posted_or_cancelled_journal_line_mutation"
_ENTRY_TRIGGER = "trg_prevent_posted_journal_mutation"
_ENTRY_DELETE_TRIGGER = "trg_prevent_journal_delete"
_LINE_TRIGGER = "trg_prevent_posted_journal_line_mutation"


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
                RAISE EXCEPTION 'Posted journal entries are immutable; use the audited cancellation/reversal workflow.'
                    USING ERRCODE = '23514';
            ELSIF OLD.status = 'cancelled' THEN
                RAISE EXCEPTION 'Cancelled journal entries are immutable audit records.'
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
            old_status TEXT;
            new_status TEXT;
        BEGIN
            IF TG_OP = 'DELETE' OR TG_OP = 'UPDATE' THEN
                SELECT status INTO old_status FROM journal_entries WHERE id = OLD.entry_id;
            END IF;
            IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
                SELECT status INTO new_status FROM journal_entries WHERE id = NEW.entry_id;
            END IF;

            IF old_status IN ('posted', 'cancelled') OR new_status IN ('posted', 'cancelled') THEN
                RAISE EXCEPTION 'Posted or cancelled journal lines are immutable audit records.'
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
    if "journal_entries" not in tables or "journal_entry_lines" not in tables:
        return

    op.execute(text(f"DROP TRIGGER IF EXISTS {_ENTRY_TRIGGER} ON journal_entries"))
    op.execute(text(f"DROP TRIGGER IF EXISTS {_ENTRY_DELETE_TRIGGER} ON journal_entries"))
    op.execute(text(f"DROP TRIGGER IF EXISTS {_LINE_TRIGGER} ON journal_entry_lines"))

    # Restore the trigger functions and DELETE protection from revision 0007.
    op.execute(text("""
        CREATE OR REPLACE FUNCTION prevent_posted_journal_mutation()
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
    op.execute(text("""
        CREATE TRIGGER trg_prevent_posted_journal_mutation
        BEFORE UPDATE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_posted_journal_mutation();
    """))

    op.execute(text("""
        CREATE OR REPLACE FUNCTION prevent_journal_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'Journal entries are never physically deleted; use the audited cancellation/reversal workflow.'
                USING ERRCODE = '23514';
        END;
        $$;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_prevent_journal_delete
        BEFORE DELETE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION prevent_journal_delete();
    """))

    op.execute(text("""
        CREATE OR REPLACE FUNCTION prevent_posted_journal_line_mutation()
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
    op.execute(text("""
        CREATE TRIGGER trg_prevent_posted_journal_line_mutation
        BEFORE INSERT OR UPDATE OR DELETE ON journal_entry_lines
        FOR EACH ROW EXECUTE FUNCTION prevent_posted_journal_line_mutation();
    """))

    op.execute(text(f"DROP FUNCTION IF EXISTS {_ENTRY_FUNCTION}()"))
    op.execute(text(f"DROP FUNCTION IF EXISTS {_LINE_FUNCTION}()"))

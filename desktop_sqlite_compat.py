"""SQLite compatibility for the self-contained Windows desktop build.

The cloud/master deployment uses PostgreSQL and can add named foreign-key
constraints to existing tables. SQLite does not support ALTER TABLE ...
ADD CONSTRAINT, while the desktop database is created with the model metadata
and already contains the foreign keys it can represent. Ignore only that
specific legacy migration statement when the active bind is SQLite.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


_ORIGINAL_EXECUTE = Session.execute


def _execute(self, statement, *args, **kwargs):
    try:
        bind = self.get_bind()
        dialect = getattr(bind, "dialect", None)
        sql = str(statement).strip().upper()
        if (
            getattr(dialect, "name", None) == "SQLITE"
            and sql.startswith("ALTER TABLE")
            and " ADD CONSTRAINT " in sql
            and " FOREIGN KEY " in sql
        ):
            return _ORIGINAL_EXECUTE(self, text("SELECT 1"), *args, **kwargs)
    except Exception:
        # Never interfere with normal SQLAlchemy error handling.
        pass
    return _ORIGINAL_EXECUTE(self, statement, *args, **kwargs)


if Session.execute is not _execute:
    Session.execute = _execute

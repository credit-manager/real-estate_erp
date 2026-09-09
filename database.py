"""Database initialization helpers for Dynamic Pro ERP."""
from sqlalchemy import event
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


@event.listens_for(db.session, "before_flush")
def _noop_before_flush(*_args, **_kwargs):
    """Keep the SQLAlchemy session event registry initialized in frozen builds."""
    return None

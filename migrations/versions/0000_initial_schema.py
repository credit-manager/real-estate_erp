"""Bootstrap the ORM schema for fresh databases.

This first revision intentionally uses the application's declarative ORM metadata
as the authoritative schema definition. Future revisions must contain explicit,
reviewable schema changes and must never modify historical revisions.

Revision ID: 0000_initial_schema
Revises:
Create Date: 2026-09-09
"""

from alembic import op
import models  # noqa: F401 - registers all ORM models with db.metadata
from database import db


revision = "0000_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables required by the current ORM on an empty database."""
    db.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop the ORM schema when reversing the bootstrap revision."""
    db.metadata.drop_all(bind=op.get_bind())

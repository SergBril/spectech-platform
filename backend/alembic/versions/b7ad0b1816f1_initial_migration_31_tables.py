"""Initial migration - 31 tables

Revision ID: b7ad0b1816f1
Revises:
Create Date: 2026-09-06

Note: Database was initialized via Base.metadata.create_all()
and stamped with this revision. Tables already exist.
Future migrations will be generated via autogenerate.
"""

# revision identifiers, used by Alembic
revision = "b7ad0b1816f1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Initial schema already exists - no operations needed."""
    # Database was initialized via SQLAlchemy Base.metadata.create_all()
    # All 31 tables already exist in the database
    # This migration is just a marker for Alembic version tracking
    pass


def downgrade() -> None:
    """Downgrade not supported for initial migration."""
    # To reset database, drop all tables manually:
    # DROP SCHEMA public CASCADE; CREATE SCHEMA public;
    pass

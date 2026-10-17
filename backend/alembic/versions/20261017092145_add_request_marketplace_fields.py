"""Add is_published and published_at to requests table."""

from alembic import op
import sqlalchemy as sa

revision = "20261017092145"
down_revision = "b900f6ea7225"  # Will be fixed manually if needed
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("requests", sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("requests", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("requests", "published_at")
    op.drop_column("requests", "is_published")

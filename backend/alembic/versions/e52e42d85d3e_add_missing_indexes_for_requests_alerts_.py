"""add_missing_indexes_for_requests_alerts_gps_marketplace

Revision ID: e52e42d85d3e
Revises: 20261017092145
Create Date: 2026-10-18 14:12:46.529963

"""

{"type": "Sequence, Union"}

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e52e42d85d3e"
down_revision: str | None = "20261017092145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_requests_company_id", "requests", ["company_id"])
    op.create_index("ix_requests_client_id", "requests", ["client_id"])
    op.create_index(
        "ix_requests_assigned_vehicle_id", "requests", ["assigned_vehicle_id"]
    )
    op.create_index(
        "ix_requests_vehicle_category_id", "requests", ["vehicle_category_id"]
    )
    op.create_index("ix_requests_status", "requests", ["status"])
    op.create_index("ix_requests_created_at", "requests", ["created_at"])
    op.create_index("ix_alerts_vehicle_id", "alerts", ["vehicle_id"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_gps_points_vehicle_id", "gps_points", ["vehicle_id"])
    op.create_index("ix_gps_points_recorded_at", "gps_points", ["recorded_at"])
    op.create_index(
        "ix_marketplace_offers_request_id", "marketplace_offers", ["request_id"]
    )
    op.create_index(
        "ix_marketplace_offers_vehicle_id", "marketplace_offers", ["vehicle_id"]
    )
    op.create_index("ix_marketplace_offers_status", "marketplace_offers", ["status"])
    op.create_index(
        "ix_maintenance_orders_vehicle_id", "maintenance_orders", ["vehicle_id"]
    )
    op.create_index("ix_maintenance_orders_status", "maintenance_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_maintenance_orders_status", "maintenance_orders")
    op.drop_index("ix_maintenance_orders_vehicle_id", "maintenance_orders")
    op.drop_index("ix_marketplace_offers_status", "marketplace_offers")
    op.drop_index("ix_marketplace_offers_vehicle_id", "marketplace_offers")
    op.drop_index("ix_marketplace_offers_request_id", "marketplace_offers")
    op.drop_index("ix_gps_points_recorded_at", "gps_points")
    op.drop_index("ix_gps_points_vehicle_id", "gps_points")
    op.drop_index("ix_alerts_status", "alerts")
    op.drop_index("ix_alerts_vehicle_id", "alerts")
    op.drop_index("ix_requests_created_at", "requests")
    op.drop_index("ix_requests_status", "requests")
    op.drop_index("ix_requests_vehicle_category_id", "requests")
    op.drop_index("ix_requests_assigned_vehicle_id", "requests")
    op.drop_index("ix_requests_client_id", "requests")
    op.drop_index("ix_requests_company_id", "requests")

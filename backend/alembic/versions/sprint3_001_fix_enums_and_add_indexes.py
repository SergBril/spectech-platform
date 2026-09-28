"""Sprint 3: Fix enum types and add telematics indexes

Revision ID: sprint3_001
Revises: add_vat_amount_001
Create Date: 2026-09-28
"""

import sqlalchemy as sa

from alembic import op

revision = "sprint3_001"
down_revision = "add_vat_amount_001"
branch_labels = None
depends_on = None


def upgrade():
    # === 1. Создаём Enum типы ДО их использования ===
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE emailstatus AS ENUM (
                'pending', 'sent', 'delivered', 'failed', 'bounced'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE emailtemplatetype AS ENUM (
                'invoice_created', 'invoice_overdue', 'act_created',
                'act_signed', 'maintenance_completed', 'welcome', 'custom'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE maintenanceordertype AS ENUM (
                'scheduled', 'repair', 'diagnostic', 'inspection'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE maintenanceorderstatus AS ENUM (
                'planned', 'in_progress', 'completed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE maintenancepriority AS ENUM (
                'low', 'medium', 'high', 'critical'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """
    )

    # === 2. Изменяем типы колонок на Enum (с USING для безопасной конвертации) ===
    op.execute(
        """
        ALTER TABLE email_logs
        ALTER COLUMN status TYPE emailstatus
        USING status::text::emailstatus;
    """
    )

    op.execute(
        """
        ALTER TABLE email_templates
        ALTER COLUMN template_type TYPE emailtemplatetype
        USING template_type::text::emailtemplatetype;
    """
    )

    op.execute(
        """
        ALTER TABLE maintenance_orders
        ALTER COLUMN order_type TYPE maintenanceordertype
        USING order_type::text::maintenanceordertype;
    """
    )

    op.execute(
        """
        ALTER TABLE maintenance_orders
        ALTER COLUMN status TYPE maintenanceorderstatus
        USING status::text::maintenanceorderstatus;
    """
    )

    op.execute(
        """
        ALTER TABLE maintenance_orders
        ALTER COLUMN priority TYPE maintenancepriority
        USING priority::text::maintenancepriority;
    """
    )

    # === 3. Индексы для телеметрии ===
    op.create_index(
        "idx_gps_points_vehicle_time",
        "gps_points",
        ["vehicle_id", sa.text("recorded_at DESC")],
    )
    op.create_index(
        "idx_gps_points_fuel",
        "gps_points",
        ["vehicle_id", "fuel_level", sa.text("recorded_at DESC")],
    )
    op.create_index(
        "idx_geofence_events_vehicle",
        "geofence_events",
        ["vehicle_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "idx_fuel_transactions_vehicle",
        "fuel_transactions",
        ["vehicle_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "idx_alerts_status_severity",
        "alerts",
        ["status", "severity"],
    )
    op.create_index(
        "idx_alerts_vehicle",
        "alerts",
        ["vehicle_id", sa.text("occurred_at DESC")],
    )


def downgrade():
    op.drop_index("idx_gps_points_vehicle_time", table_name="gps_points")
    op.drop_index("idx_gps_points_fuel", table_name="gps_points")
    op.drop_index("idx_geofence_events_vehicle", table_name="geofence_events")
    op.drop_index("idx_fuel_transactions_vehicle", table_name="fuel_transactions")
    op.drop_index("idx_alerts_status_severity", table_name="alerts")
    op.drop_index("idx_alerts_vehicle", table_name="alerts")

    op.execute("ALTER TABLE email_logs ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute(
        "ALTER TABLE email_templates ALTER COLUMN template_type TYPE VARCHAR(50)"
    )
    op.execute(
        "ALTER TABLE maintenance_orders ALTER COLUMN order_type TYPE VARCHAR(20)"
    )
    op.execute("ALTER TABLE maintenance_orders ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute("ALTER TABLE maintenance_orders ALTER COLUMN priority TYPE VARCHAR(20)")

    op.execute("DROP TYPE IF EXISTS emailstatus")
    op.execute("DROP TYPE IF EXISTS emailtemplatetype")
    op.execute("DROP TYPE IF EXISTS maintenanceordertype")
    op.execute("DROP TYPE IF EXISTS maintenanceorderstatus")
    op.execute("DROP TYPE IF EXISTS maintenancepriority")

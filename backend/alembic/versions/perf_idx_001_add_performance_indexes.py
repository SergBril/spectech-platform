"""Add performance indexes for frequently queried columns

Revision ID: perf_idx_001
Revises: sprint3_002_timescaledb_hypertable
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa

revision = "perf_idx_001"
down_revision = "sprint3_002_timescaledb_hypertable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── auth.users ──────────────────────────────────────────
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # ── auth.user_sessions / tokens ─────────────────────────
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    # ── finance.invoices ────────────────────────────────────
    op.create_index("ix_invoices_company_id", "invoices", ["company_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_client_id", "invoices", ["client_id"])
    op.create_index("ix_invoices_created_at", "invoices", ["created_at"])

    # ── finance.acts ────────────────────────────────────────
    op.create_index("ix_acts_company_id", "acts", ["company_id"])
    op.create_index("ix_acts_status", "acts", ["status"])
    op.create_index("ix_acts_created_at", "acts", ["created_at"])

    # ── finance.payouts ─────────────────────────────────────
    op.create_index("ix_payouts_company_id", "payouts", ["company_id"])
    op.create_index("ix_payouts_status", "payouts", ["status"])
    op.create_index("ix_payouts_owner_id", "payouts", ["owner_id"])

    # ── dispatch.requests ───────────────────────────────────
    op.create_index("ix_requests_status", "requests", ["status"])
    op.create_index("ix_requests_company_id", "requests", ["company_id"])
    op.create_index("ix_requests_created_at", "requests", ["created_at"])

    # ── maintenance.maintenance_orders ──────────────────────
    op.create_index("ix_maintenance_orders_vehicle_id", "maintenance_orders", ["vehicle_id"])
    op.create_index("ix_maintenance_orders_company_id", "maintenance_orders", ["company_id"])
    op.create_index("ix_maintenance_orders_status", "maintenance_orders", ["status"])

    # ── marketplace.listings ────────────────────────────────
    op.create_index("ix_marketplace_listings_company_id", "marketplace_listings", ["company_id"])
    op.create_index("ix_marketplace_listings_status", "marketplace_listings", ["status"])
    op.create_index("ix_marketplace_listings_region", "marketplace_listings", ["region"])

    # ── telematics.gps_points ───────────────────────────────
    op.create_index("ix_gps_points_vehicle_id_ts", "gps_points", ["vehicle_id", "timestamp"])

    # ── chat.messages ───────────────────────────────────────
    op.create_index("ix_chat_messages_chat_id", "chat_messages", ["chat_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])

    # ── notifications ───────────────────────────────────────
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read", "notifications", ["is_read"])

    # ── bank_statements ─────────────────────────────────────
    op.create_index("ix_bank_statements_company_id", "bank_statements", ["company_id"])
    op.create_index("ix_bank_statements_status", "bank_statements", ["status"])
    op.create_index("ix_bank_statement_lines_company_id", "bank_statement_lines", ["company_id"])


def downgrade() -> None:
    # Drop in reverse order
    tables_indexes = [
        ("bank_statement_lines", ["ix_bank_statement_lines_company_id"]),
        ("bank_statements", ["ix_bank_statements_company_id", "ix_bank_statements_status"]),
        ("notifications", ["ix_notifications_user_id", "ix_notifications_read"]),
        ("chat_messages", ["ix_chat_messages_chat_id", "ix_chat_messages_created_at"]),
        ("gps_points", ["ix_gps_points_vehicle_id_ts"]),
        ("marketplace_listings", ["ix_marketplace_listings_company_id", "ix_marketplace_listings_status", "ix_marketplace_listings_region"]),
        ("maintenance_orders", ["ix_maintenance_orders_vehicle_id", "ix_maintenance_orders_company_id", "ix_maintenance_orders_status"]),
        ("requests", ["ix_requests_status", "ix_requests_company_id", "ix_requests_created_at"]),
        ("payouts", ["ix_payouts_company_id", "ix_payouts_status", "ix_payouts_owner_id"]),
        ("acts", ["ix_acts_company_id", "ix_acts_status", "ix_acts_created_at"]),
        ("invoices", ["ix_invoices_company_id", "ix_invoices_status", "ix_invoices_client_id", "ix_invoices_created_at"]),
        ("password_reset_tokens", ["ix_password_reset_tokens_user_id"]),
        ("user_sessions", ["ix_user_sessions_user_id"]),
        ("users", ["ix_users_company_id", "ix_users_status", "ix_users_created_at"]),
    ]
    for table, indexes in tables_indexes:
        for idx in indexes:
            op.drop_index(idx, table_name=table)

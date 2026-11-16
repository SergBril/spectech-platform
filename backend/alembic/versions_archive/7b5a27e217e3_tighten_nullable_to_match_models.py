"""tighten nullable to match models

Revision ID: 7b5a27e217e3
Revises: e7abeaae0846
Create Date: 2026-11-15 14:03:17.577288

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b5a27e217e3"  # pragma: allowlist secret
down_revision: str | None = "e7abeaae0846"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COLUMNS = [
    ("audit_logs", "created_at"),
    ("auto_assign_rules", "created_at"),
    ("auto_assign_rules", "is_active"),
    ("auto_assign_rules", "priority"),
    ("bank_statements", "closing_balance"),
    ("bank_statements", "created_at"),
    ("bank_statements", "matched_transactions"),
    ("bank_statements", "opening_balance"),
    ("bank_statements", "status"),
    ("bank_statements", "total_incoming"),
    ("bank_statements", "total_outgoing"),
    ("bank_statements", "total_transactions"),
    ("bank_statements", "unmatched_transactions"),
    ("bank_transactions", "created_at"),
    ("bank_transactions", "is_excluded"),
    ("bank_transactions", "match_status"),
    ("company_cost_rates", "amortization_per_hour"),
    ("company_cost_rates", "fuel_price_per_liter"),
    ("company_cost_rates", "hourly_wage"),
    ("company_cost_rates", "updated_at"),
    ("device_tokens", "created_at"),
    ("device_tokens", "is_active"),
    ("device_tokens", "platform"),
    ("document_archive", "created_at"),
    ("edo_send_logs", "sent_at"),
    ("email_logs", "company_id"),
    ("notification_templates", "is_active"),
    ("notification_templates", "updated_at"),
    ("pre_shift_checklists", "has_issues"),
    ("salary_records", "created_at"),
    ("salary_records", "deductions"),
    ("salary_records", "gross_amount"),
    ("salary_records", "net_amount"),
    ("salary_records", "shifts_count"),
    ("salary_records", "status"),
    ("salary_records", "total_hours"),
    ("salary_records", "total_km"),
    ("shift_audit_log", "created_at"),
    ("shift_fuel_entries", "created_at"),
    ("shift_fuel_entries", "fuel_type"),
    ("shift_geofences", "auto_completed"),
    ("shift_geofences", "auto_started"),
    ("shift_geofences", "created_at"),
    ("shift_template_exclusions", "created_at"),
    ("shift_templates", "created_at"),
    ("shift_templates", "is_active"),
    ("user_notification_preferences", "notify_act_signed_email"),
    ("user_notification_preferences", "notify_act_signed_max"),
    ("user_notification_preferences", "notify_overdue_email"),
    ("user_notification_preferences", "notify_overdue_max"),
    ("user_notification_preferences", "notify_role_change_email"),
    ("user_notification_preferences", "notify_role_change_max"),
    ("user_notification_preferences", "updated_at"),
    ("users", "role"),
    ("vehicle_checklist_configs", "created_at"),
    ("vehicle_checklist_configs", "is_active"),
    ("vehicles", "marketplace_commission_agreed"),
    ("vehicles", "marketplace_commission_rate"),
]


def upgrade() -> None:
    """Set NOT NULL on columns the models already require.

    These were created by create_all against older models and stayed
    nullable after the models were tightened, with no migration to match.
    The presence-only drift check could not see it: names matched,
    nullability did not. Verified before writing: zero NULLs in every one
    of these columns, so SET NOT NULL cannot fail on existing data.
    """
    for table, column in _COLUMNS:
        op.alter_column(table, column, nullable=False)


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(table, column, nullable=True)

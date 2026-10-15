"""add_driver_profiles

Revision ID: d001_driver_profiles
Revises: c44b8a3ef7c2
Create Date: 2026-10-15 19:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd001_driver_profiles'
down_revision: Union[str, None] = 'c44b8a3ef7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('driver_profiles',
        sa.Column('employee_contractor_id', sa.Integer(), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('passport_series', sa.String(20), nullable=True),
        sa.Column('passport_number', sa.String(20), nullable=True),
        sa.Column('passport_issued_by', sa.String(500), nullable=True),
        sa.Column('passport_issue_date', sa.Date(), nullable=True),
        sa.Column('license_number', sa.String(50), nullable=True),
        sa.Column('license_category', sa.String(20), nullable=True, comment='A,B,C,D,E или BE,CE,DE'),
        sa.Column('license_issue_date', sa.Date(), nullable=True),
        sa.Column('license_expiry_date', sa.Date(), nullable=True),
        sa.Column('machinist_certificate', sa.String(100), nullable=True, comment='Номер удостоверения машиниста'),
        sa.Column('machinist_certificate_type', sa.String(100), nullable=True, comment='Тип: экскаваторщик, крановщик'),
        sa.Column('machinist_certificate_expiry', sa.Date(), nullable=True),
        sa.Column('medical_cert_expiry', sa.Date(), nullable=True, comment='Медосмотр'),
        sa.Column('safety_training_expiry', sa.Date(), nullable=True, comment='Охрана труда'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_contractor_id'], ['employees.contractor_id'], ),
        sa.PrimaryKeyConstraint('employee_contractor_id')
    )


def downgrade() -> None:
    op.drop_table('driver_profiles')
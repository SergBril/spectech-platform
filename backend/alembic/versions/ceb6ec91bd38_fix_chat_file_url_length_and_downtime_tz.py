"""fix chat file_url length and downtime tz

Revision ID: ceb6ec91bd38
Revises: fbfa59b5ac26
Create Date: 2026-10-06 19:42:49.210545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ceb6ec91bd38'
down_revision: Union[str, None] = 'fbfa59b5ac26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Добавляем колонку file_url в chat_messages
    op.add_column('chat_messages', sa.Column('file_url', sa.String(length=2048), nullable=True))

    # 2. Обновляем временные метки в downtime_events для поддержки timezone
    op.alter_column('downtime_events', 'started_at',
               existing_type=sa.DateTime(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False,
               postgresql_using='started_at AT TIME ZONE \'UTC\'')
    op.alter_column('downtime_events', 'ended_at',
               existing_type=sa.DateTime(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True,
               postgresql_using='ended_at AT TIME ZONE \'UTC\'')
    op.alter_column('downtime_events', 'approved_at',
               existing_type=sa.DateTime(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True,
               postgresql_using='approved_at AT TIME ZONE \'UTC\'')
    op.alter_column('downtime_events', 'created_at',
               existing_type=sa.DateTime(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False,
               existing_server_default=sa.text("now()"),
               postgresql_using='created_at AT TIME ZONE \'UTC\'')
    op.alter_column('downtime_events', 'updated_at',
               existing_type=sa.DateTime(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False,
               existing_server_default=sa.text("now()"),
               postgresql_using='updated_at AT TIME ZONE \'UTC\'')


def downgrade() -> None:
    # Откат timezone
    op.alter_column('downtime_events', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.DateTime(),
               existing_nullable=False,
               existing_server_default=sa.text("now()"),
               postgresql_using='updated_at AT TIME ZONE \'UTC\'')
    op.alter_column('downtime_events', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.DateTime(),
               existing_nullable=False,
               existing_server_default=sa.text("now()"),
               postgresql_using='created_at AT TIME ZONE \'UTC\'')
    op.alter_column('downtime_events', 'approved_at',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.DateTime(),
               existing_nullable=True,
               postgresql_using='approved_at AT TIME ZONE \'UTC\'')
    op.alter_column('downtime_events', 'ended_at',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.DateTime(),
               existing_nullable=True,
               postgresql_using='ended_at AT TIME ZONE \'UTC\'')
    op.alter_column('downtime_events', 'started_at',
               existing_type=sa.DateTime(timezone=True),
               type_=sa.DateTime(),
               existing_nullable=False,
               postgresql_using='started_at AT TIME ZONE \'UTC\'')

    # Откат file_url
    op.drop_column('chat_messages', 'file_url')
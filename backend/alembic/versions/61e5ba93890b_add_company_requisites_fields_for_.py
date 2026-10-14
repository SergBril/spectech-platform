"""add company requisites fields for documents

Revision ID: 61e5ba93890b
Revises: d505bed142e8
Create Date: 2026-10-14 16:27:08.212771

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61e5ba93890b'
down_revision: Union[str, None] = 'd505bed142e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('actual_address', sa.String(500), nullable=True, comment='Фактический адрес'))
    op.add_column('companies', sa.Column('email', sa.String(255), nullable=True, comment='Email для документов'))
    op.add_column('companies', sa.Column('bank_name', sa.String(300), nullable=True, comment='Наименование банка'))
    op.add_column('companies', sa.Column('bik', sa.String(20), nullable=True, comment='БИК банка'))
    op.add_column('companies', sa.Column('checking_account', sa.String(50), nullable=True, comment='Расчётный счёт'))
    op.add_column('companies', sa.Column('correspondent_account', sa.String(50), nullable=True, comment='Корреспондентский счёт'))
    op.add_column('companies', sa.Column('ogrn', sa.String(50), nullable=True, comment='ОГРН / ОГРНИП'))
    op.add_column('companies', sa.Column('okpo', sa.String(20), nullable=True, comment='ОКПО'))
    op.add_column('companies', sa.Column('director_name', sa.String(300), nullable=True, comment='ФИО руководителя'))
    op.add_column('companies', sa.Column('director_position', sa.String(100), nullable=True, comment='Должность руководителя'))
    op.add_column('companies', sa.Column('stamp_image_url', sa.String(500), nullable=True, comment='URL изображения печати'))
    op.add_column('companies', sa.Column('signature_image_url', sa.String(500), nullable=True, comment='URL изображения подписи'))


def downgrade() -> None:
    op.drop_column('companies', 'signature_image_url')
    op.drop_column('companies', 'stamp_image_url')
    op.drop_column('companies', 'director_position')
    op.drop_column('companies', 'director_name')
    op.drop_column('companies', 'okpo')
    op.drop_column('companies', 'ogrn')
    op.drop_column('companies', 'correspondent_account')
    op.drop_column('companies', 'checking_account')
    op.drop_column('companies', 'bik')
    op.drop_column('companies', 'bank_name')
    op.drop_column('companies', 'email')
    op.drop_column('companies', 'actual_address')
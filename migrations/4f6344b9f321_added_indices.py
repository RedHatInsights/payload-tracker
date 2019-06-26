"""Added Indices

Revision ID: 4f6344b9f321
Revises: ae8f0f156ca6
Create Date: 2019-06-26 08:50:41.642138

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4f6344b9f321'
down_revision = 'ae8f0f156ca6'
branch_labels = None
depends_on = None


def downgrade():
    op.drop_index('payloads_account_idx', table_name='payloads')
    op.drop_index('payloads_created_at_idx', table_name='payloads')
    op.drop_index('payloads_date_idx', table_name='payloads')
    op.drop_index('payloads_id_idx', table_name='payloads')
    op.drop_index('payloads_inventory_id_idx', table_name='payloads')
    op.drop_index('payloads_payload_id_idx', table_name='payloads')
    op.drop_index('payloads_service_idx', table_name='payloads')
    op.drop_index('payloads_source_idx', table_name='payloads')
    op.drop_index('payloads_status_idx', table_name='payloads')
    op.drop_index('payloads_status_msg_idx', table_name='payloads')
    op.drop_index('payloads_system_id_idx', table_name='payloads')


def upgrade():
    op.create_index('payloads_system_id_idx', 'payloads', ['system_id'], unique=False)
    op.create_index('payloads_status_msg_idx', 'payloads', ['status_msg'], unique=False)
    op.create_index('payloads_status_idx', 'payloads', ['status'], unique=False)
    op.create_index('payloads_source_idx', 'payloads', ['source'], unique=False)
    op.create_index('payloads_service_idx', 'payloads', ['service'], unique=False)
    op.create_index('payloads_payload_id_idx', 'payloads', ['payload_id'], unique=False)
    op.create_index('payloads_inventory_id_idx', 'payloads', ['inventory_id'], unique=False)
    op.create_index('payloads_id_idx', 'payloads', ['id'], unique=True)
    op.create_index('payloads_date_idx', 'payloads', ['date'], unique=False)
    op.create_index('payloads_created_at_idx', 'payloads', ['created_at'], unique=False)
    op.create_index('payloads_account_idx', 'payloads', ['account'], unique=False)

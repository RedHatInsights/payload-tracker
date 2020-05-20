"""create_tables

Revision ID: 85cddc32f5d2
Revises:
Create Date: 2020-05-20 12:28:07.694680

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '85cddc32f5d2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'payloads',
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('account', sa.String(), nullable=True),
        sa.Column('inventory_id', sa.String(), nullable=True),
        sa.Column('system_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"), nullable=False),
        sa.PrimaryKeyConstraint('request_id')
    )

    op.create_index('payloads_request_id_idx', 'payloads', ['request_id'], unique=True)
    op.create_index('payloads_account_idx', 'payloads', ['account'], unique=False)
    op.create_index('payloads_inventory_id_idx', 'payloads', ['inventory_id'], unique=False)
    op.create_index('payloads_system_id_idx', 'payloads', ['system_id'], unique=False)
    op.create_index('payloads_created_at_idx', 'payloads', ['created_at'], unique=False)

    op.create_table(
        'payload_statuses',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('service', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('status_msg', sa.String(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['request_id'], ['payloads.request_id'])
    )

    op.create_index('payload_statuses_id_idx', 'payload_statuses', ['id'], unique=True)
    op.create_index('payload_statuses_request_id_idx', 'payload_statuses', ['request_id'], unique=False)
    op.create_index('payload_statuses_service_idx', 'payload_statuses', ['service'], unique=False)
    op.create_index('payload_statuses_source_idx', 'payload_statuses', ['source'], unique=False)
    op.create_index('payload_statuses_status_idx', 'payload_statuses', ['status'], unique=False)
    op.create_index('payload_statuses_status_msg_idx', 'payload_statuses', ['status_msg'], unique=False)
    op.create_index('payload_statuses_date_idx', 'payload_statuses', ['date'], unique=False)
    op.create_index('payload_statuses_created_at_idx', 'payload_statuses', ['created_at'], unique=False)


def downgrade():
    op.drop_index('payload_statuses_id_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_request_id_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_service_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_source_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_status_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_status_msg_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_date_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_created_at_idx', table_name='payload_statuses')

    op.drop_table('payload_statuses')

    op.drop_index('payloads_request_id_idx', table_name='payloads')
    op.drop_index('payloads_account_idx', table_name='payloads')
    op.drop_index('payloads_inventory_id_idx', table_name='payloads')
    op.drop_index('payloads_system_id_idx', table_name='payloads')
    op.drop_index('payloads_created_at_idx', table_name='payloads')

    op.drop_table('payloads')

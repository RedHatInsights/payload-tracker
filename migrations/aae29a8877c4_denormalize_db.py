"""denormalize db

Revision ID: aae29a8877c4
Revises: 1f8a919555e1
Create Date: 2020-05-19 11:03:03.376233

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aae29a8877c4'
down_revision = '1f8a919555e1'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('payloads_id_idx', table_name='payloads')
    op.drop_index('payloads_date_idx', table_name='payloads')
    op.drop_index('payloads_service_idx', table_name='payloads')
    op.drop_index('payloads_source_idx', table_name='payloads')
    op.drop_index('payloads_status_idx', table_name='payloads')
    op.drop_index('payloads_status_msg_idx', table_name='payloads')

    op.drop_column('payloads', 'id')
    op.drop_column('payloads', 'service')
    op.drop_column('payloads', 'source')
    op.drop_column('payloads', 'status')
    op.drop_column('payloads', 'status_msg')
    op.drop_column('payloads', 'date')

    op.create_primary_key('payloads_request_id_pkey', 'payloads', ['request_id'])

    op.create_table(
        'payload_statuses',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('service', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('status_msg', sa.String(), nullable=True),
        sa.Column('date', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['request_id'], ['payloads.request_id'])
    )

    op.alter_column('payload_statuses', 'date', type_=sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"))
    op.alter_column('payload_statuses', 'created_at', type_=sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"))


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

    op.add_column('payloads', sa.Column('id', sa.Integer(), nullable=False, autoincrement=True))
    op.add_column('payloads', sa.Column('service', sa.String(), nullable=False))
    op.add_column('payloads', sa.Column('source', sa.String(), nullable=False))
    op.add_column('payloads', sa.Column('status', sa.String(), nullable=True))
    op.add_column('payloads', sa.Column('status_msg', sa.String(), nullable=True))
    op.add_column('payloads', sa.Column('date', sa.DateTime(), nullable=True))

    op.create_index('payloads_status_msg_idx', 'payloads', ['status_msg'], unique=False)
    op.create_index('payloads_status_idx', 'payloads', ['status'], unique=False)
    op.create_index('payloads_source_idx', 'payloads', ['source'], unique=False)
    op.create_index('payloads_service_idx', 'payloads', ['service'], unique=False)
    op.create_index('payloads_date_idx', 'payloads', ['date'], unique=False)
    op.create_index('payloads_id_idx', 'payloads', ['date'], unique=True)
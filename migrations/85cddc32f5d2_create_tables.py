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
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('account', sa.String(), nullable=True),
        sa.Column('inventory_id', sa.String(), nullable=True),
        sa.Column('system_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id')
    )

    op.create_index('payloads_id_idx', 'payloads', ['id'], unique=True)
    op.create_index('payloads_request_id_idx', 'payloads', ['request_id'], unique=True)
    op.create_index('payloads_account_idx', 'payloads', ['account'], unique=False)
    op.create_index('payloads_inventory_id_idx', 'payloads', ['inventory_id'], unique=False)
    op.create_index('payloads_system_id_idx', 'payloads', ['system_id'], unique=False)
    op.create_index('payloads_created_at_idx', 'payloads', ['created_at'], unique=False)

    services = op.create_table(
        'services',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_index('services_id_idx', 'services', ['id'], unique=True)
    op.create_index('services_name_idx', 'services', ['name'], unique=True)

    sources = op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_index('sources_id_idx', 'sources', ['id'], unique=True)
    op.create_index('sources_name_idx', 'sources', ['name'], unique=True)

    op.create_table(
        'payload_statuses',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('payload_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('status_msg', sa.String(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['payload_id'], ['payloads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id']),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'])
    )

    op.create_index('payload_statuses_id_idx', 'payload_statuses', ['id'], unique=True)
    op.create_index('payload_statuses_payload_id_idx', 'payload_statuses', ['payload_id'], unique=False)
    op.create_index('payload_statuses_service_id_idx', 'payload_statuses', ['service_id'], unique=False)
    op.create_index('payload_statuses_source_id_idx', 'payload_statuses', ['source_id'], unique=False)
    op.create_index('payload_statuses_status_idx', 'payload_statuses', ['status'], unique=False)
    op.create_index('payload_statuses_status_msg_idx', 'payload_statuses', ['status_msg'], unique=False)
    op.create_index('payload_statuses_date_idx', 'payload_statuses', ['date'], unique=False)
    op.create_index('payload_statuses_created_at_idx', 'payload_statuses', ['created_at'], unique=False)

    op.bulk_insert(services,
        [
            {'id': 1, 'name': 'advisor'},
            {'id': 2, 'name': 'ccx-data-pipeline'},
            {'id': 3, 'name': 'compliance'},
            {'id': 4, 'name': 'hsp-archiver'},
            {'id': 5, 'name': 'hsp-deleter'},
            {'id': 6, 'name': 'ingress'},
            {'id': 7, 'name': 'insights-advisor-service'},
            {'id': 8, 'name': 'insights-engine'},
            {'id': 9, 'name': 'insights-results-db-writer'},
            {'id': 10, 'name': 'inventory'},
            {'id': 11, 'name': 'inventory-mq-service'},
            {'id': 12, 'name': 'puptoo'},
            {'id': 13, 'name': 'vulnerability'}
        ]
    )

    op.bulk_insert(sources,
        [
            {'id': 1, 'name': 'compliance-consumer'},
            {'id': 2, 'name': 'compliance-sidekiq'},
            {'id': 3, 'name': 'insights-client'},
            {'id': 4, 'name': 'inventory'}
        ]
    )


def downgrade():
    op.drop_index('payload_statuses_id_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_payload_id_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_service_id_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_source_id_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_status_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_status_msg_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_date_idx', table_name='payload_statuses')
    op.drop_index('payload_statuses_created_at_idx', table_name='payload_statuses')

    op.drop_table('payload_statuses')

    op.drop_index('sources_id_idx', table_name='sources')
    op.drop_index('sources_name_idx', table_name='sources')

    op.drop_table('sources')

    op.drop_index('services_id_idx', table_name='services')
    op.drop_index('services_name_idx', table_name='services')

    op.drop_table('services')

    op.drop_index('payloads_request_id_idx', table_name='payloads')
    op.drop_index('payloads_account_idx', table_name='payloads')
    op.drop_index('payloads_inventory_id_idx', table_name='payloads')
    op.drop_index('payloads_system_id_idx', table_name='payloads')
    op.drop_index('payloads_created_at_idx', table_name='payloads')

    op.drop_table('payloads')

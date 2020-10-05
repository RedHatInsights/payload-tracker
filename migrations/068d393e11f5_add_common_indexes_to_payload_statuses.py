"""Add common indexes to payload_statuses

Revision ID: 068d393e11f5
Revises: 867aaf69aeba
Create Date: 2020-10-05 13:34:37.362503

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '068d393e11f5'
down_revision = 'e6fb7331772d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('payload_statuses_service_id_status_id_idx', 'payload_statuses', ['service_id', 'status_id'])
    op.create_index('payload_statuses_service_id_date_idx', 'payload_statuses', ['service_id', 'date'])
    op.create_index('payload_statuses_status_id_date_idx', 'payload_statuses', ['status_id', 'date'])
    op.create_index('payload_statuses_source_id_date_idx', 'payload_statuses', ['status_id', 'date'])
    op.create_index('payload_statuses_service_id_created_at_idx', 'payload_statuses', ['service_id', 'created_at'])
    op.create_index('payload_statuses_status_id_created_at_idx', 'payload_statuses', ['status_id', 'created_at'])
    op.create_index('payload_statuses_source_id_created_at_idx', 'payload_statuses', ['status_id', 'created_at'])


def downgrade():
    op.drop_index('payload_statuses_service_id_status_id_idx')
    op.drop_index('payload_statuses_service_id_date_idx')
    op.drop_index('payload_statuses_status_id_date_idx')
    op.drop_index('payload_statuses_source_id_date_idx')
    op.drop_index('payload_statuses_service_id_created_at_idx')
    op.drop_index('payload_statuses_status_id_created_at_idx')
    op.drop_index('payload_statuses_source_id_created_at_idx')

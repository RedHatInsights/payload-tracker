"""Convert payload IDs to BIGINT

Revision ID: 4cd848af7d8c
Revises: 068d393e11f5
Create Date: 2021-03-24 10:39:30.784421

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4cd848af7d8c'
down_revision = '068d393e11f5'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE payloads ALTER COLUMN id TYPE BIGINT;')
    op.execute('ALTER TABLE payload_statuses ALTER COLUMN id TYPE BIGINT;')
    op.execute('ALTER TABLE payload_statuses ALTER COLUMN payload_id TYPE BIGINT;')


def downgrade():
    op.execute('ALTER TABLE payloads ALTER COLUMN id TYPE INT;')
    op.execute('ALTER TABLE payload_statuses ALTER COLUMN id TYPE INT;')
    op.execute('ALTER TABLE payload_statuses ALTER COLUMN payload_id TYPE INT;')

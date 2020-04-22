"""Only require service, request_id, and status

Revision ID: ae8f0f156ca6
Revises: c730d238f517
Create Date: 2019-06-05 08:48:48.185581

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'ae8f0f156ca6'
down_revision = 'c730d238f517'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('payloads', 'source', nullable=True)
    op.alter_column('payloads', 'account', nullable=True)
    op.alter_column('payloads', 'status', nullable=False)


def downgrade():
    pass

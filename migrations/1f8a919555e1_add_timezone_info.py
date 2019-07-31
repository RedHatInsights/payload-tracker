"""Add timezone info

Revision ID: 1f8a919555e1
Revises: 4f6344b9f321
Create Date: 2019-07-31 14:16:56.880580

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1f8a919555e1'
down_revision = '4f6344b9f321'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('payloads', 'date', type_=sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"))
    op.alter_column('payloads', 'created_at', type_=sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"))


def downgrade():
    pass

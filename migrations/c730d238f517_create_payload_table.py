"""create payload table

Revision ID: c730d238f517
Revises: 
Create Date: 2019-04-24 12:02:55.233608

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c730d238f517'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('payloads',
                    sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
                    sa.Column('service', sa.String(), nullable=False),
                    sa.Column('source', sa.String(), nullable=False),
                    sa.Column('account', sa.String(), nullable=False),
                    sa.Column('payload_id', sa.String(), nullable=False),
                    sa.Column('inventory_id', sa.String(), nullable=True),
                    sa.Column('system_id', sa.String(), nullable=True),
                    sa.Column('status', sa.String(), nullable=True),
                    sa.Column('status_msg', sa.String(), nullable=True),
                    sa.Column('date', sa.DateTime(), nullable=True),
                    sa.Column('created_at', sa.DateTime(),
                                    server_default=sa.text('now()'), nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade():
    op.drop_table('payloads')

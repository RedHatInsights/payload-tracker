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


"""
{ 	'id': UUID
	‘service’: ‘The services name processing the payload’,
	‘payload_id’: ‘The ID of the payload’,
	‘inventory_id’: “The ID of the entity in term of the inventory’,
	‘system_id’: ‘The ID of the entity in terms of the actual system’,
	‘status’: ‘received|processing|success|failure’,
	‘status_msg’: ‘Information relating to the above status, should more verbiage be needed (in the event of an error)’,
	‘date’: ‘Timestamp for the message relating to the ‘status’ above’,
	'created_at': DB Timestamp
}
"""
def upgrade():
    op.create_table('payloads',
                    sa.Column('id', sa.String(), nullable=False),
                    sa.Column('service', sa.String(), nullable=False),
                    sa.Column('payload_id', sa.String(), nullable=False),
                    sa.Column('inventory_id', sa.String(), nullable=True),
                    sa.Column('system_id', sa.String(), nullable=True),
                    sa.Column('status', sa.String(), nullable=True),
                    sa.Column('status_msg', sa.String(), nullable=True),
                    sa.Column('date', sa.DateTime(), nullable=True)
                    sa.Column('created_at', sa.DateTime(),
                                    server_default=sa.text('now()'), nullable=True)
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade():
    op.drop_table('payloads')

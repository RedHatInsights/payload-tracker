"""update sequences

Revision ID: dee7867868f7
Revises: 85cddc32f5d2
Create Date: 2020-08-03 11:26:01.136424

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dee7867868f7'
down_revision = '85cddc32f5d2'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('SELECT setval(\'services_id_seq\',(SELECT GREATEST(MAX(id)+1,nextval(\'services_id_seq\'))-1 FROM services));')
    op.execute('SELECT setval(\'sources_id_seq\',(SELECT GREATEST(MAX(id)+1,nextval(\'sources_id_seq\'))-1 FROM sources));')


def downgrade():
    op.execute('ALTER SEQUENCE services_id_seq RESTART WITH 1;')
    op.execute('ALTER SEQUENCE sources_id_seq RESTART WITH 1;')

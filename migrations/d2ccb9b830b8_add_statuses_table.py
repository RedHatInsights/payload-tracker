"""add statuses table

Revision ID: d2ccb9b830b8
Revises: dee7867868f7
Create Date: 2020-08-06 11:03:39.509498

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2ccb9b830b8'
down_revision = 'dee7867868f7'
branch_labels = None
depends_on = None


def upgrade():
    statuses = op.create_table(
        'statuses',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_index('statuses_id_idx', 'services', ['id'], unique=True)
    op.create_index('statuses_name_idx', 'services', ['name'], unique=True)

    op.bulk_insert(statuses,
        [
            {'name': 'error'},
            {'name': 'failed'},
            {'name': 'processed'},
            {'name': 'processing'},
            {'name': 'processing_error'},
            {'name': 'processing_success'},
            {'name': 'recieved'},
            {'name': 'success'},
        ]
    )

    op.execute('''
        INSERT INTO statuses (name) (
            SELECT DISTINCT status
            FROM payload_statuses
            WHERE status NOT IN (SELECT name FROM statuses)
        );
    ''')

    op.execute('''
        UPDATE payload_statuses
        SET status = s.id
        FROM statuses AS s
        WHERE payload_statuses.status = s.name;
    ''')

    op.alter_column(
        'payload_statuses',
        'status',
        nullable=False,
        new_column_name='status_id',
        type_=sa.Integer(),
        postgresql_using='status::integer'
    )

    op.create_foreign_key(
        'payload_statuses_status_id_fkey',
        'payload_statuses', 'statuses',
        ['status_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():

    op.drop_constraint('payload_statuses_status_id_fkey', 'payload_statuses')

    op.alter_column(
        'payload_statuses',
        'status_id',
        nullable=False,
        new_column_name='status',
        type_=sa.String()
    )

    op.execute('''
        UPDATE payload_statuses
        SET status = s.name
        FROM statuses AS s
        WHERE payload_statuses.status = CAST(s.id AS VARCHAR);
    ''')

    op.drop_index('statuses_id_idx', table_name='statuses')
    op.drop_index('statuses_name_idx', table_name='statuses')

    op.drop_table('statuses')

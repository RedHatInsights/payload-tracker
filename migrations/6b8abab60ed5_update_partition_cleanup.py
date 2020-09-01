"""Update partition cleanup

Revision ID: 6b8abab60ed5
Revises: 6e5626d37603
Create Date: 2020-09-01 17:40:29.404664

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b8abab60ed5'
down_revision = '6e5626d37603'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
        CREATE OR REPLACE FUNCTION clean_partitions(RETENTION_DAYS int) RETURNS VOID LANGUAGE PLPGSQL AS $$
        DECLARE
            partition partitions.name%type;
            cutoff DATE := NOW() - ($1 || ' DAY')::INTERVAL;
        BEGIN
            FOR partition IN SELECT name FROM partitions LOOP
                IF (substring(partition, 11)::INTEGER <= CAST (
                    (EXTRACT(DAY FROM cutoff)
                    ) + (100 * EXTRACT(MONTH FROM cutoff)
                    ) + (10000 * EXTRACT(YEAR FROM cutoff)
                ) AS INTEGER)) THEN
                    EXECUTE FORMAT('DROP TABLE %s;', partition);
                    DELETE FROM partitions WHERE name = partition;
                END IF;
            END LOOP;
        END;
        $$;
    ''')


def downgrade():
    op.execute('DROP FUNCTION IF EXISTS clean_partitions();')

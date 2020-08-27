"""Add partition cleanup

Revision ID: 6e5626d37603
Revises: b1b88f3e5f55
Create Date: 2020-08-26 14:24:04.451213

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e5626d37603'
down_revision = 'b1b88f3e5f55'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
        CREATE OR REPLACE FUNCTION clean_partitions(RETENTION_DAYS int) RETURNS VOID LANGUAGE PLPGSQL AS $$ 
        DECLARE
            partition partitions.name%type;
        BEGIN
            FOR partition IN SELECT name FROM partitions LOOP
                IF (substring(partition, 11)::INTEGER < CAST(
                        (EXTRACT(DAY from NOW()
                    ) + (
                        100 * EXTRACT(MONTH from NOW())
                    ) + (10000 * EXTRACT(YEAR from NOW()))) AS INTEGER) - RETENTION_DAYS) THEN
                    EXECUTE FORMAT('DROP TABLE %s;', partition);
                    DELETE FROM partitions WHERE name = partition;
                END IF;
            END LOOP;
        END;
        $$;
    ''')


def downgrade():
    op.execute('DROP FUNCTION IF EXISTS clean_partitions();')

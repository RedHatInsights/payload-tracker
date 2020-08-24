"""Partition Statuses

Revision ID: b1b88f3e5f55
Revises: d2ccb9b830b8
Create Date: 2020-08-21 15:36:22.613053

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1b88f3e5f55'
down_revision = 'd2ccb9b830b8'
branch_labels = None
depends_on = None


def upgrade():
    # correct statuses indexes
    op.drop_index('statuses_id_idx', table_name='services')
    op.drop_index('statuses_name_idx', table_name='services')
    op.drop_constraint('payload_statuses_status_id_fkey', 'payload_statuses')
    op.create_foreign_key('payload_statuses_status_id_fkey', 'payload_statuses', 'statuses', ['status_id'], ['id'])
    op.create_index('statuses_id_idx', 'statuses', ['id'], unique=True)
    op.create_index('statuses_name_idx', 'statuses', ['name'], unique=True)

    # create new master table from which we will inherit and partition
    op.execute('CREATE TABLE partitioned_statuses (LIKE payload_statuses INCLUDING ALL);')
    op.create_foreign_key('partitioned_statuses_status_id_fkey', 'partitioned_statuses', 'statuses', ['status_id'], ['id'])
    op.create_foreign_key('partitioned_statuses_source_id_fkey', 'partitioned_statuses', 'sources', ['source_id'], ['id'])
    op.create_foreign_key('partitioned_statuses_service_id_fkey', 'partitioned_statuses', 'services', ['service_id'], ['id'])
    op.create_foreign_key('partitioned_statuses_payload_id_fkey', 'partitioned_statuses', 'payloads', ['payload_id'], ['id'], ondelete='CASCADE')

    op.create_table('partitions', sa.Column('name', sa.String(), nullable=False))
    op.create_index('partitions_name_idx', 'partitions', ['name'], unique=True)
    # define trigger logic -- i.e. create new table which inherits from partitioned_statuses
    op.execute('''
        CREATE OR REPLACE FUNCTION find_or_create_partition() RETURNS TRIGGER LANGUAGE PLPGSQL AS $$
        DECLARE
            part_date INTEGER := CAST((
                EXTRACT(DAY from NEW.date
            ) + (100 * EXTRACT(
                MONTH from NEW.date
            )) + (10000 * EXTRACT(
                YEAR from NEW.date))) AS INTEGER);
            partition VARCHAR := 'partition_' || part_date || '';
        BEGIN
            IF NOT EXISTS (SELECT name FROM partitions WHERE name = partition) THEN
                EXECUTE 'CREATE TABLE ' || partition || ' (LIKE partitioned_statuses INCLUDING ALL) INHERITS (partitioned_statuses);';
                EXECUTE 'ALTER TABLE ' || partition || ' ADD CONSTRAINT chk_date CHECK (CAST((
                        EXTRACT(DAY from date
                    ) + (100 * EXTRACT(
                        MONTH from date
                    )) + (10000 * EXTRACT(YEAR from date))) AS INTEGER) = ' || part_date || ');';
                EXECUTE FORMAT('ALTER TABLE %s ADD FOREIGN KEY (payload_id) REFERENCES payloads(id) ON DELETE CASCADE;', partition);
                EXECUTE FORMAT('ALTER TABLE %s ADD FOREIGN KEY (service_id) REFERENCES services(id);', partition);
                EXECUTE FORMAT('ALTER TABLE %s ADD FOREIGN KEY (source_id) REFERENCES sources(id);', partition);
                EXECUTE FORMAT('ALTER TABLE %s ADD FOREIGN KEY (status_id) REFERENCES statuses(id);', partition);
                INSERT INTO partitions VALUES (partition);
            END IF;
            EXECUTE FORMAT('INSERT INTO %s SELECT ($1).*;', partition) USING NEW;
            RETURN NULL;
        EXCEPTION
            WHEN duplicate_table THEN
                EXECUTE FORMAT('INSERT INTO %s SELECT ($1).*;', partition) USING NEW;
                RETURN NULL;
        END;
        $$
    ''')

    # define trigger
    op.execute('''
        CREATE TRIGGER partition_table
        BEFORE INSERT on partitioned_statuses
        FOR EACH ROW
        EXECUTE PROCEDURE find_or_create_partition();
    ''')

    op.execute('''
        CREATE OR REPLACE FUNCTION update_partition() RETURNS TRIGGER LANGUAGE PLPGSQL AS $$
        BEGIN
            INSERT INTO partitioned_statuses VALUES(NEW.*);
            RETURN NEW;
        END;
        $$
    ''')

    op.execute('''
        CREATE TRIGGER update_partitions
        BEFORE INSERT on payload_statuses
        FOR EACH ROW
        EXECUTE PROCEDURE update_partition();
    ''')


def downgrade():
    op.execute('DROP TRIGGER update_partitions ON payload_statuses CASCADE;')
    op.execute('DROP TABLE partitioned_statuses CASCADE;')
    op.drop_table('partitions')

    op.drop_index('statuses_id_idx', table_name='statuses')
    op.drop_index('statuses_name_idx', table_name='statuses')
    op.drop_constraint('payload_statuses_status_id_fkey', 'payload_statuses')
    op.create_foreign_key('payload_statuses_status_id_fkey', 'payload_statuses', 'statuses', ['status_id'], ['id'], ondelete='CASCADE')
    op.create_index('statuses_id_idx', 'services', ['id'], unique=True)
    op.create_index('statuses_name_idx', 'services', ['name'], unique=True)

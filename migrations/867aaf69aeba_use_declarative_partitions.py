"""Use declarative partitions

Revision ID: 867aaf69aeba
Revises: 6b8abab60ed5
Create Date: 2020-09-15 09:39:50.813263

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '867aaf69aeba'
down_revision = '6b8abab60ed5'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('partitions')
    op.drop_table('partitioned_statuses')

    op.execute('CREATE TABLE partitioned_statuses (LIKE payload_statuses INCLUDING DEFAULTS) PARTITION BY RANGE (date);')
    op.execute('ALTER TABLE partitioned_statuses ALTER COLUMN id DROP DEFAULT;')
    op.execute('CREATE SEQUENCE partitioned_statuses_id_seq INCREMENT 1 OWNED BY partitioned_statuses.id;')
    op.execute('ALTER TABLE partitioned_statuses ALTER COLUMN id SET DEFAULT nextval(\'partitioned_statuses_id_seq\'::regclass);')
    op.create_primary_key('partitioned_statuses_pk', 'partitioned_statuses', ['id', 'date'])
    op.create_foreign_key('partitioned_statuses_status_id_fkey', 'partitioned_statuses', 'statuses', ['status_id'], ['id'])
    op.create_foreign_key('partitioned_statuses_source_id_fkey', 'partitioned_statuses', 'sources', ['source_id'], ['id'])
    op.create_foreign_key('partitioned_statuses_service_id_fkey', 'partitioned_statuses', 'services', ['service_id'], ['id'])
    op.create_foreign_key('partitioned_statuses_payload_id_fkey', 'partitioned_statuses', 'payloads', ['payload_id'], ['id'], ondelete='CASCADE')

    op.execute('DROP FUNCTION IF EXISTS find_or_create_partition() CASCADE;')
    op.execute('DROP FUNCTION IF EXISTS clean_partitions(RETENTION_DAYS int) CASCADE;')

    op.execute('''
        CREATE OR REPLACE FUNCTION update_partition() RETURNS TRIGGER LANGUAGE PLPGSQL AS $$
        BEGIN
            INSERT INTO partitioned_statuses (
                payload_id, service_id, source_id, status_id, status_msg, date, created_at
            ) VALUES (
                NEW.payload_id, NEW.service_id, NEW.source_id, NEW.status_id, NEW.status_msg, NEW.date, NEW.created_at
            );
            RETURN NEW;
        END;
        $$
    ''')

    op.execute('''
        CREATE OR REPLACE FUNCTION get_date_string(VALUE TIMESTAMPTZ) RETURNS TEXT LANGUAGE PLPGSQL AS $$
            BEGIN
                RETURN CAST((
                    EXTRACT(DAY from VALUE
                ) + (100 * EXTRACT(
                    MONTH from VALUE
                )) + (10000 * EXTRACT(
                    YEAR from VALUE))) AS TEXT);
            END
        $$;
    ''')

    op.execute('''
        CREATE OR REPLACE FUNCTION create_partition(START TIMESTAMPTZ, STOP TIMESTAMPTZ) RETURNS VOID LANGUAGE PLPGSQL AS $$
            DECLARE
                start TEXT := get_date_string(START);
                stop TEXT := get_date_string(STOP);
                partition VARCHAR := FORMAT('partition_%s_%s', start, stop);
            BEGIN
                EXECUTE 'CREATE TABLE IF NOT EXISTS ' || partition || ' PARTITION OF partitioned_statuses FOR VALUES FROM (' || quote_literal(START) || ') TO (' || quote_literal(STOP) || ');';
                EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS ' || partition || '_id_idx ON ' || partition || ' USING btree(id);';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ' || partition || '_payload_id_idx ON ' || partition || ' USING btree(payload_id);';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ' || partition || '_service_id_idx ON ' || partition || ' USING btree(service_id);';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ' || partition || '_source_id_idx ON ' || partition || ' USING btree(source_id);';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ' || partition || '_status_id_idx ON ' || partition || ' USING btree(status_id);';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ' || partition || '_date_idx ON ' || partition || ' USING btree(date);';
                EXECUTE 'CREATE INDEX IF NOT EXISTS ' || partition || '_created_at_idx ON ' || partition || ' USING btree(created_at);';
            END;
        $$;
    ''')

    op.execute('''
        CREATE OR REPLACE FUNCTION drop_partition(START TIMESTAMPTZ, STOP TIMESTAMPTZ) RETURNS VOID LANGUAGE PLPGSQL AS $$
            DECLARE
                start TEXT := get_date_string(START);
                stop TEXT := get_date_string(STOP);
                partition VARCHAR := FORMAT('partition_%s_%s', start, stop);
            BEGIN
                EXECUTE 'DROP TABLE IF EXISTS ' || partition || ';';
            END;
        $$;
    ''')

    op.execute('SELECT create_partition(NOW()::DATE, NOW()::DATE + INTERVAL \'1 DAY\');')


def downgrade():
    op.drop_table('partitioned_statuses')
    op.execute('DROP FUNCTION IF EXISTS create_partition(START TIMESTAMPTZ, STOP TIMESTAMPTZ);')
    op.execute('DROP FUNCTION IF EXISTS drop_partition(START TIMESTAMPTZ, STOP TIMESTAMPTZ);')
    op.execute('DROP FUNCTION IF EXISTS get_date_string(VALUE TIMESTAMPTZ);')

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

    # define cleanup
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

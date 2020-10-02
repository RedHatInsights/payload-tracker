"""Substitute partitions for payload_statuses

Revision ID: e6fb7331772d
Revises: 867aaf69aeba
Create Date: 2020-10-01 11:02:52.302126

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6fb7331772d'
down_revision = '867aaf69aeba'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('DROP FUNCTION IF EXISTS update_partition() CASCADE;')
    op.execute('DROP FUNCTION IF EXISTS create_partition(START TIMESTAMPTZ, STOP TIMESTAMPTZ);')
    op.execute('DROP TABLE payload_statuses CASCADE;')
    op.execute('ALTER TABLE partitioned_statuses RENAME TO payload_statuses;')

    op.execute('ALTER TABLE payload_statuses RENAME CONSTRAINT partitioned_statuses_pk TO payload_statuses_pkey;')
    op.execute('ALTER TABLE payload_statuses RENAME CONSTRAINT partitioned_statuses_payload_id_fkey TO payload_statuses_payload_id_fkey;')
    op.execute('ALTER TABLE payload_statuses RENAME CONSTRAINT partitioned_statuses_service_id_fkey TO payload_statuses_service_id_fkey;')
    op.execute('ALTER TABLE payload_statuses RENAME CONSTRAINT partitioned_statuses_source_id_fkey TO payload_statuses_source_id_fkey;')
    op.execute('ALTER TABLE payload_statuses RENAME CONSTRAINT partitioned_statuses_status_id_fkey TO payload_statuses_status_id_fkey;')
    op.execute('ALTER SEQUENCE partitioned_statuses_id_seq RENAME TO payload_statuses_id_seq;')

    op.execute('''
        CREATE OR REPLACE FUNCTION create_partition(START TIMESTAMPTZ, STOP TIMESTAMPTZ) RETURNS VOID LANGUAGE PLPGSQL AS $$
            DECLARE
                start TEXT := get_date_string(START);
                stop TEXT := get_date_string(STOP);
                partition VARCHAR := FORMAT('partition_%s_%s', start, stop);
            BEGIN
                EXECUTE 'CREATE TABLE IF NOT EXISTS ' || partition || ' PARTITION OF payload_statuses FOR VALUES FROM (' || quote_literal(START) || ') TO (' || quote_literal(STOP) || ');';
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


def downgrade():
    op.execute('ALTER TABLE payload_statuses RENAME TO partitioned_statuses;')
    op.execute('ALTER TABLE partitioned_statuses RENAME CONSTRAINT payload_statuses_pkey TO partitioned_statuses_pk;')
    op.execute('ALTER TABLE partitioned_statuses RENAME CONSTRAINT payload_statuses_payload_id_fkey TO partitioned_statuses_payload_id_fkey;')
    op.execute('ALTER TABLE partitioned_statuses RENAME CONSTRAINT payload_statuses_service_id_fkey TO partitioned_statuses_service_id_fkey;')
    op.execute('ALTER TABLE partitioned_statuses RENAME CONSTRAINT payload_statuses_source_id_fkey TO partitioned_statuses_source_id_fkey;')
    op.execute('ALTER TABLE partitioned_statuses RENAME CONSTRAINT payload_statuses_status_id_fkey TO partitioned_statuses_status_id_fkey;')
    op.execute('ALTER SEQUENCE payload_statuses_id_seq RENAME TO partitioned_statuses_id_seq;')
    op.create_table(
        'payload_statuses',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('payload_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('status_id', sa.Integer(), nullable=False),
        sa.Column('status_msg', sa.String(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('utc'::text, now())"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['payload_id'], ['payloads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id']),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id']),
        sa.ForeignKeyConstraint(['status_id'], ['sources.id'])
    )

    op.create_index('payload_statuses_id_idx', 'payload_statuses', ['id'], unique=True)
    op.create_index('payload_statuses_payload_id_idx', 'payload_statuses', ['payload_id'], unique=False)
    op.create_index('payload_statuses_service_id_idx', 'payload_statuses', ['service_id'], unique=False)
    op.create_index('payload_statuses_source_id_idx', 'payload_statuses', ['source_id'], unique=False)
    op.create_index('payload_statuses_status_id_idx', 'payload_statuses', ['status_id'], unique=False)
    op.create_index('payload_statuses_status_msg_idx', 'payload_statuses', ['status_msg'], unique=False)
    op.create_index('payload_statuses_date_idx', 'payload_statuses', ['date'], unique=False)
    op.create_index('payload_statuses_created_at_idx', 'payload_statuses', ['created_at'], unique=False)

    op.execute('DROP FUNCTION IF EXISTS create_partition(START TIMESTAMPTZ, STOP TIMESTAMPTZ);')
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
        CREATE OR REPLACE FUNCTION update_partition() RETURNS TRIGGER LANGUAGE PLPGSQL AS $$
        BEGIN
            INSERT INTO partitioned_statuses (
                payload_id, service_id, source_id, status_id, status_msg, date, created_at
            ) VALUES (
                NEW.payload_id, NEW.service_id, NEW.source_id, NEW.status_id, NEW.status_msg, NEW.date, NEW.created_at
            );
            RETURN NEW;
        EXCEPTION
            WHEN check_violation THEN
                PERFORM create_partition(NEW.date::DATE, NEW.date::DATE + INTERVAL \'1 DAY\');
                INSERT INTO partitioned_statuses (
                    payload_id, service_id, source_id, status_id, status_msg, date, created_at
                ) VALUES (
                    NEW.payload_id, NEW.service_id, NEW.source_id, NEW.status_id, NEW.status_msg, NEW.date, NEW.created_at
                );
                RETURN NEW;
        END;
        $$;
    ''')

    op.execute('''
        CREATE TRIGGER update_partitions
        BEFORE INSERT on payload_statuses
        FOR EACH ROW
        EXECUTE PROCEDURE update_partition();
    ''')

#!/bin/bash
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "DELETE FROM payload_statuses WHERE created_at < (NOW() - interval '7 days');"
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "DELETE FROM payloads WHERE created_at < (NOW() - interval '7 days');"
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "VACUUM ANALYZE payload_statuses;"
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "VACUUM ANALYZE payloads;"

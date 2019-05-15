import os

db_user = os.environ.get('DB_USER', 'payloadtracker')
db_password = os.environ.get('DB_PASSWORD', 'payloadtracker')
db_host = os.environ.get('DB_HOST', 'localhost')
db_port = os.environ.get('DB_PORT', '5432')
db_name = os.environ.get('DB_NAME', 'payloadtracker')

import os

ENVIRONMENT = os.environ.get('TRACKER_ENV', 'dev')
DEBUG = ENVIRONMENT in ('dev', 'ci', 'qa')

# Logging settings
DEV_LOG_LEVEL = 'INFO'
DEV_LOG_MSG_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] " \
            "[%(thread)d  %(threadName)s] [%(process)d] %(message)s"
DEV_LOG_DATE_FORMAT = "%H:%M:%S"
APP_NAME = "payload-tracker-service"

# Database settings
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
import os

ENVIRONMENT = os.environ.get('TRACKER_ENV', 'dev')
DEBUG = ENVIRONMENT in ('dev', 'ci', 'qa')

# Logging settings
DEV_LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
DEV_LOG_MSG_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] " \
            "[%(thread)d  %(threadName)s] [%(process)d] %(message)s"
DEV_LOG_DATE_FORMAT = "%H:%M:%S"
APP_NAME = "payload-tracker-service"

# watchtower logging settings
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION_NAME = os.environ.get('AWS_REGION_NAME')
CW_LOG_GROUP = os.environ.get('CW_LOG_GROUP', 'platform-dev')
CW_LOG_STREAM_MANUAL = os.environ.get('CW_LOG_STREAM')
CW_CREATE_LOG_GROUP = os.environ.get('CW_CREATE_LOG_GROUP', "").lower() == "true"
CW_LOG_STREAM_AUTO = os.environ.get('HOSTNAME', 'payload-tracker-dev')

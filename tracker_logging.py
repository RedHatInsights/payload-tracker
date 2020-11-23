import logging
import json
import os
import sys
import traceback
import asyncio
from logstash_formatter import LogstashFormatterV1
import settings
import watchtower
from boto3 import Session

from utils import get_running_tasks


class TrackerStreamHandler(logging.StreamHandler):

    def __init__(self):
        super().__init__(sys.stdout)
        self.setFormatter(
            OurFormatter(fmt=json.dumps({"extra": {
                "component": settings.APP_NAME, "tasks": None
            }}))
        )


class OurFormatter(LogstashFormatterV1):

    def format(self, record):
        exc = getattr(record, "exc_info")
        if exc:
            setattr(record, "exception", "".join(traceback.format_exception(*exc)))
            setattr(record, "exc_info", None)

        setattr(record, "tasks", get_running_tasks())

        return super(OurFormatter, self).format(record)


class DevLogRecord(logging.LogRecord):

    def __init__(self, record, tasks):
        self.__class__ = type(record.__class__.__name__,
                             (self.__class__, record.__class__),
                             {})
        self.__dict__ = record.__dict__
        self.tasks = tasks


class DevStreamHandler(logging.StreamHandler):

    def __init__(self):
        super().__init__(sys.stdout)

    def emit(self, record):
        record = DevLogRecord(record, f'{get_running_tasks()} running task(s)')
        super(DevStreamHandler, self).emit(record)


class CWStreamHandler(watchtower.CloudWatchLogHandler):

    def __init__(self):
        CW_SESSION = Session(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                             region_name=settings.AWS_REGION_NAME)

        cw_log_stream_manual = settings.CW_LOG_STREAM_MANUAL
        cw_log_stream_auto = settings.CW_LOG_STREAM_AUTO
        cw_log_stream = cw_log_stream_manual if cw_log_stream_manual else cw_log_stream_auto
        create_log_group = settings.CW_CREATE_LOG_GROUP
        super().__init__(boto3_session=CW_SESSION,
                         log_group=settings.CW_LOG_GROUP,
                         stream_name=cw_log_stream,
                         create_log_group=create_log_group)

    def emit(self, message):
        if message.levelname.upper() == 'ERROR':
            setattr(message, 'tasks', get_running_tasks())
            return super().emit(message)


def initialize_logging():
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

    # setup root handlers
    if settings.ENVIRONMENT != "dev":
        if not logging.root.hasHandlers():
            logging.root.setLevel(LOG_LEVEL)
            logging.root.addHandler(TrackerStreamHandler())
            if (settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY):
                logging.root.addHandler(CWStreamHandler())
    else:
        if (settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY):
            handlers=[DevStreamHandler(), CWStreamHandler()]
        else:
            handlers=[DevStreamHandler()]
        logging.basicConfig(level=logging.getLevelName(settings.DEV_LOG_LEVEL),
                            format=settings.DEV_LOG_MSG_FORMAT,
                            datefmt=settings.DEV_LOG_DATE_FORMAT,
                            handlers=handlers)

    # overwrite RootLogger and return
    return logging.getLogger(settings.APP_NAME)

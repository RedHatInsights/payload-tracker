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

        setattr(record, "tasks", len([task for task in asyncio.Task.all_tasks() if not task.done()]))

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
        tasks = len([task for task in asyncio.Task.all_tasks() if not task.done()])
        record = DevLogRecord(record, f'{tasks} running task(s)')
        super(DevStreamHandler, self).emit(record)


class LoggerWrapper(logging.Logger):

    def __init__(self, baseLogger):
        self.__class__ = type(baseLogger.__class__.__name__,
                             (self.__class__, baseLogger.__class__),
                             {})
        self.__dict__ = baseLogger.__dict__
        self.cwHandler = self.init_cw()

    def init_cw(self):
        """ initialize watchtower logging handler """
        cw_handler = None
        if (settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY):
            try:
                CW_SESSION = Session(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                    region_name=settings.AWS_REGION_NAME)

                cw_log_stream_manual = settings.CW_LOG_STREAM_MANUAL
                cw_log_stream_auto = settings.CW_LOG_STREAM_AUTO
                cw_log_stream = cw_log_stream_manual if cw_log_stream_manual else cw_log_stream_auto
                create_log_group = settings.CW_CREATE_LOG_GROUP
                self.debug("Creating cloud watch log handler...")
                cw_handler = watchtower.CloudWatchLogHandler(boto3_session=CW_SESSION,
                                                            log_group=settings.CW_LOG_GROUP,
                                                            stream_name=cw_log_stream,
                                                            create_log_group=create_log_group)
                cw_handler.setFormatter(
                    OurFormatter(fmt=json.dumps({"extra": {"component": settings.APP_NAME}})))
                self.debug("Cloud watch handler configured")
            except:
                self.exception("Cloud watch logging setup encountered an Exception")
        return cw_handler

    def error(self, msg, *args, **kwargs):
        """ override the logging.Logger error method to provide watchtower logging """
        if self.cwHandler:
            handlerConfigured = False
            try:
                self.addHandler(self.cwHandler)
                handlerConfigured = True
                super(LoggerWrapper, self).error(msg, *args, **kwargs)
            except Exception as err:
                self.exception(err)
            finally:
                if handlerConfigured:
                    self.removeHandler(self.cwHandler)
        else:
            super(LoggerWrapper, self).error(msg, *args, **kwargs)


def initialize_logging():
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

    # setup root handlers
    if settings.ENVIRONMENT != "dev":
        if not logging.root.hasHandlers():
            logging.root.setLevel(LOG_LEVEL)
            logging.root.addHandler(TrackerStreamHandler())
    else:
        logging.basicConfig(level=logging.getLevelName(settings.DEV_LOG_LEVEL),
                            format=settings.DEV_LOG_MSG_FORMAT,
                            datefmt=settings.DEV_LOG_DATE_FORMAT,
                            handlers=[DevStreamHandler()])

    # overwrite RootLogger and return
    logging.root = LoggerWrapper(logging.getLogger(settings.APP_NAME))
    logging.root.manager.loggerDict[settings.APP_NAME] = logging.root
    return logging.getLogger(settings.APP_NAME)

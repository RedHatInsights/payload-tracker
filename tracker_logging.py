import logging
import json
import os
import sys
import traceback
from logstash_formatter import LogstashFormatterV1
import settings


class TrackerStreamHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__(sys.stdout)
        self.setFormatter(
            OurFormatter(fmt=json.dumps({"extra": {"component": settings.APP_NAME}}))
        )


class OurFormatter(LogstashFormatterV1):

    def format(self, record):
        exc = getattr(record, "exc_info")
        if exc:
            setattr(record, "exception", "".join(traceback.format_exception(*exc)))
            setattr(record, "exc_info", None)

        return super(OurFormatter, self).format(record)


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
                        datefmt=settings.DEV_LOG_DATE_FORMAT)

    # return app logger
    logger = logging.getLogger(settings.APP_NAME)
    return logger

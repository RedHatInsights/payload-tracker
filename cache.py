import logging
import settings
import datetime
import dateutil
import os
import json
import traceback
import hashlib
from redis import Redis

logger = logging.getLogger(settings.APP_NAME)

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', 'payloadtracker')

redis_client = Redis(host=REDIS_HOST, db=0, password=REDIS_PASSWORD)


def _convert_datetime(value):
    return value.isoformat() if isinstance(value, (datetime.date, datetime.datetime)) else value


def _revert_datetime(value):
    def check_if_datetime(data):
        datetime_obj = None
        try:
            datetime_obj = dateutil.parser.parse(data)
        except:
            pass
        return datetime_obj

    for item in value:
        for k, v in item.items():
            datetime_obj = check_if_datetime(v)
            if datetime_obj:
                item[k] = datetime_obj
    return value


def get_value(key):
    hash_key = hashlib.md5(str.encode(key)).hexdigest()
    value = redis_client.get(hash_key)
    return _revert_datetime(json.loads(value)) if value else None


def set_value(key, value):
    hash_key = hashlib.md5(str.encode(key)).hexdigest()
    cached_value = get_value(key)
    if cached_value:
        try:
            to_add = cached_value + value if type(value) is list else cached_value + [value]
            new_value = json.dumps(to_add, default=_convert_datetime)
        except:
            logger.error(traceback.format_exc())
        redis_client.set(hash_key, new_value)
    else:
        try:
            if type(value) is list:
                value = json.dumps(value, default=_convert_datetime)
            else:
                value = json.dumps([value], default=_convert_datetime)
        except:
            logger.error(traceback.format_exc())
        redis_client.set(hash_key, value)

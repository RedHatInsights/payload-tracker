import logging
import settings
import os
import json
import traceback
import hashlib
from redis import Redis

logger = logging.getLogger(settings.APP_NAME)

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', 'payloadtracker')

redis_client = Redis(host=REDIS_HOST, db=0, password=REDIS_PASSWORD)


def get_value(key):
    hash_key = hashlib.md5(str.encode(key)).hexdigest()
    value = redis_client.get(hash_key)
    return json.loads(value) if value else None


def set_value(key, value):
    hash_key = hashlib.md5(str.encode(key)).hexdigest()
    cached_value = get_value(key)
    if cached_value:
        try:
            to_add = cached_value + value if type(value) is list else cached_value + [value]
            new_value = json.dumps(to_add)
        except:
            logger.error(traceback.format_exc())
        redis_client.set(hash_key, new_value)
    else:
        try:
            value = json.dumps(value)
        except:
            logger.error(traceback.format_exc())
        redis_client.set(hash_key, value)

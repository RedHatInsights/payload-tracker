import os
import logging
import settings
import traceback
from redis import Redis

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', 'payloadtracker')
SECONDS_TO_LIVE = int(os.environ.get('SECONDS_TO_LIVE', 100))
logger = logging.getLogger(settings.APP_NAME)


class Client(Redis):

    def __init__(self, **kwargs):
        super(Client, self).__init__(**kwargs)

    def hgetall(self, name, key_is_int=False):
        # Overriding this method to provide decoding
        return {k.decode() if not key_is_int else int(
            k.decode()): v.decode() for k, v in super().hgetall(name).items()}

    def lget(self, key):
        try:
            return [item.decode() for item in self.lrange(
                key, 0, self.llen(key) - 1)] # lrange is inclusive
        except:
            logger.error(traceback.format_exc())


redis_client = Client(host=REDIS_HOST, db=0, port=REDIS_PORT, password=REDIS_PASSWORD)

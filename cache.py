import os
import logging
import settings
import traceback
import time
from redis import Redis
from prometheus_client import Summary

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
SECONDS_TO_LIVE = int(os.environ.get('SECONDS_TO_LIVE', 100))
logger = logging.getLogger(settings.APP_NAME)
REDIS_LATENCY = Summary('payload_tracker_redis_latency',
                        'Tracks latency in requests to Redis',
                        ['request_type'])


class Client(Redis):

    def __init__(self, **kwargs):
        super(Client, self).__init__(**kwargs)

    def execute_command(self, *args, **options):
        command_type = args[0]
        start = time.time()
        res = super(Client, self).execute_command(*args, **options)
        duration = time.time() - start
        if command_type in ['HGETALL', 'LLEN', 'LRANGE']:
            REDIS_LATENCY.labels(request_type='read').observe(duration)
        elif command_type in ['HSET', 'LPUSH', 'EXPIRE']:
            REDIS_LATENCY.labels(request_type='write').observe(duration)
        return res

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


redis_client = Client(host=REDIS_HOST, db=0, port=REDIS_PORT)

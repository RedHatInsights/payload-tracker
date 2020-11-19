import os
import time
import attr
import logging
import settings
import traceback
from redis import Redis
from dateutil.parser import parse
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


# Define RequestClient postprocessing function for request_client.get
def get_msgs_by_service(data):
    """ postprocessing function for request_client.get """
    msgs_by_service = {}
    for values in data.values():
        entry = values.copy() # ensure we have "source" defined
        if 'source' not in values:
            entry['source'] = None
        service = entry['service']
        del entry['service']
        if service in msgs_by_service.keys():
            msgs_by_service[service].append(entry)
        else:
            msgs_by_service[service] = [entry]
    return msgs_by_service


def get_unique_values(data):
    """ postprocessing function for request_client.get """
    unique_values = {}
    for entry in data.values():
        for k in entry.keys():
            # check for existing sanitized_payload values in the cache
            if k in ['id', 'inventory_id', 'system_id', 'account'] and k not in unique_values:
                unique_values[k] = entry[k]
    return None if not len(unique_values) > 0 else unique_values


# Define wrapper for redis_client which handles payloads in and out of the cache
@attr.s
class RequestClient():

    POSTPROCESS_FUNCTIONS = {
        'BY_SERVICE': get_msgs_by_service,
        'UNIQUE_VALUES': get_unique_values
    }

    client = attr.ib()

    def get(self, request_id, postprocess = None):
        def _decode(res):
            for k, v in res.items():
                if 'date' == k:
                    res['date'] = parse(res['date'])
                elif v == '':
                    res[k] = None
            return res

        try:
            dates = self.client.lget(request_id) # "date" is the key-value store key
            data = {date: _decode(self.client.hgetall(request_id + date)) for date in dates}
        except:
            logger.error(traceback.format_exc())
        else:
            if postprocess and postprocess in self.POSTPROCESS_FUNCTIONS:
                return self.POSTPROCESS_FUNCTIONS[postprocess](data)
            else:
                return data

    def is_unique(self, request_id, msg):
        data = self.get(request_id)
        for entry in data.values():
            unique = set()
            for k, v in entry.items():
                if k in msg.keys():
                    unique.add(v == msg[k])
            if False not in unique:
                return False
        return True

    def set(self, msg):
        request_id = msg['request_id']
        del msg['request_id']
        if self.is_unique(request_id, msg):
            data = {k: str(v) if v else '' for k, v in msg.items()}
            try:
                return self.client.pipeline().hset(
                    request_id + data['date'], mapping=data
                ).expire(
                    request_id + data['date'], SECONDS_TO_LIVE
                ).lpush(
                    request_id, data['date']
                ).expire(
                    request_id, SECONDS_TO_LIVE
                ).execute()
            except:
                logger.error(traceback.format_exc())
        else:
            return False

request_client = RequestClient(redis_client)

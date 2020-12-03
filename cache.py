import os
import time
import attr
import secrets
import logging
import asyncio
import settings
import traceback
from dateutil.parser import parse
from aioredis import Redis, create_connection
from prometheus_client import Summary

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
SECONDS_TO_LIVE = int(os.environ.get('SECONDS_TO_LIVE', 100))
logger = logging.getLogger(settings.APP_NAME)
REDIS_LATENCY = Summary('payload_tracker_redis_latency',
                        'Tracks latency in requests to Redis',
                        ['request_type'])


class Client(Redis):

    def __init__(self, pool_or_conn=None):
        if pool_or_conn:
            super(Client, self).__init__(pool_or_conn)
        else:
            pass

    def set_connection(self, pool_or_conn):
        super(Client, self).__init__(pool_or_conn)

    def check_connection(self):
        return self._pool_or_conn is not None

    def execute(self, command, *args, **kwargs):
        if self.check_connection():
            start = time.time()
            res = super(Client, self).execute(command, *args, **kwargs)
            duration = time.time() - start
            if command.decode() in ['HGETALL', 'LLEN', 'LRANGE']:
                REDIS_LATENCY.labels(request_type='read').observe(duration)
            elif command.decode() in ['HSET', 'LPUSH', 'EXPIRE']:
                REDIS_LATENCY.labels(request_type='write').observe(duration)
            return res
        else:
            logger.error('No connection found')

    async def hgetall(self, name, key_is_int=False):
        # Overriding this method to provide decoding
        res = await super(Client, self).hgetall(name)
        return {k.decode() if not key_is_int else int(
            k.decode()): v.decode() for k, v in res.items()}

    async def lget(self, key):
        try:
            llen = await self.llen(key)
            lrange = await self.lrange(key, 0, llen - 1) # lrange is inclusive
            return [item.decode() for item in lrange]
        except:
            logger.error(traceback.format_exc())


redis_client = Client()


async def init_redis():
    connection = await create_connection((REDIS_HOST, REDIS_PORT))
    redis_client.set_connection(connection)


# Define RequestClient postprocessing function for request_client.get
def get_msgs_by_service(data):
    """ postprocessing function for request_client.get """
    msgs_by_service = {}
    try:
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
    except Exception as err:
        raise err
    return None if not len(msgs_by_service) > 0 else msgs_by_service


def get_unique_values(data):
    """ postprocessing function for request_client.get """
    unique_values = {}
    try:
        for entry in data.values():
            for k in entry.keys():
                # check for existing sanitized_payload values in the cache
                if k in ['id', 'inventory_id', 'system_id', 'account'] and k not in unique_values:
                    unique_values[k] = entry[k]
    except Exception as err:
        raise err
    return None if not len(unique_values) > 0 else unique_values


@attr.s
class RequestClient:

    POSTPROCESS_FUNCTIONS = {
        'BY_SERVICE': get_msgs_by_service,
        'UNIQUE_VALUES': get_unique_values
    }

    client = attr.ib()

    async def get(self, request_id, postprocess=None):
        def _decode(res):
            for k, v in res.items():
                if 'date' == k:
                    res['date'] = parse(res['date'])
                elif v == '':
                    res[k] = None
            return res

        try:
            tokens = await self.client.lget(request_id)
            data = {}
            for token in tokens:
                entry = _decode(await self.client.hgetall(request_id + token))
                data[entry['date']] = entry
        except:
            logger.error(traceback.format_exc())
        else:
            if postprocess and postprocess in self.POSTPROCESS_FUNCTIONS:
                try:
                    res = self.POSTPROCESS_FUNCTIONS[postprocess](data)
                except:
                    logger.error(f'Postprocessing of {request_id} data failed with error: {traceback.format_exc()}')
                else:
                    return res
            else:
                return data

    async def is_unique(self, request_id, msg):
        data = await self.get(request_id)
        for entry in data.values():
            unique = set()
            for k, v in entry.items():
                if k in msg.keys():
                    unique.add(v == msg[k])
            if False not in unique:
                return False
        return True

    async def set(self, msg):
        request_id = msg['request_id']
        del msg['request_id']
        is_unique = await self.is_unique(request_id, msg)
        if is_unique:
            data = {k: str(v) if v else '' for k, v in msg.items()}
            try:
                hextoken = secrets.token_hex(nbytes=16)
                pipe = self.client.pipeline()
                fut1 = pipe.hmset_dict(request_id + hextoken, data)
                fut2 = pipe.expire(request_id + hextoken, SECONDS_TO_LIVE)
                fut3 = pipe.lpush(request_id, hextoken)
                fut4 = pipe.expire(request_id, SECONDS_TO_LIVE)
                await pipe.execute()
                res = await asyncio.gather(fut1, fut2, fut3, fut4)
            except:
                logger.error(traceback.format_exc())
            else:
                return res
        else:
            return False


request_client = RequestClient(redis_client)
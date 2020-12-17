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

from bakery import exec_baked

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
logger = logging.getLogger(settings.APP_NAME)
REDIS_LATENCY = Summary('payload_tracker_redis_latency',
                        'Tracks latency in requests to Redis',
                        ['request_type'])


class Client(Redis):

    def __init__(self, pool_or_conn=None):
        if pool_or_conn:
            super(Client, self).__init__(pool_or_conn)
        self._loop = asyncio.get_event_loop()

    def set_connection(self, pool_or_conn):
        super(Client, self).__init__(pool_or_conn)

    def check_connection(self):
        return self._pool_or_conn is not None

    async def _eval_latency(self, command, fut):
        start = time.time()
        await asyncio.gather(fut)
        duration = time.time() - start
        if command.decode() in ['HGETALL', 'LLEN', 'LRANGE']:
            REDIS_LATENCY.labels(request_type='read').observe(duration)
        elif command.decode() in ['HSET', 'LPUSH', 'EXPIRE']:
            REDIS_LATENCY.labels(request_type='write').observe(duration)

    def execute(self, command, *args, **kwargs):
        if self.check_connection():
            res = super(Client, self).execute(command, *args, **kwargs)
            self._loop.create_task(self._eval_latency(command, res))
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
            lrange = await self.lrange(key, 0, llen - 1)  # lrange is inclusive
            return [item.decode() for item in lrange]
        except:
            raise


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
            entry = values.copy()  # ensure we have "source" defined
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
    return msgs_by_service


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
    return unique_values


@attr.s
class RequestClient:

    POSTPROCESS_FUNCTIONS = {
        'BY_SERVICE': get_msgs_by_service,
        'UNIQUE_VALUES': get_unique_values
    }

    client = attr.ib()
    expiration = int(os.environ.get('SECONDS_TO_LIVE', 100))

    async def get_request_id_hash(self, request_id):
        hashvalue = await self.client.get(request_id)
        return None if not hashvalue else hashvalue.decode()

    async def set_request_id_hash(self, request_id):
        hashvalue = await self.get_request_id_hash(request_id)
        if not hashvalue:
            hashvalue = secrets.token_hex(nbytes=16)
            await self.client.set(request_id, hashvalue)
        return hashvalue

    def update_request_id_hash(self, request_id, request_hash):
        return self.client.set(request_id, request_hash)

    async def get(self, request_id, postprocess=None):
        def _decode(res):
            for k, v in res.items():
                if 'date' == k:
                    res['date'] = parse(res['date'])
                elif v == '':
                    res[k] = None
            return res

        try:
            request_hash = await self.get_request_id_hash(request_id)
            tokens = await self.client.lget(request_hash)
            assert len(tokens) > 0  # if no tokens are found then retry with the database
            data = {}
            for token in tokens:
                pipe = self.client.pipeline()
                fut1 = self.client.hgetall(request_hash + token)
                fut2 = self.client.expire(request_hash + token, self.expiration)
                fut3 = self.client.expire(request_hash, self.expiration)
                await pipe.execute()
                res = await asyncio.gather(fut1, fut2, fut3)
                entry = _decode(res[0])
                data[entry['date']] = entry  # validates the results are in the proper format
        except:
            logger.debug('Cache could not determine values. Retrying with database...')
            try:
                # collect data from database
                data = await exec_baked('BY_DATE', **{
                    'request_id': request_id,
                    **{key: (
                        await self.client.hgetall(key, key_is_int=True)
                    ) for key in ['services', 'statuses', 'sources']}
                })

                # lazy-load the data back into the cache
                request_hash = secrets.token_hex(nbytes=16)
                for entry in data.values():
                    payload = {
                        'request_id': request_id,
                        **{k: str(v) if v else '' for k, v in entry.items()}}
                    hextoken = secrets.token_hex(nbytes=16)
                    pipe = self.client.pipeline()
                    fut1 = pipe.hmset_dict(request_hash + hextoken, payload)
                    fut2 = pipe.expire(request_hash + hextoken, self.expiration)
                    fut3 = pipe.lpush(request_hash, hextoken)
                    fut4 = pipe.expire(request_hash, self.expiration)
                    await pipe.execute()
                    await asyncio.gather(fut1, fut2, fut3, fut4)
                await self.update_request_id_hash(request_id, request_hash)
            except:
                raise

        if postprocess and postprocess in self.POSTPROCESS_FUNCTIONS.keys():
            try:
                return self.POSTPROCESS_FUNCTIONS[postprocess](data)
            except:
                raise
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
                request_hash = await self.get_request_id_hash(request_id)
                if not request_hash:
                    request_hash = await self.set_request_id_hash(request_id)
                hextoken = secrets.token_hex(nbytes=16)
                pipe = self.client.pipeline()
                fut1 = pipe.hmset_dict(request_hash + hextoken, data)
                fut2 = pipe.expire(request_hash + hextoken, self.expiration)
                fut3 = pipe.lpush(request_hash, hextoken)
                fut4 = pipe.expire(request_hash, self.expiration)
                await pipe.execute()
                res = await asyncio.gather(fut1, fut2, fut3, fut4)
            except:
                logger.error(traceback.format_exc())
            else:
                return res
        else:
            return False


request_client = RequestClient(redis_client)

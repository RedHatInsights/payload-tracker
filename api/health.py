import os
import logging
import traceback
import asyncio
import aiohttp

import responses
import settings
from db import db
from kafka_consumer import consumer

logger = logging.getLogger(settings.APP_NAME)
ENABLE_SOCKETS = os.environ.get('ENABLE_SOCKETS', "").lower() == "true"
DISABLE_PROMETHEUS = True if os.environ.get('DISABLE_PROMETHEUS') == "True" else False
API_PORT = os.environ.get('API_PORT', 8080)
PROMETHEUS_PORT = os.environ.get('PROMETHEUS_PORT', 8000)
SUCCESS_MSG = 'Liveness checks passed'
FAILED_MSG = 'Liveness checks failed'
TIMEOUT_SECONDS = 30
KAFKA_RETRY_MAX = 3
KAFKA_COUNT_TIMEOUT = 5
DB_RETRY_MAX = 3
DB_COUNT_TIMEOUT = 5
MAX_ENDPOINT_CHECK_RETRY = 3
ENDPOINT_CHECK_TIMEOUT = 5
OPTIONS={'page_size': 1}


async def check_endpoint(host, port, endpoint, timeout=300, options={}):
    for count in range(0, MAX_ENDPOINT_CHECK_RETRY):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                res = await session.get(f'http://{host}:{port}{endpoint}?{"&".join([f"{k}={v}" for k, v in options.items()])}')
                if res.status == 200:
                    try:
                        return await res.json()
                    except:
                        # we simply return here since the output of this function is only applicable for the
                        # /v1/payload:request_id endpoint which will always be json decodable
                        return
                else:
                    raise Exception(f'http://{host}:{port}{endpoint} returned status {res.status}')
        except:
            if count == MAX_ENDPOINT_CHECK_RETRY - 1:
                raise Exception(traceback.format_exc())
            await asyncio.sleep(ENDPOINT_CHECK_TIMEOUT)


async def check_kafka_connection(loop):
    for count in range(0, KAFKA_RETRY_MAX):
        try:
            topics = await consumer.topics()
            if len(topics) > 0:
                return
            else:
                raise
        except:
            if count == KAFKA_RETRY_MAX - 1:
                raise Exception(traceback.format_exc())
            await asyncio.sleep(KAFKA_COUNT_TIMEOUT)


async def search(*args, **kwargs):
    logger.debug('Beginning health checks...')
    # check db connection
    logger.debug('Checking database connection...')
    for count in range(0, DB_RETRY_MAX):
        try:
            conn = await db.bind.acquire()
            await conn.release()
        except:
            if count == DB_RETRY_MAX - 1:
                return responses.failed(f'{FAILED_MSG} with error: {traceback.format_exc()}')
            await asyncio.sleep(DB_COUNT_TIMEOUT)

    # check kafka connection
    logger.debug('Checking kafka connection...')
    try:
        await check_kafka_connection(asyncio.get_event_loop())
    except Exception as err:
        return responses.failed(f'{FAILED_MSG} with error: {err}')

    # check responsiveness of /payloads
    logger.debug('Checking connection to /v1/payloads...')
    request_id = None #for use with /payloads:request_id
    try:
        payloads = await check_endpoint('localhost', API_PORT, '/v1/payloads',
                timeout=TIMEOUT_SECONDS, options=OPTIONS)
        if payloads and 'data' in payloads and len(payloads['data']) > 0:
            request_id = payloads['data'][0]['request_id']
    except Exception as err:
        return responses.failed(f'{FAILED_MSG} with error: {err}')

    # check responsiveness of /payloads/:request_id
    # database could be empty so lack of request_id is acceptable
    if request_id:
        logger.debug('Checking connection to /v1/payloads/:request_id...')
        try:
            await check_endpoint('localhost', API_PORT, f'/v1/payloads/{request_id}', timeout=TIMEOUT_SECONDS)
        except Exception as err:
            return responses.failed(f'{FAILED_MSG} with error: {err}')

    # check responsiveness of additional endpoints on API_PORT
    logger.debug(f'Checking connection to /v1/statuses...')
    try:
        await check_endpoint('localhost', API_PORT, '/v1/statuses',
            timeout=TIMEOUT_SECONDS, options=OPTIONS)
    except Exception as err:
        return responses.failed(f'{FAILED_MSG} with error: {err}')

    if ENABLE_SOCKETS:
        # check if sockets endpoint is available
        logger.debug(f'Checking connection to /socket.io...')
        try:
            await check_endpoint('localhost', API_PORT, '/socket.io')
        except Exception as err:
            return responses.failed(f'{FAILED_MSG} with error: {err}')

    if not DISABLE_PROMETHEUS:
        # check endpoints on PROMETHEUS_PORT for valid responses
        logger.debug(f'Checking connection to /metrics...')
        try:
            await check_endpoint('localhost', PROMETHEUS_PORT, '/metrics')
        except Exception as err:
            return responses.failed(f'{FAILED_MSG} with err: {err}')

    # if no exceptions to this point, success
    return responses.success(SUCCESS_MSG)

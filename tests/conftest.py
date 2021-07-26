import os
import uuid
import gino
import json
import pytest
import random
import string
import asyncio
import logging

from random import randint
from sqlalchemy.orm import Bundle
from aioredis import create_connection
from datetime import datetime, timezone

import db
import settings

from bakery import STATUS_COLUMNS
from cache import Client, RequestClient

TEST_ENV_VARS = {
    'API_HOST': 'localhost',
    'API_PORT': '8080',
    'DB_HOST': 'localhost',
    'DB_PORT': '5432',
    'DB_USER': 'payloadtracker',
    'DB_PASSWORD': 'payloadtracker',
    'DB_NAME': 'payloadtracker',
    'REDIS_HOST': 'localhost',
    'REDIS_PORT': '6379',
    'USE_REDIS': 'true'
}
os.environ.update(TEST_ENV_VARS)


@pytest.fixture(scope='module')
def logger():
    logger = logging.getLogger(settings.APP_NAME)
    yield logger


@pytest.fixture(scope='module')
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='module')
def gino_placeholder():
    return gino.Gino()


@pytest.fixture(scope='module')
def get_services(gino_placeholder):
    return gino_placeholder.bake(db.Services.query)


@pytest.fixture(scope='module')
def get_statuses(gino_placeholder):
    return gino_placeholder.bake(db.Statuses.query)


@pytest.fixture(scope='module')
def get_sources(gino_placeholder):
    return gino_placeholder.bake(db.Sources.query)


@pytest.fixture(scope='module')
def get_payload_by_request_id(gino_placeholder):
    return gino_placeholder.bake(
        db.Payload.query.where(db.Payload.request_id == gino_placeholder.bindparam('request_id'))
    )


@pytest.fixture(scope='module')
def get_statuses_by_request_id(gino_placeholder):
    return gino_placeholder.bake(
        gino_placeholder.select([Bundle(db.PayloadStatus, *STATUS_COLUMNS)]).select_from(
            db.Payload.join(
                db.PayloadStatus, db.Payload.id == db.PayloadStatus.payload_id
            )
        ).where(db.Payload.request_id == gino_placeholder.bindparam('request_id'))
    )


@pytest.fixture(scope='module')
async def database(
    gino_placeholder, get_statuses_by_request_id, get_services,
    get_statuses, get_sources, get_payload_by_request_id
):
    await gino_placeholder.set_bind('asyncpg://{}:{}@{}:{}/{}'.format(
        os.environ['DB_USER'],
        os.environ['DB_PASSWORD'],
        os.environ['DB_HOST'],
        os.environ['DB_PORT'],
        os.environ['DB_NAME'])
    )
    yield gino_placeholder
    await gino_placeholder.pop_bind().close()


@pytest.fixture(scope='module')
async def cache():
    conn = await create_connection((os.environ['REDIS_HOST'], os.environ['REDIS_PORT']))
    cache = Client()
    cache.set_connection(conn)
    yield cache
    cache._pool_or_conn.close()


@pytest.fixture(scope='module')
async def request_cache(cache):
    request_client = RequestClient(cache)
    yield request_client
    request_client.client._pool_or_conn.close()


@pytest.fixture
async def mock_app(mock_msg, event_loop, cache, request_cache, database, mocker):
    ''' This fixture should be used to execute tests which run through the main service loop '''
    mocker.patch('app.loop', event_loop)
    mocker.patch('app.request_client', request_cache)
    mocker.patch('app.redis_client', cache)
    mocker.patch('app.db', database)
    mocker.patch('bakery.db', database)
    mocker.patch('api.payloads.db', database)
    mocker.patch('api.statuses.db', database)
    mocker.patch('api.health.db', database)
    mocker.patch('api.payloads.redis_client', cache)
    mocker.patch('api.statuses.redis_client', cache)
    mocker.patch('api.health.redis_client', cache)
    for table in db.tables.values():
        # overwrite the metadata on each of the db models to use test db
        mocker.patch(f'db.{table.__qualname__}.__metadata__', database)


@pytest.fixture
def mock_payload():
    return {
        'id': 1,
        'request_id': uuid.uuid4().hex,
        'inventory_id': uuid.uuid4().hex,
        'system_id': uuid.uuid4().hex,
        'account': randint(pow(10, 5), pow(10, 6) - 1),
        'service': ''.join([random.choice(string.ascii_lowercase) for _ in range(6)]),
        'source': ''.join([random.choice(string.ascii_lowercase) for _ in range(6)]),
        'status': ''.join([random.choice(string.ascii_lowercase) for _ in range(6)]),
        'status_msg': ''.join([random.choice(string.ascii_lowercase) for _ in range(6)]),
        'date': str(datetime.now(tz=timezone.utc))
    }


@pytest.fixture
def mock_msg(mock_payload):
    return type('MockMsg', (object,), {'value': json.dumps(mock_payload)})

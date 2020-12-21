import json
import pytest

from db import tables
from api import payloads, statuses, health

pytestmark = pytest.mark.asyncio

DEFAULT_KWARGS = {
    'page': 0,
    'page_size': 10,
    'sort_by': 'created_at',
    'sort_dir': 'desc'
}


async def test_payloads_search_endpoint_with_valid_input(mock_app):
    kwargs = {**DEFAULT_KWARGS}
    resp = await payloads.search((), **kwargs)
    assert resp._status == 200
    body = json.loads(resp._body)
    assert type(body) is dict
    assert 'data' in body


async def test_payloads_get_endpoint_with_valid_input(mock_app, mock_payload, logger):
    kwargs = DEFAULT_KWARGS.copy()
    del kwargs['page']
    del kwargs['page_size']
    request_id = mock_payload['request_id']
    resp = await payloads.get(request_id, **kwargs)
    logger.debug(resp)


async def test_statuses_search_endpoint_with_valid_input(
    mock_app, cache, database, mocker, get_statuses, get_sources, get_services
):
    kwargs = {**DEFAULT_KWARGS}
    mocker.patch('bakery.BAKERY', {
        'SERVICES': get_services,
        'STATUSES': get_statuses,
        'SOURCES': get_sources
    })

    mocker.patch('api.statuses.USE_REDIS', False)
    resp = await statuses.search((), **kwargs)
    assert resp._status == 200
    body = json.loads(resp._body)
    assert type(body) is dict
    assert 'data' in body

    # update the cache with values from the database
    async with database.bind.acquire() as conn:
        for table_name in ['services', 'sources', 'statuses']:
            values = await conn.all(database.select([tables[table_name]]))
            await cache.hmset_dict(table_name, dict(values))

    mocker.patch('api.statuses.USE_REDIS', True)
    resp = await statuses.search((), **kwargs)
    assert resp._status == 200
    body = json.loads(resp._body)
    assert type(body) is dict
    assert 'data' in body


async def test_health_endpoint_for_valid_responses(mock_app, mocker):

    async def mock_check_kafka(_):
        return

    async def mock_endpoint_fail(host, port, endpoint, timeout=300, options={}):
        raise

    async def mock_endpoint_success(host, port, endpoint, timeout=300, options={}):
        return

    mocker.patch('api.health.check_kafka_connection', mock_check_kafka)
    mocker.patch('api.health.check_endpoint', mock_endpoint_fail)
    resp = await health.search()
    assert resp.status == 404
    assert health.FAILED_MSG in json.loads(resp._body)

    mocker.patch('api.health.check_kafka_connection', mock_check_kafka)
    mocker.patch('api.health.check_endpoint', mock_endpoint_success)
    resp = await health.search()
    assert resp.status == 200
    assert health.SUCCESS_MSG in json.loads(resp._body)

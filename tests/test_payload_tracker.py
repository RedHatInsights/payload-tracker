import json
import pytest

from unittest.mock import MagicMock
from prometheus_client import REGISTRY
from datetime import datetime, timezone

from app import process_payload_status, evaluate_status_metrics

pytestmark = pytest.mark.asyncio


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


async def test_process_payload_status_without_metrics(
    mocker, mock_msg, mock_app, get_statuses_by_request_id
):
    payload_dump = json.loads(mock_msg.value)
    mocker.patch('app.evaluate_status_metrics', AsyncMock())
    mocker.patch('bakery.BAKERY', {'BY_DATE': get_statuses_by_request_id})
    await process_payload_status([mock_msg])
    payload = await get_statuses_by_request_id.first(request_id=payload_dump['request_id'])
    assert payload is not None


async def test_process_payload_status_with_metrics(
    mocker, mock_msg, mock_app, get_statuses_by_request_id
):
    payload_dump = json.loads(mock_msg.value)
    mocker.patch('bakery.BAKERY', {'BY_DATE': get_statuses_by_request_id})
    await process_payload_status([mock_msg])
    payload = await get_statuses_by_request_id.first(request_id=payload_dump['request_id'])
    assert payload is not None


async def test_payload_process_status_without_redis(
    mocker, mock_msg, mock_app, get_statuses_by_request_id, get_payload_by_request_id
):
    payload_dump = json.loads(mock_msg.value)
    mocker.patch('bakery.BAKERY', {
        'BY_DATE': get_statuses_by_request_id,
        'UNIQUE_VALUES': get_payload_by_request_id})
    mocker.patch('app.USE_REDIS', False)
    mocker.patch('app.cached_values', {
        'services': {1: payload_dump['service']},
        'sources': {1: payload_dump['source']},
        'statuses': {1: payload_dump['status']}
    })
    await process_payload_status([mock_msg])
    payload = await get_payload_by_request_id.first(request_id=payload_dump['request_id'])
    assert payload is not None


async def test_evaluate_status_metrics_with_valid_input(mocker, mock_payload, mock_app):
    mock_kwargs = {v: mock_payload[v] for v in ['request_id', 'service', 'status', 'source']}

    async def mock_cache_get_single_value(_, postprocess=None):
        mock = mock_kwargs.copy()
        mock['id'] = 1
        del mock['request_id']
        return {mock['service']: [mock]}

    async def mock_cache_get_multi_values(_, postprocess=None):
        mock = mock_kwargs.copy()
        mock['id'] = 1
        del mock['request_id']
        return {mock['service']: [{
            **mock,
            'date': datetime.now(tz=timezone.utc),
            'status': status
        } for status in ['received', 'success']]}

    mocker.patch('app.request_client.get', mock_cache_get_single_value)
    await evaluate_status_metrics(**mock_kwargs)
    assert REGISTRY.get_sample_value(
        'payload_tracker_service_status_counter_total',
        {
            'service_name': mock_kwargs['service'],
            'status': mock_kwargs['status'],
            'source_name': mock_kwargs['source']
        }
    ) == 1
    REGISTRY.get_sample_value(
        'payload_tracker_upload_time_by_service_elapsed_created',
        {'service_name': mock_kwargs['service'], 'source_name': mock_kwargs['source']}
    ) is None

    mocker.patch('app.request_client.get', mock_cache_get_multi_values)
    await evaluate_status_metrics(**mock_kwargs)
    assert REGISTRY.get_sample_value(
        'payload_tracker_upload_time_by_service_elapsed_created',
        {'service_name': mock_kwargs['service'], 'source_name': mock_kwargs['source']}
    ) is not None


async def test_request_client_set_aware_and_unaware_datetimes(
    mocker, mock_app, mock_payload, cache,
    get_statuses_by_request_id, request_cache
):
    mocker.patch('app.evaluate_status_metrics', AsyncMock())
    mocker.patch('bakery.BAKERY', {'BY_DATE': get_statuses_by_request_id})

    # pass timezone aware payload
    mock_payload_aware = {**mock_payload, 'status': 'received'}
    mock_msg_aware = type('MockMsg', (object,), {'value': json.dumps(mock_payload_aware)})
    await process_payload_status([mock_msg_aware])

    # pass timezone unaware payload
    mock_payload_unaware = {**mock_payload, 'date': str(datetime.now()), 'status': 'success'}
    mock_msg_unaware = type('MockMsg', (object,), {'value': json.dumps(mock_payload_unaware)})
    await process_payload_status([mock_msg_unaware])

    mock_kwargs = {v: mock_payload_unaware[v] for v in ['request_id', 'service', 'status', 'source']}
    await evaluate_status_metrics(**mock_kwargs)

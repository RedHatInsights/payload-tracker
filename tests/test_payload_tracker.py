import json
import pytest

from app import process_payload_status
from api.stats import _percentage


@pytest.mark.asyncio
async def test_process_payload_status_missing_expected_key(mocker, database):
    mock_db = database
    payload = {
        "service": "test-service",
        "payload_id": "1"
    }

    class MockMsg(object):
        def __init__(self):
            self.value = self.create_value(payload)
            self.topic = "payload_tracker"

        def __iter__(self):
            yield self

        def create_value(self, payload):
            try:
                return json.dumps(payload)
            except:
                raise TypeError("Payload type not supported by json.dumps()")

    def mock_json():
        return list(MockMsg())

    await process_payload_status(mock_json())
    mock_transaction = mocker.patch.object(mock_db, "transaction")
    assert not mock_transaction.called


@pytest.mark.asyncio
async def test_divide_by_zero_with_stat_percentage():
    test_params = {
        "payload": ["this", "is", "a", "test"],
        "set_size": 0
    }

    with pytest.raises(ValueError):
        await _percentage(test_params)

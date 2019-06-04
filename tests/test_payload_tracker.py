import json
import pytest
import asyncio

from db import db
from app import process_payload_status

@pytest.mark.asyncio
async def test_process_payload_status_missing_expected_key(mocker):
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
    mock_transaction = mocker.patch.object(db, "transaction")
    assert not mock_transaction.called
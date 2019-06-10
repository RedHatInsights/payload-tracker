from db import Payload
import responses


async def _get_payloads(payload_id):
    return await Payload.query.where(Payload.payload_id == payload_id).gino.all()


async def get(payload_id):
    payloads = await _get_payloads(payload_id)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

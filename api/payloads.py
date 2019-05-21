import asyncio

from db import Payload, db
import responses


async def _get_one_payload(id):
    return await Payload.query.where(Payload.payload_id == id).gino.first()


async def get(id):
    body = await _get_one_payload(id)
    if body is None:
        return responses.not_found()
    else:
        return responses.get(body.dump())

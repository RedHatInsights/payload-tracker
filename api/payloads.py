import asyncio

from db.models import Payload
from connexion import responses
from connexion.db.gino import db


async def _get_one_payload(id):
    return await Payload.query.where(Payload.id == id).gino.first()


async def get(id):
    body = await _get_one_payload(id)
    if body is None:
        return responses.not_found()
    else:
        return responses.get(body.dump())

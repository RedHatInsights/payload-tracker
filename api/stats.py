import json
import asyncio

from db import Payload, db
import responses

async def search(*args, **kwargs):
    return responses.not_found()
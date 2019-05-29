import asyncio

from db import Payload, db
from datetime import datetime
import responses

async def search(start_date=None, end_date=None, status=None):
    if (not start_date and not end_date) and not status:
        all_payloads = await db.all(Payload.query)
        payload_dump = [payload.dump() for payload in all_payloads]
        return responses.get(payload_dump) if all_payloads is not [] else responses.not_found
    elif (not start_date and not end_date) and status:
        return get_by_status(status)
    elif (start_date and end_date) and not status:
        return get_by_date(start_date, end_date)
    else:
        return get_by_date_status(start_date, end_date, status)

async def _get_payloads_by_date_status(start_date, end_date, status):
    start_date = " ".join(start_date.split('-'))
    end_date = " ".join(end_date.split('-'))
    start_date = datetime.strptime(start_date, '%b %d %Y')
    end_date = datetime.strptime(end_date, '%b %d %Y')
    return await Payload.query.where((Payload.date >= start_date) & (Payload.date <= end_date) & (Payload.status == status)).gino.all()      

async def get_by_date_status(start_date, end_date, status):
    payloads = await _get_payloads_by_date_status(start_date, end_date, status)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

async def _get_payloads_by_status(status):
    ##TODO##
    ##Add filter here for invalid status parameter
    return await Payload.query.where(Payload.status == status).gino.all()

async def get_by_status(status):
    payloads = await _get_payloads_by_status(status)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

async def _get_payloads_by_date(start_date, end_date):
    start_date = " ".join(start_date.split('-'))
    end_date = " ".join(end_date.split('-'))
    start_date = datetime.strptime(start_date, '%b %d %Y')
    end_date = datetime.strptime(end_date, '%b %d %Y')
    return await Payload.query.where((Payload.date >= start_date) & (Payload.date <= end_date)).gino.all()

async def get_by_date(start_date, end_date):
    payloads = await _get_payloads_by_date(start_date, end_date)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

##
## define get functions for in path resources
##

async def _get_payloads_by_id(payload_id):
    return await Payload.query.where(Payload.payload_id == payload_id).gino.all()

async def _get_payloads_by_service(service):
    return await Payload.query.where(Payload.service == service).gino.all()

async def _get_payloads_by_account(account):
    return await Payload.query.where(Payload.account == account).gino.all()

async def _get_payloads_by_inventory(inventory_id):
    return await Payload.query.where(Payload.inventory_id == inventory_id).gino.all()

async def get_payload(payload_id):
    payloads = await _get_payloads_by_id(payload_id)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

async def get_service(service):
    payloads = await _get_payloads_by_service(service)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

async def get_account(account):
    payloads = await _get_payloads_by_account(account)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

async def get_inventory(inventory_id):
    payloads = await _get_payloads_by_inventory(inventory_id)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

async def get(payload_id=None, service=None, account=None, inventory_id=None):
    if payload_id and (not service and not account and not inventory_id):
        return get_payload(payload_id)
    elif service and (not payload_id and not account and not inventory_id):
        return get_service(service)
    elif account and (not payload_id and not service and not inventory_id):
        return get_account(account)
    elif inventory_id and (not payload_id and not service and not account):
        return get_inventory(inventory_id)
    else:
        return responses.not_found()

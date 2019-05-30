import asyncio

from db import Payload, db
from datetime import datetime

import responses

async def search(*args, **kwargs):

    #create query using any parameters with default values
    sort_func = getattr(db, kwargs['sort_dir'])
    payload_query = Payload.query.limit(kwargs['page_size']).offset(
            kwargs['page'] * kwargs['page_size']).order_by(sort_func(kwargs['sort_by']))
    
    #these filters are used to filter within the database using equality comparisons
    basic_eq_filters = ['status', 'service', 'inventory_id', 'account',
                        'source', 'system_id', 'status_msg']
    
    #compose where clauses for any of the basic equality filters in the kwargs
    for search_param_key in kwargs:
        if search_param_key in basic_eq_filters:
            search_param_value = kwargs[search_param_key]
            payload_query.append_whereclause(
                getattr(Payload, search_param_key) == search_param_value)

    #filter payloads by `date` given a start date and/or an end date
    if 'start_date' in kwargs and 'end_date' in kwargs:
        start_date = " ".join(kwargs['start_date'].split('-'))
        end_date = " ".join(kwargs['end_date'].split('-'))
        payload_query.append_whereclause(
            (getattr(Payload, 'date') >= datetime.strptime(start_date, '%b %d %Y')) &
            (getattr(Payload, 'date') <= datetime.strptime(end_date, '%b %d %Y')))
    elif 'start_date' in kwargs:
        start_date = " ".join(kwargs['start_date'].split('-'))
        payload_query.append_whereclause(
            (getattr(Payload, 'date') >= datetime.strptime(start_date, '%b %d %Y')))
    elif 'end_date' in kwargs:
        end_date = " ".join(kwargs['end_date'].split('-'))
        payload_query.append_whereclause(
            (getattr(Payload, 'date') <= datetime.strptime(end_date, '%b %d %Y')))

    #filter payloads by `created_at` given a start date and/or an end date
    if 'first_created_at' in kwargs and 'last_created_at' in kwargs:
        first_created_at = " ".join(kwargs['first_created_at'].split('-'))
        last_created_at = " ".join(kwargs['last_created_at'].split('-'))
        payload_query.append_whereclause(
            (getattr(Payload, 'created_at') >= datetime.strptime(first_created_at, '%b %d %Y %H:%M')) &
            (getattr(Payload, 'created_at') <= datetime.strptime(last_created_at, '%b %d %Y %H:%M')))
    elif 'first_created_at' in kwargs:
        first_created_at = " ".join(kwargs['first_created_at'].split('-'))
        payload_query.append_whereclause(
            (getattr(Payload, 'created_at') >= datetime.strptime(first_created_at, '%b %d %Y %H:%M')))
    elif 'last_created_at' in kwargs:
        last_created_at = " ".join(kwargs['last_created_at'].split('-'))
        payload_query.append_whereclause(
            (getattr(Payload, 'created_at') >= datetime.strptime(last_created_at, '%b %d %Y %H:%M')))

    #compile set of payloads from the database
    payloads = await payload_query.gino.all()
    payloads_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payloads_dump)

async def _get_one_payload(payload_id):
    return await Payload.query.where(Payload.payload_id == payload_id).gino.all()

async def get(payload_id):
    payload = await _get_one_payload(payload_id)
    if payload is None:
        return responses.not_found()
    else:
        return responses.get(payload.dump())

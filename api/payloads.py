import asyncio

from db import Payload, db
from datetime import datetime
<<<<<<< HEAD

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
=======
import responses

async def search(*args, **kwargs):
    sort_func = getattr(db, kwargs['sort_dir'])
    payload_query = Payload.query.limit(kwargs['page_size']).offset(
            kwargs['page'] * kwargs['page_size']).order_by(sort_func(kwargs['sort_by']))
    
    expected_filters = ['status', 'service', 'inventory_id', 'account']
    potential_date_filters = ['start_date', 'end_date', 'first_created_at', 'last_created_at']

    for search_param_key in kwargs:
        if search_param_key in expected_filters:
>>>>>>> 60354df882361f61bf898e138b8c69c583465cc2
            search_param_value = kwargs[search_param_key]
            payload_query.append_whereclause(
                getattr(Payload, search_param_key) == search_param_value)

<<<<<<< HEAD
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
=======
    found_date_filters = []

    for search_param_key in kwargs:
        if search_param_key in potential_date_filters:
            found_date_filters.append(search_param_key)

    if 'start_date' in found_date_filters and 'end_date' in found_date_filters:
        start_date = " ".join(kwargs['start_date'].split('-'))
        end_date = " ".join(kwargs['end_date'].split('-'))
        payload_query.append_whereclause(
            (getattr(Payload, 'date') >= datetime.strptime(start_date, '%b %d %Y')) &
            (getattr(Payload, 'date') <= datetime.strptime(end_date, '%b %d %Y'))
        )
    if 'first_created_at' in found_date_filters and 'last_created_at' in found_date_filters:
        first_created_at = " ".join(kwargs['first_created_at'].split('-'))
        last_created_at = " ".join(kwargs['last_created_at'].split('-'))
        print(last_created_at)
        print(first_created_at)
        payload_query.append_whereclause(
            (getattr(Payload, 'created_at') >= datetime.strptime(first_created_at, '%b %d %Y %H:%M')) &
            (getattr(Payload, 'created_at') <= datetime.strptime(last_created_at, '%b %d %Y %H:%M'))
        )

>>>>>>> 60354df882361f61bf898e138b8c69c583465cc2
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

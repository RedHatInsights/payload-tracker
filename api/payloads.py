import asyncio

from db import Payload, db
from datetime import datetime
from dateutil import parser
import responses
import operator

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

    # Perform comparisons on date fields 'date', and 'created_at'
    date_group_fns = {'_lt': operator.lt, '_lte': operator.le, 
                      '_gt': operator.gt, '_gte': operator.ge}
    for date_field in ['date', 'created_at']:
        for date_group_str, date_group_fn in date_group_fns.items():
            if date_field + date_group_str in kwargs:
                the_date = parser.parse(kwargs[date_field + date_group_str])
                payload_query.append_whereclause(
                    date_group_fn(getattr(Payload, date_field), the_date)
                )

    #compile set of payloads from the database
    payloads = await payload_query.gino.all()
    payloads_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payloads_dump)

async def _get_payloads(payload_id):
    return await Payload.query.where(Payload.payload_id == payload_id).gino.all()


async def get(payload_id):
    payloads = await _get_payloads(payload_id)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payload_dump)

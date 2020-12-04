import asyncio
import traceback

from db import db, Payload, Services, Sources, Statuses


'''
Define queries which will be pre-baked for execution by gino
Using the bakery improves the execution time of the query
It is suggested to utilize the bakery for heavily used queries
'''

get_services = db.bake(Services.query)
get_statuses = db.bake(Statuses.query)
get_sources = db.bake(Sources.query)
get_payload_by_request_id = db.bake(
    Payload.query.where(Payload.request_id == db.bindparam('request_id'))
)


BAKERY = {
    'SERVICES': get_services,
    'STATUSES': get_statuses,
    'SOURCES': get_sources,
    'PAYLOADS': get_payload_by_request_id,
    'UNIQUE_VALUES': get_payload_by_request_id
}


'''
Often times we would like to parse query results before returning their values
Adding a processing function allows us to logically group the baked query with
its processing function. The processing function MUST take a bakery_query which
will be executed using one of gino's provided db api calls.

Example:

def test_function(baked_query, **bound_params):
    return await baked_query.first(request_id=bound_params['request_id'])

'''

async def process_services_statuses_sources(baked_query, **bound_params):
    try:
        table_results_as_objs = await baked_query.all()
        tables_dump = [table_obj.dump() for table_obj in table_results_as_objs]
        values_in_table = {table_dict['id']: table_dict['name'] for table_dict in tables_dump}
    except Exception as err:
        raise err
    else:
        return values_in_table


async def process_payload_by_request_id(baked_query, **bound_params):
    try:
        payload_obj = await baked_query.first(request_id=bound_params['request_id'])
    except Exception as err:
        raise err
    else:
        return None if not payload_obj else payload_obj.dump()


async def process_payload_by_unique_keys(baked_query, **bound_params):
    try:
        payload_list = await baked_query.all(request_id=bound_params['request_id'])
        payload_dump = [payload.dump() for payload in payload_list]
        values = {k: v for payload in payload_dump for k, v in payload.items() if v is not None}
    except Exception as err:
        raise err
    else:
        return values


PROCESSING_FUNCTIONS = {
    'SERVICES': process_services_statuses_sources,
    'STATUSES': process_services_statuses_sources,
    'SOURCES': process_services_statuses_sources,
    'PAYLOADS': process_payload_by_request_id,
    'UNIQUE_VALUES': process_payload_by_unique_keys
}


'''
Use this function to return the results of the processing function
The key provided MUST match both the PROCESSING_FUNCTION AND BAKERY key
'''
async def exec_baked(key, **bound_params):
    try:
        key = key.upper()
        res = await PROCESSING_FUNCTIONS[key](BAKERY[key], **bound_params)
    except Exception as err:
        raise err
    else:
        return res

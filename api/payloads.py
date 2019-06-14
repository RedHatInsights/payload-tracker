from db import Payload, db
from dateutil import parser
import responses
import settings
import operator
import logging

logger = logging.getLogger(settings.APP_NAME)


async def search(*args, **kwargs):
    # Create query using any parameters with default values
    logger.debug(f"Payloads.search({args}, {kwargs})")
    payload_query = _build_query(kwargs)
    
    # Compile set of payloads from the database
    payloads = await payload_query.gino.all()
    payloads_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(payloads_dump)


def _build_query(query_params):
    logger.debug(f"Payloads._build_query({query_params}")
    payload_query = _get_query()
    for payload_query_fn in [_get_sort, _get_limit, _get_filters, _get_date]:
        payload_query = payload_query_fn(query_params, payload_query)
    return payload_query


def _get_query():
    logger.debug("Payloads._get_query()")
    return Payload.query


def _get_sort(query_params, payload_query):
    logger.debug(f"Payloads._get_sort({query_params}, {payload_query})")
    sort_func = getattr(db, query_params['sort_dir'])
    return payload_query.order_by(sort_func(query_params['sort_by']))


def _get_limit(query_params, payload_query):
    logger.debug(f"Payloads._get_limit({query_params}, {payload_query})")
    return payload_query.limit(query_params['page_size']).offset(
                               query_params['page'] * query_params['page_size'])


def _get_filters(query_params, payload_query):
    logger.debug(f"Payloads._get_filters({query_params}, {payload_query})")
    # These filters are used to filter within the database using equality comparisons
    basic_eq_filters = ['status', 'service', 'inventory_id', 'account',
                        'source', 'system_id', 'status_msg']
    # Compose where clauses for any of the basic equality filters in the kwargs
    for search_param_key in query_params:
        if search_param_key in basic_eq_filters:
            search_param_value = query_params[search_param_key]
            payload_query.append_whereclause(
                getattr(Payload, search_param_key) == search_param_value)
    return payload_query


def _get_date_group_fns():
    return {'_lt': operator.lt, '_lte': operator.le,
            '_gt': operator.gt, '_gte': operator.ge}


def _get_date(query_params, payload_query):
    logger.debug(f"Payloads._get_date({query_params}, {payload_query})")
    # Perform comparisons on date fields 'date', and 'created_at'
    date_group_fns = _get_date_group_fns()
    for date_field in ['date', 'created_at']:
        for date_group_str, date_group_fn in date_group_fns.items():
            if date_field + date_group_str in query_params:
                the_date = parser.parse(query_params[date_field + date_group_str])
                payload_query.append_whereclause(
                    date_group_fn(getattr(Payload, date_field), the_date)
                )
    return payload_query


async def _get_payloads(payload_id):
    logger.debug(f"Payloads._get_payloads({payload_id})")
    return await Payload.query.where(Payload.payload_id == payload_id).gino.all()


async def get(payload_id):
    logger.debug(f"Payloads.get({payload_id})")
    payloads = await _get_payloads(payload_id)
    payload_dump = [payload.dump() for payload in payloads]
    if payloads is None:
        return responses.not_found()
    else:
        payload_dump = [payload.dump() for payload in payloads]
        return responses.get(payload_dump)

from db import Payload, db
from dateutil import parser
import responses
import operator
import logging
import settings
import time

logger = logging.getLogger(settings.APP_NAME)


async def search(*args, **kwargs):

    payloads = None
    payloads_dump = []
    # Calculate elapsed time
    start = time.time()

    # initialize connection
    async with db.bind.acquire() as conn:

        # Base query
        payload_query = Payload.query

        # These filters are used to filter within the database using equality comparisons
        basic_eq_filters = ['status', 'service', 'inventory_id', 'account',
                            'source', 'system_id', 'status_msg']

        # Compose where clauses for any of the basic equality filters in the kwargs
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

        # Get the count before we apply the page size and offset
        payloads_count = await conn.scalar(payload_query.alias().count())

        # Then apply page size and offset
        sort_func = getattr(db, kwargs['sort_dir'])
        payload_query = payload_query.limit(kwargs['page_size']).offset(
                kwargs['page'] * kwargs['page_size']).order_by(sort_func(kwargs['sort_by']))

        # Compile set of payloads from the database
        payloads = await conn.all(payload_query)
        payloads_dump = [payload.dump() for payload in payloads]

        # Calculate elapsed time
        stop = time.time()
        elapsed = stop - start

    # Send results
    if payloads is None:
        return responses.not_found()
    else:
        return responses.search(payloads_count, payloads_dump, elapsed)


async def get(request_id, *args, **kwargs):

    def get_dict(res): return {item[0]: str(item[1]) for item in res}

    payloads = None
    payload_dump = []

    # initialize connection
    async with db.bind.acquire() as conn:

        logger.debug(f"Payloads.get({request_id}, {args}, {kwargs})")
        sort_func = getattr(db, kwargs['sort_dir'])
        payloads = await conn.all(Payload.query.where(
            Payload.request_id == request_id
        ).order_by(
            sort_func(kwargs['sort_by'])
        ))
        durations = get_dict(await conn.all(db.text(
            'SELECT service, duration FROM durations WHERE request_id = :request_id'
        ), { 'request_id' : request_id }))
        times = await conn.all(db.text(
            'SELECT MAX(a.end)-MIN(a.start), SUM(a.duration) FROM durations as a WHERE a.request_id = :request_id'
        ), { 'request_id' : request_id })
        durations['total_time'] = str(times[0][0])
        durations['total_time_in_services'] = str(times[0][1])
    if payloads is None:
        return responses.not_found()
    else:
        payload_dump = [payload.dump() for payload in payloads]
        return responses.get_with_duration(payload_dump, durations)
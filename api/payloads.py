from db import Payload, PayloadStatus, db
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
        basic_eq_filters = ['account', 'inventory_id', 'system_id']

        # Compose where clauses for any of the basic equality filters in the kwargs
        for search_param_key in kwargs:
            if search_param_key in basic_eq_filters:
                search_param_value = kwargs[search_param_key]
                payload_query.append_whereclause(
                    getattr(Payload, search_param_key) == search_param_value)

        # Perform comparisons on date fields 'date', and 'created_at'
        date_group_fns = {'_lt': operator.lt, '_lte': operator.le,
                          '_gt': operator.gt, '_gte': operator.ge}
        for date_field in ['created_at']:
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


def _get_durations(payloads):
    services = set()
    service_to_times = {}
    service_to_duration = {}
    all_times = []

    for payload in payloads:
        services.add(payload['service'])

    for service in services:
        for payload in payloads:
            all_times.append(payload['date'])
            if payload['service'] == service:
                if service in service_to_times:
                    service_to_times[service].append(payload['date'])
                else:
                    service_to_times[service] = [payload['date']]
    
    all_times.sort()
    service_to_duration['total_time'] = str(all_times[-1] - all_times[0])

    for service in services:
        times = [time for time in service_to_times[service]]
        times.sort()
        if 'total_time_in_services' in service_to_duration.keys():
            service_to_duration['total_time_in_services'] += times[-1] - times[0]
        else:
            service_to_duration['total_time_in_services'] = times[-1] - times[0]
        service_to_duration[service] = str(times[-1] - times[0])
    service_to_duration['total_time_in_services'] = str(service_to_duration['total_time_in_services'])

    return service_to_duration


async def get(request_id, *args, **kwargs):

    payload = None
    payload_statuses = None
    payload_dump = []
    payload_statuses_dump = []

    # initialize connection
    async with db.bind.acquire() as conn:

        logger.debug(f"Payloads.get({request_id}, {args}, {kwargs})")
        sort_func = getattr(db, kwargs['sort_dir'])
        payload_statuses = await conn.all(PayloadStatus.query.where(
            PayloadStatus.request_id == request_id
        ).order_by(
            sort_func(kwargs['sort_by'])
        ))

    if payload_statuses is None:
        return responses.not_found()
    else:
        payload_statuses_dump = [payload_status.dump() for payload_status in payload_statuses]
        durations = _get_durations(payload_statuses_dump)

        async with db.bind.acquire() as conn:
            payload = await conn.all(Payload.query.where(Payload.request_id == request_id))

        payload_dump = [p.dump() for p in payload]
        if len(payload_dump) > 0:
            for payload_status in payload_statuses_dump:
                for key in ['account', 'inventory_id', 'system_id']:
                    if key in payload_dump[0]:
                        payload_status[key] = payload_dump[0][key]

        return responses.get_with_duration(payload_statuses_dump, durations)

from db import Payload, db
from dateutil import parser
import responses
import operator
import logging
import settings

logger = logging.getLogger(settings.APP_NAME)


async def search(*args, **kwargs):

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
    payloads_count = await payload_query.alias().count().gino.scalar()

    # Then apply page size and offset
    sort_func = getattr(db, kwargs['sort_dir'])
    payload_query = payload_query.limit(kwargs['page_size']).offset(
            kwargs['page'] * kwargs['page_size']).order_by(sort_func(kwargs['sort_by']))

    # Compile set of payloads from the database
    payloads = await payload_query.gino.all()
    payloads_dump = [payload.dump() for payload in payloads]

    # Send results
    if payloads is None:
        return responses.not_found()
    else:
        return responses.search(payloads_count, payloads_dump)


def _get_durations(payloads):
    services = set()
    service_to_times = {}
    service_to_duration = {}

    for payload in payloads:
        services.add(payload['service'])

    for service in services:
        for payload in payloads:
            if payload['service'] == service:
                if service in service_to_times:
                    service_to_times[service].append(payload['date'])
                else:
                    service_to_times[service] = [payload['date']]

    for service in services:
        times = [time for time in service_to_times[service]]
        times.sort()
        if 'total' in service_to_duration.keys():
            service_to_duration['total'] += times[-1] - times[0]
        else:
            service_to_duration['total'] = times[-1] - times[0]
        service_to_duration[service] = str(times[-1] - times[0])
    service_to_duration['total'] = str(service_to_duration['total'])

    return service_to_duration


async def get(payload_id, *args, **kwargs):
    logger.debug(f"Payloads.get({payload_id}, {args}, {kwargs})")
    sort_func = getattr(db, kwargs['sort_dir'])
    payloads = await Payload.query.where(
        Payload.payload_id == payload_id
    ).order_by(
        sort_func(kwargs['sort_by'])
    ).gino.all()

    if payloads is None:
        return responses.not_found()
    else:
        payload_dump = [payload.dump() for payload in payloads]
        durations = _get_durations(payload_dump)
        return responses.get_with_duration(payload_dump, durations)

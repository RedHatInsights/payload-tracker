from db import Payload, PayloadStatus, Services, Sources, db
from utils import dump
import cache
from sqlalchemy import inspect, cast, TIMESTAMP
from sqlalchemy.orm import Bundle
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
        payload_query = db.select([Bundle(Payload, *inspect(Payload).columns)])

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
                        date_group_fn(
                            cast(getattr(Payload, date_field), TIMESTAMP), the_date.replace(tzinfo=None)))

        # Get the count before we apply the page size and offset
        payloads_count = await conn.scalar(payload_query.alias().count())

        # Then apply page size and offset
        sort_func = getattr(db, kwargs['sort_dir'])
        payload_query = payload_query.limit(kwargs['page_size']).offset(
                kwargs['page'] * kwargs['page_size']).order_by(sort_func(kwargs['sort_by']))

        # Compile set of payloads from the database
        payloads = await conn.all(payload_query)
        payloads_dump = dump(inspect(Payload).columns, payloads)

        # Calculate elapsed time
        stop = time.time()
        elapsed = stop - start

    # Send results
    if payloads is None:
        return responses.not_found()
    else:
        return responses.search(payloads_count, payloads_dump, elapsed)


def _get_durations(services, payloads):
    service_to_times = {}
    service_to_duration = {}
    all_times = []

    if len(payloads) > 0:
        for key, service in zip([i['id'] for i in services], [i['name'] for i in services]):
            for payload in payloads:
                all_times.append(payload['date'])
                if payload['service'] == service:
                    if service in service_to_times:
                        service_to_times[service].append(payload['date'])
                    else:
                        service_to_times[service] = [payload['date']]

        all_times.sort()
        service_to_duration['total_time'] = str(all_times[-1] - all_times[0])

        for service in [i['name'] for i in services]:
            if service in service_to_times.keys():
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

    # check if value is cached in-memory
    cached_value = cache.get_value(request_id)
    if cached_value:
        durations = _get_durations(cache.get_value('services'), cached_value)
        return responses.get_with_duration(cached_value, durations)

    payload = None
    payload_statuses = None
    payload_dump = []
    payload_statuses_dump = []

    status_columns = [c for c in inspect(PayloadStatus).columns if c.name is not 'payload_id']
    payload_columns = [c for c in inspect(Payload).columns if c.name in [
        'request_id', 'account', 'inventory_id', 'system_id'
    ]]
    statuses_query = db.select([Bundle(PayloadStatus, *status_columns), Bundle(Payload, *payload_columns)])

    # initialize connection
    async with db.bind.acquire() as conn:

        logger.debug(f"Payloads.get({request_id}, {args}, {kwargs})")
        sort_func = getattr(db, kwargs['sort_dir'])

        statuses_query = statuses_query.select_from(
            PayloadStatus.join(
                Payload, PayloadStatus.payload_id == Payload.id, isouter=True
            )
        ).where(
            Payload.request_id == request_id
        )

        if kwargs['sort_by'] in ['source', 'service']:
            statuses_query = statuses_query.order_by(sort_func(f'{kwargs["sort_by"]}_id'))
        else:
            statuses_query = statuses_query.order_by(sort_func(kwargs['sort_by']))

        payload_statuses = await conn.all(statuses_query)

    if payload_statuses is None:
        return responses.not_found()
    else:
        dump_columns = [*status_columns, *payload_columns]
        payload_statuses_dump = dump(dump_columns, payload_statuses)

        # replace integer values for service and source
        for status in payload_statuses_dump:
            for column in ['service', 'source']:
                if f'{column}_id' in status:
                    cached_dict = {i['id']: i['name'] for i in cache.get_value(f'{column}s')}
                    status[column] = cached_dict[status[f'{column}_id']]
                    del status[f'{column}_id']

        # add value to cache
        cache.set_value(request_id, payload_statuses_dump, ttl=3600)

        durations = _get_durations(cache.get_value('services'), payload_statuses_dump)

        return responses.get_with_duration(payload_statuses_dump, durations)

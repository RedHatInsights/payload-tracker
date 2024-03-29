from sqlalchemy import inspect, cast, TIMESTAMP
from sqlalchemy.orm import Bundle
from dateutil import parser
from dateutil.tz import tzutc
from datetime import timedelta
import responses
import operator
import logging
import settings
import time

from db import Payload, PayloadStatus, db
from bakery import exec_baked
from utils import dump, Triple, TripleSet
from cache import redis_client
from app import USE_REDIS

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
                    the_date = parser.parse(kwargs[date_field + date_group_str]).astimezone(tzutc())
                    payload_query.append_whereclause(
                        date_group_fn(
                            cast(getattr(Payload, date_field), TIMESTAMP(timezone=tzutc())), the_date))  # noqa

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


def _get_durations(payloads):
    durations = {}
    if len(payloads) > 0:
        # place payloads into buckets by service and source
        services_by_source = TripleSet()
        for payload in payloads:
            service, date, source = tuple({
                'service': payload['service'], 'date': payload['date'],
                'source': 'undefined' if 'source' not in payload else payload['source']}.values())
            if (
                (service, source) not in services_by_source.keys() or (
                    date not in services_by_source.values())
            ):
                services_by_source.append(Triple(service, source, date))

        # compute duration for each bucket of service and source
        keys = set(services_by_source.keys())
        for key in keys:
            values = [v for k, v in services_by_source.items() if k == key]
            values.sort()
            # we will use the same key structure on the frontend "service:source"
            durations[f'{key[0]}:{key[1]}'] = values[-1] - values[0]

        # compute total time in services
        durations['total_time_in_services'] = timedelta(seconds=sum(
            [time.total_seconds() for time in durations.values()]))

        # compute total time
        values = services_by_source.values()
        values.sort()
        durations['total_time'] = values[-1] - values[0]

    # return results as dict object
    return {} if durations == {} else {k: str(v) for k, v in durations.items()}


async def get(request_id, *args, **kwargs):

    payload_statuses = None
    payload_statuses_dump = []

    status_columns = [c for c in inspect(PayloadStatus).columns if c.name != 'payload_id']
    payload_columns = [c for c in inspect(Payload).columns if c.name in [
        'request_id', 'account', 'inventory_id', 'system_id'
    ]]
    statuses_query = db.select([
        Bundle(PayloadStatus, *status_columns), Bundle(Payload, *payload_columns)])

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

        if kwargs['sort_by'] in ['source', 'service', 'status']:
            statuses_query = statuses_query.order_by(
                sort_func(f'{kwargs["sort_by"]}_id'))
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
            for column_name, table_name in zip(
                ['service', 'source', 'status'], ['services', 'sources', 'statuses']
            ):
                if f'{column_name}_id' in status:
                    if USE_REDIS:
                        table = await redis_client.hgetall(table_name, key_is_int=True)
                    else:
                        table = await exec_baked(table_name)
                    status[column_name] = table[status[f'{column_name}_id']]
                    del status[f'{column_name}_id']

        durations = _get_durations(payload_statuses_dump)
        return responses.get_with_duration(payload_statuses_dump, durations)

from db import Payload, PayloadStatus, db
from utils import dump
from cache import cache
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

    statuses = None
    statuses_dump = []

    # Calculate elapsed time
    start = time.time()

    # initialize connection
    async with db.bind.acquire() as conn:

        # Base queries
        status_columns = [c for c in inspect(PayloadStatus).columns if c.name != 'payload_id']
        statuses_query = db.select([Bundle(PayloadStatus, *status_columns), Bundle(Payload, Payload.request_id)])
        statuses_count = db.select([db.func.count(Bundle(PayloadStatus, PayloadStatus.payload_id))])

        # convert string-base queries to integer equivalents
        filters_to_integers = {'service': 'services', 'source': 'sources', 'status': 'statuses'}

        for search_param_key in kwargs:
            if search_param_key in filters_to_integers.keys():
                search_param_value = kwargs[search_param_key]
                values_in_table = cache.get_value(filters_to_integers[search_param_key])
                if search_param_value not in values_in_table.values():
                    stop = time.time()
                    return responses.search(0, [], stop - start)
                for key, name in values_in_table.items():
                    if search_param_value == name:
                        for query in [statuses_query, statuses_count]:
                            query.append_whereclause(
                                getattr(PayloadStatus, f'{search_param_key}_id') == key)

        # These filters are used to filter within the database using equality comparisons
        basic_eq_filters = ['status_msg']

        # Compose where clauses for any of the basic equality filters in the kwargs
        for search_param_key in kwargs:
            if search_param_key in basic_eq_filters:
                search_param_value = kwargs[search_param_key]
                for query in [statuses_query, statuses_count]:
                    query.append_whereclause(
                        getattr(PayloadStatus, search_param_key) == search_param_value)

        # Perform comparisons on date fields 'date', and 'created_at'
        date_group_fns = {'_lt': operator.lt, '_lte': operator.le,
                          '_gt': operator.gt, '_gte': operator.ge}
        for date_field in ['date', 'created_at']:
            for date_group_str, date_group_fn in date_group_fns.items():
                if date_field + date_group_str in kwargs:
                    the_date = parser.parse(kwargs[date_field + date_group_str])
                    for query in [statuses_query, statuses_count]:
                        query.append_whereclause(
                            date_group_fn(
                                cast(getattr(PayloadStatus, date_field), TIMESTAMP), the_date.replace(tzinfo=None)))

        # Then apply page size and offset
        sort_func = getattr(db, kwargs['sort_dir'])
        statuses_query = statuses_query.limit(kwargs['page_size']).offset(
                kwargs['page'] * kwargs['page_size'])

        if kwargs['sort_by'] in ['source', 'service', 'status']:
            statuses_query = statuses_query.order_by(sort_func(f'{kwargs["sort_by"]}_id'))
        else:
            statuses_query = statuses_query.order_by(sort_func(kwargs['sort_by']))

        # compute count
        statuses_count = await statuses_count.gino.scalar()

        # Compile set of statuses from the database
        statuses = await conn.all(statuses_query.select_from(
            PayloadStatus.join(
                Payload, PayloadStatus.payload_id == Payload.id, isouter=True
            )
        ))
        dump_columns = [*status_columns, Payload.request_id]
        statuses_dump = dump(dump_columns, statuses)

        # replace integer values for service and source
        for status in statuses_dump:
            for column_name, table_name in zip(['service', 'source', 'status'], ['services', 'sources', 'statuses']):
                if f'{column_name}_id' in status:
                    status[column_name] = cache.get_value(table_name)[status[f'{column_name}_id']]
                    del status[f'{column_name}_id']

        # Calculate elapsed time
        stop = time.time()
        elapsed = stop - start

    # Send results
    if statuses is None:
        return responses.not_found()
    else:
        return responses.search(statuses_count, statuses_dump, elapsed)

from db import Payload, PayloadStatus, Services, Sources, db
from cache import cache
from sqlalchemy import inspect
from sqlalchemy.orm import Bundle
from dateutil import parser
import responses
import operator
import logging
import settings
import time

logger = logging.getLogger(settings.APP_NAME)


def dump(cols, res):
    return [{k.key: v for k, v in zip(cols, row) if v is not None} for row in res]


async def search(*args, **kwargs):

    statuses = None
    statuses_dump = []

    # Calculate elapsed time
    start = time.time()

    # initialize connection
    async with db.bind.acquire() as conn:

        # Get the count before we apply the page size and offset
        statuses_count = await db.func.count(Bundle(PayloadStatus, PayloadStatus.payload_id)).gino.scalar()

        # Base query
        status_columns = [c for c in inspect(PayloadStatus).columns if c.name is not 'payload_id']
        statuses_query = db.select([Bundle(PayloadStatus, *status_columns), Bundle(Payload, Payload.request_id)])

        # convert string-base queries to integer equivalents
        filters_to_integers = ['service', 'source']

        for search_param_key in kwargs:
            if search_param_key in filters_to_integers:
                search_param_value = kwargs[search_param_key]
                values_in_table = cache.get_value(f'{search_param_key}s')
                if search_param_value not in values_in_table.values():
                    stop = time.time()
                    return responses.search(statuses_count, [], stop - start)
                for key, name in values_in_table.items():
                    if search_param_value == name:
                        statuses_query.append_whereclause(
                            getattr(PayloadStatus, f'{search_param_key}_id') == key)

        # These filters are used to filter within the database using equality comparisons
        basic_eq_filters = ['status', 'status_msg']

        # Compose where clauses for any of the basic equality filters in the kwargs
        for search_param_key in kwargs:
            if search_param_key in basic_eq_filters:
                search_param_value = kwargs[search_param_key]
                statuses_query.append_whereclause(
                    getattr(PayloadStatus, search_param_key) == search_param_value)

        # Perform comparisons on date fields 'date', and 'created_at'
        date_group_fns = {'_lt': operator.lt, '_lte': operator.le,
                          '_gt': operator.gt, '_gte': operator.ge}
        for date_field in ['created_at']:
            for date_group_str, date_group_fn in date_group_fns.items():
                if date_field + date_group_str in kwargs:
                    the_date = parser.parse(kwargs[date_field + date_group_str])
                    statuses_query.append_whereclause(
                        date_group_fn(getattr(PayloadStatus, date_field), the_date)
                    )

        # Then apply page size and offset
        sort_func = getattr(db, kwargs['sort_dir'])
        statuses_query = statuses_query.limit(kwargs['page_size']).offset(
                kwargs['page'] * kwargs['page_size'])

        if kwargs['sort_by'] in ['source', 'service']:
            statuses_query = statuses_query.order_by(sort_func(f'{kwargs["sort_by"]}_id'))
        else:
            statuses_query = statuses_query.order_by(sort_func(kwargs['sort_by']))

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
            for column in ['service', 'source']:
                if f'{column}_id' in status:
                    status[column] = cache.get_value(f'{column}s')[status[f'{column}_id']]
                    del status[f'{column}_id']

        # Calculate elapsed time
        stop = time.time()
        elapsed = stop - start

    # Send results
    if statuses is None:
        return responses.not_found()
    else:
        return responses.search(statuses_count, statuses_dump, elapsed)

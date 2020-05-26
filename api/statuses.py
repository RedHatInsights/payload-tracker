from db import PayloadStatus, db
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

        # Base query
        statuses_query = PayloadStatus.query

        # These filters are used to filter within the database using equality comparisons
        basic_eq_filters = ['request_id', 'service', 'source', 'status', 'status_msg']

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

        # Get the count before we apply the page size and offset
        statuses_count = await conn.scalar(statuses_query.alias().count())

        # Then apply page size and offset
        sort_func = getattr(db, kwargs['sort_dir'])
        statuses_query = statuses_query.limit(kwargs['page_size']).offset(
                kwargs['page'] * kwargs['page_size']).order_by(sort_func(kwargs['sort_by']))

        # Compile set of statuses from the database
        statuses = await conn.all(statuses_query)
        statuses_dump = [status.dump() for status in statuses]

        # Calculate elapsed time
        stop = time.time()
        elapsed = stop - start

    # Send results
    if statuses is None:
        return responses.not_found()
    else:
        return responses.search(statuses_count, statuses_dump, elapsed)

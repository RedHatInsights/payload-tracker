import responses
import logging
import settings
import datetime
import operator
from db import Payload

logger = logging.getLogger(settings.APP_NAME)
LIMIT = 50000

async def search(*args, **kwargs):
    logger.debug(f"Stats.search({args}, {kwargs})")
    stat_funcs = {'SuccessRate': _success_rate}
    func = stat_funcs[kwargs['stat']]
    func_params = {}
    result = {}
    offset = 0

    payload_query = Payload.query.limit(LIMIT)
    payloads_count = await Payload.query.alias().count().gino.scalar()

    # Only get the past 24 hours for right now
    # Trying to calculate this against the whole database is too much
    twenty_four_hours = datetime.datetime.now() - datetime.timedelta(hours = 24)
    payload_query.append_whereclause(
        operator.ge(Payload.date, twenty_four_hours)
    )

    while offset < payloads_count:
        payloads = await payload_query.offset(offset).gino.all()
        payloads_dump = [payload.dump() for payload in payloads]
        func_params['payload'] = payloads_dump
        if payloads is None:
            return responses.not_found()
        result = await func(func_params, result)
        offset += LIMIT

    return responses.get(result)

async def _success_rate(params, result):
    payloads = params['payload']
    for payload in payloads:
        if payload['service'] not in result:
            result[payload['service']] = {'success': 0, 'failure': 0,
                                                 'successPercent': 0, 'failPercent': 0}
        if payload['status'] == 'success' or payload['status'] == 'successful':
            result[payload['service']]['success'] += 1
        elif payload['status'] == 'error':
            result[payload['service']]['failure'] += 1
    return result


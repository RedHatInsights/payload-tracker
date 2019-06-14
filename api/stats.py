import operator
import logging
from dateutil import parser

import responses
import settings
from db import db, Payload
from api.payloads import _get_query, _get_filters, _get_date, _get_date_group_fns

logger = logging.getLogger(settings.APP_NAME)

async def search(*args, **kwargs):
    logger.debug(f"Stats.search({args}, {kwargs})")
    payload_query = _get_query()

    stat_funcs = {"count": _count, "percentage": _percentage}
    date_group_fns = _get_date_group_fns()
    func_params = {}

    func = stat_funcs[kwargs['stat']]
    func_params['set_size'] = await db.func.count(getattr(Payload, "id")).gino.scalar()

    if 'set_constraint' in kwargs:
        constraint_query = Payload.query
        set_constraint_param = kwargs['set_constraint']
        if set_constraint_param in ['date', 'created_at']:
            for date_group_str, date_group_fn in date_group_fns.items():
                if set_constraint_param + date_group_str in kwargs:
                    the_date = parser.parse(kwargs[set_constraint_param + date_group_str])
                    constraint_query.append_whereclause(
                        date_group_fn(getattr(Payload, set_constraint_param), the_date)
                    )
        elif set_constraint_param in kwargs:
            set_constraint_value = kwargs[set_constraint_param]
            constraint_query.append_whereclause(
                getattr(Payload, set_constraint_param) == set_constraint_value
            )
        payload_dump = [payload.dump() for payload in await constraint_query.gino.all()]
        func_params['set_size'] = len(payload_dump)

    payload_query = _get_filters(kwargs, payload_query)
    payload_query = _get_date(kwargs, payload_query)

    payloads = await payload_query.gino.all()
    payloads_dump = [payload.dump() for payload in payloads]
    func_params['payload'] = payloads_dump
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(func(func_params))


def _count(params):
    payload = params['payload']
    return {"count": len(payload)}


def _percentage(params):
    payload = params['payload']
    set_size = params['set_size']
    try:
        percent = {"percentage": (len(payload) / set_size)}
    except:
        raise ValueError("Cannot divide by zero, dataset must be non-empty")
    else:
        return percent

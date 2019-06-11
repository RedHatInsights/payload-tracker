import operator
from dateutil import parser

import responses
from db import db, Payload


async def search(*args, **kwargs):
    payload_query = Payload.query
    stat_funcs = {"count": _count, "percentage": _percentage}
    basic_eq_filters = ['status', 'service', 'inventory_id', 'account',
                        'source', 'system_id', 'status_msg']
    date_group_fns = {'_lt': operator.lt, '_lte': operator.le,
                      '_gt': operator.gt, '_gte': operator.ge}
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

    for search_param_key in kwargs:
        if search_param_key in basic_eq_filters:
            search_param_value = kwargs[search_param_key]
            payload_query.append_whereclause(
                getattr(Payload, search_param_key) == search_param_value)

    for date_field in ['date', 'created_at']:
        for date_group_str, date_group_fn in date_group_fns.items():
            if date_field + date_group_str in kwargs:
                the_date = parser.parse(kwargs[date_field + date_group_str])
                payload_query.append_whereclause(
                    date_group_fn(getattr(Payload, date_field), the_date)
                )

    payloads = await payload_query.gino.all()
    payloads_dump = [payload.dump() for payload in payloads]
    func_params['payload'] = payloads_dump
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(func(func_params))


def _count(params):
    payload = params['payload']
    return {"COUNT": len(payload)}


def _percentage(params):
    payload = params['payload']
    set_size = params['set_size']
    try:
        percent = {"Percentage": (len(payload) / set_size)}
    except:
        raise ValueError("Cannot divide by zero, dataset must be non-empty")
    else:
        return percent

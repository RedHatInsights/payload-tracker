import responses
from db import db, Payload


async def search(*args, **kwargs):
    payload_query = Payload.query
    stat_funcs = {"count": _count, "percentage": _percentage}
    basic_eq_filters = ['status', 'service', 'inventory_id', 'account',
                        'source', 'system_id', 'status_msg']
    func_params = {}

    func = stat_funcs[kwargs['stat']]
    func_params['set_size'] = await db.func.count(getattr(Payload, "id")).gino.scalar()

    if 'set_constraint' in kwargs:
        set_constraint_param = kwargs['set_constraint']
        basic_eq_filters.remove(set_constraint_param)
        if set_constraint_param in kwargs:
            set_constraint_value = kwargs[set_constraint_param]
            set_size = await db.func.count(
                getattr(Payload, set_constraint_param) == set_constraint_value
            ).gino.scalar()
            func_params['set_size'] = set_size

    for search_param_key in kwargs:
        if search_param_key in basic_eq_filters:
            search_param_value = kwargs[search_param_key]
            payload_query.append_whereclause(
                getattr(Payload, search_param_key) == search_param_value)

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

import responses
import logging
import settings
from db import Payload

logger = logging.getLogger(settings.APP_NAME)


async def search(*args, **kwargs):
    logger.debug(f"Stats.search({args}, {kwargs})")
    stat_funcs = {'SuccessRate': _success_rate}
    func = stat_funcs[kwargs['stat']]
    func_params = {}

    payload_query = Payload.query

    payloads = await payload_query.gino.all()
    payloads_dump = [payload.dump() for payload in payloads]
    func_params['payload'] = payloads_dump
    if payloads is None:
        return responses.not_found()
    else:
        return responses.get(func(func_params))


def _success_rate(params):
    payloads = params['payload']
    services_dict = {}
    for payload in payloads:
        if payload['service'] not in services_dict:
            services_dict[payload['service']] = {'success': 0, 'failure': 0,
                                                 'successPercent': 0, 'failPercent': 0}
        if payload['status'] == 'success' or payload['status'] == 'successful':
            services_dict[payload['service']]['success'] += 1
        elif payload['status'] == 'error':
            services_dict[payload['service']]['failure'] += 1
    return services_dict

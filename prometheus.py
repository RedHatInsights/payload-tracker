import os
import attr
import logging
import settings
import traceback
from dateutil.parser import parse
from aiohttp.web import middleware
from prometheus_client import start_http_server, Info, Counter, Summary
from cache import redis_client, SECONDS_TO_LIVE

logger = logging.getLogger(settings.APP_NAME)


# Define prometheus configuration
PROMETHEUS_PORT = int(os.environ.get('PROMETHEUS_PORT', 8000))
SERVICE_STATUS_COUNTER = Counter('payload_tracker_service_status_counter',
                                 'Counters for services and their various statuses',
                                 ['service_name', 'status', 'source_name'])
UPLOAD_TIME_ELAPSED = Summary('payload_tracker_upload_time_elapsed',
                              'Tracks the total elapsed upload time')
UPLOAD_TIME_ELAPSED_BY_SERVICE = Summary('payload_tracker_upload_time_by_service_elapsed',
                                         'Tracks the elapsed upload time by service',
                                         ['service_name', 'source_name'])
API_RESPONSES_COUNT_BY_TYPE = Counter('payload_tracker_api_response_count',
                                      'Counter for distinct response types from API',
                                      ['status'])
MSG_COUNT_BY_PROCESSING_STATUS = Counter('payload_tracker_msg_count',
                                         'Counter for msgs processed by ["consumed", "success", "error"]',
                                         ['status'])

PAYLOAD_TRACKER_SERVICE_VERSION = Info(
    'payload_tracker_service_version',
    'Release and versioning information'
)

BUILD_NAME = os.getenv('OPENSHIFT_BUILD_NAME', 'dev')
BUILD_ID = os.getenv('OPENSHIFT_BUILD_COMMIT', 'dev')
BUILD_REF = os.getenv('OPENSHIFT_BUILD_REFERENCE', '')
BUILD_STABLE = "-stable" if BUILD_REF == "stable" else ""
if BUILD_ID and BUILD_ID != 'dev':
    BUILD_URL = ''.join(["https://console.insights-dev.openshift.com/console/",
                 "project/buildfactory/browse/builds/payload-tracker",
                 BUILD_STABLE, "/", BUILD_NAME, "?tab=logs"])
    COMMIT_URL = ("https://github.com/RedHatInsights/payload-tracker/"
                 "commit/" + BUILD_ID)
else:
    BUILD_URL = "dev"
    COMMIT_URL = "dev"
PAYLOAD_TRACKER_SERVICE_VERSION.info({'build_name': BUILD_NAME,
                              'build_commit': BUILD_ID,
                              'build_ref': BUILD_REF,
                              'build_url': BUILD_URL,
                              'commit_url': COMMIT_URL})


@middleware
async def prometheus_middleware(request, handler):
    resp = await handler(request)
    API_RESPONSES_COUNT_BY_TYPE.labels(status=resp.status).inc()
    return resp


def start_prometheus():
    logger.info("Using PROMETHEUS_PORT: %s", PROMETHEUS_PORT)
    start_http_server(PROMETHEUS_PORT)


@attr.s
class PrometheusRedisClient():
    '''
    Wraps the redis-py client with additional methods for storing and retrieving request data
    '''

    client = attr.ib()

    def get_request_data(self, request_id):
        def _decode(res):
            for k, v in res.items():
                if 'date' == k:
                    res['date'] = parse(res['date'])
                elif v == '':
                    res[k] = None
            return res

        try:
            services = self.client.lget(request_id)
            data = {s: _decode(self.client.hgetall(request_id + s)) for s in services}
        except:
            logger.error(traceback.format_exc())
        else:
            output = {}
            for k, v in data.items():
                service = k.split(':')[0]
                if service in output.keys():
                    output[service].append(v)
                else:
                    output[service] = [v]
            return output

    def is_unique(self, **kwargs):
        request_id, service, status, date, source = tuple(kwargs.values())
        resp = self.get_request_data(request_id)
        if service in resp:
            resp = resp[service]
            for entry in resp:
                unique = set()
                for k, v in entry.items():
                    if k in kwargs.keys():
                        unique.add(v == kwargs[k])
                if False not in unique:
                    return False
        return True

    def set_request_data(self, **kwargs):
        if self.is_unique(**kwargs):
            request_id, service, status, date, source = tuple(kwargs.values())
            data = {k: str(v) if v else '' for k, v in kwargs.items() if k in ['status', 'date', 'source']}
            try:
                return self.client.pipeline().hset(
                    request_id + f'{service}:{data["date"]}', mapping=data
                ).expire(
                    request_id + f'{service}:{data["date"]}', SECONDS_TO_LIVE
                ).lpush(
                    request_id, f'{service}:{data["date"]}'
                ).expire(
                    request_id, SECONDS_TO_LIVE
                ).execute()
            except:
                logger.error(traceback.format_exc())
        else:
            return False

prometheus_redis_client = PrometheusRedisClient(redis_client)

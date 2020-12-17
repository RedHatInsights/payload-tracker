import os
import logging
import settings
from aiohttp.web import middleware
from prometheus_client import start_http_server, Info, Counter, Summary

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
                                         'Counter for msgs processed by '
                                         '["consumed", "success", "error"]',
                                         ['status'])
TASKS_RUNNING_COUNT_SUMMARY = Summary('payload_tracker_tasks_running',
                                      'Tracks number of concurrently running tasks')

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

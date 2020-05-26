import os
from dateutil import parser
from dateutil.utils import default_tzinfo
from dateutil.tz import tzutc
import traceback
import json

from aiokafka import AIOKafkaConsumer
from kafkahelpers import ReconnectingClient
from prometheus_client import start_http_server, Info, Counter, Summary
from bounded_executor import BoundedExecutor
import asyncio
import connexion
import socketio
from connexion.resolver import RestyResolver

from db import init_db, db, Payload, PayloadStatus
import tracker_logging
from kibana_courier import KibanaCourier

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')
GROUP_ID = os.environ.get('GROUP_ID', 'payload_tracker')
THREAD_POOL_SIZE = int(os.environ.get('THREAD_POOL_SIZE', 8))
PAYLOAD_TRACKER_TOPIC = os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker')
API_PORT = os.environ.get('API_PORT', 8080)
KIBANA_URL = os.environ.get('KIBANA_URL')
KIBANA_COOKIES = {'_oauth_proxy': os.environ.get('KIBANA_COOKIES')}

# Prometheus configuration
DISABLE_PROMETHEUS = True if os.environ.get('DISABLE_PROMETHEUS') == "True" else False
PROMETHEUS_PORT = os.environ.get('PROMETHEUS_PORT', 8000)
SERVICE_STATUS_COUNTER = Counter('payload_tracker_service_status_counter',
                                 'Counters for services and their various statuses',
                                 ['service', 'status'])
UPLOAD_TIME_ELAPSED = Summary('payload_tracker_upload_time_elapsed',
                              'Tracks the total elapsed upload time')
UPLOAD_TIME_ELAPSED_BY_SERVICE = Summary('payload_tracker_upload_time_by_service_elapsed',
                                         'Tracks the elapsed upload time by service',
                                         ['service'])

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

# Setup logging
logger = tracker_logging.initialize_logging()

# start thread pool executor and loop
logger.info("Starting thread pool executor and asyncio loop.")
executor = BoundedExecutor(0, THREAD_POOL_SIZE)
loop = asyncio.get_event_loop()
loop.set_default_executor(executor)

# setup consumer
kafka_consumer = AIOKafkaConsumer(
    PAYLOAD_TRACKER_TOPIC, loop=loop, bootstrap_servers=BOOTSTRAP_SERVERS,
    group_id=GROUP_ID
)
CONSUMER = ReconnectingClient(kafka_consumer, "consumer")

# Setup sockets
sio = socketio.AsyncServer(async_mode='aiohttp')

# keep track of payloads and their statuses for prometheus metric counters
# payload_statuses  = {
#    '123456': {
#       'ingress': ['received', 'processing', 'success'],
#       'pup': ['received', 'processing', 'success'],
#       'advisor': ['received', 'processing', 'success']
#    }
# }
payload_statuses = {}

# payload_status_total_times = {
#    '123456': {'start':12312412, 'stop': 12312123}
# }
payload_status_total_times = {}

# payload_status_service_total_times = {
#    '123456': { 
#                  {'ingress': {'start':12312412, 'stop': 12312123},
#                  {'pup': {'start':12345}
#               }
# }
payload_status_service_total_times = {}


def check_payload_status_metrics(request_id, service, status, service_date=None):

    # Determine unique payload statuses (uniquely increment service status counts)
    unique_payload_service_and_status = True
    if request_id in payload_statuses:
        if service in payload_statuses[request_id]:
            if status in payload_statuses[request_id][service]:
                unique_payload_service_and_status = False
        else:
            payload_statuses[request_id][service] = list()
    else:
        payload_statuses[request_id] = {}
        payload_statuses[request_id][service] = list()

    if unique_payload_service_and_status:
        payload_statuses[request_id][service].append(status)
        SERVICE_STATUS_COUNTER.labels(service=service, status=status).inc()

    # Clean up anything we don't still need to track in memory
    if status in ['error', 'success', 'announced']:
        try:
            if service == 'insights-advisor-service':
                del payload_statuses[request_id]
            else:
                del payload_statuses[request_id][service]
        except:
            logger.info(f"Could not delete payload status cache for "
                        f"{request_id} - {service} - {status}")

    # Determine TOTAL Upload elapsed times (ingress all the way to advisor)
    try:
        if service == 'ingress' and status == 'received':
            payload_status_total_times[request_id] = {}
            payload_status_total_times[request_id]['start'] = service_date
        if service == 'insights-advisor-service' and status == 'success':
            start = payload_status_total_times[request_id]['start']
            stop = service_date
            elapsed = (stop - start).total_seconds()
            UPLOAD_TIME_ELAPSED.observe(elapsed)

        # Clean up memory
        if service == 'ingress' and status == 'error':
            del payload_status_total_times[request_id]
        if service == 'advisor-pup' and status == 'error':
            del payload_status_total_times[request_id]
        if service == 'insights-advisor-service' and status in ['success', 'error']:
            del payload_status_total_times[request_id]
    except:
        logger.info(f"Could not update payload status total upload time for "
                    f"{request_id} - {service} - {status}")


    # Determine elapsed times PER SERVICE INDIVIDUALLY
    try:
        # Determine ingress (at some point we should probably subtract the elapsed time for pup here)
        # The flow is ingress -> pup -> ingress -> advisor service (currently)
        # This will need to change when PUPTOO becomes a thing
        if service == 'ingress' and status == 'received':
            payload_status_service_total_times[request_id] = {}
            payload_status_service_total_times[request_id]['ingress'] = {}
            payload_status_service_total_times[request_id]['ingress']['start'] = service_date
        if service == 'ingress' and status == 'announced':
            start = payload_status_service_total_times[request_id]['ingress']['start']
            stop = service_date
            elapsed = (stop - start).total_seconds()
            UPLOAD_TIME_ELAPSED_BY_SERVICE.labels(service=service).observe(elapsed)
            del payload_status_service_total_times[request_id]['ingress']
        # Determine pup
        if service == 'advisor-pup' and status == 'processing':
            payload_status_service_total_times[request_id]['advisor-pup'] = {}
            payload_status_service_total_times[request_id]['advisor-pup']['start'] = service_date
        if service == 'advisor-pup' and status == 'success':
            start = payload_status_service_total_times[request_id]['advisor-pup']['start']
            stop = service_date
            elapsed = (stop - start).total_seconds()
            UPLOAD_TIME_ELAPSED_BY_SERVICE.labels(service=service).observe(elapsed)
            del payload_status_service_total_times[request_id]['advisor-pup']
        # Determine advisor
        if service == 'insights-advisor-service' and status == 'received':
            payload_status_service_total_times[request_id]['insights-advisor-service'] = {}
            payload_status_service_total_times[request_id]['insights-advisor-service']['start'] = service_date
        if service == 'insights-advisor-service' and status == 'success':
            start = payload_status_service_total_times[request_id]['insights-advisor-service']['start']
            stop = service_date
            elapsed = (stop - start).total_seconds()
            UPLOAD_TIME_ELAPSED_BY_SERVICE.labels(service=service).observe(elapsed)

        # Clean up any errors
        if service == 'ingress' and status == 'error':
            del payload_status_service_total_times[request_id]
        if service == 'advisor-pup' and status == 'error':
            del payload_status_service_total_times[request_id]
        if service == 'insights-advisor-service' and status in ['success', 'error']:
            del payload_status_service_total_times[request_id]

    except:
        logger.info(f"Could not update payload status service elapsed time for "
                    f"{request_id} - {service} - {status}")



# Setup Kibana courier
query_kibana = KibanaCourier(loop, logger, KIBANA_URL, KIBANA_COOKIES, check_payload_status_metrics)


@sio.event
async def connect(sid, environ):
    logger.info('Socket connected: %s', sid)


@sio.event
async def disconnect(sid):
    logger.info('Socket disconnected: %s', sid)


async def process_payload_status(json_msgs):
    logger.info(f"Processing messages: {json_msgs}")
    for msg in json_msgs:
        logger.info(f"Processing Payload Message {msg.value}")
        data = None

        try:
            data = json.loads(msg.value)
        except Exception:
            logger.exception("process_payload_status(): unable to decode msg as json: %s", msg.value)
            continue

        if data:
            logger.info("Payload message processed as JSON.")

            # Check for missing keys
            expected_keys = ["service", "request_id", "status", "date"]
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                logger.info(f"Payload {data} missing keys {missing_keys}. Expected {expected_keys}")
                continue

            # make things lower-case
            data['service'] = data['service'].lower()
            data['status'] = data['status'].lower()

            logger.info("Payload message has expected keys. Begin sanitizing")
            # sanitize the payload status
            sanitized_payload = {'request_id': data['request_id']}
            for key in ['inventory_id', 'system_id', 'account']:
                if key in data:
                    sanitized_payload[key] = data[key]

            # check if not request_id in Payloads Table and update columns
            try:
                payload = await Payload.query.where(
                    Payload.request_id == sanitized_payload['request_id']
                ).gino.all()

                logger.info(f"Sanitized Payload for DB {sanitized_payload}")
                if len(payload) == 1:
                    payload_dump = payload[0].dump()
                    values = {k: v for k, v in sanitized_payload.items() if k not in payload_dump or payload_dump[k] is None}
                    if len(values) > 0:
                        await Payload.update.values(**values).where(
                            Payload.request_id == sanitized_payload['request_id']
                        ).gino.status()
                else:
                    try:
                        async with db.transaction():
                            payload_to_create = Payload(**sanitized_payload)
                            created_payload = await payload_to_create.create()
                            dump = created_payload.dump()
                            logger.info(f"DB Transaction {created_payload} - {dump}")
                    except:
                        logger.error(f'Failed to insert Payload into Table -- will retry')
                        payload_dump = payload[0].dump()
                        values = {k: v for k, v in sanitized_payload.items() if k not in payload_dump or payload_dump[k] is None}
                        if len(values) > 0:
                            await Payload.update.values(**values).where(
                                Payload.request_id == sanitized_payload['request_id']
                            ).gino.status()
            except:
                logger.error(f"Failed to parse message with Error: {traceback.format_exc()}")
                continue

            sanitized_payload_status = {
                'service': data['service'],
                'request_id': data['request_id'],
                'status': data['status']
            }

            for key in ['status_msg', 'source']:
                if key in data:
                    sanitized_payload_status[key] = data[key]

            if 'date' in data:
                try:
                    sanitized_payload_status['date'] = default_tzinfo(parser.parse(data['date']), tzutc()).astimezone(tzutc())
                except:
                    the_error = traceback.format_exc()
                    logger.error(f"Error parsing date: {the_error}")

            # Increment Prometheus Metrics
            check_payload_status_metrics(sanitized_payload_status['request_id'],
                                         sanitized_payload_status['service'],
                                         sanitized_payload_status['status'],
                                         sanitized_payload_status['date'])

            logger.info(f"Sanitized Payload Status for DB {sanitized_payload_status}")
            # insert into database
            try:
                async with db.transaction():
                    payload_status_to_create = PayloadStatus(**sanitized_payload_status)
                    created_payload_status = await payload_status_to_create.create()
                    dump = created_payload_status.dump()
                    logger.info(f"DB Transaction {created_payload_status} - {dump}")
                    dump['date'] = str(dump['date'])
                    dump['created_at'] = str(dump['created_at'])
                    await sio.emit('payload', dump)
            except:
                logger.error(f"Failed to parse message with Error: {traceback.format_exc()}")
                continue
        else:
            continue


async def consume(client):
    data = await client.getmany()
    for tp, msgs in data.items():
        logger.info("Received messages: %s", msgs)
        loop.create_task(process_payload_status(msgs))
    await asyncio.sleep(0.1)


async def setup_db():
    app = {}
    await init_db()
    app['db'] = db
    return app


def setup_api():
    app = connexion.AioHttpApp(__name__, specification_dir='swagger/')
    app.add_api('api.spec.yaml', resolver=RestyResolver('api'))
    return app

async def setup_periodic_kibana_query():
    while True:
        logger.info("Querying Kibana for new payloads")
        await query_kibana()
        await asyncio.sleep(30, loop=loop)


def start_prometheus():
    start_http_server(PROMETHEUS_PORT)


if __name__ == "__main__":
    try:
        logger.info('Starting Payload Tracker Service')

        # Log env vars / settings
        logger.info("Using LOG_LEVEL: %s", LOG_LEVEL)
        logger.info("Using BOOTSTRAP_SERVERS: %s", BOOTSTRAP_SERVERS)
        logger.info("Using GROUP_ID: %s", GROUP_ID)
        logger.info("Using THREAD_POOL_SIZE: %s", THREAD_POOL_SIZE)
        logger.info("Using PAYLOAD_TRACKER_TOPIC: %s", PAYLOAD_TRACKER_TOPIC)
        logger.info("Using DISABLE_PROMETHEUS: %s", DISABLE_PROMETHEUS)
        logger.info("Using PROMETHEUS_PORT: %s", PROMETHEUS_PORT)
        logger.info("Using Kibana URL: %s", KIBANA_URL)
        logger.info("Using Kibana Cookies: %s", KIBANA_COOKIES)

        # setup the connexion app
        logger.info("Setting up REST API")
        app = setup_api()

        # start prometheus
        if not DISABLE_PROMETHEUS:
            logger.info('Starting Payload Tracker Prometheus Server')
            start_prometheus()

        # add consumer callbacks
        logger.info('Starting Kafka consumer for Payload status messages.')
        loop.create_task(CONSUMER.get_callback(consume)())

        # setup http app and db
        logger.info("Setting up Database")
        loop.create_task(setup_db())

        # setup sockets
        logger.info("Setting up sockets")
        sio.attach(app.app)

        # setup kibana query
        if os.environ.get('KIBANA_URL'):
            logger.info("Setting up Kibana Courier")
            loop.create_task(setup_periodic_kibana_query())

        # loops
        logger.info("Running...")
        app.run(port=API_PORT)
    except:
        the_error = traceback.format_exc()
        logger.error(f"Failed starting Payload Tracker with Error: {the_error}")
        # Shut down loop
        loop.stop()

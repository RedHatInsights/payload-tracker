import os
from dateutil import parser
import traceback
import json

from aiokafka import AIOKafkaConsumer
from kafkahelpers import ReconnectingClient
from prometheus_client import start_http_server, Info, Counter
from bounded_executor import BoundedExecutor
import asyncio
import connexion
import socketio
from connexion.resolver import RestyResolver

from db import init_db, db, Payload
import tracker_logging

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')
GROUP_ID = os.environ.get('GROUP_ID', 'payload_tracker')
THREAD_POOL_SIZE = int(os.environ.get('THREAD_POOL_SIZE', 8))
PAYLOAD_TRACKER_TOPIC = os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker')
API_PORT = os.environ.get('API_PORT', 8080)

# Prometheus configuration
DISABLE_PROMETHEUS = True if os.environ.get('DISABLE_PROMETHEUS') == "True" else False
PROMETHEUS_PORT = os.environ.get('PROMETHEUS_PORT', 8000)
SERVICE_STATUS_COUNTER = Counter('payload_tracker_service_status_counter',
                                 'Counters for services and their various statuses',
                                 ['service', 'status'])

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
#       'pup': ['rceived', 'processing', 'success'],
#       'advisor': ['received', 'processing', 'success']
#    }
# }
payload_statuses = {}


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

            # HACK: For now just copy in request_id (if present) as payload_id
            # At some point we need to redo the verbiage terminology
            # payload_id (legacy) and request_id (new) are synonymous
            if 'request_id' in data:
                data['payload_id'] = data['request_id']

            # Check for missing keys
            expected_keys = ["service", "payload_id", "status"]
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                logger.info(f"Payload {data} missing keys {missing_keys}. Expected {expected_keys}")
                continue

            # Increment Prometheus Metrics
            check_payload_status_metrics(data['payload_id'], data['service'], data['status'])

            logger.info("Payload message has expected keys. Begin sanitizing")
            # sanitize the payload status
            sanitized_payload_status = {
                'service': data['service'],
                'payload_id': data['payload_id'],
                'status': data['status']
            }
            for key in ['inventory_id', 'system_id', 'status_msg', 'source', 'account']:
                if key in data:
                    sanitized_payload_status[key] = data[key]

            if 'date' in data:
                try:
                    sanitized_payload_status['date'] = parser.parse(data['date'])
                except:
                    the_error = traceback.format_exc()
                    logger.error(f"Error parsing date: {the_error}")

            logger.info(f"Sanitized Payload for DB {sanitized_payload_status}")
            # insert into database
            async with db.transaction():
                payload_to_create = Payload(**sanitized_payload_status)
                created_payload = await payload_to_create.create()
                dump = created_payload.dump()
                logger.info(f"DB Transaction {created_payload} - {dump}")
                dump['date'] = str(dump['date'])
                dump['created_at'] = str(dump['created_at'])
                await sio.emit('payload', dump)

        else:
            continue


def check_payload_status_metrics(payload_id, service, status):
    unique_payload_service_and_status = True

    if payload_id in payload_statuses:
        if service in payload_statuses[payload_id]:
            if status in payload_statuses[payload_id][service]:
                unique_payload_service_and_status = False
    else:
        payload_statuses[payload_id] = {}
        payload_statuses[payload_id][service] = list()

    if unique_payload_service_and_status:
        payload_statuses[payload_id][service].append(status)
        SERVICE_STATUS_COUNTER.labels(service=service, status=status).inc()


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

        # loops
        logger.info("Running...")
        app.run(port=API_PORT)
    except:
        the_error = traceback.format_exc()
        logger.error(f"Failed starting Payload Tracker with Error: {the_error}")
        # Shut down loop
        loop.stop()

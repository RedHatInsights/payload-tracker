import os
import time
from dateutil import parser
from dateutil.utils import default_tzinfo
from dateutil.tz import tzutc
from datetime import timedelta
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

from db import init_db, db, Payload, PayloadStatus, tables
from cache import cache
import tracker_logging

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')
GROUP_ID = os.environ.get('GROUP_ID', 'payload_tracker')
THREAD_POOL_SIZE = int(os.environ.get('THREAD_POOL_SIZE', 8))
PAYLOAD_TRACKER_TOPIC = os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker')
API_PORT = os.environ.get('API_PORT', 8080)
ENABLE_SOCKETS = os.environ.get('ENABLE_SOCKETS', "").lower() == "true"

# Prometheus configuration
DISABLE_PROMETHEUS = True if os.environ.get('DISABLE_PROMETHEUS') == "True" else False
PROMETHEUS_PORT = os.environ.get('PROMETHEUS_PORT', 8000)
SERVICE_STATUS_COUNTER = Counter('payload_tracker_service_status_counter',
                                 'Counters for services and their various statuses',
                                 ['service_name', 'status'])
UPLOAD_TIME_ELAPSED = Summary('payload_tracker_upload_time_elapsed',
                              'Tracks the total elapsed upload time')
UPLOAD_TIME_ELAPSED_BY_SERVICE = Summary('payload_tracker_upload_time_by_service_elapsed',
                                         'Tracks the elapsed upload time by service',
                                         ['service_name'])

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
if ENABLE_SOCKETS:
    sio = socketio.AsyncServer(async_mode='aiohttp')

    @sio.event
    async def connect(sid, environ):
        logger.debug('Socket connected: %s', sid)

    @sio.event
    async def disconnect(sid):
        logger.debug('Socket disconnected: %s', sid)


# collects duration data and emits via sio as payloads are processed
# accumulated_durations = {
#   request_id: {
#     recorded: time.time(),
#     services: {
#       service: [
#         datetime(), datetime(), ...
#       ]
#     }
#   }
# }
accumulated_durations = {}

async def clean_durations():
    threshold = timedelta(int(os.environ.get('DURATIONS_DELETION_THRESHOLD', 60)))
    interval = int(os.environ.get('DURATIONS_DELETION_INTERVAL', 20))
    while True:
        await asyncio.sleep(interval, loop=loop)
        ids_to_delete = []
        for request_id, payload in accumulated_durations.items():
            now = time.time()
            if 'recorded' in payload and timedelta(now - payload['recorded']) > threshold:
                ids_to_delete.append(request_id)
        for request_id in ids_to_delete:
            logger.debug(f'Removing record for payload with request_id: {request_id}')
            del accumulated_durations[request_id]


async def accumulate_payload_durations(payload):
    def _calculate_total_time(p_id):
        times = []
        for service in accumulated_durations[p_id]['services']:
            times.extend([time for time in accumulated_durations[p_id]['services'][service]])
        times.sort()
        return times[-1] - times[0]

    def _calculate_indiv_service_time(p_id, p_service):
        times = [time for time in accumulated_durations[p_id]['services'][p_service]]
        times.sort()
        return times[-1] - times[0]

    def _calculate_total_service_time(p_id):
        total = timedelta(0)
        for service in accumulated_durations[p_id]['services']:
            total += _calculate_indiv_service_time(p_id, service)
        return total

    async def _emit(request_id, key, data):
        if ENABLE_SOCKETS:
            await sio.emit('duration', {'id': request_id, 'key': key, 'data': data })

    logger.debug(f'Preparing for duration emission with payload: {payload}')

    # scrub payload for tokens
    p_id = payload['request_id']
    p_status = payload['status']
    p_service = payload['service']
    p_date = payload['date']

    # append or remove payload from dictionary
    if p_id in accumulated_durations:
        if p_service in accumulated_durations[p_id]['services']:
            accumulated_durations[p_id]['services'][p_service].append(p_date)
        else:
            accumulated_durations[p_id]['services'][p_service] = [p_date]
    else:
        accumulated_durations[p_id] = {'services': {p_service: [p_date]}}

    accumulated_durations[p_id]['recorded'] = time.time()

    await _emit(p_id, 'total_time_in_services', str(_calculate_total_service_time(p_id)))
    await _emit(p_id, 'total_time', str(_calculate_total_time(p_id)))
    await _emit(p_id, p_service, str(_calculate_indiv_service_time(p_id, p_service)))


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


##### TODO: clean these properly
async def clean_statuses():
    interval = int(os.environ.get('STATUS_DELETION_INTERVAL', 60))
    while True:
        await asyncio.sleep(interval, loop=loop)
        payload_statuses.clear()
        payload_status_total_times.clear()
        payload_status_service_total_times.clear()

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
        SERVICE_STATUS_COUNTER.labels(service_name=service, status=status).inc()

    # Clean up anything we don't still need to track in memory
    if status in ['error', 'success', 'announced']:
        try:
            if service == 'insights-advisor-service':
                del payload_statuses[request_id]
            else:
                del payload_statuses[request_id][service]
        except:
            logger.debug(f"Could not delete payload status cache for "
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
        logger.debug(f"Could not update payload status total upload time for "
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
            UPLOAD_TIME_ELAPSED_BY_SERVICE.labels(service_name=service).observe(elapsed)
            del payload_status_service_total_times[request_id]['ingress']
        # Determine pup
        if service == 'advisor-pup' and status == 'processing':
            payload_status_service_total_times[request_id]['advisor-pup'] = {}
            payload_status_service_total_times[request_id]['advisor-pup']['start'] = service_date
        if service == 'advisor-pup' and status == 'success':
            start = payload_status_service_total_times[request_id]['advisor-pup']['start']
            stop = service_date
            elapsed = (stop - start).total_seconds()
            UPLOAD_TIME_ELAPSED_BY_SERVICE.labels(service_name=service).observe(elapsed)
            del payload_status_service_total_times[request_id]['advisor-pup']
        # Determine advisor
        if service == 'insights-advisor-service' and status == 'received':
            payload_status_service_total_times[request_id]['insights-advisor-service'] = {}
            payload_status_service_total_times[request_id]['insights-advisor-service']['start'] = service_date
        if service == 'insights-advisor-service' and status == 'success':
            start = payload_status_service_total_times[request_id]['insights-advisor-service']['start']
            stop = service_date
            elapsed = (stop - start).total_seconds()
            UPLOAD_TIME_ELAPSED_BY_SERVICE.labels(service_name=service).observe(elapsed)

        # Clean up any errors
        if service == 'ingress' and status == 'error':
            del payload_status_service_total_times[request_id]
        if service == 'advisor-pup' and status == 'error':
            del payload_status_service_total_times[request_id]
        if service == 'insights-advisor-service' and status in ['success', 'error']:
            del payload_status_service_total_times[request_id]

    except:
        logger.debug(f"Could not update payload status service elapsed time for "
                    f"{request_id} - {service} - {status}")


async def process_payload_status(json_msgs):
    logger.debug(f"Processing messages: {json_msgs}")
    for msg in json_msgs:
        logger.debug(f"Processing Payload Message {msg.value}")
        data = None

        try:
            data = json.loads(msg.value)
        except Exception:
            logger.exception("process_payload_status(): unable to decode msg as json: %s", msg.value)
            continue

        if data:
            logger.debug("Payload message processed as JSON.")

            # ensure data is of type string
            for key in data:
                data[key] = str(data[key])

            # Check for missing keys
            expected_keys = ["service", "request_id", "status", "date"]
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                logger.debug(f"Payload {data} missing keys {missing_keys}. Expected {expected_keys}")
                continue

            if data['request_id'] == '-1':
                logger.debug(f"Payload {data} has request_id -1.")
                continue

            # make things lower-case
            data['service'] = data['service'].lower()
            data['status'] = data['status'].lower()
            if 'source' in data:
                data['source'] = data['source'].lower()

            logger.debug("Payload message has expected keys. Begin sanitizing")
            # sanitize the payload status
            sanitized_payload = {'request_id': data['request_id']}
            for key in ['inventory_id', 'system_id', 'account']:
                if key in data:
                    sanitized_payload[key] = data[key]

            sanitized_payload_status = {}

            # define method for retrieving values
            async def get_payload():
                payload = await Payload.query.where(Payload.request_id == data['request_id']).gino.all()
                return payload[0].dump() if len(payload) > 0 else None
            # check if not request_id in Payloads Table and update columns
            try:
                payload_dump = await get_payload()
                logger.info(f"Sanitized Payload for DB {sanitized_payload}")
                if payload_dump:
                    sanitized_payload_status['payload_id'] = payload_dump['id']
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
                            sanitized_payload_status['payload_id'] = dump['id']
                            logger.debug(f"DB Transaction {created_payload} - {dump}")
                    except:
                        logger.error(f'Failed to insert Payload into Table -- will retry update')
                        payload_dump = await get_payload()
                        if payload_dump:
                            sanitized_payload_status['payload_id'] = payload_dump['id']
                            values = {k: v for k, v in sanitized_payload.items() if k not in payload_dump or payload_dump[k] is None}
                            if len(values) > 0:
                                await Payload.update.values(**values).where(
                                    Payload.request_id == sanitized_payload['request_id']
                                ).gino.status()
            except:
                logger.error(f"Failed to parse message with Error: {traceback.format_exc()}")
                continue

            # check if service/source is not in table
            for column_name, table_name in zip(['service', 'source', 'status'], ['services', 'sources', 'statuses']):
                current_column_items = cache.get_value(table_name)
                if column_name in data:
                    try:
                        if not data[column_name] in current_column_items.values():
                            async with db.transaction():
                                payload = {'name': data[column_name]}
                                to_create = tables[table_name](**payload)
                                created_value = await to_create.create()
                                dump = created_value.dump()
                                cache.set_value(table_name, {dump['id']: dump['name']})
                                logger.debug(f'DB Transaction {payload} - {dump}')
                                sanitized_payload_status[f'{column_name}_id'] = dump['id']
                        else:
                            cached_key = [k for k, v in current_column_items.items() if v == data[column_name]][0]
                            sanitized_payload_status[f'{column_name}_id'] = cached_key
                    except:
                        logger.error(f'Failed to add {column_name} with Error: {traceback.format_exc()}')
                        continue

            if 'status_msg' in data:
                sanitized_payload_status['status_msg'] = data['status_msg']

            if 'date' in data:
                try:
                    sanitized_payload_status['date'] = default_tzinfo(parser.parse(data['date']), tzutc()).astimezone(tzutc())
                except:
                    the_error = traceback.format_exc()
                    logger.error(f"Error parsing date: {the_error}")

            # Add payload to durations
            await accumulate_payload_durations({**data, 'date': sanitized_payload_status['date']})

            # Increment Prometheus Metrics
            check_payload_status_metrics(sanitized_payload_status['payload_id'],
                                         data['service'],
                                         data['status'],
                                         sanitized_payload_status['date'])

            logger.info(f"Sanitized Payload Status for DB {sanitized_payload_status}")
            # insert into database
            try:
                async with db.transaction():
                    payload_status_to_create = PayloadStatus(**sanitized_payload_status)
                    created_payload_status = await payload_status_to_create.create()
                    dump = created_payload_status.dump()
                    logger.debug(f"DB Transaction {created_payload_status} - {dump}")
                    dump['date'] = str(dump['date'])
                    dump['created_at'] = str(dump['created_at'])
                    # change id values back to strings for sockets
                    dump['request_id'] = data['request_id']
                    del dump['payload_id']
                    for column in ['service', 'source', 'status']:
                        if column in data:
                            dump[column] = data[column]
                            del dump[f'{column}_id']
                    if ENABLE_SOCKETS:
                        await sio.emit('payload', dump)
            except:
                logger.error(f"Failed to parse message with Error: {traceback.format_exc()}")
                continue
        else:
            continue


async def consume(client):
    data = await client.getmany()
    for tp, msgs in data.items():
        logger.debug("Received messages: %s", msgs)
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


async def update_current_services_and_sources(db):
    for table in ['services', 'sources', 'statuses']:
        res = await db.select([tables[table]]).gino.all()
        cache.set_value(table, dict(res))


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
        db = loop.run_until_complete(setup_db())['db']

        # update current services and sources
        logger.info("Adding current services and sources to memory")
        loop.create_task(update_current_services_and_sources(db))

        # setup sockets
        if ENABLE_SOCKETS:
            logger.info("Setting up sockets")
            sio.attach(app.app)

        # clean durations and statuses
        loop.create_task(clean_durations())
        loop.create_task(clean_statuses())

        # loops
        logger.info("Running...")
        app.run(port=API_PORT)
    except:
        the_error = traceback.format_exc()
        logger.error(f"Failed starting Payload Tracker with Error: {the_error}")
        # Shut down loop
        loop.stop()

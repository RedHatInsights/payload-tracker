import os
import time
from dateutil import parser
from dateutil.utils import default_tzinfo
from dateutil.tz import tzutc
from datetime import timedelta
import traceback
import json

from bounded_executor import BoundedExecutor
import asyncio
import connexion
import socketio
from connexion.resolver import RestyResolver

from db import init_db, db, Payload, PayloadStatus, tables
from prometheus import (
    start_prometheus, prometheus_middleware, SERVICE_STATUS_COUNTER,
    UPLOAD_TIME_ELAPSED_BY_SERVICE, MSG_COUNT_BY_PROCESSING_STATUS, API_RESPONSES_COUNT_BY_TYPE)
from utils import Triple, TripleSet
from cache import cache
import tracker_logging
from kafka_consumer import consumer

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
THREAD_POOL_SIZE = int(os.environ.get('THREAD_POOL_SIZE', 8))
API_PORT = os.environ.get('API_PORT', 8080)
ENABLE_SOCKETS = os.environ.get('ENABLE_SOCKETS', "").lower() == "true"
VALIDATE_REQUEST_ID = os.environ.get('VALIDATE_REQUEST_ID', "true").lower() == "true"
VALIDATE_REQUEST_ID_LENGTH = os.environ.get('VALIDATE_REQUEST_ID_LENGTH', 32)
DISABLE_PROMETHEUS = True if os.environ.get('DISABLE_PROMETHEUS') == "True" else False

# Setup logging
logger = tracker_logging.initialize_logging()

# start thread pool executor and loop
logger.info("Starting thread pool executor and asyncio loop.")
executor = BoundedExecutor(0, THREAD_POOL_SIZE)
loop = asyncio.get_event_loop()
loop.set_default_executor(executor)

# Setup sockets
if ENABLE_SOCKETS:
    sio = socketio.AsyncServer(async_mode='aiohttp')

    @sio.event
    async def connect(sid, environ):
        logger.debug('Socket connected: %s', sid)

    @sio.event
    async def disconnect(sid):
        logger.debug('Socket disconnected: %s', sid)


# Keep track of payloads and their statuses for prometheus metric counters and sockets
# Note: we are using a custom class to define the list of service statuses
# payload_statuses  = {
#   request_id: {
#       'recorded': time.time(),
#       'services': {
#          'ingress': [('success', None): datetime(), ...]
#          'insights-advisor-service': [('processing', None): datetime(), ...]
#          ...
#       }
#    }
# }
payload_statuses = {}

async def clean_statuses():
    threshold = int(os.environ.get('STATUS_DELETION_THRESHOLD', 60))
    interval = int(os.environ.get('STATUS_DELETION_INTERVAL', 20))
    while True:
        await asyncio.sleep(interval, loop=loop)
        ids_to_delete = []
        for request_id, payload in payload_statuses.items():
            if time.time() - payload['recorded'] > threshold:
                ids_to_delete.append(request_id)
        for request_id in ids_to_delete:
            try:
                del payload_statuses[request_id]
            except:
                continue


async def evaluate_status_metrics(**kwargs):
    request_id, service, status, date, source = tuple(kwargs.values())

    def calculate_upload_time(request_id):
        times = [time for service in payload_statuses[request_id]['services'].values() for time in service.values()]
        times.sort()
        return (times[-1] - times[0]).total_seconds()

    def calculate_service_time_by_source(request_id, service, source):
        times = [value for key, value in payload_statuses[request_id]['services'][service].items() if key[1] == source]
        times.sort()
        return (times[-1] - times[0]).total_seconds()

    def calculate_total_service_time(request_id):
        service_to_sources = {}
        for service, data in payload_statuses[request_id]['services'].items():
            service_to_sources[service] = set([source for status, source in data.keys()])
        return sum([calculate_service_time_by_source(
            request_id, service, source) for service, sources in service_to_sources.items() for source in sources])

    def is_service_passed_for_source():
        return status in ['success', 'error'] and ('received', source) in payload_statuses[request_id]['services'][service].keys()

    async def emit(request_id, key, data):
        await sio.emit('duration', {'id': request_id, 'key': key, 'data': data })

    def determine_uniqueness():
        if request_id in payload_statuses:
            if service in payload_statuses[request_id]['services'].keys():
                if (status, source) in payload_statuses[request_id]['services'][service].keys():
                    dates = [v for k, v in payload_statuses[request_id]['services'][service].items() if k == (status, source)]
                    if date in dates:
                        return False
                    else:
                        payload_statuses[request_id]['services'][service].append(Triple(status, source, date))
                else:
                    payload_statuses[request_id]['services'][service].append(Triple(status, source, date))
            else:
                payload_statuses[request_id]['services'][service] = TripleSet(Triple(status, source, date))
        else:
            payload_statuses[request_id] = {'services': {service: TripleSet(Triple(status, source, date))}}
        payload_statuses[request_id]['recorded'] = time.time()
        return True

    # Add payload to payload_statuses and determine uniqueness
    if determine_uniqueness():
        # evaluate prometheus metrics if not disabled
        # TODO: Add functionality for UPLOAD_TIME_ELAPSED prometheus metric
        if not DISABLE_PROMETHEUS:
            SERVICE_STATUS_COUNTER.labels(service_name=service, status=status, source_name=source).inc()
            if is_service_passed_for_source():
                UPLOAD_TIME_ELAPSED_BY_SERVICE.labels(service_name=service, source_name=source).observe(
                    calculate_service_time_by_source(request_id, service, source))

    # emit upload if sockets enabled
    if ENABLE_SOCKETS:
        await emit(request_id, 'total_time_in_services', str(
            timedelta(seconds=calculate_total_service_time(request_id))))
        await emit(request_id, 'total_time', str(
            timedelta(seconds=calculate_upload_time(request_id))))
        await emit(request_id, service, str(
            timedelta(seconds=calculate_service_time_by_source(request_id, service, source))))


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

            if VALIDATE_REQUEST_ID and (len(data['request_id']) > VALIDATE_REQUEST_ID_LENGTH):
                logger.debug(f"Payload {data} has invalid request_id length.")
                continue

            # make things lower-case
            data['service'] = data['service'].lower()
            data['status'] = data['status'].lower()
            if 'source' in data:
                data['source'] = data['source'].lower()

            logger.debug("Payload message has expected keys. Begin sanitizing")
            MSG_COUNT_BY_PROCESSING_STATUS.labels(status="consumed").inc()
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
                MSG_COUNT_BY_PROCESSING_STATUS.labels(status="error").inc()
                continue

            try:
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
                        except Exception as err:
                            raise err
            except:
                logger.error(f'Failed to add {column_name} with Error: {traceback.format_exc()}')
                MSG_COUNT_BY_PROCESSING_STATUS.labels(status="error").inc()
                continue

            if 'status_msg' in data:
                sanitized_payload_status['status_msg'] = data['status_msg']

            if 'date' in data:
                try:
                    sanitized_payload_status['date'] = default_tzinfo(parser.parse(data['date']), tzutc()).astimezone(tzutc())
                except:
                    the_error = traceback.format_exc()
                    logger.error(f"Error parsing date: {the_error}")
                    MSG_COUNT_BY_PROCESSING_STATUS.labels(status="error").inc()
                    continue

            # Increment Prometheus Metrics
            if not DISABLE_PROMETHEUS or ENABLE_SOCKETS:
                await evaluate_status_metrics(**{
                    'request_id': data['request_id'],
                    'service': data['service'],
                    'status': data['status'],
                    'date': sanitized_payload_status['date'],
                    'source': None if 'source' not in data else data['source']
                })

            logger.info(f"Sanitized Payload Status for DB {sanitized_payload_status}")
            # insert into database
            async def insert_status(sanitized_payload_status):
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
            try:
                await insert_status(sanitized_payload_status)
            except Exception as err:
                logger.error(f'Failed to insert PayloadStatus with ERROR: {err}')
                # First, we assume there is no partition. If there is a further error, simply try reinsertion
                try:
                    date = sanitized_payload_status['date']
                    await db.bind.scalar(f'SELECT create_partition(\'{date}\'::DATE, \'{date}\'::DATE + INTERVAL \'1 DAY\');')
                    await insert_status(sanitized_payload_status)
                except Exception as err:
                    logger.error(f'Failed to insert PayloadStatus with ERROR: {err}')
                    try:
                        await insert_status(sanitized_payload_status)
                    except Exception as err:
                        logger.error(f'Failed to insert PayloadStatus with ERROR: {err}')
                        MSG_COUNT_BY_PROCESSING_STATUS.labels(status="error").inc()
                        continue
            MSG_COUNT_BY_PROCESSING_STATUS.labels(status="success").inc()
        else:
            continue


async def consume(consumer):
    data = await consumer.getmany()
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
    app = connexion.AioHttpApp(
        __name__, specification_dir='swagger/', server_args={'middlewares': [prometheus_middleware]})
    app.add_api('api.spec.yaml', resolver=RestyResolver('api'))
    return app


async def update_current_services_and_sources(db):
    for table in ['services', 'sources', 'statuses']:
        res = await db.select([tables[table]]).gino.all()
        cache.set_value(table, dict(res))


if __name__ == "__main__":
    try:
        logger.info('Starting Payload Tracker Service')

        # Log env vars / settings
        logger.info("Using LOG_LEVEL: %s", LOG_LEVEL)
        logger.info("Using THREAD_POOL_SIZE: %s", THREAD_POOL_SIZE)
        logger.info("Using DISABLE_PROMETHEUS: %s", DISABLE_PROMETHEUS)

        # setup the connexion app
        logger.info("Setting up REST API")
        app = setup_api()

        # start prometheus
        if not DISABLE_PROMETHEUS:
            logger.info('Starting Payload Tracker Prometheus Server')
            start_prometheus()

        # setup http app and db
        logger.info("Setting up Database")
        db = loop.run_until_complete(setup_db())['db']

        # update current services and sources
        logger.info("Adding current services and sources to memory")
        loop.run_until_complete(update_current_services_and_sources(db))

        # start consumer and add callbacks
        logger.info('Starting Kafka consumer for Payload status messages.')
        loop.create_task(consumer.run(consume))

        # setup sockets
        if ENABLE_SOCKETS:
            logger.info("Setting up sockets")
            sio.attach(app.app)

        # clean durations and metrics
        if not DISABLE_PROMETHEUS or ENABLE_SOCKETS:
            loop.create_task(clean_statuses())

        # loops
        logger.info("Running...")
        app.run(port=API_PORT)
    except:
        the_error = traceback.format_exc()
        logger.error(f"Failed starting Payload Tracker with Error: {the_error}")
        # Shut down loop
        loop.stop()

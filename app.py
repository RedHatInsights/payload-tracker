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
from connexion.resolver import RestyResolver

from db import init_db, db, Payload, PayloadStatus, tables
from prometheus import (
    start_prometheus, prometheus_middleware, prometheus_redis_client,
    SERVICE_STATUS_COUNTER, UPLOAD_TIME_ELAPSED_BY_SERVICE, MSG_COUNT_BY_PROCESSING_STATUS)
from cache import redis_client
import tracker_logging
from kafka_consumer import consumer

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
THREAD_POOL_SIZE = int(os.environ.get('THREAD_POOL_SIZE', 8))
API_PORT = int(os.environ.get('API_PORT', 8080))
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


def evaluate_status_metrics(**kwargs):
    logger.debug(f"Processing metrics for message: {kwargs}")
    # the method set_request_data first validates the uniqueness of the message
    if prometheus_redis_client.set_request_data(**kwargs):
        request_id, service, status, date, source = tuple(kwargs.values())
        data = prometheus_redis_client.get_request_data(request_id)

        def calculate_service_time_by_source(service, source):
            times = [values['date'] for values in data[service] if values['source'] == source]
            times.sort()
            return (times[-1] - times[0]).total_seconds()

        def is_service_passed_for_source():
            # check if service has statuses "received" and "success" for source
            source_data = [value for value in data[service] if value['source'] == source]
            status_data = [value['status'] for value in source_data]
            return 'received' in status_data and 'success' in status_data

        # TODO: Add functionality for UPLOAD_TIME_ELAPSED prometheus metric
        SERVICE_STATUS_COUNTER.labels(service_name=service, status=status, source_name=source).inc()
        if is_service_passed_for_source():
            UPLOAD_TIME_ELAPSED_BY_SERVICE.labels(service_name=service, source_name=source).observe(
                calculate_service_time_by_source(service, source))


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
                    current_column_items = redis_client.hgetall(table_name, key_is_int=True)
                    if column_name in data:
                        try:
                            if not data[column_name] in current_column_items.values():
                                async with db.transaction():
                                    payload = {'name': data[column_name]}
                                    to_create = tables[table_name](**payload)
                                    created_value = await to_create.create()
                                    dump = created_value.dump()
                                    redis_client.hset(table_name, mapping={dump['id']: dump['name']})
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
            if not DISABLE_PROMETHEUS:
                evaluate_status_metrics(**{
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
        redis_client.hset(table, mapping=dict(res))


def start():
    try:
        # Log the startup environment
        logger.info("Using the following environment:")
        for key, val in globals().items():
            logger.info('%s(%s): %s', key, type(key), val)

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

        # loops
        logger.info("Running...")
        app.run(port=API_PORT)
    except:
        the_error = traceback.format_exc()
        logger.error(f"Failed starting Payload Tracker with Error: {the_error}")
        # Shut down loop
        loop.stop()


if __name__ == "__main__":
    logger.info('Starting the Payload Tracker Service')
    start()

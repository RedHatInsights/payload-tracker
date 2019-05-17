import os
import datetime
import traceback
import json

from aiokafka import AIOKafkaConsumer
from kafkahelpers import ReconnectingClient
from prometheus_client import start_http_server, Counter, Enum, Gauge, Histogram, Info
from bounded_executor import BoundedExecutor
import asyncio
import connexion

import config
from db import init_db, db, Payload
import tracker_logging

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS', 'localhost:9092')
GROUP_ID = os.environ.get('GROUP_ID', 'payload_tracker')
THREAD_POOL_SIZE = int(os.environ.get('THREAD_POOL_SIZE', 8))
PAYLOAD_TRACKER_TOPIC = os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker')

# Prometheus configuration
DISABLE_PROMETHEUS = True if os.environ.get('DISABLE_PROMETHEUS') == "True" else False
PROMETHEUS_PORT = os.environ.get('PROMETHEUS_PORT', 8000)

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
            expected_keys = ["service", "payload_id", "status"]
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                logger.info(f"Payload {data} missing keys {missing_keys}. Expected {expected_keys}")
                pass

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

            #TODO: At some point parse the date received from the payload service
            #if 'date' in data:
            #    sanitized_payload_status['date'] = dateutil.parser.parse(data['date'])
            #else:
            sanitized_payload_status['date'] = datetime.datetime.now()

            logger.info(f"Sanitized Payload for DB {sanitized_payload_status}")
            # insert into database
            async with db.transaction():
                payload_to_create = Payload(**sanitized_payload_status)
                created_payload = await payload_to_create.create()
                dump = created_payload.dump()
                logger.info(f"DB Transaction {created_payload} - {dump}")
                return dump
        else:
            continue


async def consume(client):
    data = await client.getmany()
    for tp, msgs in data.items():
        logger.info("Received messages: %s", msgs)
        loop.create_task(process_payload_status(msgs))
    await asyncio.sleep(0.1)


async def setup_app():
    app = {}
    await init_db(config)
    app['db'] = db
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

        # start prometheus
        if not DISABLE_PROMETHEUS:
            logger.info('Starting Payload Tracker Prometheus Server')
            start_prometheus()

        # add consumer callbacks
        logger.info('Starting Kafka consumer for Payload status messages.')
        loop.create_task(CONSUMER.get_callback(consume)())

        # setup http app and db
        loop.run_until_complete(setup_app())

        # loops
        loop.run_forever()
    except:
        the_error = traceback.format_exc()
        logger.error(f"Failed starting Payload Tracker with Error: {the_error}")
        # Shut down loop
        loop.stop()   
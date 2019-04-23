import os
import datetime

from confluent_kafka import Consumer, KafkaError
from prometheus_client import start_http_server, Counter, Enum, Gauge, Histogram, Info
from concurrent.futures import ThreadPoolExecutor

import tracker_logging

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS')
GROUP_ID = os.environ.get('GROUP_ID', 'payload_tracker')
THREAD_POOL_SIZE = os.environ.get('THREAD_POOL_SIZE', 8)
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


# Setup consumer
c = Consumer({
    'bootstrap.servers': BOOTSTRAP_SERVERS,
    'group.id': GROUP_ID,
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True,
    'enable.auto.offset.store': True
})

# Handle sigterms so process shuts down cleanly only after flushing messages to kafka
_sigterm_received = False


def start():
    # Log env vars / settings
    logger.info("Using LOG_LEVEL %s", LOG_LEVEL)
    logger.info("Using BOOTSTRAP_SERVERS %s", BOOTSTRAP_SERVERS)
    logger.info("Using GROUP_ID %s", GROUP_ID)
    logger.info("Using THREAD_POOL_SIZE %s", THREAD_POOL_SIZE)
    logger.info("Using PAYLOAD_TRACKER_TOPIC %s", PAYLOAD_TRACKER_TOPIC)
    logger.info("Using DISABLE_PROMETHEUS %s", DISABLE_PROMETHEUS)
    logger.info("Using PROMETHEUS_PORT %s", PROMETHEUS_PORT)

    # start thread pool executor
    logger.info("Starting thread pool executor.")
    executor = ThreadPoolExecutor(max_workers=int(THREAD_POOL_SIZE))

    # start prometheus
    if not DISABLE_PROMETHEUS:
        logger.info('Starting Payload Tracker Prometheus Server')
        submit_to_executor(executor, start_prometheus)

    # Subscribe to our topics
    topic_subscriptions = [PAYLOAD_TRACKER_TOPIC]
    logger.info("Subscribing to Kafka topics %s, %s" % (PAYLOAD_TRACKER_TOPIC))
    c.subscribe(topic_subscriptions)
    logger.info("Subscribed to topics.")

    # Poll the topics we are consuming from
    logger.info("Begin polling Kafka.")
    while not _sigterm_received:
        msg = c.poll(1.0)

        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                logger.info(msg.error())
                continue

        logger.info(
            'Received Platform Kafka message at %s from topic %s: %s',
            datetime.datetime.now(), msg.topic(), msg.value()
        )

    # Shut down executor
    executor.shutdown()
    # Close consumer connection
    c.close()


def submit_to_executor(executor, fn, *args, **kwargs):
    future = executor.submit(fn, *args, **kwargs)
    logger.info("Submitted to executor, future: %s", future)
    future.add_done_callback(on_thread_done)


def on_thread_done(future):
    try:
        future.result()
    except Exception:
        logger.exception("Future %s hit exception", future)


def start_prometheus():
    start_http_server(PROMETHEUS_PORT)


if __name__ == "__main__":
    logger.info('Starting Payload Tracker Service')
    start()

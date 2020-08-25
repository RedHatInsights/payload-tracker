import os
import json
import datetime
import uuid
import asyncio
import time
from datetime import timedelta
from random import randint, shuffle
from confluent_kafka import Producer

loop = asyncio.get_event_loop()
terminate = int(os.environ.get('DURATION', 60))

statues_dict = {
    1: 'received',
    2: 'processing',
    3: 'success',
    4: 'processed',
    5: 'processing_success',
}

services_to_statuses = {
    'ingress': [1, 3],
    'puptoo': [1, 3],
    'inventory-mq-service': [1, 2, 5, 3],
    'storage-broker': [3],
    'vulernability': [1, 3],
    'insights-engine': [1, 3],
    'insights-advisor-service': [1, 3, 2, 3],
    'platform-legacy-bridge': [1, 3],
    'hsp-archiver': [1, 3],
    'ccx-data-pipeline': [1, 3],
    'insights-results-db-writer': [1, 4, 3]
}

payload_path_one = ['ingress', 'ccx-data-pipeline', 'insights-results-db-writer']
payload_path_two = [
    'ingress', 'puptoo', 'inventory-mq-service', 'storage-broker', 'vulernability']
path_two_randomized = [
    'insights-engine', 'insights-advisor-service', 'platform-legacy-bridge', 'hsp-archiver']


def produceMessageCallback(err, msg):
    print('Produce message callback err: %s' % (err))
    print('Produce message callback msg: %s' % (msg))
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))


async def post_payload():
    async def generate_payload(request_id, service, speed=0):
        for status in services_to_statuses[service]:
            time.sleep(speed)
            print(f'Posting payload status with request_id: {request_id}')
            payload = { 'request_id' : request_id, 'service': service, 'status': statues_dict[status] }
            p = Producer({'bootstrap.servers': os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')})
            payload['date'] = str(datetime.datetime.now())
            p.poll(0)
            p.produce(os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker'),
                    json.dumps(payload), callback=produceMessageCallback)
            p.flush()
    request_id = str(uuid.uuid1())
    randomized = path_two_randomized.copy()
    shuffle(randomized)
    path_two = payload_path_two.copy()
    path_two.extend(randomized)
    paths = [payload_path_one, path_two]
    path = randint(0, len(paths) - 1)
    speed = 0
    for service in paths[path]:
        speed += 0.01
        time.sleep(0.075)
        await generate_payload(request_id, service, speed)


if __name__ == '__main__':
    start = time.time()
    time_run = timedelta(0)
    while time_run < timedelta(terminate):
        loop.run_until_complete(post_payload())
        time_run = timedelta(time.time() - start)

import os
import json
import datetime
import time
import random
import uuid
from confluent_kafka import Producer


# Define environment variables
NUMBER_OF_BATCHES = os.environ.get('NUMBER_OF_BATCHES', 1)
SIZE_OF_BATCH = os.environ.get('SIZE_OF_BATCH', 10)

# Define Producer
p = Producer({'bootstrap.servers': os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')})


class RandomPool():
    ''' This class randomizes the retrieval of elements from a list of lists '''

    def __init__(self, pool):
        self.pool = pool if set([type(x) for x in pool]) == set([type([])]) else []

    def __len__(self):
        return len(self.pool)

    def _get_random_index(self):
        return random.randint(0, len(self.pool) - 1)

    def pop(self):
        index = self._get_random_index()
        while not len(self.pool[index]) > 0:
            index = self._get_random_index()
        item = self.pool[index].pop()
        if len(self.pool[index]) == 0:
            del self.pool[index]
        return item

    def get_pool(self):
        return self.pool


def produceMessageCallback(err, msg):
    print('Produce message callback err: %s' % (err))
    print('Produce message callback msg: %s' % (msg))
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))


def get_payloads(request_id):
    payloads = [{
        'service': 'inventory',
        'request_id': request_id,
        'status': 'received'
    }, {
        'service': 'inventory',
        'request_id': request_id,
        'status': 'processing'
    }, {
        'service': 'inventory',
        'request_id': request_id,
        'status': 'processing_success'
    }, {
        'service': 'insights-advisor-service',
        'request_id': request_id,
        'status': 'received',
        'source': 'inventory'
    }, {
        'service': 'insights-advisor-service',
        'request_id': request_id,
        'status': 'processing',
        'source': 'inventory'
    }, {
        'service': 'insights-advisor-service',
        'request_id': request_id,
        'status': 'success',
        'source': 'inventory'
    }, {
        'service': 'hsp-deleter',
        'request_id': request_id,
        'status': 'received'
    }, {
        'service': 'hsp-deleter',
        'request_id': request_id,
        'status': 'success'
    }]
    payloads.reverse()
    return payloads


if __name__ == '__main__':
    for _ in range(NUMBER_OF_BATCHES):
        request_id = str(uuid.uuid4().hex)
        payload_length = len(get_payloads(request_id)) - len([
            x for x in get_payloads(request_id) if x['service'] == 'inventory'])
        pool = RandomPool([get_payloads(request_id) for _ in range(SIZE_OF_BATCH)])
        awaiting_inv_pass = True
        while len(pool) > 0:
            p.poll(0)
            # this checks for completion of the inventory process
            if False in [len(x) > payload_length for x in pool.get_pool()] and awaiting_inv_pass:
                payload = {
                    'service': 'inventory',
                    'request_id': request_id,
                    'status': 'success'
                }
                awaiting_inv_pass = False
            else:
                payload = pool.pop()
            payload['date'] = str(datetime.datetime.utcnow())
            p.produce(os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker'),
                        json.dumps(payload), callback=produceMessageCallback)
            p.flush()
            time.sleep(0.25)

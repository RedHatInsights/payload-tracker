import os
import json
import datetime
import uuid
from random import randint
from confluent_kafka import Producer


def generatePayloads():
    request_id = str(uuid.uuid1())
    inventory_id = str(uuid.uuid1())
    system_id = str(uuid.uuid1())
    account = str(randint(pow(10, 5), pow(10,6) - 1))
    print(f'request_id: {request_id}')
    return [
        {
            'service': 'ingress',
            'request_id': request_id,
            'status': 'received'
        },
        {
            'service': 'ingress',
            'request_id': request_id,
            'status': 'processing',
            'inventory_id': inventory_id,
            'system_id': system_id
        },
        {
            'service': 'ingress',
            'request_id': request_id,
            'status': 'validated',
            'account': account
        },
        {
            'service': 'advisor-pup',
            'request_id': request_id,
            'status': 'processing',
            'inventory_id': inventory_id
        },
        {
            'service': 'advisor-pup',
            'request_id': request_id,
            'status': 'success'
        },
        {
            'service': 'ingress',
            'request_id': request_id,
            'status': 'announced',
            'system_id': system_id
        },
        {
            'service': 'insights-advisor-service',
            'request_id': request_id,
            'status': 'received',
            'inventory_id': inventory_id
        },
        {
            'service': 'insights-advisor-service',
            'request_id': request_id,
            'status': 'processing',
            'status_msg': 'analyzing archive',
            'system_id': system_id
        },
        {
            'service': 'insights-advisor-service',
            'request_id': request_id,
            'status': 'processing',
            'status_msg': 'generating reports'
        },
        {
            'service': 'insights-advisor-service',
            'request_id': request_id,
            'status': 'processing',
            'status_msg': 'performing db operations',
            'inventory_id': inventory_id
        },
        {
            'service': 'insights-advisor-service',
            'request_id': request_id,
            'status': 'success'
        },
    ]


def produceMessageCallback(err, msg):
    print('Produce message callback err: %s' % (err))
    print('Produce message callback msg: %s' % (msg))
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))


print("Posting payload status")
p = Producer({'bootstrap.servers': os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')})

for x in range(100):  # increase this for more messages
    payloads = generatePayloads()
    for payload in payloads:
        payload['date'] = str(datetime.datetime.now())
        p.poll(0)
        p.produce(os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker'),
                    json.dumps(payload), callback=produceMessageCallback)
        p.flush()

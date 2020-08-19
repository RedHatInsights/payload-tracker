import os
import json
import datetime
import time
import uuid
from confluent_kafka import Producer


def produceMessageCallback(err, msg):
    print('Produce message callback err: %s' % (err))
    print('Produce message callback msg: %s' % (msg))
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))

request_id = str(uuid.uuid1())
payloads = [
{
       'service': 'ingress',
       'request_id': request_id,
       'status': 'received'
},
{
       'service': 'ingress',
       'request_id': request_id,
       'status': 'processing'
},
{
       'service': 'ingress',
       'request_id': request_id,
       'status': 'validated'
},
{
       'service': 'advisor-pup',
       'request_id': request_id,
       'status': 'processing'
},
{
       'service': 'advisor-pup',
       'request_id': request_id,
       'status': 'success'
},
{
       'service': 'ingress',
       'request_id': request_id,
       'status': 'announced'
},
{
       'service': 'insights-advisor-service',
       'request_id': request_id,
       'status': 'received'
},
{
       'service': 'insights-advisor-service',
       'request_id': request_id,
       'status': 'processing',
       'status_msg': 'analyzing archive'
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
       'status_msg': 'performing db operations'
},
{
       'service': 'insights-advisor-service',
       'request_id': request_id,
       'status': 'success'
},
]


print(f'Posting payload status with request_id: {request_id}')
p = Producer({'bootstrap.servers': os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')})
for payload in payloads:
  payload['date'] = str(datetime.datetime.now())
  p.poll(0)
  p.produce(os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker'),
            json.dumps(payload), callback=produceMessageCallback)
  p.flush()
  time.sleep(1)

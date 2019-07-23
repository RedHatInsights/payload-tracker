import os
import json
import datetime
import time
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


payloads = [
{
       'service': 'ingress',
       'payload_id': '12345',
       'status': 'received',
       'date': str(datetime.datetime.now())
},
{
       'service': 'ingress',
       'payload_id': '12345',
       'status': 'processing',
       'date': str(datetime.datetime.now())
},
{
       'service': 'ingress',
       'payload_id': '12345',
       'status': 'success',
       'date': str(datetime.datetime.now())
},
{
       'service': 'pup',
       'payload_id': '12345',
       'status': 'received',
       'date': str(datetime.datetime.now())
},
{
       'service': 'pup',
       'payload_id': '12345',
       'status': 'processing',
       'date': str(datetime.datetime.now())
},
{
       'service': 'pup',
       'payload_id': '12345',
       'status': 'success',
       'date': str(datetime.datetime.now())
},{
       'service': 'insights-advisor-service',
       'payload_id': '12345',
       'status': 'received',
       'date': str(datetime.datetime.now())
},
{
       'service': 'insights-advisor-service',
       'payload_id': '12345',
       'status': 'processing',
       'status_msg': 'analyzing archive',
       'date': str(datetime.datetime.now())
},
{
       'service': 'insights-advisor-service',
       'payload_id': '12345',
       'status': 'processing',
       'status_msg': 'generating reports',
       'date': str(datetime.datetime.now())
},
{
       'service': 'insights-advisor-service',
       'payload_id': '12345',
       'status': 'processing',
       'status_msg': 'performing db operations',
       'date': str(datetime.datetime.now())
},
{
       'service': 'insights-advisor-service',
       'payload_id': '12345',
       'status': 'success',
       'date': str(datetime.datetime.now())
},
]


print("Posting payload status")
p = Producer({'bootstrap.servers': os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')})
for payload in payloads:
  p.poll(0)
  p.produce(os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker'),
            json.dumps(payload), callback=produceMessageCallback)
  p.flush()
  time.sleep(1)

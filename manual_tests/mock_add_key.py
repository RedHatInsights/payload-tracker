import os
import json
import datetime
import time
import uuid
from confluent_kafka import Producer


request_id = str(uuid.uuid4().hex)
inventory_id = str(uuid.uuid4().hex)
system_id = str(uuid.uuid4().hex)
payload = {
    'service': 'this_service_is_new',
    'request_id': request_id,
    'status': 'this_status_is_new',
    'inventory_id': inventory_id,
    'system_id': system_id,
    'source': 'this_source_is_new'
}


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
payload['date'] = str(datetime.datetime.utcnow())
p.poll(0)
p.produce(os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker'),
        json.dumps(payload), callback=produceMessageCallback)
p.flush()
time.sleep(1)

import os
import json
import datetime
from confluent_kafka import Producer, KafkaError


def produceMessageCallback(err, msg):
    print('Produce message callback err: %s' % (err))
    print('Produce message callback msg: %s' % (msg))
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))


payload_info = {
       'service': 'test-service',
       'payload_id': '12345',
       'status': 'received',
       'date': str(datetime.datetime.now())
}


print("Posting payload status")
p = Producer({'bootstrap.servers': os.environ.get('BOOTSTRAP_SERVERS', 'localhost:9092')})
p.poll(0)
p.produce(os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker'),
          json.dumps(payload_info), callback=produceMessageCallback)
p.flush()

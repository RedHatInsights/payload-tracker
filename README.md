Payload Tracker
===========================================


Overview
--------------------
The Payload Tracker is a centralized location for tracking payloads through the Platform. Finding the status (current, or past) of a payload is difficult as logs are spread amongst various services and locations. Furthermore, Prometheus is meant purely for an aggregation of metrics and not for individualized transactions or tracking.

The Payload Tracker aims to provide a mechanism to query for a ‘payload_id,’ ‘inventory_id,’ or ‘system_uuid’ (machine-id) and see the current, last or previous X statuses of this upload through the platform. In the future, hopefully it will allow for more robust filtering based off of ‘service,’ ‘account,’ and ‘status.’

The ultimate goal of this service is to say that the upload made it through X services and was successful, or that the upload made it through X services was a failure and why it was a failure.


Architecture
--------------------
Payload Tracker is a service that lives in ‘platform-<env>’. This service has its own database representative of the current payload status in the platform. There are REST API endpoints that give access to the payload status. There is not currently any front-end UI for this service. This service listens to messages on the Kafka MQ topic ‘platform.payload-status.’


Integration
--------------------
Simply send a message on the ‘platform.payload-status’ for your given Kafka MQ Broker in the appropriate environment. Currently, the only required fields are ‘service,’ ‘payload_id’ and ‘status,’ however this may change.The format is as follows:

```
{ 	
‘service’: ‘The services name processing the payload’,
‘source’: ‘This is indicative of a third party rule hit analysis. (not Insights Client)’,
‘account’: ‘The RH associated account’,
‘payload_id’: ‘The ID of the payload’,
‘inventory_id’: “The ID of the entity in terms of the inventory’,
‘system_id’: ‘The ID of the entity in terms of the actual system’,
‘status’: ‘received|processing|success|failure|invalid’,
‘status_msg’: ‘Information relating to the above status, should more verbiage be needed (in the event of an error)’,
‘date’: ‘Timestamp for the message relating to the ‘status’ above’ 
}
```
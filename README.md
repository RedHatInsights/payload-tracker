Payload Tracker
===========================================


Overview
--------------------
The Payload Tracker is a centralized location for tracking payloads through the Platform. Finding the status (current, or past) of a payload is difficult as logs are spread amongst various services and locations. Furthermore, Prometheus is meant purely for an aggregation of metrics and not for individualized transactions or tracking.

The Payload Tracker aims to provide a mechanism to query for a `payload_id,` `inventory_id,` or `system_uuid` (machine-id) and see the current, last or previous X statuses of this upload through the platform. In the future, hopefully it will allow for more robust filtering based off of `service,` `account,` and `status.`

The ultimate goal of this service is to say that the upload made it through X services and was successful, or that the upload made it through X services was a failure and why it was a failure.


Architecture
--------------------
Payload Tracker is a service that lives in `platform-<env>`. This service has its own database representative of the current payload status in the platform. There are REST API endpoints that give access to the payload status. There is not currently any front-end UI for this service. This service listens to messages on the Kafka MQ topic `platform.payload-status.`


REST API Endpoints
--------------------
Please see the Swagger Spec for API Endpoints. The API Swagger Spec is located in `swagger/api.spec.yaml`. They are currently as follows and can be combined:
```
/v1/payloads
	?page=<integer>
	?page_size=<integer>
	?sort_by=<string>[service, source, account, payload_id, inventory_id, system_id, status, status_msg, date, created_at]
	?status=<string>(The status as given on the Payload.)
	?service=<string>(The service that processed the Payload.)
	?inventory_id=<string>(The Inventory ID, if received on the Payload.)
	?account=<string>(An account number, if received on the Payload.)
	?source=<string>(A source received by the Payload, usually indicated a third-party rule hit.)
	?system_id=<string>(The Physical Machine ID if it was received on the Payload.)
	?status_msg=<string>(A verbose status message given with the Payload.)
	?date_lt=<string>(YYYY-MM-DD)
	?date_lte=<string>(YYYY-MM-DD)
	?date_gt=<string>(YYYY-MM-DD)
	?date_gte=<string>(YYYY-MM-DD)
	?created_at_lt=<string>(YYYY-MM-DD)
	?created_at_lte=<string>(YYYY-MM-DD)
	?created_at_gt=<string>(YYYY-MM-DD)
	?created_at_gte=<string>(YYYY-MM-DD)
	?sort_dir=<string>(asc, desc)
/v1/payloads/{payload_id}
```


Integration
--------------------
Simply send a message on the ‘platform.payload-status’ for your given Kafka MQ Broker in the appropriate environment. Currently, the only required fields are ‘service,’ ‘payload_id’ and ‘status,’ however this may change.The format is as follows:

```
{ 	
'service': 'The services name processing the payload',
'source': 'This is indicative of a third party rule hit analysis. (not Insights Client)',
'account': 'The RH associated account',
'payload_id': 'The ID of the payload',
'inventory_id': 'The ID of the entity in terms of the inventory',
'system_id': 'The ID of the entity in terms of the actual system',
'status': 'received|processing|success|failure|invalid',
'status_msg': 'Information relating to the above status, should more verbiage be needed (in the event of an error)',
'date': 'Timestamp for the message relating to the status above' 
}
```


Docker
--------------------

The docker-compose file included in this repo will stand up a message queue (Kafka), and
a Postgresql Database


Prequisites
--------------------
    docker
    docker-compose


Queue
--------------------

You can either connect to a remote kafka server, or set up a local one. To spawn your own
Kafka server, simply install it using your favorite package manager. To run Kafka, you need
Zookeeper and JRE. First launch Zookeeper and then Kafka, possibly set them up as services
so they relaunch on reboot.

Make sure that your Kafka server can accept connection from your apps. Especially the
`listeners` configuration value in your `server.properties` config file must be properly
set. If Kafka runs on the same machine as the apps, the default config should work.


Dev Setup
--------------------
1. Install dependencies
```
pip install pipenv alembic --user
pipenv install
```

2. Start Postgres Database and Kafka (might need to run this as root depending on your docker setup)
```
docker-compose up
```

3. Migrate the Database
```
pipenv shell
PYTHONPATH=. alembic upgrade head
```

4. Start the server
```
pipenv run server
```


Sending Mock Payloads
--------------------
1. Install dependencies
```
pip install --dev
```

2. Run the manual mock payload
```
python manual_tests/mock_payload.py
```


Contributing
--------------------
All outstanding issues or feature requests should be filed as Issues on this Github
page. PRs should be submitted against the master branch for any new features or changes.


Versioning
--------------------
Anytime an endpoint is modified, the versin should be incremented by `0.1`. New
functionality introduced that may effect the client should increment by `1`. Minor
features and bug fixes can increment by `0.0.1`
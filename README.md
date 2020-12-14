Payload Tracker
===========================================


Overview
--------------------
The Payload Tracker is a centralized location for tracking payloads through the Platform. Finding the status (current, or past) of a payload is difficult as logs are spread amongst various services and locations. Furthermore, Prometheus is meant purely for an aggregation of metrics and not for individualized transactions or tracking.

The Payload Tracker aims to provide a mechanism to query for a `request_id,` `inventory_id,` or `system_uuid` (physical machine-id) and see the current, last or previous X statuses of this upload through the platform. In the future, hopefully it will allow for more robust filtering based off of `service,` `account,` and `status.`

The ultimate goal of this service is to say that the upload made it through X services and was successful, or that the upload made it through X services was a failure and why it was a failure.


Architecture
--------------------
Payload Tracker is a service that lives in `platform-<env>`. This service has its own database representative of the current payload status in the platform. There are REST API endpoints that give access to the payload status. This service listens to messages on the Kafka MQ topic `platform.payload-status.` There is now a front-end UI for this service located in the same `platform-<env>`. It is respectively titled "payload-tracker-frontend."


REST API Endpoints
--------------------
Please see the Swagger Spec for API Endpoints. The API Swagger Spec is located in `swagger/api.spec.yaml`.


Integration
--------------------
Simply send a message on the ‘platform.payload-status’ for your given Kafka MQ Broker in the appropriate environment. Currently, the only required fields are ‘service,’ ‘request_id,‘ ‘status,’ and ‘date‘ however this may change.The format is as follows:

```
{ 	
'service': 'The services name processing the payload',
'source': 'This is indicative of a third party rule hit analysis. (not Insights Client)',
'account': 'The RH associated account',
'request_id': 'The ID of the payload',
'inventory_id': 'The ID of the entity in terms of the inventory',
'system_id': 'The ID of the entity in terms of the actual system',
'status': 'received|processing|success|error|etc',
'status_msg': 'Information relating to the above status, should more verbiage be needed (in the event of an error)',
'date': 'Timestamp for the message relating to the status above' 
}
```
The following statuses are required:
```
‘received‘ 
‘success/error‘ # success OR error
```

A status of ‘received,‘ and ‘success/error‘ (success OR error) are the only required statuses. Received indicates your service has touched a payload and will begin performing some action upon it. This allows the payload tracker to begin elapsed time analysis for this lifecycle of the upload/payload. The success/error indicates your service has finished with the payload/upload (for this stage) of the upload. Whether or not your service may or may not touch the payload again is irrelevant. It is simply indicating that for this stage of the upload your service is done. Any additional statuses may be sent in but are purely for more verbose analysis and not currently used in any other calculations (such as elapsed upload times).

For example you may send in a ‘processing‘ status. This status obviously indicates your service is in a processing state, and will additionally show up in Grafana charts, and on the frontend. This is useful for seeing the volume of uploads currently in processing states across various services.

Docker
--------------------

The docker-compose file included in this repo will stand up a message queue (Kafka), and
a Postgresql Database


Prequisites
--------------------
    docker
    docker-compose
    python == 3.6.5


Requirements
--------------------
    aiohttp <= 3.7.2
    aiokafka == 0.5.2


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

If you are only running the API/Server service then run this command:
```
pipenv run server
```
If you are running the frontend along with this service then run this command instead. This defines the API_PORT so that it will not conflict with the frontend. The frontend has a proxy pass set.
```
API_PORT=8081 pipenv run server
```


Sending Mock Payloads
--------------------
1. Install dependencies
```
pip install --dev
```

2. Run the manual mock payload or mock load test
```
pipenv shell
python manual_tests/mock_payload.py
python manual_tests/mock_loaddtest.py
```


Running Tests
--------------------
Tests can be running using the `pipenv` cli. The `Pipfile` included in the repo has a
script for running tests, which can be called using `pipenv run tests`. This will run unit tests
as well as code coverage. Similarly, the `Pipfile` includes a script for running the flake8 linter,
which can be called using `pipenv run linter`. Each of these three tests will be run by Jenkins
when a new PR is opened and when PRs are merged to master.


Contributing
--------------------
All outstanding issues or feature requests should be filed as Issues on this Github
page. PRs should be submitted against the master branch for any new features or changes.


Versioning
--------------------
Anytime an endpoint is modified, the versin should be incremented by `0.1`. New
functionality introduced that may effect the client should increment by `1`. Minor
features and bug fixes can increment by `0.0.1`

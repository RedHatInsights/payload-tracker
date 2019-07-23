import os
import aiohttp
import asyncio
import json
import traceback

from datetime import datetime, timedelta
from dateutil import parser
from concurrent.futures import ALL_COMPLETED

from db import db, Payload


KIBANA_POST_DATA = {"from": 0, "size": 10000,
  "query": {"bool": {"must":
        [{"match": {"msg": {"query": "Platform Proxy: Upload service responded to upload"}}}],
        "filter": [{"range": {"@timestamp": {"gt": "", "lte": ""}}}]}}}
KIBANA_HEADERS = {"Content-Type": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "kbn-version": "6.5.4",
        "Accept": "text/plain, */*; q=0.01"}


class KibanaCourier:
    def __init__(self, loop, logger, url, cookies, check_payload_status_metrics):
        self.data = {'payloads': []}
        self.url = url
        self.loop = loop
        self.logger = logger
        self.session = aiohttp.ClientSession(headers=KIBANA_HEADERS, cookies=cookies)

    def _set_date_time(self):
        now = datetime.utcnow()
        minus_thirty_seconds = now - timedelta(seconds=30)
        KIBANA_POST_DATA['query']['bool']['filter'][0]['range']['@timestamp']['gt'] = str(minus_thirty_seconds.isoformat())
        KIBANA_POST_DATA['query']['bool']['filter'][0]['range']['@timestamp']['lte'] = str(now.isoformat())

    async def _fetch(self):
        self._set_date_time()
        async with self.session.post(self.url, data=json.dumps(KIBANA_POST_DATA)) as resp:
            status = resp.status
            assert status == 200
            return await resp.json()

    async def __call__(self):
        task = [self._fetch()]
        done, pending = await asyncio.wait(
            task,
            loop=self.loop,
            return_when=ALL_COMPLETED
        )
        for task in done:
            data = task.result()
            data = data['hits']
            for data in data['hits']:
                payload = data['_source']
                expected_keys = ['req_id', 'msg', 'statusCode', '@log_stream']
                missing_keys = [key for key in expected_keys if key not in payload]
                if missing_keys:
                    self.logger.info(f"Payload {data['_id']} missing keys {missing_keys}. Expected {expected_keys}")
                    continue

                self.logger.info("Payload message has expected keys. Begin sanitizing")
                sanitized_payload_status = {
                    'payload_id': payload['req_id'],
                    'service': payload['@log_stream'],
                    'status_msg': f"{str(payload['statusCode'])}: {str(payload['msg'])}",
                    'status': str(payload['statusCode']),
                    'source': 'legacy-insights'
                }

                # increment prometheus metrics
                check_payload_status_metrics(payload['req_id'], 'legacy-insights', str(payload['statusCode']))

                if '@timestamp' in payload:
                    try:
                        sanitized_payload_status['date'] = parser.parse(payload['@timestamp']).replace(tzinfo=None)
                    except:
                        the_error = traceback.format_exc()
                        self.logger.error(f"Error parsing date: {the_error}")

                self.data['payloads'].append(sanitized_payload_status)

        for sanitized_payload_status in self.data['payloads']:
            self.logger.info(f"Sanitized Payload for DB {sanitized_payload_status['payload_id']}")
            async with db.transaction():
                payload_to_create = Payload(**sanitized_payload_status)
                created_payload = await payload_to_create.create()
                dump = created_payload.dump()
                self.logger.info(f"DB Transaction {created_payload} - {dump}")
                dump['date'] = str(dump['date'])
                dump['created_at'] = str(dump['created_at'])

    def __del__(self):
        self.session.close()

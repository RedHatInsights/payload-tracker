from aiohttp.web import json_response
import datetime
from functools import partial
from http import HTTPStatus
import json


def _dumps(obj):
    if isinstance(obj, datetime.datetime):
        return str(obj)
    raise TypeError('Unable to serialize {!r}'.format(obj))


def _response(data=None, status=HTTPStatus.NOT_IMPLEMENTED):
    return json_response(data=data, status=status, dumps=partial(json.dumps, default=_dumps))


def _message(message):
    return {'message': message}


def internal_server_error(message=None):
    if message is None:
        message = 'Internal server error.'
    return _response(data=_message(message), status=HTTPStatus.INTERNAL_SERVER_ERROR)


def resource_exists(message=None):
    if message is None:
        message = 'Resource exists.'
    return _response(data=_message(message), status=HTTPStatus.CONFLICT)


def not_found(message=None):
    if message is None:
        message = 'Resource not found.'
    return _response(data=_message(message), status=HTTPStatus.NOT_FOUND)


def invalid_request_parameters(message=None):
    if message is None:
        message = 'Invalid request parameters.'
    return _response(data=_message(message), status=HTTPStatus.BAD_REQUEST)


def delete():
    return HTTPStatus.NO_CONTENT


def create(body):
    return _response(data=body, status=HTTPStatus.CREATED)


def search(count, entities):
    return _response(data={'count': count, 'data': entities}, status=HTTPStatus.OK)


def get(entity):
    return _response(data=entity, status=HTTPStatus.OK)


def update(entity):
    return _response(data=entity, status=HTTPStatus.OK)

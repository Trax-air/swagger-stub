# -*- coding: utf-8 -*-

import httpretty
import inspect
import json
import pytest
import re

try:
    from urlparse import parse_qsl
    from urlparse import urlsplit
except ImportError:  # Python3
    from urllib.parse import parse_qsl
    from urllib.parse import urlsplit

from swagger_parser import SwaggerParser


class StubMemory(object):
    """Store data about calls made to the stub."""

    def __init__(self, swagger_parser):
        self.memory = []
        self.mock_call = {}
        self.side_effect = {}

        self.definitions = swagger_parser.definitions_example

    def add_call(self, action, path, body, query, status_code):
        """Add a call to the memory

        Args:
            action: action of the call.
            path: path of the call.
            body: body of the call.
            query: query of the call.
            status_code: status_code of the call.
        """
        self.memory.append({'path': path,
                            'action': action,
                            'body': body,
                            'query': query,
                            'status_code': status_code})

    def get_call(self, action=None, path=None):
        """Get a call with the given action and/or path.

        Args:
            action: action of the call.
            path: path of the call.
        """
        return_call = []
        for data in self.memory:
            if action is None or data['action'] == action and\
               path is None or data['path'] == path:
                return_call.append(data)

        return return_call

    def add_mock_call(self, action, path, body, status_code=200):
        """Add a mock call to the list.

        Args:
            action: action of the call to mock.
            path: path of the call to mock.
            body: body to return during the call.
        """
        if action not in self.mock_call:
            self.mock_call[action] = {}
        self.mock_call[action][path] = (body, status_code)

    def add_mock_side_effect(self, action, path, side_effect):
        """Add a side effect to a call.

        Args:
            action: action of the call to mock.
            path: path of the call to mock.
            side_effect: either an Exception, a function or a [(body, status_code)] or [body]
        """
        if action not in self.side_effect:
            self.side_effect[action] = {}
        self.side_effect[action][path] = {}
        self.side_effect[action][path]['counter'] = -1
        self.side_effect[action][path]['effect'] = side_effect

    def process_side_effect(self, action, path):
        """Get the side_effect for the given action and path.

        Args:
            action: http action.
            path: path of the request to mock.

        Returns:
            (body, status_code) or raise the side_effect error

        Raises:
            IndexError: We have gone through the side_effect list (if it's a list)
        """
        # TODO(Handle functions)
        if action in self.side_effect and path in self.side_effect[action]:
            if (inspect.isclass(self.side_effect[action][path]['effect']) and
                issubclass(self.side_effect[action][path]['effect'], Exception)) or \
                    (inspect.isclass(type(self.side_effect[action][path]['effect'])) and
                        issubclass(type(self.side_effect[action][path]['effect']), Exception)):
                raise self.side_effect[action][path]['effect']
            elif isinstance(self.side_effect[action][path]['effect'], list):
                # Update the counter
                self.side_effect[action][path]['counter'] += 1
                index = self.side_effect[action][path]['counter']
                if isinstance(self.side_effect[action][path]['effect'][index],
                              tuple):
                    return (json.dumps(self.side_effect[action][path]['effect'][index][0]),
                            self.side_effect[action][path]['effect'][index][1])
                else:
                    return json.dumps(self.side_effect[action][path]['effect'][index]), 200


swagger_url = {}  # Store SwaggerParser with the associate url
memory = {}  # Stub memory


def get_parsed_body(request):
    """Get the body (json or formData) of the request parsed.

    Args:
        request: request object to get the body from.

    Returns:
        A dictionary of the body.

    Raises:
        ValueError: if it is neither a json or a formData
    """
    data = None
    if not request.parsed_body == '':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:  # Decode formData
            data = dict(parse_qsl(request.body))

            if not data:  # Not a form data
                raise
    return data


def get_data_from_request(request, uri, headers):
    """Get the data for the given request.

    Args:
        request: the request to process.
        uri: uri of the request.
        headers: headers of the request.

    Returns:
        (status code, headers, reponse message)
    """
    # Get body data
    data = None
    try:
        data = get_parsed_body(request)
    except ValueError:  # Decode formData
        return 400, headers, '{"body": ["Not valid json."]}'

    # Get uri data
    data_url = urlsplit(uri)
    mem = memory['{uri.scheme}://{uri.netloc}'.format(uri=data_url)]
    swagger_parser = swagger_url[
        '{uri.scheme}://{uri.netloc}'.format(uri=data_url)]

    path = data_url[2]
    query = dict(parse_qsl(data_url[3]))
    action = request.method.lower()

    # Get swagger spec
    if path == '/swagger.json':
        return 200, headers, swagger_parser.json_specification

    # Check mock call
    if action in mem.mock_call and path in mem.mock_call[action]:
        mem.add_call(action, path, data, query, mem.mock_call[action][path][1])
        return mem.mock_call[action][path][1], headers, json.dumps(mem.mock_call[action][path][0])

    # Check side_effect
    side = mem.process_side_effect(action, path)
    if side is not None:
        return (side[1], headers, side[0])

    # Test path + action exists
    if swagger_parser.get_path_spec(path, action) == (None, None):
        if action == 'post':
            mem.add_call(action, path, data, query, 400)
            return 400, headers, ''  # Invalid operation
        else:
            mem.add_call(action, path, data, query, 404)
            return 404, headers, ''  # Not found

    # Test request
    if swagger_parser.validate_request(path, action, data, query):
        # Return response from SwaggerParser
        response = swagger_parser.get_request_data(path, action)
        mem.add_call(action, path, data, query, min(response.keys()))
        return (min(response.keys()), headers, json.dumps(response[min(response.keys())]))
    else:
        # Invalid request
        mem.add_call(action, path, data, query, 400)
        return (400, headers, '')


@pytest.yield_fixture
def swagger_stub(swagger_files_url):
    """Fixture to stub a microservice from swagger files.

    To use this fixture you need to define a swagger fixture named
    swagger_files_url with the path to your swagger files, and the url to stub.
    Then just add this fixture to your tests and your request pointing to the
    urls in swagger_files_url will be managed by the stub.

    Example:
        @pytest.fixture
        def swagger_files_url():
            return [('tests/swagger.yaml', 'http://localhost:8000')]
    """
    httpretty.enable()

    for i in swagger_files_url:  # Get all given swagger files and url
        base_url = i[1]
        s = SwaggerParser(i[0])
        swagger_url[base_url] = s

        # Register all urls
        httpretty.register_uri(
            httpretty.GET, re.compile(base_url + r'/.*'),
            body=get_data_from_request)

        httpretty.register_uri(
            httpretty.POST, re.compile(base_url + r'/.*'),
            body=get_data_from_request)

        httpretty.register_uri(
            httpretty.PUT, re.compile(base_url + r'/.*'),
            body=get_data_from_request)

        httpretty.register_uri(
            httpretty.PATCH, re.compile(base_url + r'/.*'),
            body=get_data_from_request)

        httpretty.register_uri(
            httpretty.DELETE, re.compile(base_url + r'/.*'),
            body=get_data_from_request)

        memory[base_url] = StubMemory(s)
        yield memory[base_url]

    # Close httpretty
    httpretty.disable()
    httpretty.reset()

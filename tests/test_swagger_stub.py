#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import pytest
import requests

from swagger_stub import swagger_stub


@pytest.fixture
def swagger_stub_test():
    try:
        return swagger_stub([(os.path.join(os.path.dirname(__file__), 'swagger.yaml'), 'http://localhost:8000')]).next()
    except AttributeError:
        return swagger_stub([(os.path.join(os.path.dirname(__file__), 'swagger.yaml'), 'http://localhost:8000')]).__next__()


@pytest.fixture
def pet_definition_example():
    return {
        'category': {
            'id': 42,
            'name': 'string'
        },
        'status': 'string',
        'name': 'doggie',
        'tags': [
            {
                'id': 42,
                'name': 'string'
            }
        ],
        'photoUrls': [
            'string',
            'string2'
        ],
        'id': 42
    }


def test_swagger_stub(swagger_stub_test, pet_definition_example):
    # Test data example
    swagger_stub_test.definitions['Pet'] == pet_definition_example

    # Wrong url
    response = requests.get('http://localhost:8000/v2/error')
    assert response.status_code == 404
    response = requests.get('http://localhost:8000/pets/5121')
    assert response.status_code == 404
    response = requests.post('http://localhost:8000/v2/error')
    assert response.status_code == 400

    # Wrong body type
    response = requests.post('http://localhost:8000/v2/pets', data='error')
    assert response.status_code == 400
    assert response.json() == {'body': ['Not valid json.']}

    # Post
    response = requests.post('http://localhost:8000/v2/pets', data=json.dumps(pet_definition_example))
    assert response.status_code == 201

    # Wrong body
    response = requests.post('http://localhost:8000/v2/pets', data=json.dumps({}))
    assert response.status_code == 400

    # Request with path parameter
    response = requests.get('http://localhost:8000/v2/pets/5121')
    assert response.status_code == 200
    assert response.json() == pet_definition_example

    # Mock
    swagger_stub_test.add_mock_call('get', '/v2/test', {'mock': 'call'})
    response = requests.get('http://localhost:8000/v2/test')
    assert response.json() == {'mock': 'call'}

    # Side effect
    swagger_stub_test.add_mock_side_effect('get', '/v2/side', [{'test': '1'}, {'test': '2'}, {'test': '3'}])
    response = requests.get('http://localhost:8000/v2/side')
    assert response.json() == {'test': '1'}
    response = requests.get('http://localhost:8000/v2/side')
    assert response.json() == {'test': '2'}
    response = requests.get('http://localhost:8000/v2/side')
    assert response.json() == {'test': '3'}

    swagger_stub_test.add_mock_side_effect('get', '/v2/error', Exception)

    with pytest.raises(Exception):
        response = requests.get('http://localhost:8000/v2/error')

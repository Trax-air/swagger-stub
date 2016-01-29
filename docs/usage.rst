=====
Usage
=====

To use Swagger Stub in a project:

.. code:: python

  import pytest
  import requests

  from swagger_stub import swagger_stub

  # This is the fixture of your stub
  # You only need to specify the path of the swagger file and the address
  # where you want to bind your stub.
  @pytest.fixture
  def test_stub():
      return swagger_stub([('swagger.yaml', 'http://foo.com')]).next()

  # Then you can use this fixture anywhere you want like your API is really running.
  def test_swagger_stub(test_stub):
      # Check a simple call
      response = requests.get('http://foo.com/v1/bar/')
      assert response.status_code == 200
      assert response.json() == {
        'foo': 'bar'
      }

      # Check that an invalid body cause an error
      response = requests.post('http://foo.com/v1/bar/', data='invalid data')
      assert response.status_code == 400

      # Mock a call
      test_stub.add_mock_call('get', '/test', {'mock': 'call'})
      response = requests.get('http://foo.com/v1/test')
      assert response.json() == {'mock': 'call'}

      # Set some side_effect like in the mock library
      test_stub.add_mock_side_effect('get', '/iter', [{'test': '1'}, {'test': '2'}, {'test': '3'}])
      response = requests.get('http://foo.com/v1/iter')
      assert response.json() == {'test': '1'}
      response = requests.get('http://foo.com/v1/iter')
      assert response.json() == {'test': '2'}
      response = requests.get('http://foo.com/v1/iter')
      assert response.json() == {'test': '3'}

      # This side effect will raise a custom error
      test_stub.add_mock_side_effect('get', '/error', Exception)

      with pytest.raises(Exception):
          response = requests.get('http://foo.com/v1/error')

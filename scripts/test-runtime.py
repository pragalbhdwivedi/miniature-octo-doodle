"""Container-local smoke probes. Never makes a provider completion request."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def request(url, key=None, body=None, expected=200):
    headers = {}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data, headers), timeout=15) as response:
            status, payload = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, payload = error.code, b'{}'
    print(f'HTTP {status}: {urllib.parse.urlsplit(url).path}')
    assert status in ([expected] if isinstance(expected, int) else expected), f'Unexpected HTTP status {status}'
    return json.loads(payload) if payload else None


def run():
    if sys.argv[1] == 'gateway':
        base = 'http://127.0.0.1:4000'
        key = os.environ['LITELLM_MASTER_KEY']
        request(base + '/health/liveliness')
        request(base + '/v1/models', expected=[401, 403])
        models = request(base + '/v1/models', key)['data']
        assert 'local-private' not in [m['id'] for m in models]
        print('PASS: internal gateway liveness, unauthenticated rejection, authenticated model listing')
        print(f'Configured gateway models: {len(models)}; no inference requested')
    else:
        gateway = os.environ['OPENAI_API_BASE_URL']
        key = os.environ['OPENAI_API_KEY']
        models = request(gateway + '/models', key)['data']
        request(gateway.removesuffix('/v1') + '/key/list', key, expected=[401, 403])
        request('http://127.0.0.1:8080/health')
        login = request('http://127.0.0.1:8080/api/v1/auths/signin', body={
            'email': os.environ['WEBUI_ADMIN_EMAIL'], 'password': os.environ['WEBUI_ADMIN_PASSWORD']})
        assert login['role'] == 'admin'
        discovered = request('http://127.0.0.1:8080/api/models', login['token'])['data']
        print('Gateway model IDs:', [m['id'] for m in models])
        print('WebUI model IDs:', [m['id'] for m in discovered])
        assert sorted(m['id'] for m in discovered) == sorted(m['id'] for m in models)
        print('PASS: internal WebUI login, LiteLLM discovery, inference key accepted, administration denied')


try:
    run()
except Exception as error:
    # Upstream errors can contain keys/connection strings. Do not print response bodies.
    sys.exit(f'Container probe failed ({type(error).__name__}); inspect local state without publishing secrets.')

"""Synthetic-only OpenViking account isolation and deletion acceptance on VM loopback."""

import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.request


BASE = 'http://127.0.0.1:1933'
ACCOUNT = 'gatewayai-private-acceptance-20261001b'
TEXT = 'Synthetic private memory marker: violet otter 742.'


def call(method, path, key, value=None):
    payload = None if value is None else json.dumps(value).encode()
    request = urllib.request.Request(BASE + path, payload,
                                     {'X-API-Key': key, 'Content-Type': 'application/json'},
                                     method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read(131073)
            status = response.status
    except urllib.error.HTTPError as error:
        return error.code, None
    if len(raw) > 131072:
        raise ValueError('Unexpected oversized response')
    body = json.loads(raw)
    if body.get('status') != 'ok':
        raise ValueError('OpenViking operation rejected')
    return status, body.get('result')


def accept(root):
    root = Path(root).resolve(strict=True)
    if os.name != 'posix' or os.geteuid() != 0 or not root.is_dir():
        raise ValueError('Root-only VM acceptance required')
    private = root/'private-acceptance-test.json'
    if private.exists():
        raise ValueError('Existing test receipt requires inspection')
    admin = json.loads((root/'admin.json').read_text())['root_api_key']
    public = json.loads((root/'account.json').read_text())['result']['user_key']
    status, account = call('POST', '/api/v1/admin/accounts', admin,
                           {'account_id': ACCOUNT, 'admin_user_id': 'owner'})
    if status != 200 or not isinstance(account, dict):
        raise ValueError('Synthetic account creation failed')
    user_key = account['user_key']
    os.umask(0o077)
    with private.open('x') as stream:
        json.dump({'account_id': ACCOUNT, 'user_key': user_key}, stream)
    private.chmod(0o600)
    status, session = call('POST', '/api/v1/sessions', user_key, {})
    if status != 200:
        raise ValueError('Private session creation failed')
    session_id = session['session_id']
    path = '/api/v1/sessions/'+session_id
    status, _ = call('POST', path+'/messages', user_key,
                     {'role': 'user', 'content': TEXT})
    if status != 200:
        raise ValueError('Private message creation failed')
    owner_read, owned = call('GET', path, user_key)
    other_read, _ = call('GET', path, public)
    anonymous_read, _ = call('GET', path, '')
    root_read, _ = call('GET', path, admin)
    if owner_read != 200 or other_read not in (401, 403, 404) or anonymous_read != 401 or root_read not in (401, 403):
        raise ValueError('Private session read isolation failed')
    status, _ = call('DELETE', path, user_key)
    after_delete, _ = call('GET', path, user_key)
    if status != 200 or after_delete not in (404, 410):
        raise ValueError('Session deletion did not revoke read access')
    status, _ = call('DELETE', '/api/v1/admin/accounts/'+ACCOUNT, admin)
    if status != 202:
        raise ValueError('Synthetic account deletion failed')
    after_account, _ = call('GET', '/api/v1/sessions', user_key)
    if after_account not in (401, 403):
        raise ValueError('Deleted account key still works')
    private.unlink()
    print(json.dumps({'private_owner_read': owner_read, 'public_account_read': other_read,
                      'anonymous_read': anonymous_read, 'root_data_read': root_read,
                      'session_after_delete': after_delete,
                      'account_key_after_delete': after_account,
                      'synthetic_only': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    accept(args.root)

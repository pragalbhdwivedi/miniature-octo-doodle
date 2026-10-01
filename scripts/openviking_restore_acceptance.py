"""Read-only acceptance of a restored OpenViking workspace on a clean VM."""

import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


def request(base, key, method, path, value=None):
    data = None if value is None else json.dumps(value).encode()
    req = urllib.request.Request(base+path, data,
                                 {'X-API-Key': key, 'Content-Type': 'application/json'},
                                 method=method)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=40) as reply:
            raw = reply.read(131073)
            status = reply.status
    except urllib.error.HTTPError as error:
        return error.code, None
    if len(raw) > 131072:
        raise ValueError('Oversized restore response')
    body = json.loads(raw)
    if body.get('status') != 'ok':
        raise ValueError('Restore request rejected')
    return status, body.get('result')


def accept(base, root):
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('Root-only restore acceptance required')
    root = Path(root).resolve(strict=True)
    if root.stat().st_mode & 0o077:
        raise ValueError('Restored directory permissions too broad')
    public = json.loads((root/'account.json').read_text())['result']['user_key']
    private = json.loads((root/'webui-private.json').read_text())['user_key']
    admin = json.loads((root/'admin.json').read_text())['root_api_key']
    manifest = json.loads((root/'public-main.json').read_text())
    private_state = json.loads((root/'webui-private-state.json').read_text())
    sha = manifest['source_sha']
    prefix = f'viking://resources/gatewayai/public-main-{sha}/'
    health = json.load(urllib.request.urlopen(base+'/health', timeout=10))
    if health.get('version') != 'v0.4.22':
        raise ValueError('Restored service version mismatch')
    if manifest['status'] != 'ready' or len(manifest['entries']) != 3:
        raise ValueError('Restored public manifest not ready')
    status, search = request(base, public, 'POST', '/api/v1/search/find',
                             {'query': 'OpenViking persistent context',
                              'target_uri': prefix, 'context_type': 'resource', 'limit': 3})
    hits = search.get('resources', []) if isinstance(search, dict) else []
    if status != 200 or not hits:
        raise ValueError('Restored authenticated public search failed')
    session = next(iter(private_state['chats'].values()))['session_id']
    path = '/api/v1/sessions/'+session
    owner_code, owner = request(base, private, 'GET', path)
    public_code, _ = request(base, public, 'GET', path)
    admin_code, _ = request(base, admin, 'GET', path)
    anonymous_code, _ = request(base, '', 'GET', path)
    if owner_code != 200 or not isinstance(owner, dict):
        raise ValueError('Restored private session unavailable')
    if public_code not in (401, 403, 404) or admin_code not in (401, 403) or anonymous_code != 401:
        raise ValueError('Restored private account isolation failed')
    if len(private_state['chats']) != 5:
        raise ValueError('Restored private chat count mismatch')
    return {'version': health['version'], 'public_source_sha': sha,
            'public_hits': len(hits), 'private_chat_count': len(private_state['chats']),
            'private_owner_read': owner_code, 'public_account_private_read': public_code,
            'root_private_read': admin_code, 'anonymous_private_read': anonymous_code,
            'read_only_test': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(accept(args.base, args.root)))

"""Bounded public-document OpenViking ingest/search acceptance on VM loopback."""

import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request


SOURCE_SHA = '8c57104bcf7d1386bf5f0075a0febaff9e526a22'
SOURCE = ('https://raw.githubusercontent.com/pragalbhdwivedi/'
          f'miniature-octo-doodle/{SOURCE_SHA}/docs/OPENVIKING.md')
BASE = 'http://127.0.0.1:1933'


def call(method, path, key=None, value=None):
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['X-API-Key'] = key
    request = urllib.request.Request(BASE+path,
        None if value is None else json.dumps(value).encode(), headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read(131073)
            status = response.status
    except urllib.error.HTTPError as exc:
        return exc.code, None
    if len(raw) > 131072:
        raise ValueError('OpenViking response exceeded limit')
    return status, json.loads(raw)


def accept(root, mode, existing_task=None, verify_only=False):
    root = Path(root).resolve(strict=True)
    admin = json.loads((root/'admin.json').read_text(encoding='utf-8'))
    account = json.loads((root/'account.json').read_text(encoding='utf-8'))
    user_key = account['result']['user_key']
    path = '/api/v1/fs/ls?'+urllib.parse.urlencode({'uri': 'viking://resources/'})
    anonymous, _ = call('GET', path)
    root_status, _ = call('GET', path, admin['root_api_key'])
    user_status, _ = call('GET', path, user_key)
    if anonymous != 401 or root_status not in (401, 403) or user_status != 200:
        raise ValueError('Account authorization boundary failed')
    destination = 'viking://resources/gatewayai/phase9-'+mode
    if existing_task:
        task_id = existing_task
    else:
        status, created = call('POST', '/api/v1/resources', user_key,
                               {'path': SOURCE, 'to': destination, 'processing_mode': mode})
        if status != 200 or created.get('status') != 'ok':
            raise ValueError('Public resource request failed')
        task_id = created['result']['task_id']
    outcome = None
    for _ in range(100):
        status, task = call('GET', '/api/v1/tasks/'+task_id, user_key)
        if status != 200 or task.get('status') != 'ok':
            raise ValueError('Task status lookup failed')
        outcome = task['result']['status']
        if outcome in ('completed', 'failed', 'error'):
            break
        time.sleep(3)
    if outcome != 'completed':
        raise ValueError('Resource task did not complete: '+str(outcome))
    status, found = call('POST', '/api/v1/search/find', user_key,
                         {'query': 'persistent memory context for agents',
                          'target_uri': destination, 'limit': 3})
    if status != 200 or found.get('status') != 'ok':
        raise ValueError('Authenticated search failed')
    result = found.get('result') or {}
    count = sum(len(result.get(group) or []) for group in ('resources', 'memories', 'skills'))
    receipt = {'source_sha': SOURCE_SHA, 'mode': mode, 'uri': destination,
               'task_id': task_id, 'task_status': outcome, 'find_count': count,
               'anonymous_http': anonymous, 'root_data_http': root_status,
               'user_data_http': user_status}
    target = root/('acceptance-'+mode+'.json')
    if not verify_only:
        with target.open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
        target.chmod(0o600)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--mode', choices=('vectors_only', 'semantic_and_vectors'), required=True)
    parser.add_argument('--existing-task')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if args.verify_only and not args.existing_task:
        parser.error('--verify-only requires --existing-task')
    accept(args.root, args.mode, args.existing_task, args.verify_only)

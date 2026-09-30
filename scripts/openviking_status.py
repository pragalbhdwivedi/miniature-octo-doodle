"""Print bounded, nonsecret OpenViking task statuses for VM operations."""

import argparse
import json
from pathlib import Path
import urllib.request


def status(root):
    root = Path(root).resolve(strict=True)
    account = json.loads((root/'account.json').read_text(encoding='utf-8'))
    request = urllib.request.Request('http://127.0.0.1:1933/api/v1/tasks',
                                      headers={'X-API-Key': account['result']['user_key']})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=15) as response:
        raw = response.read(131073)
    if len(raw) > 131072:
        raise ValueError('Task list exceeded limit')
    payload = json.loads(raw)
    result = payload.get('result')
    if isinstance(result, dict):
        tasks = result.get('tasks', [])
    elif isinstance(result, list):
        tasks = result
    else:
        raise ValueError('Unexpected task response')
    for task in tasks[:20]:
        print(json.dumps({'task_id': task.get('task_id') or task.get('id'),
                          'status': task.get('status'),
                          'processing_mode': task.get('processing_mode')}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    status(args.root)

"""Create one synthetic-only GatewayAI OpenViking account on VM loopback.

The root and returned admin credentials remain in root-only VM files.
"""

import argparse
import json
import os
from pathlib import Path
import urllib.request


def bootstrap(root):
    root = Path(root).resolve(strict=True)
    target = root/'account.json'
    if target.exists():
        raise ValueError('Account receipt already exists; inspect instead of recreating')
    admin = json.loads((root/'admin.json').read_text(encoding='utf-8'))
    if admin.get('url') != 'http://127.0.0.1:1933' or not admin.get('root_api_key'):
        raise ValueError('Expected loopback-only root credential')
    payload = json.dumps({'account_id': 'gatewayai', 'admin_user_id': 'operator'}).encode()
    request = urllib.request.Request(admin['url']+'/api/v1/admin/accounts', payload,
                                     {'Content-Type': 'application/json',
                                      'X-API-Key': admin['root_api_key']}, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=30) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError('Account response exceeded limit')
    receipt = json.loads(raw)
    os.umask(0o077)
    with target.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    target.chmod(0o600)
    print('Created gatewayai/operator account; private receipt saved; response fields:',
          sorted(receipt), sorted(receipt.get('result', {})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    bootstrap(args.root)

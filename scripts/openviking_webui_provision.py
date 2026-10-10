"""Create a dedicated OpenViking account for one Open WebUI administrator."""

import argparse
import json
import os
from pathlib import Path
import sqlite3

from openviking_webui_private import SyncError, api


ACCOUNT_ID = 'gatewayai-webui-admin'


def provision(db_path, root):
    root = Path(root).resolve(strict=True)
    if os.name != 'posix' or os.geteuid() != 0 or root.stat().st_mode & 0o077:
        raise SyncError('Root-only memory directory required')
    target = root/'webui-private.json'
    if target.exists():
        raise SyncError('Private account already provisioned; inspect before retrying')
    with sqlite3.connect(f'file:{Path(db_path).resolve(strict=True)}?mode=ro', uri=True) as db:
        rows = db.execute("SELECT id FROM user WHERE role = 'admin'").fetchall()
    if len(rows) != 1 or not isinstance(rows[0][0], str):
        raise SyncError('Expected exactly one WebUI admin account')
    admin_path = root/'admin.json'
    if admin_path.is_symlink() or admin_path.stat().st_mode & 0o077:
        raise SyncError('Administrative key file permissions too broad')
    admin_key = json.loads(admin_path.read_text(encoding='utf-8'))['root_api_key']
    status, result = api(admin_key, 'POST', '/api/v1/admin/accounts',
                         {'account_id': ACCOUNT_ID, 'admin_user_id': 'webui-admin'})
    if status != 200 or not isinstance(result, dict) or not result.get('user_key'):
        raise SyncError('Private account creation failed')
    os.umask(0o077)
    try:
        with target.open('x', encoding='utf-8') as stream:
            json.dump({'schema': 'gatewayai.webui-private.v1',
                       'account_id': ACCOUNT_ID, 'webui_user_id': rows[0][0],
                       'user_key': result['user_key']}, stream)
            stream.write('\n')
        target.chmod(0o600)
    except Exception:
        api(admin_key, 'DELETE', '/api/v1/admin/accounts/'+ACCOUNT_ID)
        raise
    print(json.dumps({'account_id': ACCOUNT_ID, 'webui_admin_count': 1,
                      'credential_location': str(target)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    provision(args.db, args.root)

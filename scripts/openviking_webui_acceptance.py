"""Synthetic live acceptance for WebUI owner isolation, mirror updates and deletion."""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3

from openviking_webui_private import api, sync


def chat(content):
    return {'history': {'currentId': 'm2', 'messages': {
        'm1': {'role': 'user', 'content': 'Synthetic prompt', 'parentId': None},
        'm2': {'role': 'assistant', 'content': content, 'parentId': 'm1'}}}}


def run(root):
    if os.geteuid() != 0:
        raise ValueError('Root-only acceptance required')
    root = Path(root).resolve(strict=True)
    admin = json.loads((root/'admin.json').read_text())['root_api_key']
    public = json.loads((root/'account.json').read_text())['result']['user_key']
    account_id = 'gatewayai-webui-acceptance-'+secrets.token_hex(4)
    status, account = api(admin, 'POST', '/api/v1/admin/accounts',
                          {'account_id': account_id, 'admin_user_id': 'owner'})
    if status != 200:
        raise ValueError('Acceptance account failed')
    key = account['user_key']
    test_root = root/('webui-acceptance-'+secrets.token_hex(4))
    test_root.mkdir(mode=0o700)
    try:
        (test_root/'webui-private.json').write_text(json.dumps({
            'schema': 'gatewayai.webui-private.v1', 'webui_user_id': 'owner',
            'user_key': key}))
        (test_root/'webui-private.json').chmod(0o600)
        db_path = test_root/'webui.db'
        with sqlite3.connect(db_path) as db:
            db.execute('CREATE TABLE user (id TEXT, role TEXT)')
            db.execute('CREATE TABLE chat (id TEXT, user_id TEXT, chat TEXT)')
            db.executemany('INSERT INTO user VALUES (?, ?)',
                           [('owner', 'admin'), ('other', 'user')])
            db.executemany('INSERT INTO chat VALUES (?, ?, ?)', [
                ('owned', 'owner', json.dumps(chat('Synthetic answer one'))),
                ('other-chat', 'other', json.dumps(chat('Other account secret')))])
        first = sync(db_path, test_root)
        state = json.loads((test_root/'webui-private-state.json').read_text())
        if first['created'] != 1 or set(state['chats']) != {'owned'}:
            raise ValueError('Owner scoping failed')
        sid = state['chats']['owned']['session_id']
        owner_read, _ = api(key, 'GET', '/api/v1/sessions/'+sid)
        public_read, _ = api(public, 'GET', '/api/v1/sessions/'+sid)
        if owner_read != 200 or public_read not in (401, 403, 404):
            raise ValueError('Owner isolation failed')
        if sync(db_path, test_root)['created'] != 0:
            raise ValueError('Idempotent sync failed')
        with sqlite3.connect(db_path) as db:
            db.execute('UPDATE chat SET chat = ? WHERE id = ?',
                       (json.dumps(chat('Synthetic answer two')), 'owned'))
        if sync(db_path, test_root)['updated'] != 1:
            raise ValueError('Update sync failed')
        with sqlite3.connect(db_path) as db:
            db.execute('DELETE FROM chat WHERE id = ?', ('owned',))
        if sync(db_path, test_root)['deleted'] != 1:
            raise ValueError('Deletion sync failed')
        deleted_read, _ = api(key, 'GET', '/api/v1/sessions/'+sid)
        if deleted_read != 404:
            raise ValueError('Deleted session remains readable')
        print(json.dumps({'owner_scoped': True, 'other_account_denied': True,
                          'repeat_noop': True, 'update_replaced': True,
                          'deleted_session_read': deleted_read, 'synthetic_only': True}))
    finally:
        status, _ = api(admin, 'DELETE', '/api/v1/admin/accounts/'+account_id)
        if status != 202:
            raise ValueError('Acceptance account cleanup failed')
        shutil.rmtree(test_root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)

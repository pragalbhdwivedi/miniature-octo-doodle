"""Mirror one Open WebUI user's saved text chats into isolated OpenViking sessions.

Run on the VM as root. The WebUI SQLite database is opened read-only; credentials,
session IDs and sync state stay in a mode-0700 directory. No extracted long-term
memory is produced, so deleting a WebUI chat deletes its complete mirror.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import urllib.error
import urllib.request
import uuid


BASE = 'http://127.0.0.1:1933'
MAX_CHAT_BYTES = 262144
MAX_MESSAGE_BYTES = 32768
MAX_RESPONSE_BYTES = 131072
NAMESPACE = uuid.UUID('d1864f13-a76e-4f9e-82a2-018baf5af317')


class SyncError(RuntimeError):
    pass


def api(key, method, path, value=None):
    data = None if value is None else json.dumps(value, separators=(',', ':')).encode()
    req = urllib.request.Request(BASE + path, data,
                                 {'X-API-Key': key, 'Content-Type': 'application/json'},
                                 method=method)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=40) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return 404, None
        raise SyncError(f'OpenViking HTTP {error.code} at {path}') from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise SyncError('OpenViking unavailable') from error
    if len(raw) > MAX_RESPONSE_BYTES:
        raise SyncError('OpenViking response too large')
    body = json.loads(raw)
    if not isinstance(body, dict) or body.get('status') != 'ok':
        raise SyncError(f'OpenViking rejected {path}')
    return status, body.get('result')


def active_messages(chat):
    history = chat.get('history')
    if not isinstance(history, dict):
        raise SyncError('WebUI chat history missing')
    table = history.get('messages')
    current = history.get('currentId')
    if not isinstance(table, dict) or not isinstance(current, str):
        raise SyncError('WebUI active branch missing')
    result = []
    seen = set()
    while current:
        if current in seen or current not in table:
            raise SyncError('WebUI chat branch invalid')
        seen.add(current)
        message = table[current]
        if not isinstance(message, dict):
            raise SyncError('WebUI message invalid')
        role = message.get('role')
        content = message.get('content')
        if role not in ('user', 'assistant') or not isinstance(content, str):
            raise SyncError('WebUI chat contains unsupported message type')
        if len(content.encode('utf-8')) > MAX_MESSAGE_BYTES:
            raise SyncError('WebUI message exceeds private-memory limit')
        result.append({'role': role, 'content': content})
        current = message.get('parentId')
        if current is not None and not isinstance(current, str):
            raise SyncError('WebUI branch parent invalid')
    result.reverse()
    # Never capture a prompt whose assistant completion has not been saved.
    if result and result[-1]['role'] == 'user':
        result.pop()
    return result


def read_chats(db_path, owner_id):
    path = Path(db_path).resolve(strict=True)
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=10) as db:
        db.execute('PRAGMA query_only=ON')
        owner = db.execute('SELECT role FROM user WHERE id = ?', (owner_id,)).fetchone()
        if owner != ('admin',):
            raise SyncError('Configured WebUI admin account missing or changed')
        rows = db.execute('SELECT id, chat FROM chat WHERE user_id = ?', (owner_id,)).fetchall()
    output = {}
    for chat_id, raw in rows:
        if not isinstance(chat_id, str) or not isinstance(raw, str):
            raise SyncError('Invalid WebUI chat row')
        chat = json.loads(raw)
        messages = active_messages(chat)
        if not messages:
            continue
        encoded = json.dumps(messages, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(encoded) > MAX_CHAT_BYTES:
            raise SyncError('WebUI chat exceeds private-memory limit')
        output[chat_id] = (hashlib.sha256(encoded).hexdigest(), messages)
    return output


def atomic_save(path, value):
    next_path = path.with_suffix('.next')
    with next_path.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write('\n')
    next_path.chmod(0o600)
    os.replace(next_path, path)


def sync(db_path, root, *, client=api):
    root = Path(root)
    if os.name != 'posix' or os.geteuid() != 0 or root.is_symlink() or not root.is_dir():
        raise SyncError('Root-only memory directory required')
    root = root.resolve(strict=True)
    if root.stat().st_mode & 0o077:
        raise SyncError('Memory directory permissions too broad')
    config_path = root/'webui-private.json'
    if config_path.is_symlink() or config_path.stat().st_mode & 0o077:
        raise SyncError('Private credential permissions too broad')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if config.get('schema') != 'gatewayai.webui-private.v1':
        raise SyncError('Private account config schema mismatch')
    key, owner = config['user_key'], config['webui_user_id']
    if not isinstance(key, str) or not key or not isinstance(owner, str) or not owner:
        raise SyncError('Private account config invalid')
    chats = read_chats(db_path, owner)
    state_path = root/'webui-private-state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {
        'schema': 'gatewayai.webui-private-state.v1', 'webui_user_id': owner, 'chats': {}}
    if state.get('schema') != 'gatewayai.webui-private-state.v1' or state.get('webui_user_id') != owner:
        raise SyncError('Private sync state does not match account')
    recorded = state['chats']
    created = updated = deleted = 0
    # Never delete a session on a partial database read or malformed chat.
    for chat_id in sorted(set(recorded) - set(chats)):
        status, _ = client(key, 'DELETE', '/api/v1/sessions/'+recorded[chat_id]['session_id'])
        if status not in (200, 202, 204, 404):
            raise SyncError('OpenViking session deletion failed')
        del recorded[chat_id]
        atomic_save(state_path, state)
        deleted += 1
    for chat_id, (digest, messages) in sorted(chats.items()):
        previous = recorded.get(chat_id)
        if previous and previous['sha256'] == digest:
            continue
        session_id = str(uuid.uuid5(NAMESPACE, owner+':'+chat_id))
        # Also clear a partially uploaded session left by an interrupted run.
        status, _ = client(key, 'DELETE', '/api/v1/sessions/'+session_id)
        if status not in (200, 202, 204, 404):
            raise SyncError('OpenViking session replacement failed')
        status, result = client(key, 'POST', '/api/v1/sessions', {'session_id': session_id,
                                                                 'telemetry': False})
        if status != 200 or not isinstance(result, dict) or result.get('session_id') != session_id:
            raise SyncError('OpenViking session creation failed')
        for message in messages:
            status, _ = client(key, 'POST', '/api/v1/sessions/'+session_id+'/messages', message)
            if status != 200:
                raise SyncError('OpenViking message creation failed')
        recorded[chat_id] = {'session_id': session_id, 'sha256': digest,
                             'message_count': len(messages)}
        atomic_save(state_path, state)
        if previous:
            updated += 1
        else:
            created += 1
    return {'owner_chat_count': len(chats), 'created': created, 'updated': updated,
            'deleted': deleted, 'mirrored': len(recorded)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(sync(args.db, args.root)))

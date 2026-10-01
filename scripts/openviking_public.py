"""Bounded, resumable public-main OpenViking resource sync and advisory lookup.

Only named public repository files may be imported. GitHub remains authoritative;
an incomplete or stale import is never served to a caller.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


REPOSITORY = 'https://github.com/pragalbhdwivedi/miniature-octo-doodle.git'
DOCS = ('PROJECT.md', 'docs/ROADMAP.md', 'docs/OPENVIKING.md')
BASE = 'http://127.0.0.1:1933'
MAX_REPLY = 131072


class ContextError(ValueError):
    pass


def main_sha():
    result = subprocess.run(['git', 'ls-remote', REPOSITORY, 'refs/heads/main'],
                            capture_output=True, timeout=20, check=True)
    line = result.stdout.decode('ascii').strip()
    if not re.fullmatch(r'[a-f0-9]{40}\trefs/heads/main', line):
        raise ContextError('Public main revision unavailable')
    return line.split('\t', 1)[0]


def request(key, method, path, body=None):
    if not isinstance(key, str) or not key:
        raise ContextError('Operator key missing')
    data = None if body is None else json.dumps(body, separators=(',', ':')).encode()
    req = urllib.request.Request(BASE + path, data,
                                 {'X-API-Key': key, 'Content-Type': 'application/json'}, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=45) as response:
            raw = response.read(MAX_REPLY + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ContextError('OpenViking request unavailable') from exc
    if len(raw) > MAX_REPLY:
        raise ContextError('OpenViking response too large')
    result = json.loads(raw)
    if not isinstance(result, dict) or result.get('status') != 'ok':
        raise ContextError('OpenViking rejected operation')
    return result.get('result')


def read_key(root):
    path = root/'account.json'
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ContextError('Credential receipt invalid')
    return json.loads(path.read_text(encoding='utf-8'))['result']['user_key']


def save(path, value):
    data = json.dumps(value, sort_keys=True, indent=2)+'\n'
    next_path = path.with_suffix('.json.next')
    with next_path.open('w', encoding='utf-8') as stream:
        stream.write(data)
    next_path.chmod(0o600)
    os.replace(next_path, path)


def load(root):
    path = root/'public-main.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def destination(sha, name):
    slug = name.replace('/', '-')
    return f'viking://resources/gatewayai/public-main-{sha}/{slug}'


def sync(root, *, sha_reader=main_sha, api=request, pause=time.sleep):
    if Path(root).is_symlink():
        raise ContextError('Private OpenViking root required')
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ContextError('Private OpenViking root required')
    key = read_key(root)
    sha = sha_reader()
    state = load(root)
    if state and state.get('source_sha') == sha and state.get('status') == 'ready':
        return {'status': 'ready', 'source_sha': sha, 'changed': False}
    if not state or state.get('source_sha') != sha:
        state = {'schema': 'gatewayai.openviking-public.v1', 'source_sha': sha,
                 'status': 'building', 'entries': {}}
        save(root/'public-main.json', state)
    if state.get('schema') != 'gatewayai.openviking-public.v1' or state.get('status') == 'failed':
        raise ContextError('Inspect failed or unexpected sync state before retrying')
    for name in DOCS:
        entry = state['entries'].get(name)
        uri = destination(sha, name)
        if entry and entry.get('status') == 'completed':
            continue
        if not entry:
            source = (f'https://raw.githubusercontent.com/pragalbhdwivedi/'
                      f'miniature-octo-doodle/{sha}/{name}')
            result = api(key, 'POST', '/api/v1/resources',
                         {'path': source, 'to': uri, 'processing_mode': 'vectors_only'})
            task_id = result['task_id']
            if not re.fullmatch(r'[a-f0-9-]{36}', task_id):
                raise ContextError('Invalid resource task ID')
            entry = {'uri': uri, 'task_id': task_id, 'status': 'running'}
            state['entries'][name] = entry
            save(root/'public-main.json', state)
        # Return on a still-running task; a timer resumes it without duplicate ingestion.
        for attempt in range(24):
            task = api(key, 'GET', '/api/v1/tasks/'+entry['task_id'])
            status = task.get('status')
            if status == 'completed':
                entry['status'] = 'completed'
                save(root/'public-main.json', state)
                break
            if status in ('failed', 'error'):
                state['status'] = 'failed'
                save(root/'public-main.json', state)
                raise ContextError('Resource ingestion failed; inspect before retrying')
            if status not in ('pending', 'running'):
                raise ContextError('Unexpected resource task state')
            if attempt < 23:
                pause(5)
        if entry['status'] != 'completed':
            return {'status': 'building', 'source_sha': sha, 'changed': True}
    if sha_reader() != sha:
        return {'status': 'stale', 'source_sha': sha, 'changed': True}
    state['status'] = 'ready'
    save(root/'public-main.json', state)
    return {'status': 'ready', 'source_sha': sha, 'changed': True}


def find(root, source_sha, query, *, role='controller', sha_reader=main_sha, api=request):
    if role not in ('controller', 'webui-public') or not isinstance(query, str) or not 1 <= len(query.strip()) <= 200:
        raise ContextError('Public context query denied')
    if not isinstance(source_sha, str) or not re.fullmatch(r'[a-f0-9]{40}', source_sha) or sha_reader() != source_sha:
        raise ContextError('GitHub main advanced; stale context denied')
    root = Path(root).resolve(strict=True)
    state = load(root)
    if (not isinstance(state, dict) or state.get('schema') != 'gatewayai.openviking-public.v1'
            or state.get('status') != 'ready' or state.get('source_sha') != source_sha
            or set(state.get('entries', {})) != set(DOCS)
            or any(e.get('status') != 'completed' or e.get('uri') != destination(source_sha, name)
                   for name, e in state['entries'].items())):
        raise ContextError('Current public context unavailable')
    prefix = f'viking://resources/gatewayai/public-main-{source_sha}/'
    result = api(read_key(root), 'POST', '/api/v1/search/find',
                 {'query': query.strip(), 'target_uri': prefix, 'context_type': 'resource', 'limit': 3})
    if not isinstance(result, dict):
        raise ContextError('Invalid retrieval response')
    hits = []
    allowed = tuple(destination(source_sha, name) for name in DOCS)
    for item in (result.get('resources') or [])[:3]:
        uri = item.get('uri')
        abstract = item.get('abstract') or item.get('overview') or ''
        if (not isinstance(uri, str) or not uri.startswith(prefix)
                or not any(uri == base or uri.startswith(base+'/') for base in allowed)
                or not isinstance(abstract, str)):
            raise ContextError('Out-of-scope retrieval result')
        if not abstract:
            content = api(read_key(root), 'GET',
                          '/api/v1/content/read?'+urllib.parse.urlencode({'uri': uri}))
            if not isinstance(content, str):
                raise ContextError('Invalid public content result')
            abstract = content
        hits.append({'uri': uri, 'abstract': abstract[:600]})
    return {'schema': 'gatewayai.openviking-result.v1', 'source_sha': source_sha,
            'classification': 'public', 'advisory_only': True,
            'query_sha256': hashlib.sha256(query.encode()).hexdigest(),
            'hits': hits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('sync', 'find'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-sha')
    parser.add_argument('--query')
    args = parser.parse_args()
    if os.name != 'posix':
        raise ContextError('VM operator only')
    import fcntl
    with (args.root/'public-main.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        value = sync(args.root) if args.action == 'sync' else find(args.root, args.source_sha, args.query)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ContextError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        raise SystemExit('OpenViking public workflow stopped: '+type(exc).__name__) from None

"""Operator-only AADI issue and draft PR publisher; never merges or edits Dev.

Configuration, admission and test/review evidence belong to the operator worker,
not to model output. Credentials are obtained from the existing Git helper only
inside the transport. Durable intent records turn uncertain writes into read-only
reconciliation, never an automatic duplicate creation.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import urllib.error
import urllib.request


REPOSITORY = 'pragalbhdwivedi/aadi'
BASE = 'Dev'
API = 'https://api.github.com/repos/' + REPOSITORY
REMOTE = 'https://github.com/' + REPOSITORY + '.git'


class PublishError(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def task_key(task_id):
    if not isinstance(task_id, str) or not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9-]{0,63}', task_id):
        raise PublishError('Invalid task ID')
    return task_id.lower()[:40] + '-' + digest(task_id)[:12]


def branch_for(task_id):
    return 'supervisor/' + task_key(task_id)


def marker_for(task_id):
    return '<!-- aadi-supervisor:' + task_key(task_id) + ' -->'


def artifact_digest(task):
    return digest({k: task[k] for k in ('id', 'source_sha', 'files')})


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, encoding='utf-8', delete=False) as f:
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
        name = f.name
    os.replace(name, path)


@contextmanager
def _lock(path):
    """A crash intentionally leaves a lock requiring operator reconciliation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise PublishError('Publisher is active or needs stale-lock reconciliation') from None
    os.close(fd)
    try:
        yield
    finally:
        path.unlink()


def git(repo, *args, data=None, timeout=90):
    env = os.environ.copy()
    for name in list(env):
        if name.startswith('GIT_TRACE') or name == 'GIT_CURL_VERBOSE':
            env.pop(name)
    env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    try:
        result = subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull,
            '-c', 'commit.gpgsign=false', '-C', str(repo), *args], input=data,
            capture_output=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise PublishError('Git operation failed or timed out') from None
    if result.returncode:
        # Git stderr may include authenticated remote URLs. Never return it.
        raise PublishError('Git operation failed: ' + args[0])
    if len(result.stdout) > 2_000_000:
        raise PublishError('Git result exceeds limit')
    return result.stdout.decode('utf-8').strip()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublishError('GitHub redirect refused')


class Github:
    def __init__(self, config, transport=None):
        if config.get('repository', REPOSITORY) != REPOSITORY or config.get('base', BASE) != BASE:
            raise PublishError('Only the admitted AADI Dev repository is supported')
        self.config = dict(config)
        self.ledger = Path(config['ledger_path'])
        self.transport = transport or self._transport

    def _transport(self, method, path, body=None):
        # Only this fixed repository API receives the helper credential.
        if not re.fullmatch(r'/(issues|pulls)(/[1-9][0-9]*)?(\?[a-zA-Z0-9_=&:%.-]+)?', path):
            raise PublishError('API endpoint is outside publisher scope')
        if method not in ('GET', 'POST', 'PATCH'):
            raise PublishError('API operation is outside publisher scope')
        credential = git(self.config['repo'], 'credential', 'fill',
            data=('protocol=https\nhost=github.com\npath=' + REPOSITORY + '.git\n\n').encode())
        secret = dict(line.split('=', 1) for line in credential.splitlines() if '=' in line).get('password')
        if not secret:
            raise PublishError('Existing GitHub credential helper has no credential')
        request = urllib.request.Request(API + path,
            data=None if body is None else json.dumps(body).encode(), method=method,
            headers={'Authorization': 'Bearer ' + secret, 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json',
                     'User-Agent': 'aadi-bounded-supervisor'})
        try:
            with urllib.request.build_opener(_NoRedirect).open(request, timeout=30) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise PublishError('GitHub response exceeds limit')
            return json.loads(data)
        except Exception:
            raise PublishError('GitHub request failed; reconcile before retrying a write') from None

    def _rows(self, kind, state='all'):
        rows = []
        for page in range(1, 21):
            part = self.transport('GET', f'/{kind}?state={state}&per_page=100&page={page}')
            if not isinstance(part, list):
                raise PublishError('Invalid GitHub list response')
            rows.extend(part)
            if len(part) < 100:
                return [r for r in rows if kind != 'issues' or 'pull_request' not in r]
        raise PublishError('Repository list exceeds reconciliation bound')

    def open_work(self):
        return {'issues': self._rows('issues', 'open'), 'pulls': self._rows('pulls', 'open')}

    def publication_preflight(self, task_id):
        """Reject a closed/ready/foreign draft before changing its source branch."""
        marker = marker_for(task_id)
        for kind in ('issues', 'pulls'):
            found = [r for r in self._rows(kind) if marker in (r.get('body') or '')]
            if len(found) > 1:
                raise PublishError('Duplicate task markers require operator reconciliation')
            for row in found:
                if row.get('state') != 'open':
                    raise PublishError('Existing task has closed; publication is stopped')
                if kind == 'pulls' and (row.get('draft') is not True or row.get('auto_merge')
                        or row.get('head', {}).get('ref') != branch_for(task_id)
                        or row.get('head', {}).get('repo', {}).get('full_name') != REPOSITORY
                        or row.get('base', {}).get('ref') != BASE):
                    raise PublishError('Existing PR is outside admitted draft scope')

    def ensure_issue(self, task_id, title, body):
        return self._ensure('issues', task_id, title, body)

    def ensure_draft(self, task_id, branch, title, body, issue_number=None):
        if branch != branch_for(task_id):
            raise PublishError('Unexpected task branch')
        if issue_number is not None:
            if type(issue_number) is not int or issue_number < 1:
                raise PublishError('Invalid issue number')
            body += '\n\nTracked task: #' + str(issue_number)
        body += '\n\nDraft for owner review. No merge or deployment has been performed.'
        return self._ensure('pulls', task_id, title, body, branch)

    def _ensure(self, kind, task_id, title, body, branch=None):
        marker = marker_for(task_id)
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise PublishError('Invalid title')
        if not isinstance(body, str) or len(body) > 30_000:
            raise PublishError('Invalid body')
        body = body.rstrip() + '\n\n' + marker
        desired = {'title': title.strip(), 'body': body}
        key = kind + ':' + task_key(task_id)
        with _lock(self.ledger.with_suffix('.lock')):
            ledger = json.loads(self.ledger.read_text()) if self.ledger.exists() else {}
            previous = ledger.get(key, {})
            matches = [r for r in self._rows(kind) if marker in (r.get('body') or '')]
            if len(matches) > 1:
                raise PublishError('Duplicate task markers require operator reconciliation')
            found = matches[0] if matches else None
            if found:
                number = found.get('number')
                if type(number) is not int or number < 1 or found.get('state') != 'open':
                    raise PublishError('Existing task is closed or invalid; no replacement will be created')
                if kind == 'pulls' and (found.get('draft') is not True
                    or found.get('head', {}).get('ref') != branch
                    or found.get('head', {}).get('repo', {}).get('full_name') != REPOSITORY
                    or found.get('base', {}).get('ref') != BASE):
                    raise PublishError('Existing PR is outside the admitted draft scope')
                if previous.get('number') not in (None, number):
                    raise PublishError('Task marker changed identity')
                if any(found.get(k) != v for k, v in desired.items()):
                    observed = digest({k: found.get(k) for k in desired})
                    if previous.get('state') == 'intent' and previous.get('digest') != observed:
                        raise PublishError('Uncertain update not observed; manual reconciliation required')
                    ledger[key] = {'state': 'intent', 'number': number, 'digest': digest(desired)}
                    _write(self.ledger, ledger)
                    self.transport('PATCH', f'/{kind}/{number}', desired)
                    # Reconcile using a new read, not a possibly ambiguous response.
                    found = self.transport('GET', f'/{kind}/{number}')
            else:
                if previous:
                    raise PublishError('Uncertain or missing remote task; creation is not replayed')
                payload = dict(desired)
                if kind == 'pulls':
                    payload.update(head=branch, base=BASE, draft=True, maintainer_can_modify=False)
                ledger[key] = {'state': 'intent', 'digest': digest(desired)}
                _write(self.ledger, ledger)
                created = self.transport('POST', '/' + kind, payload)
                number = created.get('number') if isinstance(created, dict) else None
                if type(number) is not int or number < 1:
                    raise PublishError('Creation is uncertain; awaiting remote reconciliation')
                # Repository lists can lag a successful write. Verify the exact
                # resource with a fresh GET; never repeat POST on uncertainty.
                found = self.transport('GET', f'/{kind}/{number}')
                if found.get('number') != number or marker not in (found.get('body') or ''):
                    raise PublishError('Created resource identity was not confirmed')
            if any(found.get(k) != v for k, v in desired.items()):
                raise PublishError('Remote update not confirmed')
            if found.get('state') != 'open' or (kind == 'pulls' and (found.get('draft') is not True
                    or found.get('head', {}).get('ref') != branch or found.get('base', {}).get('ref') != BASE
                    or found.get('head', {}).get('repo', {}).get('full_name') != REPOSITORY)):
                raise PublishError('Remote task is no longer an open admitted draft')
            receipt = {'state': 'confirmed', 'number': found['number'], 'url': found['html_url'],
                       'digest': digest(desired), 'kind': kind}
            if kind == 'pulls':
                receipt.update(draft=True, branch=branch, base=BASE)
            ledger[key] = receipt
            _write(self.ledger, ledger)
            return receipt


def _validate(config, task, evidence):
    task_key(task['id'])
    if not re.fullmatch('[a-f0-9]{40}', task.get('source_sha', '')):
        raise PublishError('Invalid pinned source SHA')
    if (evidence.get('tests_passed') is not True or evidence.get('review_passed') is not True
            or evidence.get('source_sha') != task['source_sha']
            or evidence.get('artifact_sha256') != artifact_digest(task)):
        raise PublishError('Fresh matching test and review evidence is required')
    files = task['files']
    admitted = config['admitted_paths']
    if not isinstance(files, dict) or not 1 <= len(files) <= 16 or not isinstance(admitted, list):
        raise PublishError('Invalid admitted replacement files')
    seen = set()
    for name, content in files.items():
        p = PurePosixPath(name)
        if (not isinstance(name, str) or name not in admitted or p.as_posix() != name
                or p.is_absolute() or any(x in ('.', '..') or x.startswith('.') for x in p.parts)
                or re.search(r'[:\\\x00-\x1f]', name) or name.casefold() in seen
                or p.parts[0].casefold() in ('secrets', 'creds', 'vm_notes', 'local_certificates')
                or not isinstance(content, str) or '\x00' in content):
            raise PublishError('Replacement is outside admitted text paths')
        seen.add(name.casefold())
    if sum(len(v.encode()) for v in files.values()) > 262144:
        raise PublishError('Replacement content exceeds bound')


def _remote_head(repo, branch):
    result = git(repo, 'ls-remote', '--heads', REMOTE, 'refs/heads/' + branch)
    if not result:
        return None
    rows = result.splitlines()
    if len(rows) != 1 or rows[0].split()[1] != 'refs/heads/' + branch:
        raise PublishError('Unexpected remote reference')
    return rows[0].split()[0]


def publish_candidate(config, task, evidence, github=None):
    """Publish operator-admitted, tested replacements only to a task draft branch.

    Updates must retain the same pinned source; the previous supervisor commit is
    their parent. No branch deletion/reset/force push/merge exists in this adapter.
    Worktrees and journals are retained as evidence, never recursively removed.
    """
    client = github or Github(config)
    _validate(config, task, evidence)
    repo = Path(config['repo']).resolve()
    branch = branch_for(task['id'])
    root = Path(config['worktree_root']).resolve()
    if root == repo or root.is_relative_to(repo):
        raise PublishError('Publisher worktrees must be outside source checkout')
    root.mkdir(parents=True, exist_ok=True)
    journal = root / (task_key(task['id']) + '.json')
    folder = root / task_key(task['id'])
    artifact = artifact_digest(task)
    with _lock(root / (task_key(task['id']) + '.lock')):
        state = json.loads(journal.read_text()) if journal.exists() else {}
        client.publication_preflight(task['id'])
        if state.get('source_sha', task['source_sha']) != task['source_sha']:
            raise PublishError('Task source changed; use a new task ID after fresh admission')
        if state.get('paths', sorted(task['files'])) != sorted(task['files']):
            raise PublishError('Task file scope changed; fresh task admission is required')
        if _remote_head(repo, BASE) != task['source_sha']:
            raise PublishError('Dev advanced; refresh admission and verification')
        remote = _remote_head(repo, branch)
        if state.get('pushing'):
            if remote != state['commit']:
                raise PublishError('Uncertain push not observed; read-only reconciliation required')
            state['pushing'] = False
            _write(journal, state)
        if remote and remote != state.get('commit'):
            raise PublishError('Remote task branch is not owned by this journal')
        if state.get('commit') and remote != state['commit']:
            raise PublishError('Published task branch is missing; publication is stopped')
        if state.get('artifact') != artifact:
            if not folder.exists():
                if state:
                    raise PublishError('Retained publication worktree is missing')
                git(repo, 'worktree', 'add', '-b', branch, str(folder), task['source_sha'])
            if git(folder, 'status', '--porcelain'):
                raise PublishError('Publication worktree is dirty; inspect retained evidence')
            if git(folder, 'rev-parse', 'HEAD') != state.get('commit', task['source_sha']):
                raise PublishError('Publication worktree HEAD changed')
            if git(folder, 'symbolic-ref', '--short', 'HEAD') != branch:
                raise PublishError('Publication worktree branch changed')
            for name, content in task['files'].items():
                destination = folder / name
                if not destination.resolve().is_relative_to(folder.resolve()):
                    raise PublishError('Symlink escaped publication worktree')
                entry = git(folder, 'ls-files', '-s', '--', name)
                if entry and entry.split()[0] not in ('100644', '100755'):
                    raise PublishError('Only regular tracked text files may be replaced')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content.encode('utf-8'))
                # Store exact reviewed bytes. Git clean filters must not transform
                # the candidate or execute while staging model-generated content.
                blob = git(folder, 'hash-object', '-w', '--stdin', '--no-filters', data=content.encode('utf-8'))
                mode = entry.split()[0] if entry else '100644'
                git(folder, 'update-index', '--add', '--cacheinfo', mode, blob, name)
            changed = git(folder, 'diff', '--cached', '--name-only').splitlines()
            if not changed or not set(changed).issubset(task['files']):
                raise PublishError('Staged content does not match admitted files')
            git(folder, '-c', 'user.name=AADI Supervisor', '-c', 'user.email=supervisor@users.noreply.github.com',
                'commit', '-m', 'Draft task ' + task['id'])
            state.update(source_sha=task['source_sha'], artifact=artifact,
                         paths=sorted(task['files']), commit=git(folder, 'rev-parse', 'HEAD'), pushing=True)
            _write(journal, state)
            # Explicit refspec and fixed HTTPS repository; never updates Dev/main.
            client.publication_preflight(task['id'])
            git(folder, 'push', '--no-verify', REMOTE, 'HEAD:refs/heads/' + branch)
            if _remote_head(repo, branch) != state['commit']:
                raise PublishError('Remote task branch publication not confirmed')
            state['pushing'] = False
            _write(journal, state)
        issue = client.ensure_issue(task['id'], task['title'], task.get('body', ''))
        body = (task.get('body', '') + '\n\nTests and independent review passed for artifact `' + artifact
                + '`.\nPinned source: `' + task['source_sha'] + '`.')
        pr = client.ensure_draft(task['id'], branch, task['title'], body, issue['number'])
        receipt = {'task_id': task['id'], 'source_sha': task['source_sha'], 'artifact_sha256': artifact,
                   'commit': state['commit'], 'branch': branch, 'issue': issue, 'pull_request': pr,
                   'merged': False, 'deployed': False}
        state['receipt'] = receipt
        _write(journal, state)
        return receipt

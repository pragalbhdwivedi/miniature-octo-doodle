"""Operator-only admitted-project draft publisher; never merges or edits bases.

Configuration, admission and test/review evidence belong to the operator worker,
not to model output. Credentials are obtained from the existing Git helper only
inside the transport. Durable intent records turn uncertain writes into read-only
reconciliation, never an automatic duplicate creation.
"""
from contextlib import contextmanager
from datetime import datetime
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
PROJECTS = {REPOSITORY: BASE, 'pragalbhdwivedi/miniature-octo-doodle': 'main'}


class PublishError(RuntimeError):
    pass


def project_scope(config):
    repository = config.get('repository', REPOSITORY)
    base = config.get('base', PROJECTS.get(repository))
    if repository not in PROJECTS or base != PROJECTS[repository]:
        raise PublishError('Repository and base are outside the operator allowlist')
    return repository, base


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
    value = {k: task[k] for k in ('id', 'source_sha', 'files')}
    repository, base = project_scope(task)
    # Keep existing AADI receipt hashes usable. New-project hashes explicitly
    # bind repository/base so identical files cannot transfer review authority.
    if repository != REPOSITORY or 'repository' in task or 'base' in task:
        value.update(repository=repository, base=base)
    return digest(value)


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
        self.repository, self.base = project_scope(config)
        self.api = 'https://api.github.com/repos/' + self.repository
        self.remote = REMOTE if self.repository == REPOSITORY else 'https://github.com/' + self.repository + '.git'
        self.config = dict(config)
        self.ledger = Path(config['ledger_path'])
        self.transport = transport or self._transport

    def _transport(self, method, path, body=None):
        # Only this fixed repository API receives the helper credential.
        if not re.fullmatch(r'/(issues|pulls)(/[1-9][0-9]*(/(reviews|comments))?)?(\?[a-zA-Z0-9_=&:%.-]+)?', path):
            raise PublishError('API endpoint is outside publisher scope')
        if method not in ('GET', 'POST', 'PATCH'):
            raise PublishError('API operation is outside publisher scope')
        if re.search(r'/(reviews|comments)(\?|$)', path) and method != 'GET':
            raise PublishError('Review and comment endpoints are read-only')
        credential = git(self.config['repo'], 'credential', 'fill',
            data=('protocol=https\nhost=github.com\npath=' + self.repository + '.git\n\n').encode())
        secret = dict(line.split('=', 1) for line in credential.splitlines() if '=' in line).get('password')
        if not secret:
            raise PublishError('Existing GitHub credential helper has no credential')
        request = urllib.request.Request(self.api + path,
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

    def _discussion_rows(self, path):
        rows = []
        for page in range(1, 6):
            part = self.transport('GET', f'{path}?per_page=100&page={page}')
            if not isinstance(part, list) or len(part) > 100 or any(not isinstance(r, dict) for r in part):
                raise PublishError('Invalid PR discussion response')
            rows.extend(part)
            if len(part) < 100:
                return rows
        # Do not silently omit an older/newer blocking review at the bound.
        raise PublishError('PR discussion exceeds reconciliation bound')

    def reconcile_pr(self, number, task_id=None):
        """Read one exact PR and its reviews/comments; grants no approval.

        Latest review and latest decisive review are separate: a COMMENTED review
        must not silently erase an actor's outstanding CHANGES_REQUESTED review.
        Text and actor roles are returned as evidence for the controller's own
        policy, never interpreted as instructions or publication authority.
        """
        if type(number) is not int or number < 1:
            raise PublishError('Invalid pull request number')

        def snapshot():
            row = self.transport('GET', f'/pulls/{number}')
            if (not isinstance(row, dict) or row.get('number') != number
                    or row.get('base', {}).get('repo', {}).get('full_name') != self.repository
                    or row.get('base', {}).get('ref') != self.base
                    or row.get('state') not in ('open', 'closed')
                    or type(row.get('draft')) is not bool or type(row.get('merged')) is not bool
                    or not re.fullmatch('[a-f0-9]{40}', row.get('head', {}).get('sha', ''))):
                raise PublishError('Exact PR identity or state was not confirmed')
            if task_id is not None and (marker_for(task_id) not in (row.get('body') or '')
                    or row.get('head', {}).get('ref') != branch_for(task_id)
                    or row.get('head', {}).get('repo', {}).get('full_name') != self.repository):
                raise PublishError('PR does not match the admitted task')
            return row

        pr = snapshot()
        raw_reviews = self._discussion_rows(f'/pulls/{number}/reviews')
        raw_comments = self._discussion_rows(f'/issues/{number}/comments')
        raw_inline = self._discussion_rows(f'/pulls/{number}/comments')
        fresh = snapshot()
        for key in ('head', 'base', 'state', 'draft', 'merged', 'updated_at'):
            if pr.get(key) != fresh.get(key):
                raise PublishError('PR changed during reconciliation; refresh the snapshot')

        def normalize(row, kind):
            actor = row.get('user') or {}
            body = row.get('body') or ''
            if (type(row.get('id')) is not int or row['id'] < 1 or not isinstance(body, str)
                    or not isinstance(actor.get('login'), str) or not 1 <= len(actor['login']) <= 100
                    or type(actor.get('id')) is not int or actor['id'] < 1):
                raise PublishError('Invalid review/comment identity')
            result = {'id': row['id'], 'kind': kind, 'actor': actor['login'], 'actor_id': actor['id'],
                      'actor_type': actor.get('type'), 'association': row.get('author_association'),
                      'body': body[:4000], 'body_truncated': len(body) > 4000,
                      'created_at': row.get('submitted_at') or row.get('created_at'),
                      'updated_at': row.get('updated_at'), 'url': row.get('html_url'),
                      'commit_id': row.get('commit_id'),
                      'at_head': row.get('commit_id') == pr['head']['sha']}
            if kind == 'review':
                if row.get('state') not in ('PENDING', 'COMMENTED', 'APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
                    raise PublishError('Unknown GitHub review state')
                result['state'] = row['state']
            if kind == 'inline_comment':
                result.update(path=row.get('path'), line=row.get('line'),
                              in_reply_to_id=row.get('in_reply_to_id'))
            return result

        reviews = [normalize(row, 'review') for row in raw_reviews]
        comments = ([normalize(row, 'issue_comment') for row in raw_comments]
                    + [normalize(row, 'inline_comment') for row in raw_inline])
        latest, decisive = {}, {}
        def order(row):
            try:
                stamp = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                if stamp.tzinfo is None:
                    raise ValueError()
                return stamp.timestamp(), row['id']
            except (AttributeError, TypeError, ValueError):
                raise PublishError('Completed review has an invalid submission time') from None

        # A review may be created as a draft before another review but submitted
        # afterwards. Submission time, with ID as a tie breaker, controls order.
        for row in sorted((r for r in reviews if r['state'] != 'PENDING'), key=order):
            actor = row['actor']
            if actor in latest and latest[actor]['actor_id'] != row['actor_id']:
                raise PublishError('Review actor identity changed during reconciliation')
            latest[actor] = row
            if row['state'] in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
                decisive[actor] = row
        return {'repository': self.repository, 'base': self.base, 'number': number,
                'url': pr.get('html_url'), 'state': 'merged' if pr['merged'] else
                    ('closed' if pr['state'] == 'closed' else ('draft' if pr['draft'] else 'open')),
                'open': pr['state'] == 'open', 'draft': pr['draft'], 'merged': pr['merged'],
                'head_sha': pr['head']['sha'], 'head_ref': pr['head']['ref'],
                'updated_at': pr.get('updated_at'), 'reviews': reviews,
                'latest_reviews': latest, 'review_decisions': decisive,
                'requested_changes': [r for r in decisive.values() if r['state'] == 'CHANGES_REQUESTED'],
                'comments': comments, 'content_trusted': False, 'authority': 'advisory-only'}

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
                        or row.get('head', {}).get('repo', {}).get('full_name') != self.repository
                        or row.get('base', {}).get('ref') != self.base):
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
            scope = {'repository': self.repository, 'base': self.base}
            if ledger and ledger.get('_scope', {'repository': REPOSITORY, 'base': BASE}) != scope:
                raise PublishError('Publisher ledger belongs to another project')
            ledger['_scope'] = scope
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
                    or found.get('head', {}).get('repo', {}).get('full_name') != self.repository
                    or found.get('base', {}).get('ref') != self.base):
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
                    payload.update(head=branch, base=self.base, draft=True, maintainer_can_modify=False)
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
                    or found.get('head', {}).get('ref') != branch or found.get('base', {}).get('ref') != self.base
                    or found.get('head', {}).get('repo', {}).get('full_name') != self.repository)):
                raise PublishError('Remote task is no longer an open admitted draft')
            receipt = {'state': 'confirmed', 'number': found['number'], 'url': found['html_url'],
                       'digest': digest(desired), 'kind': kind}
            if kind == 'pulls':
                receipt.update(draft=True, branch=branch, base=self.base)
            ledger[key] = receipt
            _write(self.ledger, ledger)
            return receipt


def _validate(config, task, evidence):
    task_key(task['id'])
    repository, base = project_scope(config)
    if project_scope(task) != (repository, base):
        raise PublishError('Task project does not match operator configuration')
    if (repository != REPOSITORY or 'repository' in evidence or 'base' in evidence):
        if evidence.get('repository') != repository or evidence.get('base') != base:
            raise PublishError('Test and review evidence belongs to another project')
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


def _remote_head(repo, branch, remote=None):
    result = git(repo, 'ls-remote', '--heads', remote or REMOTE, 'refs/heads/' + branch)
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
    repository, base = project_scope(config)
    if (client.repository, client.base) != (repository, base):
        raise PublishError('GitHub client belongs to another project')
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
        if state and (state.get('repository', REPOSITORY), state.get('base', BASE)) != (repository, base):
            raise PublishError('Publication journal belongs to another project')
        client.publication_preflight(task['id'])
        if state.get('source_sha', task['source_sha']) != task['source_sha']:
            raise PublishError('Task source changed; use a new task ID after fresh admission')
        if state.get('paths', sorted(task['files'])) != sorted(task['files']):
            raise PublishError('Task file scope changed; fresh task admission is required')
        if _remote_head(repo, base, client.remote) != task['source_sha']:
            raise PublishError(base + ' advanced; refresh admission and verification')
        remote = _remote_head(repo, branch, client.remote)
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
            state.update(repository=repository, base=base, source_sha=task['source_sha'], artifact=artifact,
                         paths=sorted(task['files']), commit=git(folder, 'rev-parse', 'HEAD'), pushing=True)
            _write(journal, state)
            # Explicit refspec and fixed HTTPS repository; never updates Dev/main.
            client.publication_preflight(task['id'])
            git(folder, 'push', '--no-verify', client.remote, 'HEAD:refs/heads/' + branch)
            if _remote_head(repo, branch, client.remote) != state['commit']:
                raise PublishError('Remote task branch publication not confirmed')
            state['pushing'] = False
            _write(journal, state)
        issue = client.ensure_issue(task['id'], task['title'], task.get('body', ''))
        body = (task.get('body', '') + '\n\nTests and independent review passed for artifact `' + artifact
                + '`.\nPinned source: `' + task['source_sha'] + '`.')
        pr = client.ensure_draft(task['id'], branch, task['title'], body, issue['number'])
        receipt = {'task_id': task['id'], 'source_sha': task['source_sha'], 'artifact_sha256': artifact,
                   'repository': repository, 'base': base,
                   'commit': state['commit'], 'branch': branch, 'issue': issue, 'pull_request': pr,
                   'merged': False, 'deployed': False}
        state['receipt'] = receipt
        _write(journal, state)
        return receipt

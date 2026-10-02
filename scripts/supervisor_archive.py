"""Verified, operator-owned cold archives for closed supervisor tasks.

No database, shell, network, model, or background scheduling authority. Call
archive_state inside the existing Store.mutate CAS operation; only the returned
candidate can be committed. A failed CAS may leave an unused, harmless archive.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

MAX_FILE_BYTES = 8_000_000
MAX_HOT_BYTES = 1_900_000
CLOSED = {'merged', 'closed'}
DONE = {'answered', 'completed', 'done', 'cancelled', 'closed'}
JOB_DONE = {'draft_ready', 'reviewed', 'completed', 'cancelled'}


class ArchiveError(ValueError):
    """Fixed diagnostics, without source text, paths, or credentials."""


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def task_scope_digest(job):
    """Compact duplicate-key guard for catalog integration, not execution authority."""
    keys = ('id', 'owner', 'repo', 'repository', 'project', 'operation',
            'development_profile', 'paths', 'write_paths', 'test_files',
            'source_sha', 'prompt', 'depends_on', 'roadmap_recipe_id', 'roadmap_goal')
    return digest({key: job.get(key) for key in keys})


def instant(value=None):
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ArchiveError('An aware archive timestamp is required')
    return value.astimezone(timezone.utc)


def plan(state, *, now=None, retain=20, fresh_seconds=900):
    """Select oldest eligible closures while retaining at least the newest 20.

    A recent GitHub observation must match the saved published PR identity.
    Closed means GitHub closed/merged, never merely a locally completed draft.
    Unknown states and all pending interactions block that task's archival.
    """
    at = instant(now)
    if type(retain) is not int or retain < 20 or retain > 100:
        raise ArchiveError('Archive retention must be between 20 and 100')
    if type(fresh_seconds) is not int or not 1 <= fresh_seconds <= 900:
        raise ArchiveError('Archive evidence freshness must be at most 900 seconds')
    ongoing, board = state['ongoing'], state['supervision']
    if ongoing.get('lease') or any(x.get('state') == 'running' for x in state.get('leases', {}).values()):
        return None
    jobs = ongoing['jobs']
    if len({j['id'] for j in jobs}) != len(jobs):
        raise ArchiveError('Duplicate hot task keys')
    closed, eligible = [], set()
    for job in jobs:
        sid = job.get('supervisor_id')
        meta = board['tasks'].get(sid, {})
        obs = job.get('pr_observation', {})
        if obs.get('state') not in CLOSED or meta.get('review_state') != obs.get('state'):
            continue
        closed.append(job)
        if job.get('state') not in JOB_DONE or not re.fullmatch(r'SUP-[0-9]{6,}', sid or ''):
            continue
        published = job.get('publication', {}).get('pull_request', {})
        url = published.get('url', '')
        if (not re.fullmatch(r'https://github\.com/pragalbhdwivedi/(aadi|miniature-octo-doodle)/pull/[1-9][0-9]*', url)
                or obs.get('url') != url or obs.get('open') is not False
                or obs.get('draft') is not False
                or obs.get('merged') is not (obs['state'] == 'merged')
                or obs.get('repository') != job.get('repository', 'pragalbhdwivedi/aadi')
                or obs.get('number') != int(url.rsplit('/', 1)[1])
                or not re.fullmatch('[a-f0-9]{40}', obs.get('head_sha', ''))
                or board['by_key'].get(job['id']) != sid or meta.get('key') != job['id']):
            continue
        try:
            age = (at - instant(job.get('pr_observed_at', ''))).total_seconds()
        except (ValueError, TypeError):
            continue
        if not 0 <= age <= fresh_seconds:
            continue
        if any(c.get('task_id') == sid and c.get('state') not in DONE for c in board.get('corrections', [])):
            continue
        if any(q.get('task_id') == sid and q.get('state') not in DONE for q in state.get('questions', [])):
            continue
        if (board.get('pending_reply') or {}).get('task_id') == sid:
            continue
        if any(m.get('task_id') == sid and m.get('state') != 'sent' for m in state.get('outbox', [])):
            continue
        eligible.add(job['id'])
    # GitHub update/closure time is stable across polling; never order by the
    # local polling timestamp. Older receipts fall back to the task update time.
    def closure_order(job):
        meta = board['tasks'][job['supervisor_id']]
        obs = job['pr_observation']
        value = obs.get('closed_at') or obs.get('updated_at') or meta['updated_at']
        return instant(value), job['supervisor_id']
    closed.sort(key=closure_order)
    selected = {j['id'] for j in closed[:-retain]} & eligible
    # Never remove a prerequisite still referenced by a retained job.
    while True:
        protected = {d for j in jobs if j['id'] not in selected for d in j.get('depends_on', [])}
        revised = selected - protected
        if revised == selected:
            break
        selected = revised
    if not selected:
        return None
    ids = sorted(j['supervisor_id'] for j in jobs if j['id'] in selected)
    return {'version': 1, 'created_at': at.isoformat(), 'state_sha256': digest(state),
            'board_revision': board['revision'], 'retain': retain, 'fresh_seconds': fresh_seconds,
            'task_ids': ids, 'job_ids': sorted(selected)}


class ArchiveStore:
    """Protected operator directory. Files are content-addressed and immutable."""
    def __init__(self, directory):
        self.directory = Path(directory)
        if not self.directory.is_absolute() or self.directory.is_symlink():
            raise ArchiveError('An absolute nonsymlink archive directory is required')
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == 'posix' and self.directory.stat().st_mode & 0o077:
            raise ArchiveError('Archive directory must be operator-private')

    def _path(self, archive_id):
        if not isinstance(archive_id, str) or not re.fullmatch('[a-f0-9]{64}', archive_id):
            raise ArchiveError('Invalid archive identifier')
        return self.directory / (archive_id + '.json')

    def _sync_directory(self):
        # Linux deployment: durable directory entry after atomic link. Windows
        # does not provide this POSIX primitive; the CLI is preparation-only there.
        if os.name == 'posix':
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def persist(self, state, proposal):
        if proposal != plan(state, now=proposal['created_at'], retain=proposal['retain'],
                            fresh_seconds=proposal['fresh_seconds']):
            raise ArchiveError('Archive proposal no longer matches source state')
        payload = {'version': 1, 'plan': copy.deepcopy(proposal), 'state': copy.deepcopy(state)}
        raw = encoded(payload)
        if len(raw) > MAX_FILE_BYTES:
            raise ArchiveError('Archive payload limit exceeded')
        archive_id = hashlib.sha256(raw).hexdigest()
        target = self._path(archive_id)
        if not target.exists():
            fd, name = tempfile.mkstemp(prefix='.archive-', suffix='.tmp', dir=self.directory)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(name, target)  # atomic publication, never overwrite
                except FileExistsError:
                    pass
                self._sync_directory()
            finally:
                Path(name).unlink(missing_ok=True)
        saved = self.read(archive_id)
        if saved != payload:
            raise ArchiveError('Archive readback differs from prepared evidence')
        return {'archive_id': archive_id, 'bytes': len(raw),
                'state_sha256': proposal['state_sha256'], 'created_at': proposal['created_at'],
                'task_count': len(proposal['task_ids'])}

    def read(self, archive_id):
        path = self._path(archive_id)
        try:
            if path.is_symlink():
                raise ArchiveError('Archive symlinks are not accepted')
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
            fd = os.open(path, flags)
            with os.fdopen(fd, 'rb') as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or (os.name == 'posix' and info.st_mode & 0o077):
                    raise ArchiveError('Archive file must be a private regular file')
                raw = handle.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES or hashlib.sha256(raw).hexdigest() != archive_id:
                raise ArchiveError('Archive integrity verification failed')
            value = json.loads(raw)
            if (not isinstance(value, dict) or value.get('version') != 1 or digest(value['state']) != value['plan']['state_sha256']
                    or encoded(value) != raw):
                raise ArchiveError('Archive structure verification failed')
            return value
        except ArchiveError:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            raise ArchiveError('Archive could not be verified') from None

    def task(self, state, task_id):
        """Full privileged task evidence; do NOT expose this as public HTTP JSON."""
        entry = state['supervision'].get('archived_tasks', {}).get(task_id)
        if not entry:
            raise ArchiveError('Unknown archived task')
        payload = self.read(entry['archive_id'])
        if task_id not in payload['plan']['task_ids']:
            raise ArchiveError('Task is not in this archive')
        source = payload['state']
        meta = source['supervision']['tasks'][task_id]
        job = next(j for j in source['ongoing']['jobs'] if j['id'] == meta['key'])
        hashes = {h['evidence_digest'] for h in meta.get('history', [])}
        return {'task': copy.deepcopy(job), 'metadata': copy.deepcopy(meta),
                'evidence': {k: copy.deepcopy(v) for k, v in source['supervision']['evidence'].items() if k in hashes},
                'events': [copy.deepcopy(e) for e in source['supervision']['events'] if e.get('task_id') == task_id]}


def compact(state, receipt, store, *, now=None):
    """Return an exact-state CAS candidate only after verifying persisted bytes."""
    payload = store.read(receipt['archive_id'])
    proposal = payload['plan']
    if (receipt.get('created_at') != proposal['created_at']
            or digest(state) != proposal['state_sha256'] or state != payload['state']
            or receipt['state_sha256'] != proposal['state_sha256']
            or receipt['bytes'] != len(encoded(payload))
            or receipt['task_count'] != len(proposal['task_ids'])):
        raise ArchiveError('Archive source changed; retain hot state and prepare again')
    # Current eligibility is rechecked, not inherited from an old preparation.
    current = plan(state, now=now, retain=proposal['retain'], fresh_seconds=proposal['fresh_seconds'])
    if not current or current['task_ids'] != proposal['task_ids']:
        raise ArchiveError('Archive eligibility changed or PR evidence became stale')
    candidate = copy.deepcopy(state)
    board = candidate['supervision']
    archived = board.setdefault('archived_tasks', {})
    index = board.setdefault('archive_index', {})
    removed_hashes = set()
    jobs_by_key = {j['id']: j for j in candidate['ongoing']['jobs']}
    for sid in proposal['task_ids']:
        meta = board['tasks'].pop(sid)
        observed = meta.get('observed', {})
        # Only existing public projection fields belong in the hot history index.
        summary = {k: copy.deepcopy(observed.get(k)) for k in
                   ('id', 'key', 'project', 'title', 'owner', 'pr_url', 'pr_number',
                    'coder_model', 'reviewer_model', 'coder_confidence', 'reviewer_confidence')}
        summary.update(id=sid, key=meta['key'], state=meta['review_state'],
                       created_at=meta['created_at'], updated_at=meta['updated_at'],
                       archived_at=proposal['created_at'], archive_id=receipt['archive_id'])
        job = jobs_by_key[meta['key']]
        summary.update(source_sha=job.get('source_sha'), roadmap_recipe_id=job.get('roadmap_recipe_id'),
                       repository=job.get('repository', 'pragalbhdwivedi/aadi'),
                       roadmap_goal_digest=digest(job.get('roadmap_goal', job.get('prompt'))),
                       scope_digest=task_scope_digest(job))
        archived[sid] = summary
        removed_hashes.update(h['evidence_digest'] for h in meta.get('history', []))
    candidate['ongoing']['jobs'] = [j for j in candidate['ongoing']['jobs'] if j['id'] not in proposal['job_ids']]
    retained_hashes = {h['evidence_digest'] for m in board['tasks'].values() for h in m.get('history', [])}
    retained_hashes.update(c.get('evidence_digest') for c in board.get('corrections', []))
    for key in removed_hashes - retained_hashes:
        board['evidence'].pop(key, None)
    index[receipt['archive_id']] = copy.deepcopy(receipt)
    board['revision'] += 1
    board['events'].append({'sequence': len(board['events']) + 1, 'timestamp': instant(now).isoformat(),
        'actor': 'Operator archive service', 'task_id': None, 'action': 'archive_verified',
        'detail': 'Archived '+str(receipt['task_count'])+' closed tasks; SHA-256 '+receipt['archive_id']})
    if len(json.dumps(candidate, allow_nan=False).encode()) > MAX_HOT_BYTES:
        raise ArchiveError('Verified task archival is insufficient for the hot state limit')
    if len(encoded(candidate)) >= len(encoded(state)):
        raise ArchiveError('Archive compaction would not reduce hot state size')
    return candidate


def archive_state(state, directory, *, now=None, retain=20):
    """CAS adapter: prepare + durable readback + compact; original never mutates."""
    at = instant(now)
    proposal = plan(state, now=at, retain=retain)
    if proposal is None:
        return copy.deepcopy(state), None
    store = ArchiveStore(directory)
    receipt = store.persist(state, proposal)
    return compact(state, receipt, store, now=at if now is not None else None), receipt


def history_index(state, *, offset=0, limit=100):
    """Read-only bounded summaries; safe to integrate behind existing HTTP gates."""
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
        raise ArchiveError('Invalid archive history page')
    rows = sorted(state['supervision'].get('archived_tasks', {}).values(), key=lambda x: x['id'])
    return {'tasks': copy.deepcopy(rows[offset:offset+limit]), 'total': len(rows),
            'offset': offset, 'limit': limit, 'omitted': max(0, len(rows)-offset-limit)}


def main():
    parser = argparse.ArgumentParser(description='Operator-only verified supervisor archive inspection')
    parser.add_argument('--directory', required=True)
    parser.add_argument('--archive-id', required=True)
    parser.add_argument('--export', type=Path, help='Create a new private full-state evidence export; never overwrite')
    args = parser.parse_args()
    payload = ArchiveStore(args.directory).read(args.archive_id)
    if args.export:
        if not args.export.is_absolute():
            raise ArchiveError('Export destination must be absolute and operator-private')
        fd = os.open(args.export, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(encoded(payload)); output.flush(); os.fsync(output.fileno())
    print(json.dumps({'archive_id': args.archive_id, 'task_ids': payload['plan']['task_ids'],
                      'state_sha256': payload['plan']['state_sha256'], 'verified': True}))


if __name__ == '__main__':
    main()

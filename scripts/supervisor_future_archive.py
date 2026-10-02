"""Verified future-backlog archival through the existing operator CAS boundary.

Only independently observed merged work is eligible. Full state, task text,
generation receipts and audit events are durably backed up before compaction.
The retained identity indexes preserve dependency and replay guards; they are
bounded and never silently evicted. Configuration, never a request, owns paths.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import supervisor_archive as archive
import supervisor_future as future

ArchiveError = archive.ArchiveError


def _merged(job):
    obs = job.get('pr_observation', {})
    url = job.get('publication', {}).get('pull_request', {}).get('url', '')
    return (job.get('state') in archive.JOB_DONE and not job.get('supervision_paused')
            and obs.get('state') == 'merged' and obs.get('merged') is True
            and obs.get('open') is False and obs.get('draft') is False
            and isinstance(url, str)
            and re.fullmatch(r'https://github\.com/pragalbhdwivedi/(aadi|miniature-octo-doodle)/pull/[1-9][0-9]*', url)
            and obs.get('url') == url and obs.get('number') == int(url.rsplit('/', 1)[1])
            and type(obs.get('number')) is int
            and obs.get('repository') == job.get('repository', 'pragalbhdwivedi/aadi')
            and obs.get('repository') == '/'.join(url.split('/')[3:5])
            and isinstance(obs.get('head_sha'), str)
            and re.fullmatch('[a-f0-9]{40}', obs.get('head_sha', '')))


def _evidence(state, task):
    board = state['supervision']
    sid = task.get('intake_id')
    if not isinstance(sid, str) or not re.fullmatch(r'SUP-[0-9]{6}', sid):
        return None
    if board.get('tasks', {}).get(sid, {}).get('paused'):
        return None
    if any(c.get('task_id') == sid and c.get('state') not in archive.DONE for c in board.get('corrections', [])):
        return None
    if any(q.get('task_id') == sid and q.get('state') not in archive.DONE for q in state.get('questions', [])):
        return None
    if (board.get('pending_reply') or {}).get('task_id') == sid:
        return None
    jobs = [j for j in state.get('ongoing', {}).get('jobs', []) if j.get('intake_id') == sid]
    if jobs:
        if len(jobs) != 1 or jobs[0].get('supervisor_id') != sid or not _merged(jobs[0]):
            return None
        job = jobs[0]
        return {'pr_url': job['pr_observation']['url'], 'pr_number': job['pr_observation']['number'],
                'source_archive_id': None}
    row = board.get('archived_tasks', {}).get(sid)
    if not row or row.get('state') != 'merged':
        return None
    receipt = board.get('archive_index', {}).get(row.get('archive_id'))
    if not receipt or receipt.get('archive_id') != row['archive_id']:
        return None
    return {'pr_url': row.get('pr_url'), 'pr_number': row.get('pr_number'),
            'source_archive_id': row['archive_id']}


def plan(state, *, now=None, retain=20):
    at = archive.instant(now).isoformat()
    if type(retain) is not int or not 20 <= retain <= 100:
        raise ArchiveError('Future archive retention must be between 20 and 100')
    f = state.get('supervision', {}).get('future')
    if not f:
        return None
    if len({t['id'] for t in f['tasks']}) != len(f['tasks']):
        raise ArchiveError('Duplicate future identity')
    eligible = []
    for task in f['tasks']:
        if task['state'] != 'completed' or not task.get('completed_at'):
            continue
        evidence = _evidence(state, task)
        if evidence:
            eligible.append((archive.instant(task['completed_at']), task['id'], evidence))
    selected = sorted(eligible)[:-retain]
    if not selected:
        return None
    return {'version': 1, 'kind': 'supervisor_future', 'created_at': at,
            'state_sha256': archive.digest(state), 'board_revision': state['supervision']['revision'],
            'retain': retain, 'task_ids': [row[1] for row in selected],
            'evidence': {row[1]: row[2] for row in selected}}


class ArchiveStore(archive.ArchiveStore):
    def persist(self, state, proposal):
        if proposal != plan(state, now=proposal['created_at'], retain=proposal['retain']):
            raise ArchiveError('Future archive proposal changed')
        _verify_prior(state, proposal, self)
        payload = {'version': 1, 'plan': copy.deepcopy(proposal), 'state': copy.deepcopy(state)}
        raw = archive.encoded(payload)
        if len(raw) > archive.MAX_FILE_BYTES:
            raise ArchiveError('Future archive payload limit exceeded')
        archive_id = hashlib.sha256(raw).hexdigest()
        target = self._path(archive_id)
        if not target.exists():
            fd, name = tempfile.mkstemp(prefix='.future-', suffix='.tmp', dir=self.directory)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(name, target)
                except FileExistsError:
                    pass
                self._sync_directory()
            finally:
                Path(name).unlink(missing_ok=True)
        if self.read(archive_id) != payload:
            raise ArchiveError('Future archive readback differs from prepared evidence')
        return {'archive_id': archive_id, 'bytes': len(raw), 'state_sha256': proposal['state_sha256'],
                'created_at': proposal['created_at'], 'task_count': len(proposal['task_ids'])}


def _verify_prior(state, proposal, store):
    """A saved index alone cannot substitute for the verified original evidence."""
    tasks = {t['id']: t for t in state['supervision']['future']['tasks']}
    payloads = {}
    for fid, evidence in proposal['evidence'].items():
        archive_id = evidence['source_archive_id']
        if not archive_id:
            continue
        if archive_id not in payloads:
            payloads[archive_id] = store.read(archive_id)
        payload = payloads[archive_id]
        sid = tasks[fid]['intake_id']
        if sid not in payload['plan']['task_ids']:
            raise ArchiveError('Prior archive does not contain linked work')
        jobs = [j for j in payload['state']['ongoing']['jobs'] if j.get('intake_id') == sid]
        if (len(jobs) != 1 or jobs[0].get('supervisor_id') != sid or not _merged(jobs[0])
                or jobs[0]['pr_observation']['url'] != evidence['pr_url']
                or jobs[0]['pr_observation']['number'] != evidence['pr_number']):
            raise ArchiveError('Prior archive does not verify merged future work')


def compact(state, receipt, store):
    payload = store.read(receipt['archive_id'])
    proposal = payload['plan']
    if (proposal.get('kind') != 'supervisor_future' or payload['state'] != state
            or proposal['state_sha256'] != archive.digest(state)
            or receipt['state_sha256'] != proposal['state_sha256']
            or receipt['created_at'] != proposal['created_at']
            or receipt['bytes'] != len(archive.encoded(payload))
            or receipt['task_count'] != len(proposal['task_ids'])
            or proposal != plan(state, now=proposal['created_at'], retain=proposal['retain'])):
        raise ArchiveError('Future archive source or receipt changed; retain hot state')
    _verify_prior(state, proposal, store)
    candidate = copy.deepcopy(state)
    board = candidate['supervision']
    f = board['future']
    cold = f.setdefault('archived_tasks', {})
    requests = f.setdefault('archived_requests', {})
    selected = set(proposal['task_ids'])
    if (len(cold)+len(selected) > future.MAX_ARCHIVED
            or len(requests)+sum(r['state'] in ('completed', 'failed') for r in f['requests']) > future.MAX_ARCHIVED):
        raise ArchiveError('Future archive identity index is full; explicit long-term migration is required')
    for task in f['tasks']:
        if task['id'] not in selected:
            continue
        if task['id'] in cold:
            raise ArchiveError('Future identity was already archived')
        spec = {k: task[k] for k in future.FIELDS | {'id', 'not_before'} if k in task}
        cold[task['id']] = {k: copy.deepcopy(task[k]) for k in ('id', 'project', 'title', 'intake_id', 'completed_at')}
        cold[task['id']].update(state='completed', prompt_digest=future._digest(' '.join(task['prompt'].casefold().split())),
            spec_digest=future._digest(spec), archived_at=proposal['created_at'], archive_id=receipt['archive_id'],
            **proposal['evidence'][task['id']])
    for request in f['requests']:
        if request['state'] in ('completed', 'failed'):
            if request['request_id'] in requests:
                raise ArchiveError('Generation receipt identity was already archived')
            requests[request['request_id']] = copy.deepcopy(request)
    f['requests'] = [r for r in f['requests'] if r['state'] in ('pending', 'running')]
    f['tasks'] = [t for t in f['tasks'] if t['id'] not in selected]
    f['events'] = [{'timestamp': proposal['created_at'], 'kind': 'archive_verified',
                    'archive_id': receipt['archive_id'], 'task_count': len(selected)}]
    f.setdefault('archive_index', {})[receipt['archive_id']] = copy.deepcopy(receipt)
    board['revision'] += 1
    if len(json.dumps(candidate, allow_nan=False).encode()) > archive.MAX_HOT_BYTES:
        raise ArchiveError('Future archive compaction exceeds hot ledger size limit')
    if len(archive.encoded(candidate)) >= len(archive.encoded(state)):
        raise ArchiveError('Future archive would not reduce hot state size')
    return candidate


def archive_state(state, directory, *, now=None, retain=20):
    proposal = plan(state, now=now, retain=retain)
    if proposal is None:
        return copy.deepcopy(state), None
    store = ArchiveStore(directory)
    receipt = store.persist(state, proposal)
    return compact(state, receipt, store), receipt


def run(store, request, config):
    if (not isinstance(request, dict) or set(request) != {'action', 'revision'}
            or request['action'] != 'ongoing_future_archive' or type(request['revision']) is not int):
        raise ArchiveError('Invalid future archive operator request')
    if (not isinstance(config, dict) or config.get('enabled') is not True
            or not isinstance(config.get('directory'), str)):
        raise ArchiveError('Operator archive writing is disabled')
    def apply(state):
        if state['supervision']['revision'] != request['revision']:
            raise ArchiveError('Board changed; refresh before future archive preparation')
        candidate, receipt = archive_state(state, config['directory'])
        if receipt:
            state.clear()
            state.update(candidate)
        return {'archived': receipt['task_count'] if receipt else 0, 'receipt': receipt,
                'revision': state['supervision']['revision']}
    return store.mutate(apply)

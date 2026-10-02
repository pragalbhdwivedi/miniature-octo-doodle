"""Pure, bounded future planning; readiness never grants execution authority.

Call mutations inside the ledger's durable CAS operation. ``begin_generation``
must be persisted before inference: a running request is never automatically
retried. Scope names and evidence paths are suggestions, independently admitted
by the operator pipeline. Only verified integration should mark work completed.
All timestamps are supplied by the caller. No transport, models, or I/O live here.
"""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

MAX_TASKS = 500
MAX_REQUESTS = 500
MAX_EVENTS = 5000
TASK_ID = r'FUT-[0-9]{6}'
SCOPE_ID = r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}'
FIELDS = {'project', 'title', 'prompt', 'scope_id', 'priority', 'evidence',
          'acceptance', 'dependencies', 'risk'}
OUTSTANDING = {'ready', 'queued', 'admitted'}


def _at(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('An aware timestamp is required')
    return value.astimezone(timezone.utc).isoformat()


def _text(value, limit, name):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        raise ValueError('Invalid '+name)
    return value


def _identifier(value, pattern, name):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('Invalid '+name)
    return value


def _list(value, limit, name):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError('Invalid '+name)
    return value


def _spec(entry, seeded):
    allowed = FIELDS | ({'id', 'not_before'} if seeded else set())
    required = FIELDS | ({'id'} if seeded else set())
    if not isinstance(entry, dict) or not required <= entry.keys() or not entry.keys() <= allowed:
        raise ValueError('Unknown or missing future proposal fields')
    result = copy.deepcopy(entry)
    if seeded:
        _identifier(entry['id'], TASK_ID, 'future ID')
        if entry['id'] == 'FUT-000000':
            raise ValueError('Future IDs start at one')
    if entry['project'] not in ('AADI', 'GatewayAI'):
        raise ValueError('Unknown project')
    _text(entry['title'], 180, 'title')
    _text(entry['prompt'], 1000, 'prompt')
    if entry['scope_id'] != '':
        _identifier(entry['scope_id'], SCOPE_ID, 'scope suggestion')
    if type(entry['priority']) is not int or not 1 <= entry['priority'] <= 5:
        raise ValueError('Priority must be an integer from 1 to 5')
    if entry['risk'] not in ('routine', 'needs_owner'):
        raise ValueError('Invalid risk')
    if not entry['evidence']:
        raise ValueError('Repository evidence is required')
    for path in _list(entry['evidence'], 12, 'evidence'):
        _text(path, 200, 'evidence path')
        if (path.startswith(('/', '\\')) or '\\' in path or ':' in path
                or any(p in ('', '.', '..') for p in path.split('/'))
                or any(ord(c) < 32 for c in path)):
            raise ValueError('Evidence must be a relative repository path')
    if not entry['acceptance']:
        raise ValueError('Acceptance criteria are required')
    for item in _list(entry['acceptance'], 8, 'acceptance'):
        _text(item, 500, 'acceptance criterion')
    for dependency in _list(entry['dependencies'], 20, 'dependencies'):
        _identifier(dependency, TASK_ID, 'dependency')
    if len(set(entry['dependencies'])) != len(entry['dependencies']):
        raise ValueError('Duplicate dependencies')
    if 'not_before' in entry:
        result['not_before'] = _at(entry['not_before'])
    return result


def _empty():
    return {'version': 1, 'tasks': [], 'next_id': 1, 'interval_minutes': 5,
            'batch_size': 10, 'next_batch_at': None, 'override_pending': False,
            'generation': {'state': 'idle'}, 'requests': [], 'events': []}


def _ensure(s):
    return s.setdefault('supervision', {}).setdefault('future', _empty())


def _change(s, operation):
    # Reuse atomic validation and reference-preserving commit from the ledger.
    from supervisor_board import _transaction
    return _transaction(s, lambda candidate: operation(_ensure(candidate), candidate))


def _event(f, at, kind, **details):
    if len(f['events']) >= MAX_EVENTS:
        raise ValueError('Future audit is full; explicit archival is required')
    f['events'].append({'timestamp': at, 'kind': kind, **details})


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _duplicate(a, b):
    normal = lambda value: ' '.join(value.casefold().split())
    return a['project'] == b['project'] and any(
        normal(a[key]) == normal(b[key]) for key in ('title', 'prompt'))


def _dependencies(tasks):
    by_id = {task['id']: task for task in tasks}
    visited, visiting = set(), set()
    def visit(task_id):
        if task_id not in by_id:
            raise ValueError('Unknown future dependency: '+task_id)
        if task_id in visiting:
            raise ValueError('Future dependencies contain a cycle')
        if task_id in visited:
            return
        visiting.add(task_id)
        for child in by_id[task_id]['dependencies']:
            visit(child)
        visiting.remove(task_id)
        visited.add(task_id)
    for task_id in by_id:
        visit(task_id)


def _append(f, spec, at, origin):
    if len(f['tasks']) >= MAX_TASKS:
        raise ValueError('Future backlog is full; explicit archival is required')
    task = {**spec, 'state': 'planned', 'created_at': at, 'updated_at': at,
            'origin': origin}
    f['tasks'].append(task)
    f['next_id'] = max(f['next_id'], int(spec['id'][4:])+1)
    return task


def seed(s, entries, now):
    """Import operator-authored entries atomically; exact reimports are harmless."""
    at = _at(now)
    specs = [_spec(entry, True) for entry in _list(entries, MAX_TASKS, 'seed entries')]
    def change(f, candidate):
        added = []
        for spec in specs:
            old = next((t for t in f['tasks'] if t['id'] == spec['id']), None)
            if old:
                original = {k: old[k] for k in FIELDS | {'id', 'not_before'} if k in old}
                if original != spec:
                    raise ValueError('Existing future ID has a different specification')
                continue
            if any(_duplicate(spec, t) for t in f['tasks']):
                raise ValueError('Duplicate future task under a different ID')
            _append(f, spec, at, 'operator_seed')
            added.append(spec['id'])
        _dependencies(f['tasks'])
        if added:
            _event(f, at, 'seeded', task_ids=added)
        return {'ok': True, 'added': added, 'total': len(f['tasks'])}
    return _change(s, change)


def public(s, now):
    """Read-only bounded projection, including every retained task."""
    at = _at(now)
    f = s.get('supervision', {}).get('future', _empty())
    counts = {}
    for task in f['tasks']:
        counts[task['state']] = counts.get(task['state'], 0)+1
    return {'tasks': copy.deepcopy(f['tasks']), 'counts': counts,
            'generation': copy.deepcopy(f['generation']), 'total': len(f['tasks']),
            'next_batch_size': f['batch_size'], 'interval_minutes': f['interval_minutes'],
            'next_batch_at': f['next_batch_at'], 'override_pending': f['override_pending'],
            'observed_at': at}


def _request(f, request_id):
    _identifier(request_id, r'[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}', 'request ID')
    return next((r for r in f['requests'] if r['request_id'] == request_id), None)


def request_generation(s, request_id, now):
    at = _at(now)
    def change(f, candidate):
        old = _request(f, request_id)
        if old:
            return copy.deepcopy(old)
        if f['generation']['state'] in ('pending', 'running'):
            raise ValueError('A generation request is already pending or running')
        if len(f['requests']) >= MAX_REQUESTS or len(f['tasks']) >= MAX_TASKS:
            raise ValueError('Future storage is full; explicit archival is required')
        request = {'request_id': request_id, 'state': 'pending', 'requested_at': at}
        f['requests'].append(request)
        f['generation'] = copy.deepcopy(request)
        _event(f, at, 'generation_requested', request_id=request_id)
        return copy.deepcopy(request)
    return _change(s, change)


def begin_generation(s, request_id, now):
    """Persist execute=True before inference. Running replays never execute twice."""
    at = _at(now)
    def change(f, candidate):
        request = _request(f, request_id)
        if request is None:
            raise ValueError('Unknown generation request')
        if request['state'] != 'pending':
            return {'execute': False, **copy.deepcopy(request)}
        if candidate.get('ongoing', {}).get('enabled') is not True:
            return {'execute': False, 'reason': 'paused', **copy.deepcopy(request)}
        request.update(state='running', started_at=at)
        f['generation'] = copy.deepcopy(request)
        _event(f, at, 'generation_started', request_id=request_id)
        return {'execute': True, **copy.deepcopy(request)}
    return _change(s, change)


def finish_generation(s, request_id, proposals, model, now):
    at = _at(now)
    _text(model, 160, 'model')
    specs = [_spec(p, False) for p in _list(proposals, 10, 'generated proposals')]
    digest = _digest({'proposals': specs, 'model': model})
    def change(f, candidate):
        request = _request(f, request_id)
        if request is None:
            raise ValueError('Unknown generation request')
        if request['state'] == 'completed' and request['result_digest'] == digest:
            return copy.deepcopy(request)
        if request['state'] != 'running':
            raise ValueError('Generation is not running or result conflicts with saved receipt')
        added, duplicates = [], []
        for index, spec in enumerate(specs):
            match = next((t for t in f['tasks'] if _duplicate(spec, t)), None)
            if match:
                duplicates.append({'index': index, 'existing_id': match['id']})
                continue
            if f['next_id'] > 999999:
                raise ValueError('Future ID space exhausted')
            task_id = 'FUT-'+str(f['next_id']).zfill(6)
            _append(f, {'id': task_id, **spec}, at, 'model_proposal')
            added.append(task_id)
        _dependencies(f['tasks'])
        request.update(state='completed', finished_at=at, model=model,
                       result_digest=digest, added=added, duplicates=duplicates)
        f['generation'] = copy.deepcopy(request)
        _event(f, at, 'generation_completed', request_id=request_id, task_ids=added, model=model)
        return copy.deepcopy(request)
    return _change(s, change)


def fail_generation(s, request_id, error, now):
    at = _at(now)
    _text(error, 1000, 'generation error')
    def change(f, candidate):
        request = _request(f, request_id)
        if request is None:
            raise ValueError('Unknown generation request')
        if request['state'] == 'failed' and request['error'] == error:
            return copy.deepcopy(request)
        if request['state'] not in ('pending', 'running'):
            raise ValueError('Generation is already terminal')
        request.update(state='failed', finished_at=at, error=error)
        f['generation'] = copy.deepcopy(request)
        _event(f, at, 'generation_failed', request_id=request_id)
        return copy.deepcopy(request)
    return _change(s, change)


def promote(s, scope_ids, now):
    """Fill up to ten outstanding slots; scope hints still need real admission."""
    at = _at(now)
    if not isinstance(scope_ids, (list, tuple, set)):
        raise ValueError('Registered scope IDs are required')
    scopes = {_identifier(v, SCOPE_ID, 'registered scope') for v in scope_ids}
    def change(f, candidate):
        if candidate.get('ongoing', {}).get('enabled') is not True:
            return {'state': 'paused', 'ready': [], 'ready_ids': [], 'next_batch_at': f['next_batch_at']}
        completed = {t['id'] for t in f['tasks'] if t['state'] == 'completed'}
        slots = max(0, f['batch_size']-sum(t['state'] in OUTSTANDING for t in f['tasks']))
        cadence = f['override_pending'] or f['next_batch_at'] is None or at >= f['next_batch_at']
        selected = []
        for task in sorted(f['tasks'], key=lambda t: (-t['priority'], t['id'])):
            if task['state'] in OUTSTANDING | {'completed', 'review_ready'} or task.get('intake_id'):
                continue
            if task['risk'] == 'needs_owner':
                state, reason = 'needs_owner', 'Owner review required'
            elif task['scope_id'] not in scopes:
                state, reason = 'needs_scope', 'Scope suggestion is not registered'
            elif not set(task['dependencies']) <= completed:
                state, reason = 'planned', 'Waiting for completed dependencies'
            elif task.get('not_before') and at < task['not_before']:
                state, reason = 'scheduled', 'Waiting for task start time'
            elif not cadence:
                state, reason = 'scheduled', 'Waiting for next refill time'
            elif slots:
                state, reason = 'ready', 'Ready for independent scope admission'
                slots -= 1
                selected.append(task['id'])
            else:
                state, reason = 'planned', 'Outstanding batch is full'
            if (task['state'], task.get('reason')) != (state, reason):
                task.update(state=state, reason=reason, updated_at=at)
        if selected:
            f['next_batch_at'] = (datetime.fromisoformat(at)+timedelta(minutes=f['interval_minutes'])).isoformat()
            f['override_pending'] = False
            _event(f, at, 'promoted', task_ids=selected)
        return {'state': 'ready' if selected else 'waiting', 'ready_ids': selected,
                'ready': copy.deepcopy([t for t in f['tasks'] if t['id'] in selected]),
                'next_batch_at': f['next_batch_at']}
    return _change(s, change)


def request_override(s, now):
    """Override the next refill delay, never pause, task time, risk or scope gates."""
    at = _at(now)
    def change(f, candidate):
        if not f['override_pending']:
            f['override_pending'] = True
            _event(f, at, 'refill_override_requested')
        return {'ok': True, 'override_pending': True}
    return _change(s, change)


def _task(f, future_id):
    _identifier(future_id, TASK_ID, 'future ID')
    task = next((t for t in f['tasks'] if t['id'] == future_id), None)
    if task is None:
        raise ValueError('Unknown future task')
    return task


def _transition(s, future_id, intake_id, state, previous, now):
    at = _at(now)
    if intake_id is not None:
        _identifier(intake_id, r'SUP-[0-9]{6}', 'intake ID')
    def change(f, candidate):
        task = _task(f, future_id)
        if intake_id and task.get('intake_id') not in (None, intake_id):
            raise ValueError('Future task is linked to a different intake')
        if state == 'queued' and any(t.get('intake_id') == intake_id and t['id'] != future_id for t in f['tasks']):
            raise ValueError('Intake is already linked to another future task')
        if task['state'] == state:
            return copy.deepcopy(task)
        if task['state'] not in previous:
            raise ValueError('Invalid future task transition')
        task.update(state=state, updated_at=at)
        if intake_id:
            task['intake_id'] = intake_id
        task[state+'_at'] = at
        _event(f, at, state, task_id=future_id, intake_id=task.get('intake_id'))
        return copy.deepcopy(task)
    return _change(s, change)


def mark_intake(s, future_id, intake_id, now):
    return _transition(s, future_id, intake_id, 'queued', {'ready'}, now)


def mark_admitted(s, future_id, intake_id, now):
    return _transition(s, future_id, intake_id, 'admitted', {'queued'}, now)


def mark_review_ready(s, future_id, now):
    """Release a work slot; dependencies still require verified integration."""
    return _transition(s, future_id, None, 'review_ready', {'admitted'}, now)


def mark_completed(s, future_id, now):
    return _transition(s, future_id, None, 'completed', {'admitted', 'review_ready'}, now)

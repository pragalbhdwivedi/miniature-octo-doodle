"""Pure Telegram pilot presentation; input is an operator-admitted snapshot.

No I/O or authority decisions occur here. Field allowlists and obvious-credential
redaction are defense in depth, not complete secret or personal-data detection.
The caller must admit safe snapshot content and send render() as plain text.
"""
import re


VIEWS = ('status', 'inputs', 'outputs', 'questions', 'controls', 'usage', 'ask')
LEVELS = ('brief', 'detailed', 'full')
LABELS = {'status': 'Status', 'inputs': 'Inputs', 'outputs': 'Outputs',
          'questions': 'Decisions', 'controls': 'Controls', 'usage': 'Usage',
          'ask': 'Ask / follow-up'}
LEVEL_LABELS = {'brief': 'Brief', 'detailed': 'Detailed', 'full': 'Comprehensive'}
NOTICE = '\n\nView shortened. The comprehensive report is downloadable.'
ADMITTED = frozenset('id goal state created_at deadline max_tasks title prompt '
    'source_sha paths tests review result usage summary proposal findings verdict '
    'status passed failed skipped total count exit_code command name duration_seconds '
    'started_at finished_at verified evidence reason message text question answer '
    'decision options selected task_id type kind action at timestamp actor '
    'input_tokens output_tokens total_tokens cached_tokens tokens cost cost_usd '
    'currency model provider requests calls model_calls elapsed_seconds remaining_seconds '
    'completed_tasks failed_tasks pending_tasks max_minutes max_seconds max_cost_usd '
    'max_tokens max_model_calls source_writes publication tests_executed '
    'gemini_sha256 codex_sha256 critique automatic_retry blocked_tasks admitted_tasks '
    'changed_files changes path content candidates gemini codex diff suite records '
    'turns reported cached_input_tokens gpt_calls max_gpt_calls minutes repairs_per_task paid_api_fallback normal_passed '
    'mutation_detected new_test test_count sha256 planner_note selected attempt '
    'results coordination_result coordination_task_id mutation last_seen '
    'published commit commit_sha artifact_sha256 branch repository source_branch '
    'base_sha selected_candidate receipt checks publication_digest answer_mode answered_at '.split())
SECRET_KEY = re.compile(r'(?i)(?:password|passwd|secret|credential|private[_ -]?key|'
                        r'api[_ -]?key|access[_ -]?token|refresh[_ -]?token|bot[_ -]?token)')
ASSIGNMENT = re.compile(r'''(?ix)\b(password|passwd|secret|api[_ -]?key|access[_ -]?token|
    refresh[_ -]?token|bot[_ -]?token|token)\b["']?\s*[:=]\s*
    (?:"[^"\n]*"|'[^'\n]*'|[^\s,;&}\]]+)''')
TOKEN = re.compile(r'(?i)\b(?:sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9]{16,}|'
                   r'github_pat_[a-z0-9_]{16,}|\d{6,}:[a-z0-9_-]{20,})\b')
PRIVATE_KEY = re.compile(r'-----BEGIN [^-\n]*PRIVATE KEY-----.*?'
                         r'(?:-----END [^-\n]*PRIVATE KEY-----|\Z)', re.S)


def _redact(text):
    text = PRIVATE_KEY.sub('[private key redacted]', text)
    text = re.sub(r'(?i)\bBearer\s+[^\s,;]+', 'Bearer [redacted]', text)
    text = ASSIGNMENT.sub(lambda m: m[1]+'=[redacted]', text)
    text = TOKEN.sub('[credential redacted]', text)
    return ''.join(c for c in text if c in '\n\t' or ord(c) >= 32)


def _clean(value, depth=0):
    if depth > 12:
        return '[nested content omitted]'
    if isinstance(value, dict):
        return {key: ('[redacted]' if SECRET_KEY.search(key) else _clean(item, depth+1))
                for key, item in value.items() if isinstance(key, str)
                and (key in ADMITTED or SECRET_KEY.search(key))}
    if isinstance(value, (list, tuple)):
        return [_clean(item, depth+1) for item in value]
    if isinstance(value, str):
        return _redact(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return '[unsupported value omitted]'


def _snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError('Snapshot must be an admitted object')
    return {key: _clean(snapshot.get(key, default)) for key, default in
            (('batch', {}), ('tasks', []), ('events', []), ('questions', []),
             ('totals', {}), ('limits', {}), ('publication', {}),
             ('publication_result', {}), ('worker', {}), ('ongoing', {}))}


def _text(value):
    if value is None:
        return 'Not recorded'
    if value is True:
        return 'Yes'
    if value is False:
        return 'No'
    if isinstance(value, dict):
        return '\n'.join(key.replace('_', ' ').capitalize()+': '+_text(item)
                         for key, item in value.items()) or 'Not recorded'
    if isinstance(value, list):
        return '\n'.join('- '+_text(item) for item in value) or 'None recorded'
    return str(value)


def _field(data, key, label=None):
    return (label or key.replace('_', ' ').capitalize())+': '+_text(data.get(key))


def _tasks(data):
    return [item for item in data['tasks'] if isinstance(item, dict)] if isinstance(data['tasks'], list) else []


def _section(view, level, data):
    batch = data['batch'] if isinstance(data['batch'], dict) else {}
    tasks = _tasks(data)
    short = level == 'brief'
    lines = [LABELS[view]]
    if view == 'status':
        lines += [_field(batch, 'goal'), _field(batch, 'state'),
                  'Tasks admitted: '+str(len(tasks)), _field(batch, 'max_tasks', 'Task limit'),
                  _field(batch, 'deadline')]
        worker=data['worker'] if isinstance(data['worker'],dict) else {}
        lines += [_field(worker,'last_seen','Laptop worker last seen'),
                  'Last seen records a worker check-in; it does not prove the worker is online now.']
        lines += [(str(t.get('title') or t.get('id') or 'Task')+': '+
                   str(t.get('state', 'Not recorded'))) for t in tasks]
        if not short:
            lines += [_field(batch, 'id', 'Batch'), _field(batch, 'created_at'),
                      'Recent events:\n'+_text(data['events'])]
    elif view == 'inputs':
        lines += ['Only operator-admitted tasks and source files enter this pilot.']
        for task in tasks:
            lines += ['', _field(task, 'title', 'Task')]
            if not short:
                lines += [_field(task, 'prompt', 'Request'), _field(task, 'paths', 'Admitted files'),
                          _field(task, 'source_sha', 'Source revision')]
            else:
                paths = task.get('paths', [])
                lines += ['Admitted files: '+str(len(paths) if isinstance(paths, list) else 'Not recorded')]
        if not tasks:
            lines += ['No admitted task inputs.']
    elif view == 'outputs':
        lines += ['Test results are shown as recorded; missing evidence is unverified. '
                  'Model review is advisory and is not approval.']
        for task in tasks:
            lines += ['', _field(task, 'title', 'Task'), _field(task, 'state'),
                      _field(task, 'tests', 'Test evidence'), _field(task, 'review', 'Advisory review')]
            result = task.get('result')
            if short and isinstance(result, dict):
                result = {k: v for k, v in result.items() if k in ('summary', 'state', 'status')}
            lines += ['Result: '+_text(result)]
            if not short and 'candidates' in task:
                candidates = task['candidates']
                if level == 'detailed' and isinstance(candidates, dict):
                    candidates = {owner: {key: value for key, value in record.items()
                                          if key in ('summary', 'proposal', 'state')}
                                  for owner, record in candidates.items() if isinstance(record, dict)}
                lines += ['Coder candidates:\n'+_text(candidates)]
                if level == 'detailed':
                    lines += ['Candidate diffs are available in Comprehensive and the downloadable report.']
        if not tasks:
            lines += ['No task outputs recorded.']
        if data['publication']:
            lines += ['', 'Combined publication evidence:\n'+_text(data['publication'])]
        if data['publication_result']:
            lines += ['', 'Publication result:\n'+_text(data['publication_result'])]
    elif view == 'questions':
        questions=data['questions'] if isinstance(data['questions'],list) else []
        visible=[q for q in questions if isinstance(q,dict) and q.get('state') in ('pending','answering')]
        if not visible:lines += ['No answer is needed right now.']
        for q in visible:lines += ['',str(q.get('question','Question')), 'Choose a fixed answer below, or Custom to type your own.']
        if not short:lines += ['Recorded answers and decisions:', _text(questions)]
        if not short:
            lines += ['Decision history:\n'+_text(data['events'])]
        lines += ['Use Ask / follow-up for clarification. A model suggestion does not record your approval.']
    elif view == 'controls':
        lines += [_field(batch, 'state', 'Current state'), _field(batch, 'deadline'),
                  _field(batch, 'max_tasks', 'Task limit'),
                  'Pause or resume the pilot using the buttons below. Confirm the returned state.',
                  'Controls do not approve source changes, publication or deployment.']
        if not short:
            lines += ['Configured limits:\n'+_text(data['limits'])]
    elif view == 'usage':
        lines += ['Recorded usage:\n'+_text(data['totals']),
                  'Limits:\n'+_text(data['limits']),
                  'Missing usage is unknown, not zero. Subscription usage is not a verified API bill.']
        if not short:
            for task in tasks:
                lines += ['', _field(task, 'title', 'Task'), _field(task, 'usage')]
    else:
        lines += ['Send your follow-up with the task name and what you want clarified.',
                  'Review Inputs for the request, Outputs for evidence, or Decisions for pending questions.',
                  'A follow-up does not by itself approve a source change or deployment.']
        if not short:
            lines += ['Current questions:\n'+_text(data['questions'])]
    return '\n'.join(lines)


def _validate(view, level):
    level = 'full' if isinstance(level, str) and level.lower() == 'comprehensive' else level
    if view not in VIEWS or level not in LEVELS:
        raise ValueError('Unknown pilot view or detail level')
    return view, level


def _clip(text):
    # Telegram counts UTF-16 code units; stay below the requested 3500 even
    # with emoji. Never leave a split surrogate pair in the returned string.
    encoded = text.encode('utf-16-le', errors='replace')
    if len(encoded) <= 7000:
        return text
    budget = 7000-len(NOTICE.encode('utf-16-le'))
    return encoded[:budget].decode('utf-16-le', errors='ignore').rstrip()+NOTICE


def render(view, level, snapshot):
    """Return plain text, at most 3500 characters and UTF-16 code units."""
    view, level = _validate(view, level)
    text = _section(view, level, _snapshot(snapshot))
    if level == 'brief':
        text = re.sub(r'\b[a-fA-F0-9]{40,64}\b', '[revision omitted]', text)
    return _clip(text)


def keyboard(view, level):
    """Return buttons only; authorization and callback handling belong elsewhere."""
    view, level = _validate(view, level)
    def button(label, target, detail=level):
        return {'text': label, 'callback_data': 'p:'+target+':'+detail}
    rows = [[button(LABELS[a], a), button(LABELS[b], b)]
            for a, b in [('status', 'inputs'), ('outputs', 'questions'), ('controls', 'usage')]]
    rows += [[button(LABELS['ask'], 'ask', 'brief')],
             [button(LEVEL_LABELS[item], view, item) for item in LEVELS],
             [button('Download comprehensive report', 'report', 'full')]]
    if view == 'controls':
        rows += [[button('Pause', 'pause', 'brief'), button('Resume', 'resume', 'brief')]]
    return {'inline_keyboard': rows}


def report(snapshot):
    """Complete Markdown rendering of admitted fields; no truncation or I/O.

    Unknown keys are deliberately omitted. Credential redaction is heuristic;
    the caller must exclude sensitive/private content before building snapshots.
    """
    data = _snapshot(snapshot)
    def escape(text):
        return re.sub(r'([\\`*_{}\[\]<>()#+.!|>-])', r'\\\1', text)
    sections = ['# Pilot comprehensive report',
                'Model reviews are advisory. Execution evidence is shown only as recorded.']
    for key, title in [('batch', 'Batch'), ('tasks', 'Tasks: inputs and outputs'),
                       ('questions', 'Questions and decisions'), ('events', 'Event history'),
                       ('totals', 'Usage totals'), ('limits', 'Limits'),
                       ('publication','Combined publication evidence'),
                       ('publication_result','Publication result'), ('worker','Worker availability'),
                       ('ongoing','Ongoing assigned work and model usage')]:
        sections += ['## '+title, escape(_text(data[key]))]
    sections += ['Credential redaction is heuristic; this report requires an admitted, safe snapshot.']
    return '\n\n'.join(sections)+'\n'

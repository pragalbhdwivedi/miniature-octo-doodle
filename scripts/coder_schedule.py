"""One Antigravity sidecar tick; notify once per operator-admitted task.

Uses the documented sidecar agentapi CLI, never an editor backend or UI input.
No task admission, source edits, permission changes, inference or publication.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from coder_coordination import Coordinator
from sidecar_runtime import active_host


def now():
    return datetime.now(timezone.utc).isoformat()


def notify(executable, conversation, prompt):
    # Agentapi's own event log retains delivery evidence. Do not duplicate
    # conversation content into scheduler logs or inherit an interactive console.
    result = subprocess.run(
        [executable, 'send-message', conversation, prompt],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=30, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError('Agentapi delivery failed')


def tick(coordinator, conversation, executable, sender=notify):
    if not isinstance(conversation, str) or not re.fullmatch(
            r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', conversation):
        raise ValueError('An operator-selected conversation UUID is required')
    with coordinator.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS scheduled_dispatches ('
                   'id TEXT PRIMARY KEY, state TEXT NOT NULL, '
                   'created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
        rows = db.execute('SELECT id,state,packet FROM tasks WHERE state != "closed"').fetchall()
        if not rows:
            return {'state': 'idle', 'model_calls': 0}
        if len(rows) != 1 or rows[0]['state'] != 'queued':
            return {'state': 'held', 'model_calls': 0}
        row = rows[0]
        prior = db.execute('SELECT state FROM scheduled_dispatches WHERE id=?', (row['id'],)).fetchone()
        if prior:
            return {'state': 'already_dispatched', 'dispatch_state': prior['state'],
                    'task_id': row['id'], 'model_calls': 0, 'automatic_retry': False}
        try:
            coordinator.fresh(json.loads(row['packet']))
        except Exception:
            db.execute('INSERT INTO scheduled_dispatches VALUES(?,?,?,?)',
                       (row['id'], 'blocked_source', now(), now()))
            return {'state': 'blocked_source', 'task_id': row['id'], 'model_calls': 0}
        db.execute('INSERT INTO scheduled_dispatches VALUES(?,?,?,?)',
                   (row['id'], 'delivery_started', now(), now()))
    # Persist before delivery: a crash or timeout can never cause a repeat send.
    prompt = (
        'Scheduled AADI coordination task '+row['id']+'. Use ONLY '
        'aadi-coder-coordination MCP tools. Read coordination_status. Continue '
        'only if this exact task is queued; otherwise stop. Call claim_next_task '
        'once with expected_task_id="'+row['id']+'", generate your own candidate from the returned source/task packet, '
        'submit_candidate as a JSON object, then call advance_task ONCE. '
        'If disconnected or timed out, use coordination_status; never rerun '
        'advance_task or take over a claim. Report source SHA, both hashes and '
        'advisory findings. Do not read other files, use other tools, execute '
        'commands/tests, edit source, publish, merge or deploy. Permission '
        'requests must remain pending for the user. Stop at human_review_required.')
    state = 'notified'
    try:
        sender(executable, conversation, prompt)
    except Exception:
        state = 'delivery_uncertain'
    with coordinator.connect() as db:
        db.execute('UPDATE scheduled_dispatches SET state=?,updated_at=? WHERE id=?',
                   (state, now(), row['id']))
    return {'state': state, 'task_id': row['id'], 'automatic_retry': False}


def heartbeat(root, result):
    # Fixed-size latest status; concurrent ticks use separate temporary files.
    value = {'checked_at': now(), **result}
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root,
                                     prefix='schedule-', suffix='.tmp', delete=False) as f:
        json.dump(value, f)
        temporary = f.name
    os.replace(temporary, root/'schedule-status.json')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    coordinator = Coordinator(json.loads(Path(config['coordination_config']).read_text(encoding='utf-8')))
    executable = shutil.which('agentapi')
    if not active_host():
        # Old Antigravity timers can outlive their host on Windows. Do not let
        # their dead agentapi context take a task reservation or overwrite the
        # current scheduler heartbeat. A direct shell invocation is also idle.
        print(json.dumps({'checked_at':now(),'state':'inactive_sidecar_host','model_calls':0}))
        return
    if executable:
        result = tick(coordinator, config['conversation_id'], executable)
    else:
        result = {'state': 'agentapi_unavailable', 'model_calls': 0}
    print(json.dumps(heartbeat(coordinator.root, result)))


if __name__ == '__main__':
    main()

"""Worker ownership, code scope and real synthetic mutation acceptance tests."""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import pilot_worker as w


BASE = '''from copy import deepcopy
import json
from pathlib import Path
import unittest
from aadi_contracts.identity import validate_snapshot

class IdentityContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((Path(__file__).resolve().parents[1] / 'contracts/identity_snapshot.v1.example.json').read_text())
        self.actor = None

    def test_existing(self):
        self.assertEqual(validate_snapshot(self.payload, self.actor).mappings, 1)

if __name__ == '__main__':
    unittest.main()
'''
SOURCE = '''from collections import namedtuple
Receipt = namedtuple('Receipt', 'mappings verified_mappings')
class ContractError(ValueError):
    pass
def validate_snapshot(payload, actor):
    groups = {}
    for row in payload['mappings']:
        scope = tuple(row[k] for k in ('institution_id', 'source_system', 'source_instance', 'source_entity', 'source_record_id'))
        if scope in groups:
            raise ContractError("Overlapping source mapping; review required")
        groups[scope] = row
    return Receipt(len(groups), len(groups))
'''
ROW = {'institution_id': 'SYN-A', 'source_system': 'hikcentral', 'source_instance': 'SYN-1',
       'source_entity': 'employee', 'source_record_id': '0007'}


def proposed(mutation='system-case'):
    values = {
        'system-case': ('source_system', 'hikcentral', 'HIKCENTRAL'),
        'id-space': ('source_record_id', 'AB CD', 'ABCD'),
        'id-case': ('source_record_id', 'AbC', 'abc'),
    }
    key, first, second = values[mutation]
    added = f'''
    def test_new_regression(self):
        data = deepcopy(self.payload)
        data['mappings'][0]['{key}'] = '{first}'
        other = deepcopy(data['mappings'][0])
        other['{key}'] = '{second}'
        data['mappings'].append(other)
        before = deepcopy(data)
        receipt = validate_snapshot(data, self.actor)
        self.assertEqual(receipt.mappings, 2)
        self.assertEqual(receipt.verified_mappings, 2)
        self.assertEqual(data, before)
        data['mappings'].reverse()
        before = deepcopy(data)
        self.assertEqual(validate_snapshot(data, self.actor), receipt)
        self.assertEqual(data, before)

'''
    return BASE.replace("if __name__", added+"if __name__")


class FakeCoordinator:
    def __init__(self, repo, root):
        self.repo, self.root, self.executable = repo, root, Path(sys.executable)
        self.rows, self.closed, self.admitted = [], [], []

    @contextmanager
    def connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.root/'coordination.sqlite3')
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def status(self):
        return {'tasks': self.rows}

    def close(self, child, reason):
        self.closed.append(child)
        next(row for row in self.rows if row['id'] == child)['state'] = 'closed'

    def admit(self, child, prompt, paths):
        self.admitted.append((child, prompt, paths))
        return {'task_id': child, 'source_sha': 'a'*40}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root/'repo'
        self.repo.mkdir()
        self.env = patch.dict(os.environ, {'LOCALAPPDATA': str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.coordinator = FakeCoordinator(self.repo, self.root/'coordination')
        self.config = {'source_repo': str(self.repo), 'output_root': str(self.root/'private'),
                       'test_image': 'sha256:'+'1'*64}
        self.messages = []
        self.work = {'action': 'dispatch', 'batch': {'id': '123456abcdef'},
                     'task': {'id': 't1', 'attempt': 0, 'source_sha': 'a'*40,
                         'paths': [w.TEST_PATH], 'mutation': 'system-case', 'prompt': 'Add regression.'},
                     'token': 'lease-test'}
        self.files = {'src/aadi_contracts/__init__.py': '', w.SOURCE_PATH: SOURCE,
                      w.TEST_PATH: BASE, 'contracts/identity_snapshot.v1.example.json':
                          json.dumps({'mappings': [ROW]})}
        self.worker = w.Worker(self.config, remote=self.remote, coordinator=self.coordinator)
        self.source_patch = patch.object(self.worker, 'source', return_value=self.files)
        self.source_patch.start()
        self.addCleanup(self.source_patch.stop)

    def remote(self, request):
        self.messages.append(request)
        return self.work if request['action'] == 'work' else {'state': 'accepted'}

    def make_child(self, mutation='system-case'):
        child = self.worker.child_id(self.work)
        self.work['task']['coordination_task_id'] = child
        self.work['task']['mutation'] = mutation
        values = {owner: {'summary': 'Synthetic regression', 'proposal': 'No tests run.',
                         'changes': [{'path': w.TEST_PATH, 'content': proposed(mutation)}]}
                  for owner in ('gemini', 'codex')}
        directory = self.coordinator.root/child
        directory.mkdir(parents=True)
        for owner, value in values.items():
            w.write_json(directory/(owner+'.json'), value)
        self.coordinator.rows.append({'id': child, 'state': 'human_review_required',
            'result': {**{owner+'_sha256': w.coordination.digest(v) for owner, v in values.items()},
                       'source_sha': 'a'*40, 'critique': {'verdict': 'review', 'findings': []}}})
        return child

    def fixture_runner(self, command, **kwargs):
        # Execute only this test module's authored synthetic fixture, never a
        # model candidate. Production paths always invoke Docker isolation.
        self.assertEqual(command[:3], ['docker', 'run', '--rm'])
        for flag in ('--pull=never', '--read-only', 'ALL', 'no-new-privileges', '65534:65534',
                     '64', '256m', '/tmp:rw,noexec,nosuid,size=32m'):
            self.assertIn(flag, command)
        self.assertEqual(command[command.index('--network')+1], 'none')
        self.assertEqual(kwargs, {'timeout': 60, 'limit': 65536})
        mount = command[command.index('--mount')+1]
        self.assertTrue(mount.endswith(',dst=/work,readonly'))
        stage = Path(mount.removeprefix('type=bind,src=').removesuffix(',dst=/work,readonly'))
        self.assertEqual({p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}, set(w.FILES))
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                 '-p', 'test_identity_contract.py', '-v'], cwd=stage,
                    env={**os.environ, 'PYTHONPATH': str(stage/'src'), 'PYTHONDONTWRITEBYTECODE': '1'},
                    capture_output=True, timeout=10)
        return result.returncode, result.stdout, result.stderr

    def test_all_three_real_mutations_are_detected_only_by_added_test(self):
        self.worker.runner = self.fixture_runner
        for mutation in w.MUTATIONS:
            with self.subTest(mutation=mutation):
                self.work['task']['id'] = 't'+str(list(w.MUTATIONS).index(mutation)+1)
                self.make_child(mutation)
                directory = self.worker.task_directory(self.work)/'test'
                directory.mkdir()
                result = self.worker.test(self.work, directory)
                for candidate in result['candidates'].values():
                    self.assertTrue(candidate['passed'], candidate.get('normal_output', candidate))
                    self.assertEqual((candidate['normal_exit'], candidate['mutation_exit']), (0, 1))
                    self.assertEqual(candidate['test_count'], 2)
                    self.assertEqual(candidate['sha256'], hashlib.sha256(candidate['content'].encode()).hexdigest())

    def test_preserves_every_existing_ast_and_rejects_extra_executable_code(self):
        self.assertEqual(w.validate_addition(BASE, proposed()), ('test_new_regression', 2))
        attacks = [proposed().replace('.mappings, 1', '.mappings, 2'),
                   proposed()+'\nprint("side effect")\n',
                   proposed().replace('data = deepcopy(self.payload)', 'import os\n        data = deepcopy(self.payload)'),
                   proposed().replace('data = deepcopy(self.payload)', 'data = open("secret")'),
                   proposed().replace('receipt.mappings', 'receipt.__class__'),
                   proposed().replace("        data['mappings'].reverse()", '        self.actor = None'),
                   proposed().replace('def test_new_regression(self):', '@unittest.skip("skip")\n    def test_new_regression(self):'),
                   proposed().replace('data = deepcopy(self.payload)', 'validate_snapshot = deepcopy(self.payload)'),
                   proposed().replace('data = deepcopy(self.payload)', 'while True:\n            pass'),
                   proposed().replace('def test_new_regression(self):', 'def test_new_regression(self, x=open("x")):')]
        for attack in attacks:
            with self.subTest(attack=attack[-100:]), self.assertRaises((w.WorkerError, SyntaxError)):
                w.validate_addition(BASE, attack)

    def test_mutation_infrastructure_or_unrelated_failure_is_not_acceptance(self):
        valid = ('test_existing (test_identity_contract.IdentityContractTests.test_existing) ... ok\n'
                 'test_new_regression (test_identity_contract.IdentityContractTests.test_new_regression) ... ERROR\n'
                 'aadi_contracts.identity.ContractError: Overlapping source mapping; review required\n'
                 'Ran 2 tests in 0.001s\nFAILED (errors=1)\n')
        self.assertTrue(w.test_result(1, valid, 2, 'test_new_regression', mutant=True))
        for bad in (valid.replace('ContractError', 'ImportError'),
                    valid.replace('test_new_regression', 'test_existing'),
                    valid.replace('Ran 2 tests', 'Ran 1 test'),
                    valid.replace('... ok', '... FAIL'), 'Docker not running'):
            self.assertFalse(w.test_result(1, bad, 2, 'test_new_regression', mutant=True))
        self.assertFalse(w.test_result(125, valid, 2, 'test_new_regression', mutant=True))

    def test_candidate_hash_mismatch_stops_before_execution(self):
        child = self.make_child()
        path = self.coordinator.root/child/'gemini.json'
        value = w.read_json(path)
        value['summary'] += 'changed'
        w.write_json(path, value)
        self.worker.runner = lambda *a, **k: self.fail('Must not execute tampered candidate')
        with self.assertRaisesRegex(w.WorkerError, 'hash mismatch'):
            self.worker.test(self.work, self.root)

    def test_owned_child_cannot_read_another_queue_task(self):
        self.make_child()
        self.work['task']['coordination_task_id'] = 'other-task'
        with self.assertRaisesRegex(w.WorkerError, 'ownership mismatch'):
            self.worker.observe(self.work)

    def test_dispatch_and_replay_never_duplicate_admission(self):
        self.assertEqual(self.worker.tick()['state'], 'finished')
        self.assertEqual(len(self.coordinator.admitted), 1)
        self.assertEqual(self.worker.tick()['state'], 'blocked')
        self.assertEqual(len(self.coordinator.admitted), 1)
        self.assertEqual(self.messages[-1]['action'], 'fail')
        exported = w.read_json(self.worker.task_directory(self.work)/'dispatch'/'task.json')
        self.assertIn('created_at', exported)
        self.assertEqual(exported['task']['prompt'], 'Add regression.')

    def test_unrelated_or_running_child_cannot_be_closed(self):
        for task in ({'id': 'unrelated', 'state': 'human_review_required'},
                     {'id': 'pilot-123456abcdef-t1-a0', 'state': 'running'}):
            self.coordinator.rows = [task]
            with self.assertRaisesRegex(w.WorkerError, 'unreconciled'):
                self.worker.dispatch(self.work, self.root)
        self.assertEqual(self.coordinator.closed, [])

    def test_previous_own_child_requires_both_test_and_review_evidence(self):
        child = self.make_child()
        directory = self.worker.task_directory(self.work)
        self.work['task']['id'] = 't2'
        with self.assertRaisesRegex(w.WorkerError, 'incomplete'):
            self.worker.dispatch(self.work, self.root)
        for stage in ('test', 'review'):
            (directory/stage).mkdir()
            w.write_json(directory/stage/'result.json', {'verified': True})
        self.worker.dispatch(self.work, self.root)
        self.assertEqual(self.coordinator.closed, [child])

    def test_independent_reviewer_cannot_override_failed_tests(self):
        directory = self.worker.task_directory(self.work)
        (directory/'test').mkdir()
        (directory/'review').mkdir()
        w.write_json(directory/'test'/'result.json', {'candidates': {'gemini': {'passed': False}, 'codex': {'passed': True}}})
        calls = []
        def reviewer(executable, prompt, path, schema):
            calls.append((prompt, schema))
            return {'verdict': 'pass', 'selected': 'gemini', 'findings': []}
        self.worker.coder = reviewer
        result = self.worker.review(self.work, directory/'review')
        self.assertEqual((result['verdict'], result['selected']), ('repair', 'none'))
        self.assertFalse(result['usage']['reported'])
        self.assertIn('source', calls[0][0])
        self.assertEqual(calls[0][1], w.REVIEW_SCHEMA)

    def publication_tasks(self):
        tasks = []
        for index, mutation in enumerate(w.MUTATIONS):
            content = proposed(mutation).replace('test_new_regression', 'test_'+mutation.replace('-', '_'))
            tasks.append({**self.work['task'], 'id': 't'+str(index+1), 'mutation': mutation,
                          'selected': 'gemini', 'results': {'candidates': {'gemini': {
                              'passed': True, 'content': content,
                              'sha256': hashlib.sha256(content.encode()).hexdigest()}}}})
        return tasks

    def test_combined_artifact_preserves_baseline_and_detects_each_mutation(self):
        self.work.update(action='prepare_publication', tasks=self.publication_tasks())
        self.worker.runner = self.fixture_runner
        self.worker.coder = lambda *a, **k: {'verdict': 'pass', 'findings': []}
        self.assertEqual(self.worker.tick()['state'], 'finished')
        result = self.messages[-1]['result']
        self.assertTrue(result['passed'])
        self.assertEqual(result['test_evidence']['test_count'], 4)
        self.assertEqual(len(result['test_evidence']['mutations']), 3)
        self.assertTrue(all(v['detected'] for v in result['test_evidence']['mutations']))
        self.assertIn('def test_existing(self)', result['content'])

    def test_combining_colliding_test_names_cannot_silently_drop_tests(self):
        tasks = self.publication_tasks()
        content = tasks[1]['results']['candidates']['gemini']['content'].replace('test_id_space', 'test_system_case')
        tasks[1]['results']['candidates']['gemini'].update(content=content, sha256=hashlib.sha256(content.encode()).hexdigest())
        self.work['tasks'] = tasks
        with self.assertRaisesRegex(w.WorkerError, 'collide'):
            self.worker.prepare_publication(self.work, self.root)

    def test_exact_approved_artifact_publishes_fast_forward_dev_only(self):
        def git(*args):
            result = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            return result.stdout.decode().strip()
        remote = self.root/'origin.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
        git('init')
        git('config', 'user.email', 'synthetic@example.invalid')
        git('config', 'user.name', 'Synthetic Worker Test')
        git('config', 'core.autocrlf', 'false')
        for path, content in self.files.items():
            target = self.repo/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8', newline='\n')
        git('add', '.')
        git('commit', '-m', 'Synthetic baseline')
        base_sha = git('rev-parse', 'HEAD')
        git('remote', 'add', 'origin', str(remote))
        git('push', 'origin', 'HEAD:Dev', 'HEAD:main')
        git('checkout', '--detach', base_sha)
        self.work['task']['source_sha'] = base_sha
        self.work.update(action='prepare_publication', tasks=self.publication_tasks())
        self.worker.runner = self.fixture_runner
        self.worker.coder = lambda *a, **k: {'verdict': 'pass', 'findings': []}
        self.assertEqual(self.worker.tick()['state'], 'finished')
        artifact = self.messages[-1]['result']
        digest = hashlib.sha256(json.dumps(artifact, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.work.update(action='publish', publication=artifact, publication_digest=digest)
        self.worker.runner = w.bounded_run
        self.source_patch.stop()
        with patch.object(w.coordination, 'REPOSITORY', str(remote).removesuffix('.git')):
            state = self.worker.tick()['state']
            failure = self.worker.root/self.work['batch']['id']/'publish'/'failure.json'
            self.assertEqual(state, 'finished', w.read_json(failure) if failure.exists() else '')
        result = self.messages[-1]['result']
        self.assertTrue(result['published'])
        self.assertEqual(git('ls-remote', 'origin', 'refs/heads/main'), base_sha+'\trefs/heads/main')
        self.assertEqual(git('ls-remote', 'origin', 'refs/heads/Dev'), result['commit']+'\trefs/heads/Dev')
        self.assertEqual(git('rev-parse', 'HEAD'), result['commit'])
        self.assertEqual(git('diff', '--name-only', base_sha, result['commit']), w.TEST_PATH)
        self.assertEqual(git('status', '--porcelain'), '')
        self.assertEqual(self.worker.tick()['state'], 'blocked')
        self.assertEqual(git('rev-parse', 'HEAD'), result['commit'])

    def test_observe_passes_exact_owned_identity_and_blocked_state_without_lease(self):
        child = self.make_child()
        self.worker.observe(self.work)
        request = self.messages[-1]
        self.assertEqual(request['action'], 'observed')
        self.assertEqual(request['coordination_task_id'], child)
        self.assertEqual(request['result']['state'], 'human_review_required')
        self.assertEqual(request['result']['source_sha'], 'a'*40)
        self.coordinator.rows[0]['state'] = 'blocked'
        self.worker.observe(self.work)
        self.assertEqual(self.messages[-1]['result']['state'], 'blocked')
        self.assertNotIn('token', self.messages[-1])

    def test_observer_reports_delivery_problem_without_resetting_or_retrying(self):
        child = self.make_child()
        self.coordinator.rows[0]['state'] = 'queued'
        self.assertEqual(self.worker.observe(self.work)['state'], 'waiting_for_coders')
        with self.coordinator.connect() as db:
            db.execute('CREATE TABLE scheduled_dispatches(id TEXT PRIMARY KEY,state TEXT)')
            db.execute('INSERT INTO scheduled_dispatches VALUES(?,?)', ('unrelated-task', 'delivery_uncertain'))
        self.assertEqual(self.worker.observe(self.work)['state'], 'waiting_for_coders')
        for delivery, expected in [('delivery_started', 'delivery_uncertain'),
                                   ('delivery_uncertain', 'delivery_uncertain'),
                                   ('blocked_source', 'blocked')]:
            with self.subTest(delivery=delivery):
                with self.coordinator.connect() as db:
                    db.execute('INSERT OR REPLACE INTO scheduled_dispatches VALUES(?,?)', (child, delivery))
                self.worker.observe(self.work)
                request = self.messages[-1]
                self.assertEqual(request['action'], 'observed')
                self.assertEqual(request['coordination_task_id'], child)
                self.assertEqual(request['result']['state'], expected)
                self.assertEqual(request['result']['dispatch_state'], delivery)
                self.assertFalse(request['result']['automatic_retry'])
                self.assertNotIn('token', request)
                with self.coordinator.connect() as db:
                    self.assertEqual(db.execute('SELECT state FROM scheduled_dispatches WHERE id=?',
                                               (child,)).fetchone()['state'], delivery)
        self.coordinator.rows[0]['state'] = 'gemini_claimed'
        previous = len(self.messages)
        self.assertEqual(self.worker.observe(self.work)['coordination_state'], 'gemini_claimed')
        self.assertEqual(len(self.messages), previous)
        self.assertEqual(self.coordinator.admitted, [])
        self.assertEqual(self.coordinator.closed, [])

    def test_idle_does_not_create_model_or_stage_work(self):
        self.work = {'action': 'idle'}
        self.worker.coder = lambda *a, **k: self.fail('No idle model calls')
        self.assertEqual(self.worker.tick(), {'state': 'idle', 'model_calls': 0})
        self.assertEqual(self.messages, [{'action': 'work'}])

    def test_publication_is_fail_closed(self):
        self.work['action'] = 'publish'
        self.assertEqual(self.worker.tick()['state'], 'blocked')
        self.assertEqual(self.messages[-1]['action'], 'fail')

    def test_plan_only_returns_one_prompt_per_fixed_task(self):
        self.work['action'] = 'plan'
        self.work['batch']['tasks'] = [{'id': 't1', 'mutation': 'system-case'}]
        self.worker.coder = lambda *a, **k: {'prompts': ['One test.', 'Unexpected scope.']}
        self.assertEqual(self.worker.tick()['state'], 'blocked')
        self.assertFalse(any(message['action'] == 'finish' for message in self.messages))

    def test_question_uses_only_local_model_and_marks_advisory(self):
        self.work.update(action='ask', question={'id': 'q-1', 'text': 'What failed?'},
                         snapshot={'state': 'testing'})
        self.worker.coder = lambda *a, **k: self.fail('No GPT question calls')
        self.worker.chat = lambda model, messages, schema, tokens: {'answer': 'Tests are running; no failure is recorded.'}
        self.assertEqual(self.worker.tick()['state'], 'finished')
        finish = self.messages[-1]
        self.assertEqual(finish['question_id'], 'q-1')
        self.assertTrue(finish['result']['advisory'])

    def test_fixed_config_denies_image_tags_or_shell_metacharacters(self):
        with self.assertRaisesRegex(w.WorkerError, 'digest'):
            w.Worker({**self.config, 'test_image': 'python:latest'}, coordinator=self.coordinator)
        for key, bad in [('ssh_host', '-oProxyCommand=bad'), ('remote_script', '/safe;bad'),
                         ('remote_config', '/safe/../secret')]:
            config = {'ssh_host': 'operator@vm', 'remote_script': '/opt/pilot.py', 'remote_config': '/etc/pilot.json', key: bad}
            with self.assertRaises(w.WorkerError):
                w.Remote(config)

    def test_remote_json_stdin_is_not_interpolated_as_shell(self):
        calls = []
        remote = w.Remote({'ssh_host': 'operator@vm', 'remote_script': '/opt/pilot.py',
                           'remote_config': '/etc/pilot.json'},
                          lambda command, **kw: (calls.append((command, kw)) or (0, b'{"action":"idle"}', b'')))
        malicious = {'action': 'ask', 'text': '$(touch x); `bad`'}
        self.assertEqual(remote(malicious), {'action': 'idle'})
        command, args = calls[0]
        self.assertNotIn(malicious['text'], ' '.join(command))
        self.assertEqual(json.loads(args['data']), malicious)
        self.assertEqual(args['timeout'], 30)

    def test_bounded_process_timeout_and_overflow(self):
        with self.assertRaisesRegex(w.WorkerError, 'deadline'):
            w.bounded_run([sys.executable, '-c', 'import time; time.sleep(2)'], timeout=.1)
        with self.assertRaisesRegex(w.WorkerError, 'output'):
            w.bounded_run([sys.executable, '-c', 'print("x"*5000)'], limit=128)
        code, stdout, stderr = w.bounded_run([sys.executable, '-c', 'print("ok")'])
        self.assertEqual((code, stdout.strip(), stderr), (0, b'ok', b''))

    def test_lock_blocks_parallel_step_and_releases_after_scope(self):
        with w.local_lock(self.worker.root) as first:
            self.assertTrue(first)
            with w.local_lock(self.worker.root) as second:
                self.assertFalse(second)
        with w.local_lock(self.worker.root) as third:
            self.assertTrue(third)


if __name__ == '__main__':
    unittest.main()

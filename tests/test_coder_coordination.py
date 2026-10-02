import concurrent.futures
import json
import os
from pathlib import Path
import sqlite3
import sys
import subprocess
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import coder_coordination as c
import test_local_agent as fixture


class CoordinationTests(unittest.TestCase):
    command = fixture.LocalAgentTests.command

    def setUp(self):
        fixture.LocalAgentTests.setUp(self)
        self.command('push', '-q', 'origin', 'HEAD:Dev')
        for p in (patch.object(c, 'REPOSITORY', str(self.remote).removesuffix('.git')),
                  patch.dict(os.environ, {'LOCALAPPDATA': str(self.repo.parent)})):
            p.start()
            self.addCleanup(p.stop)
        self.calls = []
        self.value = {'summary': 'Return 42', 'proposal': 'No tests run.',
                      'changes': [{'path': 'example.py', 'content': 'def answer():\n    return 42\n'}]}
        def coder(*args):
            self.calls.append('codex')
            self.assertNotIn('Gemini candidate', args[1])
            return self.value
        def chat(*args):
            self.calls.append('qwen')
            return {'verdict': 'review', 'findings': ['Run the acceptance test.']}
        self.config = {'repo': str(self.repo), 'output_root': str(self.repo.parent/'evidence'),
                       'codex': sys.executable}
        self.coordinator = c.Coordinator(self.config, coder, chat)

    def admit(self):
        self.coordinator.admit('test-1', 'Return 42', ['example.py'])

    def claimed(self):
        self.admit()
        item = self.coordinator.claim()
        return item['task_id'], item['claim_token']

    def test_real_git_two_coder_pipeline_retains_source_and_hashes(self):
        task, token = self.claimed()
        self.coordinator.submit(task, token, self.value)
        result = self.coordinator.advance(task, token)
        self.assertEqual(self.calls, ['codex', 'qwen'])
        self.assertEqual(result['state'], 'human_review_required')
        self.assertFalse(result['source_writes'])
        self.assertEqual(result['gemini_sha256'], c.digest(self.value))
        self.assertEqual((self.repo/'example.py').read_text(), 'def answer():\n    return 41\n')
        for owner in ('codex', 'gemini'):
            self.assertIn('+    return 42', (self.coordinator.root/task/(owner+'.patch')).read_text())
            self.assertEqual((self.coordinator.root/task/owner/'example.py').read_text(), self.value['changes'][0]['content'])
        restored = c.Coordinator(self.config)
        self.assertEqual(restored.status()['tasks'][0]['state'], 'human_review_required')
        self.assertEqual(restored.status()['tasks'][0]['result'], result)
        with self.assertRaises(c.agent.AgentError):
            restored.advance(task, token)
        restored.close(task, 'Reviewed fixture artifacts; no source publication.')
        self.assertEqual(restored.status()['tasks'][0]['result'], result)
        restored.admit('test-2', 'Next task', ['example.py'])
        self.assertIn('claim_token', restored.claim())

    def test_concurrent_claims_have_single_owner(self):
        self.admit()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.coordinator.claim(), range(2)))
        self.assertEqual(sum('claim_token' in r for r in results), 1)
        self.assertEqual(sum(r.get('state') == 'no_queued_task' for r in results), 1)

    def test_duplicate_admission_and_replay_denied(self):
        task, token = self.claimed()
        with self.assertRaises(c.agent.AgentError):
            self.admit()
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.submit(task, 'bad', self.value)
        self.coordinator.submit(task, token, self.value)
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.submit(task, token, self.value)
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.admit('test-2', 'Another task', ['example.py'])

    def test_source_staleness_denied_before_provider(self):
        task, token = self.claimed()
        self.coordinator.submit(task, token, self.value)
        (self.repo/'example.py').write_text('changed')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.advance(task, token)
        self.assertEqual(self.calls, [])

    def test_remote_advance_denied(self):
        self.command('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                     'commit', '--allow-empty', '-m', 'advance')
        self.command('push', 'origin', 'HEAD:Dev')
        self.command('reset', '--hard', 'HEAD~1')
        with self.assertRaises(c.agent.AgentError):
            self.admit()

    def test_paths_schema_and_scope_denied(self):
        for paths in (['../private.py'], ['creds/key.json'], ['new.py'], ['.env'], ['example.py']*2):
            with self.assertRaises(c.agent.AgentError):
                self.coordinator.admit('bad', 'Read', paths)
        task, token = self.claimed()
        for value in ({}, {**self.value, 'command': 'echo bad'},
                      {**self.value, 'changes': [{'path': '../outside.py', 'content': 'x'}]}):
            with self.assertRaises(c.agent.AgentError):
                self.coordinator.submit(task, token, value)

    def test_crash_retains_claim_no_retry(self):
        task, token = self.claimed()
        self.coordinator.submit(task, token, self.value)
        def failure(*args):
            raise RuntimeError('private failure')
        self.coordinator.coder = failure
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.advance(task, token)
        self.assertEqual(self.coordinator.status()['tasks'][0]['state'], 'blocked')
        self.assertNotIn('private failure', json.dumps(self.coordinator.status()))
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.advance(task, token)
        self.assertEqual(self.coordinator.claim()['state'], 'no_queued_task')

    def test_operator_can_close_stale_preinference_but_not_running(self):
        task, token = self.claimed()
        (self.repo/'example.py').write_text('changed')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.submit(task, token, self.value)
        self.coordinator.close(task, 'Source changed; no inference began; cancel old packet.')
        self.command('checkout', '--', 'example.py')
        self.coordinator.admit('replacement', 'Return 42', ['example.py'])
        item = self.coordinator.claim()
        with self.coordinator.connect() as db:
            db.execute('UPDATE tasks SET state="running" WHERE id="replacement"')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.close(item['task_id'], 'Do not release uncertain work')

    def test_stalled_cli_input_and_logs_have_wall_clock_deadline(self):
        directory = self.coordinator.root/'deadline-test'
        directory.mkdir()
        launch = subprocess.Popen
        def stalled(command, **kwargs):
            self.assertIn('--strict-config', command)
            self.assertIn('forced_login_method="chatgpt"', command)
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            self.assertNotIn('OPENAI_BASE_URL', kwargs['env'])
            return launch([sys.executable, '-c', 'import time; time.sleep(30)'], **kwargs)
        started = time.monotonic()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-only', 'OPENAI_BASE_URL': 'https://example.invalid'}), \
                patch.object(c.subprocess, 'Popen', side_effect=stalled), patch.object(c, 'CODEX_TIMEOUT', 0.2):
            with self.assertRaisesRegex(c.agent.AgentError, 'deadline exceeded'):
                c.codex_candidate(sys.executable, 'x'*65536, directory)
        self.assertLess(time.monotonic()-started, 5)

    def test_codex_optional_routing_keeps_strict_cli_boundary(self):
        directory = self.coordinator.root/'routing-test'
        directory.mkdir()
        def capture(command, **kwargs):
            self.assertEqual(command[command.index('-m')+1], 'gpt-6-luna')
            self.assertIn('model_reasoning_effort="low"', command)
            self.assertIn('--strict-config', command)
            self.assertIn('forced_login_method="chatgpt"', command)
            raise RuntimeError('Captured command without inference')
        with patch.object(c.subprocess, 'Popen', side_effect=capture):
            with self.assertRaisesRegex(RuntimeError, 'Captured command'):
                c.codex_candidate(sys.executable, 'Synthetic probe', directory,
                                  model='gpt-6-luna', effort='low')
        for kwargs in ({'model': 'arbitrary-provider'}, {'effort': 'unbounded'}):
            with patch.object(c.subprocess, 'Popen') as launch:
                with self.assertRaises(c.agent.AgentError):
                    c.codex_candidate(sys.executable, 'Synthetic probe', directory, **kwargs)
                launch.assert_not_called()

    def test_codex_uses_platform_home_without_inherited_api_configuration(self):
        directory = self.coordinator.root/'portable-home-test'
        directory.mkdir()
        safe_home = self.repo.parent/'operator-home'
        def capture(command, **kwargs):
            self.assertEqual(kwargs['env']['CODEX_HOME'], str(safe_home/'.codex'))
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            self.assertNotIn('CODEX_HOME_OVERRIDE', kwargs['env'])
            raise RuntimeError('Captured portable environment')
        environment={k:v for k,v in os.environ.items() if k not in ('USERPROFILE','CODEX_HOME')}
        environment.update(OPENAI_API_KEY='synthetic-only',CODEX_HOME_OVERRIDE='untrusted')
        with patch.dict(os.environ,environment,clear=True),patch.object(c.Path,'home',return_value=safe_home),patch.object(c.subprocess,'Popen',side_effect=capture):
            with self.assertRaisesRegex(RuntimeError,'Captured portable environment'):
                c.codex_candidate(sys.executable,'Synthetic probe',directory)

    def test_run_logs_stop_at_byte_ceiling(self):
        directory = self.coordinator.root/'log-limit-test'
        directory.mkdir()
        launch = subprocess.Popen
        def flood(command, **kwargs):
            return launch([sys.executable, '-c', 'import sys,time; sys.stdout.buffer.write(b"x"*2000000); sys.stdout.flush(); time.sleep(30)'], **kwargs)
        with patch.object(c.subprocess, 'Popen', side_effect=flood), patch.object(c, 'CODEX_TIMEOUT', 5):
            with self.assertRaises(c.agent.AgentError):
                c.codex_candidate(sys.executable, 'Synthetic probe', directory)
        self.assertLessEqual((directory/'codex-events.jsonl').stat().st_size, 1024*1024)

    def test_protocol_has_only_fixed_tools_and_notifications_cannot_claim(self):
        self.admit()
        bridge = c.Bridge(self.coordinator)
        self.assertIsNone(bridge.handle({'jsonrpc': '2.0', 'method': 'tools/call',
                         'params': {'name': 'claim_next_task'}}))
        bridge.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'})
        reply = bridge.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
        self.assertEqual(len(reply['result']['tools']), 4)
        for name, args in [('admit', {}), ('claim_next_task', {'paths': ['example.py']}), ('shell', {})]:
            with self.assertRaises(c.agent.AgentError):
                bridge.call(name, args)
        with self.assertRaises(c.agent.AgentError):
            bridge.call('claim_next_task', {})
        self.assertIn('claim_token', bridge.call('claim_next_task', {'expected_task_id': 'test-1'}))

    def test_delayed_scheduled_claim_cannot_take_replacement_task(self):
        self.admit()
        self.coordinator.close('test-1', 'Operator cancels prior task before scheduled claim')
        self.coordinator.admit('test-2', 'Replacement task', ['example.py'])
        bridge = c.Bridge(self.coordinator)
        with self.assertRaises(c.agent.AgentError):
            bridge.call('claim_next_task', {'expected_task_id': 'test-1'})
        self.assertEqual(self.coordinator.status()['tasks'][1]['state'], 'queued')
        self.assertEqual(bridge.call('claim_next_task', {'expected_task_id': 'test-2'})['task_id'], 'test-2')


if __name__ == '__main__':
    unittest.main()

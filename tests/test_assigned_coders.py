import concurrent.futures
import json
import threading
import unittest

import test_coder_coordination as fixture
import coder_coordination as c
import coder_schedule as schedule


class AssignedCoderTests(unittest.TestCase):
    command = fixture.CoordinationTests.command

    def setUp(self):
        fixture.CoordinationTests.setUp(self)
        (self.repo/'second.py').write_text('def other():\n    return 1\n')
        self.command('add', 'second.py')
        self.command('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Second independent source')
        self.command('push', '-q', 'origin', 'HEAD:Dev')
        self.paths = ['example.py', 'second.py']

    def admit(self, task, owner, write):
        return self.coordinator.admit(task, 'Bounded assigned subtask', self.paths,
                                      owner=owner, write_paths=[write])

    def test_local_assignment_has_its_own_claim_and_never_enters_cloud_sidecar(self):
        self.admit('local-task','local','example.py')
        self.assertEqual(self.coordinator.claim()['state'],'no_queued_task')
        calls=[]
        def generate(prompt,directory):
            calls.append(prompt)
            return self.value
        result=self.coordinator.run_local('local-task',generate)
        self.assertEqual(result['owner'],'local')
        self.assertEqual(result['state'],'human_review_required')
        self.assertEqual(len(calls),1)
        self.assertEqual(self.calls,[])
        with self.assertRaises(c.agent.AgentError):self.coordinator.run_local('local-task',generate)

    def test_parallel_different_subtasks_with_shared_read_context(self):
        self.admit('codex-task', 'codex', 'example.py')
        self.admit('gemini-task', 'gemini', 'second.py')
        entered, release = threading.Event(), threading.Event()
        def coder(*args):
            self.calls.append('codex')
            entered.set()
            self.assertTrue(release.wait(10))
            return self.value
        self.coordinator.coder = coder
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.coordinator.run_codex, 'codex-task')
            try:
                self.assertTrue(entered.wait(10))
                claim = self.coordinator.claim('gemini-task')
                self.assertEqual(claim['packet']['write_paths'], ['second.py'])
                self.assertEqual(set(claim['packet']['source']['files']), set(self.paths))
                value = {'summary': 'Other return', 'proposal': 'No tests run.',
                         'changes': [{'path': 'second.py', 'content': 'def other():\n    return 2\n'}]}
                self.coordinator.submit('gemini-task', claim['claim_token'], value)
                gemini = self.coordinator.advance('gemini-task', claim['claim_token'])
                self.assertEqual(gemini['owner'], 'gemini')
                self.assertEqual(gemini['candidate_sha256'], c.digest(value))
                self.assertNotIn('codex_sha256', gemini)
            finally:
                release.set()
            codex = future.result()
        self.assertEqual(self.calls, ['codex'])
        self.assertEqual(codex['owner'], 'codex')
        self.assertEqual(codex['candidate_sha256'], c.digest(self.value))
        self.assertEqual([t['state'] for t in self.coordinator.status()['tasks']],
                         ['human_review_required', 'human_review_required'])
        self.assertFalse(c.agent.git(self.repo, 'status', '--porcelain'))
        for task, owner in [('codex-task', 'codex'), ('gemini-task', 'gemini')]:
            saved = json.loads((self.coordinator.root/task/'result.json').read_text())
            self.assertEqual(saved['owner'], owner)
            self.assertTrue((self.coordinator.root/task/(owner+'.json')).is_file())
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.run_codex('codex-task')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.advance('gemini-task', claim['claim_token'])

    def test_same_coder_overlap_and_legacy_exclusive(self):
        self.admit('gemini-task', 'gemini', 'example.py')
        for owner, path in [('gemini', 'second.py'), ('codex', 'example.py'), ('dual', 'second.py')]:
            with self.assertRaises(c.agent.AgentError):
                self.admit('conflict', owner, path)
        self.admit('codex-task', 'codex', 'second.py')
        self.assertEqual(len(self.coordinator.status()['tasks']), 2)

    def test_atomic_competing_admissions_reserve_one_coder(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            def attempt(i):
                try:
                    self.admit('race-'+str(i), 'codex', self.paths[i])
                    return True
                except c.agent.AgentError:
                    return False
            self.assertEqual(sum(pool.map(attempt, range(2))), 1)

    def test_codex_cannot_be_claimed_or_started_through_mcp(self):
        self.admit('codex-task', 'codex', 'example.py')
        self.assertEqual(self.coordinator.claim('codex-task'), {'state': 'no_queued_task'})
        with self.assertRaises(c.agent.AgentError):
            c.Bridge(self.coordinator).call('run_codex', {'task_id': 'codex-task'})
        self.assertEqual(self.coordinator.status()['tasks'][0]['state'], 'queued')
        self.assertEqual(self.calls, [])

    def test_read_only_context_changes_rejected_for_both_owners(self):
        self.admit('gemini-task', 'gemini', 'second.py')
        claim = self.coordinator.claim('gemini-task')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.submit('gemini-task', claim['claim_token'], self.value)
        self.coordinator.close('gemini-task', 'Cancel fixture without any source changes')
        self.admit('codex-task', 'codex', 'second.py')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.run_codex('codex-task')
        self.assertEqual(self.coordinator.status()['tasks'][1]['state'], 'blocked')
        self.assertEqual(self.calls, ['codex'])

    def test_invalid_owner_and_write_scope_denied(self):
        for owner, paths in [('bad', ['example.py']), ('codex', []),
                             ('codex', ['missing.py']), ('codex', ['example.py', 'example.py'])]:
            with self.assertRaises(c.agent.AgentError):
                self.coordinator.admit('invalid', 'Synthetic task', self.paths, owner=owner, write_paths=paths)
        self.assertEqual(self.coordinator.status()['tasks'], [])

    def test_codex_failure_keeps_claim_and_blocks_same_owner_repair(self):
        self.admit('codex-task', 'codex', 'example.py')
        def fail(*args):
            self.calls.append('codex')
            raise RuntimeError('Private provider failure')
        self.coordinator.coder = fail
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.run_codex('codex-task')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.run_codex('codex-task')
        with self.assertRaises(c.agent.AgentError):
            self.admit('repair', 'codex', 'example.py')
        self.assertEqual(self.calls, ['codex'])
        self.assertNotIn('Private provider failure', json.dumps(self.coordinator.status()))
        self.admit('gemini-task', 'gemini', 'second.py')
        self.assertEqual(self.coordinator.claim('gemini-task')['task_id'], 'gemini-task')

    def test_scheduler_skips_codex_and_reports_only_assigned_candidate(self):
        self.admit('codex-task', 'codex', 'example.py')
        sent = []
        conversation = '11111111-2222-3333-4444-555555555555'
        self.assertEqual(schedule.tick(self.coordinator, conversation, 'agentapi', lambda *a: sent.append(a))['state'], 'idle')
        self.admit('gemini-task', 'gemini', 'second.py')
        result = schedule.tick(self.coordinator, conversation, 'agentapi', lambda *a: sent.append(a))
        self.assertEqual(result['task_id'], 'gemini-task')
        self.assertIn('owner and candidate hash', sent[0][2])
        self.assertNotIn('both hashes', sent[0][2])
        self.assertEqual(self.calls, [])

    def test_legacy_packet_without_owner_still_excludes_other_admission(self):
        self.coordinator.admit('legacy', 'Legacy duplicate proposal', ['example.py'])
        with self.coordinator.connect() as db:
            packet = json.loads(db.execute('SELECT packet FROM tasks').fetchone()['packet'])
            del packet['owner']
            del packet['write_paths']
            db.execute('UPDATE tasks SET packet=?', (json.dumps(packet),))
        with self.assertRaises(c.agent.AgentError):
            self.admit('assigned', 'codex', 'second.py')
        self.assertEqual(self.coordinator.claim()['task_id'], 'legacy')

    def test_concurrent_codex_runs_cannot_duplicate_provider(self):
        self.admit('codex-task', 'codex', 'example.py')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            def attempt(_):
                try:
                    self.coordinator.run_codex('codex-task')
                    return True
                except c.agent.AgentError:
                    return False
            self.assertEqual(sum(pool.map(attempt, range(2))), 1)
        self.assertEqual(self.calls, ['codex'])

    def test_assigned_source_stale_stops_before_codex(self):
        self.admit('codex-task', 'codex', 'example.py')
        (self.repo/'second.py').write_text('dirty context')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.run_codex('codex-task')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.coordinator.status()['tasks'][0]['state'], 'blocked')

    def test_cli_gemini_never_claimed_by_mcp_or_scheduler(self):
        self.coordinator.admit('cli-gemini', 'Synthetic CLI task', self.paths,
                               owner='gemini', write_paths=['example.py'], transport='cli')
        self.assertEqual(self.coordinator.claim(), {'state':'no_queued_task'})
        with self.assertRaises(c.agent.AgentError):
            c.Bridge(self.coordinator).call('claim_next_task', {'expected_task_id':'cli-gemini'})
        sent=[]
        result=schedule.tick(self.coordinator,'11111111-2222-3333-4444-555555555555',
                             'agentapi',lambda *a:sent.append(a))
        self.assertEqual(result['state'],'idle')
        self.assertEqual(sent,[])
        self.assertEqual(self.coordinator.status()['tasks'][0]['state'],'queued')
        self.assertEqual(self.coordinator.status()['tasks'][0]['transport'],'cli')

    def test_cli_gemini_saves_only_own_candidate_no_codex_or_qwen(self):
        self.coordinator.admit('cli-gemini', 'Synthetic CLI task', self.paths,
                               owner='gemini', write_paths=['example.py'], transport='cli')
        def generate(prompt,directory):
            self.calls.append('gemini-cli')
            packet=json.loads(prompt.split('Task packet: ',1)[1])
            self.assertEqual(packet['transport'],'cli')
            self.assertEqual(packet['write_paths'],['example.py'])
            self.assertEqual(set(packet['source']['files']),set(self.paths))
            self.assertEqual(directory,self.coordinator.root/'cli-gemini')
            return self.value
        result=self.coordinator.run_gemini('cli-gemini',generate)
        self.assertEqual(self.calls,['gemini-cli'])
        self.assertEqual(result['owner'],'gemini')
        self.assertEqual(result['transport'],'cli')
        self.assertEqual(result['candidate_sha256'],c.digest(self.value))
        self.assertNotIn('codex_sha256',result)
        self.assertFalse(c.agent.git(self.repo,'status','--porcelain'))
        self.assertTrue((self.coordinator.root/'cli-gemini'/'gemini.json').is_file())
        with self.assertRaises(c.agent.AgentError):self.coordinator.run_gemini('cli-gemini',generate)
        self.assertEqual(self.calls,['gemini-cli'])

    def test_cli_gemini_ambiguous_failure_retains_claim_without_fallback(self):
        self.coordinator.admit('cli-gemini','Synthetic CLI task',self.paths,
                               owner='gemini',write_paths=['example.py'],transport='cli')
        def fail(*args):
            self.calls.append('gemini-cli')
            raise TimeoutError('Unknown provider completion')
        with self.assertRaises(c.agent.AgentError):self.coordinator.run_gemini('cli-gemini',fail)
        with self.assertRaises(c.agent.AgentError):self.coordinator.run_gemini('cli-gemini',fail)
        self.assertEqual(self.coordinator.status()['tasks'][0]['state'],'blocked')
        self.assertEqual(self.calls,['gemini-cli'])
        self.assertEqual(self.coordinator.claim(),{'state':'no_queued_task'})

    def test_oversized_summary_recovers_saved_candidate_without_model_replay(self):
        self.coordinator.admit('cli-gemini','Synthetic CLI task',self.paths,
                               owner='gemini',write_paths=['example.py'],transport='cli')
        oversized={**self.value,'summary':'Confidence: 9/10. '+('evidence '*80)}
        original=json.loads(json.dumps(oversized))
        def generate(prompt,directory):
            self.calls.append('gemini-cli')
            (directory/'antigravity-result.json').write_text(json.dumps({
                'candidate':oversized,'route':{'model':'synthetic'},'usage':{}}))
            return oversized
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.run_gemini('cli-gemini',generate)
        result=self.coordinator.recover_assigned(
            'cli-gemini','Normalize the retained oversized summary and run independent acceptance')
        self.assertEqual(self.calls,['gemini-cli'])
        self.assertFalse(result['model_replayed'])
        self.assertEqual(result['operator_correction'],'summary_shortened_to_contract')
        self.assertEqual(result['route']['model'],'synthetic')
        saved=json.loads((self.coordinator.root/'cli-gemini'/'gemini.json').read_text())
        self.assertLessEqual(len(saved['summary']),512)
        self.assertEqual(saved['proposal'],original['proposal'])
        self.assertEqual(saved['changes'],original['changes'])
        receipt=json.loads((self.coordinator.root/'cli-gemini'/'antigravity-result.json').read_text())
        self.assertEqual(receipt['candidate'],original)
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.recover_assigned('cli-gemini','A duplicate recovery must be rejected')

    def test_blocked_task_releases_coder_but_keeps_write_path_claim(self):
        self.admit('codex-task','codex','example.py')
        self.coordinator.coder=lambda *args: (_ for _ in ()).throw(RuntimeError('failure'))
        with self.assertRaises(c.agent.AgentError):self.coordinator.run_codex('codex-task')
        self.admit('independent','codex','second.py')
        with self.assertRaises(c.agent.AgentError):
            self.coordinator.admit('overlap','Another task',self.paths,
                                   owner='gemini',write_paths=['example.py'])
        self.assertEqual([x['state'] for x in self.coordinator.status()['tasks']],
                         ['blocked','queued'])

    def test_cli_runner_cannot_take_sidecar_or_other_coder_task(self):
        self.admit('sidecar-gemini','gemini','example.py')
        self.admit('codex-task','codex','second.py')
        for task in ('sidecar-gemini','codex-task'):
            with self.assertRaises(c.agent.AgentError):
                self.coordinator.run_gemini(task,lambda *a:self.calls.append('bad'))
        self.assertEqual(self.calls,[])
        self.assertEqual([r['state'] for r in self.coordinator.status()['tasks']],['queued','queued'])
        for owner,transport in [('codex','cli'),('dual','cli'),('gemini','unknown')]:
            with self.assertRaises(c.agent.AgentError):
                self.coordinator.admit('invalid','Synthetic task',self.paths,owner=owner,transport=transport)

    def test_concurrent_cli_gemini_runs_invoke_provider_once(self):
        self.coordinator.admit('cli-gemini','Synthetic CLI task',self.paths,
                               owner='gemini',write_paths=['example.py'],transport='cli')
        def generate(*args):
            self.calls.append('gemini-cli')
            return self.value
        def attempt(_):
            try:
                self.coordinator.run_gemini('cli-gemini',generate)
                return True
            except c.agent.AgentError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(attempt,range(2))),1)
        self.assertEqual(self.calls,['gemini-cli'])

    def test_gemini_cli_and_codex_generate_concurrently_for_disjoint_files(self):
        self.coordinator.admit('cli-gemini','Synthetic CLI task',self.paths,
                               owner='gemini',write_paths=['second.py'],transport='cli')
        self.admit('codex-task','codex','example.py')
        together=threading.Barrier(2,timeout=10)
        def gemini(prompt,directory):
            self.calls.append('gemini-cli')
            together.wait()
            return {'summary':'Second file','proposal':'No tests run.',
                    'changes':[{'path':'second.py','content':'def other():\n    return 2\n'}]}
        def codex(*args):
            self.calls.append('codex')
            together.wait()
            return self.value
        self.coordinator.coder=codex
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.coordinator.run_gemini,'cli-gemini',gemini)
            b=pool.submit(self.coordinator.run_codex,'codex-task')
            self.assertEqual(a.result()['owner'],'gemini')
            self.assertEqual(b.result()['owner'],'codex')
        self.assertCountEqual(self.calls,['gemini-cli','codex'])
        self.assertFalse(c.agent.git(self.repo,'status','--porcelain'))

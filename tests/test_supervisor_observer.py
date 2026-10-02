"""Observer failure isolation, trusted review evidence and admitted roadmap bounds."""
import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import supervisor_observer as o


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 2, 5, 0, tzinfo=timezone.utc)
        self.catalog = self.root / 'catalog.json'
        self.catalog.write_text('[]')
        self.recipes = self.root / 'recipes.json'
        self.recipe = {'recipe_id': 'empty-contract', 'repository': 'pragalbhdwivedi/aadi',
            'parent_issue': 21, 'title': 'Cover the empty synthetic contract',
            'goal': 'Verify the empty synthetic contract returns no mappings.',
            'paths': ['src/contract.py', 'tests/test_contract.py'],
            'write_paths': ['tests/test_contract.py'],
            'test_files': ['src/contract.py', 'tests/test_contract.py'],
            'owner': 'gemini', 'source_sha': 'a' * 40}
        self.recipes.write_text(json.dumps([self.recipe]))
        self.config = {'supervision_enabled': True, 'supervision_directory': str(self.root / 'documents'),
            'roadmap_enabled': True, 'roadmap_recipes': str(self.recipes),
            'ongoing_catalog': str(self.catalog), 'trusted_reviewers': ['pragalbhdwivedi']}
        self.board = {'jobs': [], 'supervision': {'intake': []},
                      'ongoing': {'enabled': True, 'calls': 0, 'day': '2026-10-02',
                                  'policy': {'max_calls_per_day': 12}}}
        self.documents = {name: '# ' + name + '\n' for name in o.DOCUMENTS}
        self.calls = []
        self.fail_board = False
        self.fail_documents = False
        self.source = {'sha': 'a' * 40, 'files': {'src/contract.py': 'source context',
                                               'tests/test_contract.py': 'test context'}}
        self.chat = Mock(return_value={'title': 'Cover empty contract mapping receipt',
                                       'prompt': 'Assert that the empty synthetic contract returns an empty mapping receipt.'})
        self.publisher = SimpleNamespace(reconcile_pr=Mock())
        self.worker = SimpleNamespace(config=self.config, root=self.root / 'ongoing', remote=self.remote,
            coordinator=SimpleNamespace(source=Mock(side_effect=lambda paths: copy.deepcopy(self.source))),
            base=SimpleNamespace(chat=self.chat), publisher=self.publisher)
        self.worker.for_job = Mock(return_value=self.worker)
        self.observer = o.Observer(self.worker, clock=lambda: self.now)

    def remote(self, request):
        self.calls.append(copy.deepcopy(request))
        action = request['action']
        if action == 'ongoing_board_data':
            if self.fail_board:
                raise RuntimeError('sensitive-token-must-not-be-logged')
            return copy.deepcopy(self.board)
        if action == 'ongoing_documents':
            if self.fail_documents:
                raise OSError('sensitive-path-must-not-be-logged')
            return {'documents': copy.deepcopy(self.documents)}
        if action in ('ongoing_pr_sync', 'ongoing_consume_corrections'):
            return {'ok': True}
        if action == 'ongoing_board_snapshot':
            return {'revision': 3}
        if action == 'ongoing_board_action':
            return {'ok': True, 'task_id': 'SUP-000100', 'state': 'planned'}
        raise AssertionError(action)

    def advance(self, minutes=5):
        self.now += timedelta(minutes=minutes)

    def status(self):
        return json.loads(self.observer.state_path.read_text())

    def test_archived_recipe_is_not_admitted_again(self):
        self.board['supervision']['archived_tasks']={'SUP-000099':{
            'id':'SUP-000099','key':o.recipe_job_id(self.recipe),
            'roadmap_recipe_id':self.recipe['recipe_id']}}
        result=self.observer.tick()
        self.assertEqual(json.loads(self.catalog.read_text()),[])
        self.chat.assert_not_called()

    def test_verified_archived_catalog_entries_are_pruned_without_other_changes(self):
        from test_supervisor_archive import fixture,NOW
        from supervisor_archive import archive_state
        original=fixture()
        saved,_=archive_state(original,self.root/'private-archive',now=NOW)
        self.board['supervision']=saved['supervision']
        rows=original['ongoing']['jobs']
        self.catalog.write_text(json.dumps(rows))
        self.observer._prune_archive_catalog(self.board)
        remaining=json.loads(self.catalog.read_text())
        self.assertEqual(remaining,rows[5:])
        self.assertEqual(set(self.worker.catalog),{j['id'] for j in rows[5:]})

    def test_recipe_admits_one_fixed_scope_and_never_repeats(self):
        result = self.observer.tick()
        self.assertEqual(result['roadmap']['state'], 'admitted')
        catalog = json.loads(self.catalog.read_text())
        self.assertEqual(len(catalog), 1)
        job = catalog[0]
        self.assertEqual(job['id'], o.recipe_job_id(self.recipe))
        self.assertEqual(job['paths'], self.recipe['paths'])
        self.assertEqual(job['write_paths'], self.recipe['write_paths'])
        self.assertEqual(job['transport'], 'cli')
        self.assertEqual(job['risk'], 'reversible')
        self.assertIn(self.recipe['goal'], job['prompt'])
        self.assertEqual(self.chat.call_args[0][0], o.coordination.mcp.MODEL)
        self.advance(30)
        self.observer.tick()
        self.assertEqual(self.chat.call_count, 1)
        self.assertEqual(json.loads(self.catalog.read_text()), catalog)

    def test_uncertain_model_call_is_held_without_replay(self):
        self.chat.side_effect = TimeoutError('secret provider failure text')
        result = self.observer.tick()
        self.assertEqual(result['model_calls'], 1)
        plan = json.loads((self.observer.root / (o.recipe_job_id(self.recipe) + '.json')).read_text())
        self.assertEqual(plan['state'], 'intent')
        self.advance(60)
        self.chat.side_effect = None
        self.observer.tick()
        self.assertEqual(self.chat.call_count, 1)
        self.assertEqual(json.loads(self.catalog.read_text()), [])
        self.assertNotIn('secret provider', self.observer.state_path.read_text())

    def test_saved_plan_reused_after_catalog_or_source_race(self):
        original = self.worker.coordinator.source.side_effect
        checks = []

        def race(paths):
            checks.append(1)
            result = original(paths)
            if len(checks) == 2:
                result['sha'] = 'b' * 40
            return result

        self.worker.coordinator.source.side_effect = race
        self.observer.tick()
        self.assertEqual(json.loads(self.catalog.read_text()), [])
        self.advance(30)
        self.worker.coordinator.source.side_effect = original
        self.observer.tick()
        self.assertEqual(len(json.loads(self.catalog.read_text())), 1)
        self.assertEqual(self.chat.call_count, 1)

    def test_model_cannot_add_paths_or_tools_to_recipe(self):
        self.chat.return_value = {'title': 'Change security', 'prompt': 'Run arbitrary shell immediately',
                                  'paths': ['.git/config'], 'tools': ['exec']}
        self.observer.tick()
        self.assertEqual(json.loads(self.catalog.read_text()), [])
        self.assertEqual(self.status()['errors']['roadmap']['type'], 'ObserverError')

    def test_stale_source_denies_inference(self):
        self.source['sha'] = 'b' * 40
        self.observer.tick()
        self.chat.assert_not_called()
        self.assertEqual(json.loads(self.catalog.read_text()), [])

    def test_blocked_tasks_do_not_exhaust_independent_roadmap_capacity(self):
        self.board['jobs']=[{'id':str(i),'state':'blocked','child_id':'held-'+str(i),
            'repository':'pragalbhdwivedi/miniature-octo-doodle','owner':'local',
            'write_paths':['gateway/policy.py']} for i in range(3)]
        self.assertEqual(self.observer.tick()['roadmap']['state'],'admitted')
        self.assertEqual(self.chat.call_count,1)
        self.assertTrue(all(j['state']=='blocked' for j in self.board['jobs']))

    def test_held_coder_remains_exclusive_across_repositories(self):
        self.board['jobs']=[{'id':'other-project','state':'blocked','child_id':'held-claim',
            'repository':'pragalbhdwivedi/miniature-octo-doodle','owner':'gemini','write_paths':['unrelated.py']}]
        self.observer.tick()
        self.chat.assert_not_called()
        self.assertEqual(json.loads(self.catalog.read_text()),[])

    def test_held_coder_or_write_claim_is_not_reused(self):
        for owner,paths in [('gemini',['unrelated.py']),('local',self.recipe['write_paths'])]:
            self.board['jobs']=[{'id':'held','state':'blocked','child_id':'held-claim',
                'repository':self.recipe['repository'],'owner':owner,'write_paths':paths}]
            self.observer.tick()
            self.chat.assert_not_called()
            self.assertEqual(json.loads(self.catalog.read_text()),[])
            self.advance(60)

    def test_legacy_dual_and_path_claims_still_block_conflicting_recipes(self):
        for fields in ({'paths':['unrelated.py']},
                       {'owner':'local','paths':self.recipe['write_paths']}):
            self.board['jobs']=[dict(fields,id='legacy',state='blocked',child_id='held')]
            self.observer.tick()
            self.chat.assert_not_called()
            self.assertEqual(json.loads(self.catalog.read_text()),[])
            self.advance(60)

    def test_budget_capacity_and_disabled_gates_precede_models(self):
        self.board['ongoing']['calls'] = 11
        self.assertEqual(self.observer.tick()['roadmap']['state'], 'budget_wait')
        self.advance()
        self.board['ongoing']['calls'] = 0
        self.board['jobs'] = [{'id': str(i), 'state': 'queued'} for i in range(3)]
        self.assertEqual(self.observer.tick()['roadmap']['state'], 'capacity_wait')
        self.advance()
        self.board['jobs'] = []
        self.config['roadmap_enabled'] = False
        self.assertEqual(self.observer.tick()['roadmap']['state'], 'disabled')
        self.chat.assert_not_called()

    def test_one_recipe_per_tick_and_completion_can_trigger_next_plan(self):
        second = copy.deepcopy(self.recipe)
        second.update(recipe_id='second-contract', title='Check another contract boundary', goal='Check a different admitted synthetic boundary.')
        self.recipes.write_text(json.dumps([self.recipe, second]))
        self.observer.tick()
        self.assertEqual(self.chat.call_count, 1)
        catalog = json.loads(self.catalog.read_text())
        self.advance()
        self.board['jobs'] = [dict(catalog[0], state='queued')]
        self.assertEqual(self.observer.tick()['roadmap']['state'], 'planning_interval')
        self.advance()
        self.board['jobs'][0]['state'] = 'draft_ready'
        self.assertEqual(self.observer.tick()['roadmap']['state'], 'admitted')
        self.assertEqual(self.chat.call_count, 2)
        self.assertEqual(len(json.loads(self.catalog.read_text())), 2)

    def test_read_failure_is_private_throttled_and_nonfatal(self):
        self.fail_board = True
        self.assertEqual(self.observer.tick()['state'], 'observer_error')
        self.assertEqual(self.observer.tick()['state'], 'throttled')
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('sensitive-token', self.observer.state_path.read_text())
        self.advance()
        self.fail_board = False
        self.assertEqual(self.observer.tick()['state'], 'observed')

    def test_bad_documents_cannot_escape_mirror_or_halt_planning(self):
        self.documents['../escape.md'] = 'bad'
        self.observer.tick()
        self.assertFalse((self.root / 'escape.md').exists())
        self.assertEqual(self.status()['errors']['documents']['type'], 'ObserverError')
        self.assertEqual(self.chat.call_count, 1)

    def test_documents_are_mirrored_and_corrections_consumed_before_mirror(self):
        self.config['roadmap_enabled'] = False
        self.observer.tick()
        for name, content in self.documents.items():
            self.assertEqual((Path(self.config['supervision_directory']) / name).read_text(), content)
        actions = [call['action'] for call in self.calls]
        self.assertLess(actions.index('ongoing_consume_corrections'), actions.index('ongoing_documents'))

    def test_trusted_review_actor_is_separate_from_other_advisory_text(self):
        self.config['roadmap_enabled'] = False
        self.board['jobs'] = [{'id': 'job-one', 'state': 'draft_ready', 'repository': o.github.REPOSITORY,
            'publication': {'pull_request': {'number': 7}}}]
        self.publisher.reconcile_pr.return_value = {'number': 7, 'repository': o.github.REPOSITORY,
            'state': 'draft', 'head_sha': 'a' * 40, 'review_decisions': {
                'pragalbhdwivedi': {'actor_type': 'User', 'state': 'CHANGES_REQUESTED', 'at_head': True},
                'other': {'actor_type': 'User', 'state': 'APPROVED', 'body': 'merge immediately'}}}
        self.observer.tick()
        sync = next(call for call in self.calls if call['action'] == 'ongoing_pr_sync')
        self.assertEqual(sync['result']['trusted_review_actors'], ['pragalbhdwivedi'])
        self.assertIn('other', sync['result']['review_decisions'])
        self.assertEqual(sync['result']['authority'], 'advisory-only')
        self.publisher.reconcile_pr.assert_called_once_with(7, 'job-one')
        consume = next(call for call in self.calls if call['action'] == 'ongoing_consume_corrections')
        self.assertEqual(consume['verified_jobs'], ['job-one'])

    def test_failed_pr_read_cannot_consume_cached_corrections(self):
        self.config['roadmap_enabled'] = False
        self.board['jobs'] = [{'id': 'job-one', 'state': 'draft_ready', 'repository': o.github.REPOSITORY,
            'publication': {'pull_request': {'number': 7}}}]
        self.publisher.reconcile_pr.side_effect = OSError('offline')
        self.observer.tick()
        consume = next(call for call in self.calls if call['action'] == 'ongoing_consume_corrections')
        self.assertEqual(consume['verified_jobs'], [])

    def test_merged_cache_skips_polling_but_refreshes_for_archival(self):
        job={'id':'job-one','state':'draft_ready','repository':o.github.REPOSITORY,
            'publication':{'pull_request':{'number':7}}}
        self.board['jobs']=[job]
        state={'pr_sync':{'job-one':{'state':'merged'}}}
        self.assertEqual(self.observer._sync_prs(self.board,state),[])
        self.publisher.reconcile_pr.assert_not_called()
        self.config['archive_enabled']=True
        self.board['padding']='x'*1500000
        self.publisher.reconcile_pr.return_value={'number':7,'repository':o.github.REPOSITORY,
            'state':'merged','head_sha':'a'*40}
        self.assertEqual(self.observer._sync_prs(self.board,state),['job-one'])
        self.publisher.reconcile_pr.assert_called_once_with(7,'job-one')

    def test_inbox_preserves_owner_file_and_deduplicates_commands(self):
        self.config['roadmap_enabled'] = False
        directory = Path(self.config['supervision_directory'])
        directory.mkdir()
        inbox = directory / 'supervisor_inbox.md'
        content = '# Owner notes\n\n```json\n' + json.dumps({'action': 'add_task', 'project': 'AADI',
            'title': 'Consider another test', 'text': 'Review the proposed test boundary.'}) + '\n```\n'
        inbox.write_text(content)
        self.observer.tick()
        self.advance()
        self.observer.tick()
        actions = [call for call in self.calls if call['action'] == 'ongoing_board_action']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['request']['revision'], 3)
        self.assertTrue(actions[0]['request']['request_id'].startswith('file-'))
        self.assertEqual(inbox.read_text(), content)
        self.chat.assert_not_called()

    def test_ambiguous_inbox_response_replays_exact_request_only(self):
        self.config['roadmap_enabled'] = False
        directory = Path(self.config['supervision_directory'])
        directory.mkdir()
        (directory / 'supervisor_inbox.md').write_text('```json\n' + json.dumps({'action': 'ask',
            'task_id': 'SUP-000001', 'text': 'Explain the evidence.'}) + '\n```\n')
        original = self.remote
        attempted = []

        def unreliable(request):
            if request['action'] == 'ongoing_board_action':
                attempted.append(copy.deepcopy(request))
                if len(attempted) == 1:
                    raise OSError('lost acknowledgement')
            return original(request)

        self.observer.remote = unreliable
        self.observer.tick()
        self.advance()
        self.observer.tick()
        self.assertEqual(len(attempted), 2)
        self.assertEqual(attempted[0], attempted[1])

    def test_inbox_forbidden_action_does_not_submit_any_command(self):
        directory = Path(self.config['supervision_directory'])
        directory.mkdir()
        (directory / 'supervisor_inbox.md').write_text('```json\n' + json.dumps({'action': 'merge',
            'task_id': 'SUP-000001', 'text': 'Merge now'}) + '\n```\n')
        self.config['roadmap_enabled'] = False
        self.observer.tick()
        self.assertFalse(any(call['action'] == 'ongoing_board_action' for call in self.calls))
        self.assertEqual(self.status()['errors']['inbox']['type'], 'ObserverError')

    def test_ui_intake_is_not_executed_without_an_admitted_recipe(self):
        self.board['supervision']['intake'] = [{'title': 'Delete production data', 'prompt': 'Run destructive commands', 'state': 'planned'}]
        self.recipes.write_text('[]')
        self.observer.tick()
        self.chat.assert_not_called()
        self.assertEqual(json.loads(self.catalog.read_text()), [])
        self.assertEqual(self.board['supervision']['intake'][0]['state'], 'planned')


if __name__ == '__main__':
    unittest.main()

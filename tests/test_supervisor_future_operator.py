"""Offline operator planning: durable ownership, saved receipts and no coding authority."""
import copy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import supervisor_board as board
import supervisor_future as future
import supervisor_future_operator as operator
import supervisor_future_runtime as runtime


def proposal():
    return {'project': 'GatewayAI', 'title': 'Validate missing route names',
            'prompt': 'Reject a missing route name with a stable error and add a regression test.',
            'scope_id': 'gateway-routes', 'priority': 3, 'evidence': ['src/app.py'],
            'acceptance': ['An empty route has a stable validation error.'],
            'dependencies': [], 'risk': 'routine'}


class FutureOperatorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = datetime.now(timezone.utc)
        self.s = {'ongoing': {'enabled': True, 'jobs': [], 'lease': None, 'calls': 0,
                             'day': self.now.date().isoformat(), 'policy': {'max_calls_per_day': 10}},
                  'questions': [], 'outbox': []}
        board.ensure(self.s, self.now)
        future.request_generation(self.s, 'manual-one', self.now)
        self.calls = []
        self.fail_finish = None
        self.state = {}
        scope = {'repository': 'pragalbhdwivedi/miniature-octo-doodle', 'owner': 'gemini',
                 'paths': ['src/app.py', 'tests/test_app.py'], 'write_paths': ['src/app.py'],
                 'description': 'Bounded source validation'}
        self.profiles = {'gateway-routes': scope}
        self.source = {'sha': 'a' * 40, 'files': {'src/app.py': 'def route(name): return name\n',
                                               'tests/test_app.py': '# immutable tests\n'}}
        self.project = SimpleNamespace(coordinator=SimpleNamespace(source=Mock(return_value=self.source)))
        self.worker = SimpleNamespace(for_job=Mock(return_value=self.project), run=Mock(), code=Mock())
        self.observer = SimpleNamespace(config={'antigravity_cli': 'unused-native'}, root=self.root,
                                        state_path=self.root / 'state.json', remote=self.remote, worker=self.worker)
        self.route = {'model': 'gemini-3.1-pro-low', 'group': 'Gemini Models', 'api_fallback': False}
        self.receipt = {'candidate': {'tasks': [proposal()]}, 'route': self.route,
                        'usage': {'status': 'observed', 'input_tokens': 10}}
        self.scopes = self.patch('admission.scopes', return_value=self.profiles)
        self.refresh = self.patch('admission.refresh_source', return_value=True)
        self.prepare = self.patch('native.prepare', return_value=self.route)
        self.run = self.patch('native.run', side_effect=lambda *a, **k: copy.deepcopy(self.receipt))
        review_patch = patch('supervisor_future_review.review', side_effect=lambda executable, context, proposals, directory, route: {
            'proposals': copy.deepcopy(proposals), 'accepted': list(range(len(proposals))),
            'rejected': [], 'route': {'model': 'independent-review-model'}})
        self.review = review_patch.start()
        self.addCleanup(review_patch.stop)

    def patch(self, name, **kwargs):
        patcher = patch('supervisor_future_operator.' + name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def remote(self, request):
        self.calls.append(copy.deepcopy(request))
        if request['action'] == 'ongoing_board_snapshot':
            return board.snapshot(self.s, self.now)
        if request['action'] == 'ongoing_future_finish' and self.fail_finish == 'before':
            self.fail_finish = None
            raise OSError('Lost request before remote completion')
        result = runtime.rpc(self.s, request)
        if request['action'] == 'ongoing_future_finish' and self.fail_finish == 'after':
            self.fail_finish = None
            raise OSError('Lost response after committed completion')
        return result

    def tick(self):
        return operator.tick(self.observer, {'ongoing': copy.deepcopy(self.s['ongoing']),
                                            'jobs': copy.deepcopy(self.s['ongoing']['jobs'])},
                             self.state, self.now)

    def test_success_records_actual_planner_model_without_coding_authority(self):
        self.tick()
        self.assertEqual(self.s['supervision']['future']['generation']['model'], self.route['model'])
        self.assertEqual(self.s['ongoing']['calls'], 2)
        self.assertEqual(self.s['ongoing']['jobs'], [])
        self.assertEqual(self.s['supervision']['intake'], [])
        self.worker.run.assert_not_called()
        self.worker.code.assert_not_called()
        args, kwargs = self.run.call_args
        self.assertEqual(args[3], 'hard')
        self.assertEqual(kwargs['prepared'], self.route)
        self.assertEqual(kwargs['schema'], operator.SCHEMA)
        self.assertIn(self.source['sha'], args[1])
        self.assertEqual(len(list(self.root.glob('future-*/result.json'))), 1)

    def test_only_independently_accepted_proposals_reach_finish(self):
        self.receipt['candidate']['tasks'].append({**proposal(), 'title': 'Already implemented boolean guard'})
        self.review.side_effect = lambda executable, context, proposals, directory, route: {
            'proposals': [copy.deepcopy(proposals[0])], 'accepted': [0],
            'rejected': [{'index': 1, 'reason': 'Exact type excludes bool already.'}],
            'route': {'model': 'independent-review-model'}}
        self.tick()
        finished = next(r for r in self.calls if r['action'] == 'ongoing_future_finish')
        self.assertEqual(finished['proposals'], [proposal()])
        self.assertEqual(len(self.s['supervision']['future']['tasks']), 1)

    def test_quota_preflight_wait_does_not_claim_or_repeat_before_reset(self):
        reset = (self.now + timedelta(hours=1)).isoformat()
        self.prepare.side_effect = operator.native.QuotaWait(reset)
        self.assertEqual(self.tick()['state'], 'quota_wait')
        self.assertEqual(self.tick()['state'], 'preflight_wait')
        self.assertEqual(self.prepare.call_count, 1)
        self.run.assert_not_called()
        self.assertEqual(self.s['ongoing']['calls'], 0)
        self.assertEqual(self.s['supervision']['future']['generation']['state'], 'pending')

    def test_budget_or_live_lease_denies_model_call(self):
        for field, value in [('calls', 9), ('calls', 10), ('lease', {'stage': 'coding'})]:
            with self.subTest(field=field):
                self.s['ongoing'].update(calls=0, lease=None)
                self.s['ongoing'][field] = value
                self.assertFalse(self.tick()['execute'])
                self.run.assert_not_called()
                self.assertEqual(self.s['supervision']['future']['generation']['state'], 'pending')

    def test_source_busy_holds_before_native_preflight(self):
        self.refresh.return_value = False
        self.assertEqual(self.tick()['state'], 'source_busy')
        self.prepare.assert_not_called()
        self.run.assert_not_called()
        self.assertEqual(self.s['ongoing']['calls'], 0)

    def test_proposal_cannot_cite_test_file_omitted_from_planner_context(self):
        self.receipt['candidate']['tasks'][0]['evidence'] = ['tests/test_app.py']
        self.assertEqual(self.tick()['state'], 'failed_evidence_retained')
        prompt = self.run.call_args.args[1]
        self.assertNotIn('tests/test_app.py', prompt)
        self.assertNotIn('# immutable tests', prompt)
        self.assertEqual(self.s['supervision']['future']['tasks'], [])
        self.assertFalse(list(self.root.glob('future-*/result.json')))
        self.assertFalse(any(r['action'] == 'ongoing_future_finish' for r in self.calls))
        self.tick()
        self.assertEqual(self.run.call_count, 1)

    def test_proposal_cannot_cite_oversized_file_omitted_from_planner_context(self):
        self.source['files']['src/oversized.py'] = '# omitted large source\n' + 'x' * 12001
        self.profiles['gateway-routes']['paths'].append('src/oversized.py')
        self.receipt['candidate']['tasks'][0]['evidence'] = ['src/oversized.py']
        self.assertEqual(self.tick()['state'], 'failed_evidence_retained')
        prompt = self.run.call_args.args[1]
        self.assertNotIn('src/oversized.py', prompt)
        self.assertNotIn('# omitted large source', prompt)
        self.assertEqual(self.s['supervision']['future']['tasks'], [])
        self.assertFalse(list(self.root.glob('future-*/result.json')))
        self.assertFalse(any(r['action'] == 'ongoing_future_finish' for r in self.calls))

    def test_no_visible_writable_source_holds_without_running_ownership(self):
        for files, writable in (({}, ['src/app.py']),
                ({'src/app.py': 'x' * 12001, 'src/helper.py': 'PUBLIC_HELPER = 1\n'}, ['src/app.py']),
                ({'src/helper.py': 'PUBLIC_HELPER = 1\n', 'tests/test_app.py': '# test only\n'}, ['tests/test_app.py'])):
            with self.subTest(writable=writable, paths=list(files)):
                self.source['files'] = files
                self.profiles['gateway-routes'].update(paths=list(files), write_paths=writable)
                self.assertEqual(self.tick()['state'], 'source_busy')
                self.assertEqual(self.s['supervision']['future']['generation']['state'], 'pending')
                self.assertEqual(self.s['ongoing']['calls'], 0)
                self.assertFalse(any(r['action'] == 'ongoing_future_begin' for r in self.calls))
                self.prepare.assert_not_called()
                self.run.assert_not_called()

    def test_pause_and_resume_retain_request_without_implicit_coding(self):
        self.s['ongoing']['enabled'] = False
        self.assertEqual(self.tick()['state'], 'paused')
        self.prepare.assert_not_called()
        self.s['ongoing']['enabled'] = True
        self.tick()
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual(self.s['ongoing']['jobs'], [])

    def test_unknown_scope_evidence_or_authority_fails_without_replay(self):
        self.s['ongoing']['policy']['max_calls_per_day'] = 40
        for change in ({'scope_id': 'host-shell'}, {'evidence': ['private/credentials']},
                       {'project': 'AADI'}, {'dependencies': ['FUT-000001']}, {'risk': 'needs_owner'},
                       {'priority': True}, {'acceptance': []}, {'command': 'execute something'}):
            with self.subTest(change=change):
                # A fresh manual request, not an automatic retry of held evidence.
                request_id = 'manual-' + str(len(self.s['supervision']['future']['requests']) + 1)
                if self.s['supervision']['future']['generation']['state'] == 'pending':
                    future.fail_generation(self.s, 'manual-one', 'Replace test fixture', self.now)
                future.request_generation(self.s, request_id, self.now)
                self.receipt['candidate']['tasks'] = [{**proposal(), **change}]
                self.assertEqual(self.tick()['state'], 'failed_evidence_retained')
                count = self.run.call_count
                self.tick()
                self.assertEqual(self.run.call_count, count)
                self.assertEqual(self.s['supervision']['future']['tasks'], [])
        self.assertFalse(list(self.root.glob('future-*/result.json')))

    def test_uncertain_inference_is_not_retried(self):
        self.run.side_effect = TimeoutError('No confirmed structured response')
        self.assertEqual(self.tick()['state'], 'failed_evidence_retained')
        self.tick()
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual(self.s['ongoing']['calls'], 2)

    def test_running_without_saved_result_never_restarts_native(self):
        runtime.rpc(self.s, {'action': 'ongoing_future_begin', 'request_id': 'manual-one'})
        self.assertEqual(self.tick()['state'], 'running_evidence_retained')
        self.prepare.assert_not_called()
        self.run.assert_not_called()
        self.assertEqual(self.s['ongoing']['calls'], 2)

    def test_existing_native_intent_prevents_duplicate_inference(self):
        directory = self.root / ('future-' + operator.github.digest('manual-one')[:24])
        directory.mkdir()
        (directory / 'antigravity-intent.json').write_text('{}')
        self.assertEqual(self.tick()['state'], 'running_evidence_retained')
        self.prepare.assert_not_called()
        self.run.assert_not_called()

    def test_empty_useful_batch_completes_without_invented_work(self):
        self.receipt['candidate']['tasks'] = []
        self.tick()
        self.assertEqual(self.s['supervision']['future']['generation']['state'], 'completed')
        self.assertEqual(self.s['supervision']['future']['tasks'], [])
        self.assertEqual(self.s['ongoing']['calls'], 2)

    def test_saved_result_recovery_uses_zero_additional_model_calls(self):
        self.fail_finish = 'before'
        with self.assertRaises(OSError):
            self.tick()
        self.assertEqual(self.s['supervision']['future']['generation']['state'], 'running')
        self.assertTrue(list(self.root.glob('future-*/result.json')))
        self.prepare.reset_mock()
        self.run.reset_mock()
        self.tick()
        self.prepare.assert_not_called()
        self.run.assert_not_called()
        self.assertEqual(self.s['supervision']['future']['generation']['state'], 'completed')
        self.assertEqual(self.s['ongoing']['calls'], 2)

    def test_committed_completion_with_lost_response_is_not_new_generation(self):
        self.fail_finish = 'after'
        with self.assertRaises(OSError):
            self.tick()
        self.assertEqual(self.s['supervision']['future']['generation']['state'], 'completed')
        self.prepare.reset_mock()
        self.run.reset_mock()
        self.tick()
        self.prepare.assert_not_called()
        self.run.assert_not_called()
        self.assertEqual(len(self.s['supervision']['future']['tasks']), 1)

    def test_full_prompt_is_bounded_before_claiming_or_spending(self):
        rows = [{**proposal(), 'id': f'FUT-{i:06d}', 'scope_id': 'unregistered',
                 'title': f'{i:03d} ' + 'x' * 176, 'prompt': f'Unique scoped task {i} with regression acceptance.'}
                for i in range(1, 491)]
        future.seed(self.s, rows, self.now)
        try:
            self.tick()
        except ValueError:
            pass
        self.run.assert_not_called()
        self.assertEqual(self.s['ongoing']['calls'], 0)


if __name__ == '__main__':
    unittest.main()

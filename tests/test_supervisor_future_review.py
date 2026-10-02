"""Independent future-task review never rewrites scope or replays inference."""
import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import supervisor_future_review as review


class FutureReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.planner = {'model': 'gemini-pro', 'group': 'Gemini Models'}
        self.route = {'model': 'claude-opus', 'group': 'Claude and GPT models'}
        self.proposals = [{'title': 'Already rejects booleans', 'scope_id': 'public-source'},
                          {'title': 'Validate missing route', 'scope_id': 'public-source'}]
        self.answer = {'candidate': {'accepted': [1], 'rejected': [{'index': 0, 'reason': 'Exact type already excludes bool.'}]},
                       'route': self.route, 'usage': {'input_tokens': 100}}
        self.runner = SimpleNamespace(prepare=Mock(return_value=self.route),
                                      run=Mock(side_effect=lambda *a, **k: copy.deepcopy(self.answer)))
        self.context = 'Full source: def valid(v): return type(v) in (int, float)'

    def run_review(self, directory=None):
        return review.review('unused-native', self.context, self.proposals,
                             directory or self.root, self.planner, runner=self.runner)

    def test_indexes_select_unchanged_proposals_and_record_independent_model(self):
        result = self.run_review()
        self.assertEqual(result['proposals'], [self.proposals[1]])
        self.assertEqual(result['rejected'], self.answer['candidate']['rejected'])
        self.assertEqual(result['route']['model'], 'claude-opus')
        self.assertEqual(self.runner.prepare.call_args.kwargs['prefer_group'], 'Claude and GPT models')
        prompt = self.runner.run.call_args.args[1]
        self.assertIn(self.context, prompt)
        self.assertIn('already implemented', prompt)
        result['proposals'][0]['scope_id'] = 'changed-local-copy'
        self.assertEqual(self.proposals[1]['scope_id'], 'public-source')

    def test_all_rejected_and_empty_batch_do_not_create_work(self):
        self.answer['candidate'] = {'accepted': [], 'rejected': [
            {'index': 0, 'reason': 'Already implemented.'}, {'index': 1, 'reason': 'No evidenced gap.'}]}
        self.assertEqual(self.run_review()['proposals'], [])
        self.runner.run.reset_mock()
        self.runner.prepare.reset_mock()
        self.proposals = []
        self.assertEqual(self.run_review()['proposals'], [])
        self.runner.prepare.assert_not_called()
        self.runner.run.assert_not_called()

    def test_same_model_is_held_before_inference_but_same_group_other_model_allowed(self):
        self.route.update(self.planner)
        with self.assertRaisesRegex(ValueError, 'different actual model'):
            self.run_review()
        self.runner.run.assert_not_called()
        self.route['model'] = 'gemini-other'
        result = self.run_review()
        self.assertEqual(result['route']['model'], 'gemini-other')

    def test_duplicate_missing_out_of_range_and_boolean_indexes_rejected(self):
        invalid = [
            {'accepted': [0, 0], 'rejected': []},
            {'accepted': [0], 'rejected': []},
            {'accepted': [0, 2], 'rejected': []},
            {'accepted': [False, 1], 'rejected': []},
            {'accepted': [1], 'rejected': [{'index': True, 'reason': 'bad'}]},
            {'accepted': [0], 'rejected': [{'index': 0, 'reason': 'duplicate'}]},
            {'accepted': [1], 'rejected': [{'index': 0, 'reason': ''}]},
            {'accepted': [0, 1], 'rejected': [], 'new_scope': 'host-shell'},
        ]
        for i, candidate in enumerate(invalid):
            with self.subTest(candidate=candidate):
                self.answer['candidate'] = candidate
                directory = self.root / str(i)
                with self.assertRaises(ValueError):
                    self.run_review(directory)
                self.assertTrue((directory / 'review-response.json').exists())
                count = self.runner.run.call_count
                with self.assertRaisesRegex(ValueError, 'retained'):
                    self.run_review(directory)
                self.assertEqual(self.runner.run.call_count, count)

    def test_response_cannot_change_actual_model(self):
        self.answer['route'] = {'model': 'unexpected-model'}
        with self.assertRaisesRegex(ValueError, 'model differs'):
            self.run_review()
        self.assertTrue((self.root / 'review-response.json').exists())

    def test_uncertain_call_retains_intent_and_never_replays(self):
        self.runner.run.side_effect = TimeoutError('uncertain')
        with self.assertRaises(TimeoutError):
            self.run_review()
        with self.assertRaisesRegex(ValueError, 'retained'):
            self.run_review()
        self.assertEqual(self.runner.run.call_count, 1)

    def test_quota_preflight_never_creates_inference_intent(self):
        self.runner.prepare.side_effect = review.native.QuotaWait('2026-10-03T00:00:00+00:00')
        with self.assertRaises(review.native.QuotaWait):
            self.run_review()
        self.runner.run.assert_not_called()
        self.assertFalse((self.root / 'review-intent.json').exists())

    def test_saved_success_replays_without_new_inference_and_rejects_changed_context(self):
        result = self.run_review()
        self.runner.prepare.reset_mock()
        self.runner.run.reset_mock()
        self.assertEqual(self.run_review(), result)
        self.runner.prepare.assert_not_called()
        self.runner.run.assert_not_called()
        self.context += '\nnew code'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.run_review()

    def test_full_source_is_not_truncated_when_review_exceeds_bound(self):
        self.context = 'x' * 65536
        with self.assertRaisesRegex(ValueError, 'exceeds bound'):
            self.run_review()
        self.runner.prepare.assert_not_called()
        self.runner.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

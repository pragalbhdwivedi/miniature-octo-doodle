import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import pilot_views as v


class PilotViewTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'batch': {'id': 'pilot-1', 'goal': 'Synthetic regression coverage',
            'state': 'running', 'max_tasks': 3, 'deadline': '2026-10-02T11:00:00Z'},
            'tasks': [{'id': 'task-1', 'title': 'Namespace tests', 'state': 'human_review_required',
                'prompt': 'Add synthetic tests only', 'paths': ['tests/test_contract.py'],
                'source_sha': 'a'*40, 'tests': {'passed': 19, 'failed': 0, 'exit_code': 0},
                'review': {'verdict': 'review', 'findings': ['Run the bounded test suite.']},
                'result': {'summary': 'Two tests added', 'codex_sha256': 'b'*64},
                'usage': {'input_tokens': 123}}], 'events': [{'state': 'running', 'message': 'Task admitted'}],
            'questions': [{'question': 'Select candidate?', 'state': 'pending'}],
            'totals': {'model_calls': 3}, 'limits': {'max_minutes': 60, 'max_tasks': 3}}

    def test_all_views_and_levels_are_bounded_and_pure(self):
        original = copy.deepcopy(self.snapshot)
        for view in v.VIEWS:
            for level in v.LEVELS:
                with self.subTest(view=view, level=level):
                    text = v.render(view, level, self.snapshot)
                    self.assertIn(v.LABELS[view], text)
                    self.assertLessEqual(len(text), 3500)
                    self.assertLessEqual(len(text.encode('utf-16-le')), 7000)
        self.assertEqual(self.snapshot, original)

    def test_brief_hides_hashes_and_outputs_distinguish_advice(self):
        self.snapshot['tasks'][0]['review']['findings'].append('Revision '+'c'*40)
        text = v.render('outputs', 'brief', self.snapshot)
        for value in ['a'*40, 'b'*64, 'c'*40]:
            self.assertNotIn(value, text)
        self.assertIn('advisory', text)
        self.assertIn('not approval', text)
        self.assertIn('19', text)
        self.assertIn('a'*40, v.render('inputs', 'detailed', self.snapshot))

    def test_truncation_announces_download_and_respects_emoji_limit(self):
        self.snapshot['tasks'][0]['prompt'] = '🙂'*5000
        text = v.render('inputs', 'full', self.snapshot)
        self.assertLessEqual(len(text.encode('utf-16-le')), 7000)
        self.assertTrue(text.endswith(v.NOTICE))
        self.assertEqual(v.report(self.snapshot).count('🙂'), 5000)

    def test_credentials_redacted_unknown_fields_omitted(self):
        self.snapshot['tasks'][0].update(password='do-not-leak', unapproved_dump='private dump')
        self.snapshot['tasks'][0]['prompt'] = (
            'api_key=abc123 password="secret words" Bearer abc.def.ghi '
            'ghp_1234567890abcdefghijkl sk-abcdefghijklmnop '
            '123456789:abcdefghijklmnopqrstuvwx '
            '-----BEGIN PRIVATE KEY-----\nkeymaterial\n-----END PRIVATE KEY-----')
        for text in (v.render('inputs', 'full', self.snapshot), v.report(self.snapshot)):
            for secret in ('do-not-leak', 'private dump', 'abc123', 'secret words', 'abc.def.ghi',
                           'ghp_1234567890abcdefghijkl', 'sk-abcdefghijklmnop', 'keymaterial',
                           '123456789:abcdefghijklmnopqrstuvwx'):
                self.assertNotIn(secret, text)
            self.assertIn('redacted', text)

    def test_keyboards_navigation_details_and_controls(self):
        for view in v.VIEWS:
            buttons = [b for row in v.keyboard(view, 'detailed')['inline_keyboard'] for b in row]
            callbacks = {b['callback_data'] for b in buttons}
            self.assertIn('p:inputs:detailed', callbacks)
            self.assertIn('p:outputs:detailed', callbacks)
            self.assertIn('p:ask:brief', callbacks)
            self.assertIn('p:report:full', callbacks)
            self.assertIn('p:'+view+':full', callbacks)
            for button in buttons:
                self.assertLessEqual(len(button['callback_data'].encode()), 64)
            self.assertEqual('p:pause:brief' in callbacks, view == 'controls')
            self.assertEqual('p:resume:brief' in callbacks, view == 'controls')

    def test_report_preserves_all_admitted_evidence_without_interpretation(self):
        self.snapshot['tasks'][0]['review']['verdict'] = 'revise'
        text = v.report(self.snapshot)
        for phrase in ('Two tests added', 'revise', 'Select candidate?', 'Task admitted',
                       'a'*40, 'b'*64, '123'):
            self.assertIn(phrase, text)
        self.assertIn('advisory', text)

    def test_candidate_evidence_and_comprehensive_alias(self):
        self.snapshot['tasks'][0]['candidates'] = {
            'gemini': {'summary': 'Gemini candidate', 'proposal': 'Add a regression', 'diff': '+ test_one()'},
            'codex': {'summary': 'Codex candidate', 'proposal': 'Check both orders', 'diff': '+ test_two()'}}
        self.snapshot['tasks'][0]['tests'].update(suite='identity contract', count=19)
        full = v.render('outputs', 'full', self.snapshot)
        self.assertIn('Gemini candidate', full)
        self.assertIn('Codex candidate', full)
        self.assertIn('identity contract', full)
        self.assertEqual(full, v.render('outputs', 'Comprehensive', self.snapshot))
        self.assertEqual(v.keyboard('outputs', 'full'), v.keyboard('outputs', 'comprehensive'))
        self.assertIn('Check both orders', v.report(self.snapshot))
        self.assertIn('+ test_one()', full)
        self.assertNotIn('+ test_one()', v.render('outputs', 'detailed', self.snapshot))

    def test_empty_snapshot_and_unknown_usage_are_explicit(self):
        self.assertIn('No task outputs', v.render('outputs', 'brief', {}))
        self.assertIn('unknown, not zero', v.render('usage', 'brief', {}))
        self.assertIn('Not recorded', v.render('status', 'brief', {}))
        for invalid in [('not-a-view', 'brief'), ('status', 'invalid')]:
            with self.assertRaises(ValueError):
                v.render(*invalid, {})
            with self.assertRaises(ValueError):
                v.keyboard(*invalid)


if __name__ == '__main__':
    unittest.main()

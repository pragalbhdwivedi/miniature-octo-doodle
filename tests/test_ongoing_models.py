import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import ongoing_models as models


class ModelRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = self.root/'models.json'
        self.cache.write_text(json.dumps({'fetched_at': '2026-10-02T00:00:00Z', 'models': [
            {'slug': name, 'supported_reasoning_levels': [{'effort': e} for e in ('low', 'medium', 'high')]}
            for name in ('gpt-6-luna', 'gpt-6-sol', 'gpt-6-astra')]}), encoding='utf-8')
        self.calls = []

    def coder(self, executable, prompt, directory, **kwargs):
        self.calls.append(kwargs)
        (directory/'codex-events.jsonl').write_text(json.dumps({'type': 'turn.completed', 'usage': {
            'input_tokens': 100, 'cached_input_tokens': 60, 'output_tokens': 12}}), encoding='utf-8')
        return {'summary': 'done'}

    def test_defaults_choose_focused_models_and_explicit_escalation_only(self):
        self.assertEqual(models.route()['model'], 'gpt-6-luna')
        self.assertEqual(models.route()['effort'], 'medium')
        self.assertEqual(models.route(stage='review')['effort'], 'low')
        self.assertEqual(models.route('complex')['model'], 'gpt-6-sol')
        self.assertEqual(models.route('hard')['model'], 'gpt-6-astra')
        self.assertEqual(models.route(attempt=1)['model'], 'gpt-6-sol')
        self.assertEqual(models.route('complex', attempt=1)['model'], 'gpt-6-astra')
        for attempt in (2, -1, True, '1'):
            with self.assertRaises(models.RoutingError): models.route(attempt=attempt)
        with self.assertRaises(models.RoutingError): models.route('hard', attempt=1)

    def test_quota_fallback_requires_explicit_denial_without_generated_output(self):
        path=self.root/'codex-events.jsonl'
        for message in ("You've hit your usage limit", "You\u2019ve hit your usage limit", 'usage_limit_reached'):
            path.write_text(json.dumps({'type':'error','message':message}),encoding='utf-8')
            self.assertTrue(models.confirmed_quota_denial(self.root))
        with path.open('a',encoding='utf-8') as f:
            f.write('\n'+json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'partial'}}))
        self.assertFalse(models.confirmed_quota_denial(self.root))
        path.write_text(json.dumps({'type':'error','message':'network timeout'}),encoding='utf-8')
        self.assertFalse(models.confirmed_quota_denial(self.root))

    def test_model_and_effort_are_validated_before_inference(self):
        self.cache.write_text('{"models":[]}', encoding='utf-8')
        with self.assertRaises(models.RoutingError):
            models.run('codex', 'Focused prompt', self.root/'run', coder=self.coder, cache_path=self.cache)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root/'run').exists())

    def test_unsupported_effort_rejected(self):
        self.cache.write_text(json.dumps({'models': [{'slug': 'gpt-6-luna',
            'supported_reasoning_levels': [{'effort': 'high'}]}]}), encoding='utf-8')
        with self.assertRaises(models.RoutingError): models.validate_route(models.route(), self.cache)

    def test_run_passes_route_and_observed_usage_and_prevents_replay(self):
        folder = self.root/'run'
        result = models.run('codex', 'Focused prompt', folder, coder=self.coder, cache_path=self.cache)
        self.assertEqual(self.calls, [{'schema': None, 'model': 'gpt-6-luna', 'effort': 'medium'}])
        self.assertEqual(result['candidate']['summary'], 'done')
        self.assertEqual(result['usage']['cached_input_tokens'], 60)
        self.assertEqual(json.loads((folder/'model-report.json').read_text())['state'], 'completed')
        with self.assertRaises(models.RoutingError):
            models.run('codex', 'Focused prompt', folder, coder=self.coder, cache_path=self.cache)
        self.assertEqual(len(self.calls), 1)

    def test_failure_does_not_retry_or_switch_model(self):
        def fail(*args, **kwargs):
            self.calls.append(kwargs)
            raise RuntimeError('quota')
        folder = self.root/'failed'
        with self.assertRaises(RuntimeError):
            models.run('codex', 'Focused prompt', folder, coder=fail, cache_path=self.cache)
        self.assertEqual(len(self.calls), 1)
        report = json.loads((folder/'model-report.json').read_text())
        self.assertEqual(report['state'], 'failed_no_retry')
        self.assertEqual(report['usage']['status'], 'unavailable')
        self.assertFalse(report['route']['api_fallback'])

    def test_oversize_prompt_does_not_call_model(self):
        with self.assertRaises(models.RoutingError):
            models.run('codex', 'x'*(models.MAX_PROMPT_BYTES+1), self.root/'large', coder=self.coder, cache_path=self.cache)
        self.assertEqual(self.calls, [])

    def test_missing_or_ambiguous_usage_stays_unknown(self):
        path = self.root/'events.jsonl'
        self.assertIsNone(models.usage_from_events(path)['input_tokens'])
        for text in ('bad json', '{"type":"turn.completed"}',
                     '{"type":"turn.completed"}\n{"type":"turn.completed"}'):
            path.write_text(text, encoding='utf-8')
            self.assertEqual(models.usage_from_events(path)['status'], 'unavailable')

    def test_gemini_configuration_is_not_claimed_as_enforced_selection(self):
        value = models.gemini_status('Gemini Pro High')
        self.assertEqual(value['configured_conversation_model'], 'Gemini Pro High')
        self.assertFalse(value['actual_model_verified'])
        self.assertFalse(value['per_message_override'])
        self.assertFalse(value['automatic_switching'])

    def test_quota_exhaustion_skips_entire_shared_group(self):
        original = {}
        quotas = models.mark_quota_exhausted(original, 'gemini', '2026-10-02T10:00:00Z')
        self.assertEqual(original, {})
        result = models.select_available_model(models.ANTIGRAVITY_MODELS, quotas,
                                               now='2026-10-02T09:00:00Z', fallback_count=1)
        self.assertEqual(result['group'], 'claude_gpt')
        self.assertFalse(result['selection_enforced'])
        self.assertFalse(result['execution_retry'])

    def test_all_exhausted_waits_without_invented_reset_or_rotation(self):
        quotas = models.mark_quota_exhausted({}, 'gemini')
        quotas = models.mark_quota_exhausted(quotas, 'claude_gpt')
        result = models.select_available_model(models.ANTIGRAVITY_MODELS, quotas)
        self.assertEqual(result['status'], 'wait')
        self.assertIsNone(result['next_known_reset'])
        self.assertEqual(result['blocked_groups'], ['claude_gpt', 'gemini'])

    def test_known_reset_restores_eligibility_not_claimed_execution(self):
        quotas = models.mark_quota_exhausted({}, 'gemini', '2026-10-02T10:00:00Z')
        result = models.select_available_model(models.ANTIGRAVITY_MODELS, quotas,
                                               now='2026-10-02T10:00:00Z')
        self.assertEqual(result['group'], 'gemini')
        self.assertEqual(result['status'], 'recommended')
        with self.assertRaises(models.RoutingError):
            models.select_available_model(models.ANTIGRAVITY_MODELS, quotas, fallback_count=2)
        with self.assertRaises(models.RoutingError):
            models.mark_quota_exhausted({}, 'gemini', '2026-10-02T10:00:00')


if __name__ == '__main__':
    unittest.main()

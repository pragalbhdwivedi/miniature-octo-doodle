"""Provider declarations validate independently, then narrow key authority."""
import json
from pathlib import Path
import tempfile
import unittest

from gateway.policy import Denied, Ledger, Policy


class DevelopmentProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = json.loads(Path('config/policy/policy.json').read_text())
        self.candidates = [
            {'alias': 'openai-chat', 'model': 'openai/gpt-5.4-mini'},
            {'alias': 'gemini-chat', 'model': 'gemini/gemini-3.1-flash-lite'},
        ]
        self.config['resolved_routes'] = {'coding-standard': self.candidates}
        self.ledger = Ledger(Path(self.temp.name) / 'ledger.sqlite3', 100)
        self.policy = Policy(self.config, self.ledger)
        self.body = {'model': 'coding-standard',
                     'messages': [{'role': 'user', 'content': 'synthetic hello'}],
                     'max_completion_tokens': 64}

    def admit(self, request=None, key=None):
        return self.policy.admit(dict(self.body, metadata=request or {}), key)

    def test_capacity_limits_reject_missing_and_malformed_configuration(self):
        for name in ('max_input_bytes', 'max_output_tokens'):
            missing = dict(self.config)
            del missing[name]
            with self.subTest(name=name, missing=True), self.assertRaisesRegex(ValueError, name):
                Policy(missing, self.ledger)
            for value in (None, True, False, 0, -1, 1.0, float('nan'),
                          float('inf'), '100', [], {}):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, name):
                    Policy(dict(self.config, **{name: value}), self.ledger)

    def test_positive_integer_capacity_limits_preserve_config_and_admission(self):
        for name in ('max_input_bytes', 'max_output_tokens'):
            config = dict(self.config, **{name: 1})
            policy = Policy(config, self.ledger)
            self.assertIs(policy.config, config)
            self.assertEqual(config[name], 1)
        request_id, candidates, _ = self.admit()
        self.assertEqual(candidates, self.candidates)
        self.ledger.release(request_id)

    def test_narrow_request_does_not_invalidate_broader_key(self):
        for provider in ('openai', 'gemini'):
            with self.subTest(provider=provider):
                request_id, candidates, _ = self.admit(
                    {'allowed_providers': [provider]},
                    {'allowed_providers': ['openai', 'gemini']})
                self.assertEqual(candidates, [c for c in self.candidates
                                             if c['model'].startswith(provider + '/')])
                self.ledger.attempt(request_id, candidates[0]['model'])
                forbidden = next(c['model'] for c in self.candidates if c not in candidates)
                with self.assertRaises(Denied):
                    self.ledger.attempt(request_id, forbidden)
                self.ledger.release(request_id)

    def test_missing_declarations_and_duplicates_preserve_route_order(self):
        for request, key, expected in (
            ({}, {}, self.candidates),
            ({}, {'allowed_providers': ['gemini']}, self.candidates[1:]),
            ({'allowed_providers': ['openai']}, {}, self.candidates[:1]),
            ({'allowed_providers': ['gemini', 'openai', 'openai']},
             {'allowed_providers': ['openai', 'gemini']}, self.candidates),
        ):
            with self.subTest(request=request, key=key):
                request_id, candidates, _ = self.admit(request, key)
                self.assertEqual(candidates, expected)
                self.ledger.release(request_id)

    def test_empty_declarations_and_disjoint_restrictions_deny_consistently(self):
        for request, key in (([], None), (None, []), ([], []),
                             (['openai'], []), ([], ['gemini']),
                             (['openai'], ['gemini']), (['gemini'], ['openai'])):
            with self.subTest(request=request, key=key):
                request_meta = {} if request is None else {'allowed_providers': request}
                key_meta = {} if key is None else {'allowed_providers': key}
                with self.assertRaises(Denied) as error:
                    self.admit(request_meta, key_meta)
                self.assertEqual(error.exception.reason, 'no_allowed_provider')

    def test_explicit_request_cannot_widen_key_authority(self):
        for key_provider in ('openai', 'gemini'):
            with self.subTest(key_provider=key_provider), self.assertRaises(Denied) as error:
                self.admit({'allowed_providers': ['openai', 'gemini']},
                           {'allowed_providers': [key_provider]})
            self.assertEqual(error.exception.reason, 'invalid_provider_allowlist')

    def test_each_declaration_validates_against_universe_before_intersection(self):
        for invalid in (None, 'openai', {'openai': True}, True, [True], [1],
                        [{}], [['openai']], ['unknown'], ['openai', 'unknown']):
            for source in ('request', 'key'):
                with self.subTest(value=invalid, source=source):
                    metadata = {'allowed_providers': invalid}
                    # An empty opposite declaration cannot hide malformed input.
                    empty = {'allowed_providers': []}
                    with self.assertRaises(Denied) as error:
                        self.admit(metadata if source == 'request' else empty,
                                   metadata if source == 'key' else empty)
                    self.assertEqual(error.exception.reason, 'invalid_provider_allowlist')

    def test_local_provider_membership_uses_explicit_enablement(self):
        for enabled in (False, 'true', 1):
            self.config['local_models_enabled'] = enabled
            with self.subTest(enabled=enabled), self.assertRaises(Denied) as error:
                self.admit({'allowed_providers': ['ollama']})
            self.assertEqual(error.exception.reason, 'invalid_provider_allowlist')
        self.config['local_models_enabled'] = True
        request_id, candidates, _ = self.admit(
            {'allowed_providers': ['openai']},
            {'allowed_providers': ['openai', 'gemini', 'ollama']})
        self.assertEqual(candidates, self.candidates[:1])
        self.ledger.release(request_id)
        # A valid provider declaration still cannot manufacture a configured route.
        with self.assertRaises(Denied) as error:
            self.admit({'allowed_providers': ['ollama']})
        self.assertEqual(error.exception.reason, 'no_allowed_provider')


if __name__ == '__main__':
    unittest.main()

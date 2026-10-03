import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gateway.policy import Denied, Ledger, Policy


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


routes = load('mac_gateway_routes')
acceptance = load('mac_gateway_acceptance')
setup = load('mac_gateway_setup')
GOOD = '\n'.join('def %s(a,b):\n    return a %s b' % pair for pair in
                 [('add', '+'), ('subtract', '-'), ('multiply', '*'), ('divide', '/')])


class MacGatewayTests(unittest.TestCase):
    def test_real_arithmetic_checks_and_wrong_code(self):
        self.assertEqual(acceptance.check_source(GOOD), 14)
        with self.assertRaises(ValueError):
            acceptance.check_source(GOOD.replace('a - b', 'b - a'))

    def test_executable_payloads_rejected_before_execution(self):
        for source in ['import os\n' + GOOD, GOOD.replace('a + b', '__import__("os")'),
                       GOOD.replace('a + b', 'a.__class__'), GOOD.replace('a + b', 'a ** b'),
                       GOOD.replace('def add(a,b):', 'def add(a,b=print("bad")):'),
                       '@print("bad")\n' + GOOD, GOOD + '\nprint("bad")',
                       GOOD.replace('return a + b', 'while True: pass')]:
            with self.subTest(source=source), self.assertRaises((ValueError, SyntaxError)):
                acceptance.check_source(source)

    def test_staging_preserves_routes_and_no_fallback(self):
        cfg = {'model_list': [{'model_name': 'old', 'litellm_params': {'model': 'openai/x'}}]}
        policy = {'decision_plane': {'mode': 'deterministic', 'jev_enabled': False},
                  'resolved_routes': {'old': [{'alias': 'old', 'model': 'openai/x'}]},
                  'prices': {'openai/x': {'input_micro_usd': 1, 'output_micro_usd': 2}}}
        result, guard = routes.render(cfg, policy, 'http://172.26.0.1:11436')
        self.assertEqual(result['model_list'][:-1], cfg['model_list'])
        self.assertEqual(guard['resolved_routes']['old'], policy['resolved_routes']['old'])
        self.assertEqual(guard['resolved_routes'][routes.ALIAS], [{'alias': routes.ALIAS, 'model': routes.MODEL}])
        self.assertEqual(len(cfg['model_list']), 1)
        self.assertEqual(guard['prices'][routes.MODEL]['input_micro_usd'], 0)
        self.assertEqual(result['model_list'][-1]['litellm_params']['reasoning_effort'], 'none')
        for base in ['http://172.26.0.1:11435', 'https://172.26.0.1:11436',
                     'http://8.8.8.8:11436', 'http://user:pass@172.26.0.1:11436',
                     'http://172.26.0.1:11436/path', 'http://172.26.0.1:11436?q=x']:
            with self.subTest(base=base), self.assertRaises(ValueError):
                routes.render(cfg, policy, base)
        with self.assertRaises(ValueError):
            routes.render(result, guard, 'http://172.26.0.1:11436')

    def test_connection_does_not_accept_admin_or_public_host(self):
        cfg = {'host': '10.0.0.1', 'port': 22, 'user': 'gatewayai-mac-test', 'vpn_address': '10.1.0.2',
               'host_key': 'ssh-ed25519 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'connection.json'
            path.write_text(json.dumps(cfg))
            self.assertEqual(setup.load_connection(path), cfg)
            for patch in [{'host': '8.8.8.8'}, {'user': 'root'}, {'port': 7000},
                          {'host_key': 'ssh-ed25519 ABC\nHost *'}, {'password': 'example'}]:
                path.write_text(json.dumps(dict(cfg, **patch)))
                with self.subTest(patch=patch), self.assertRaises(ValueError):
                    setup.load_connection(path)

    def test_wireguard_is_required_not_a_lan_or_other_vpn(self):
        cfg = {'host': '10.0.0.1', 'vpn_address': '10.1.0.2'}
        with patch.object(setup, 'output', side_effect=[' interface: utun8\n', ' inet 10.1.0.2 --> 10.1.0.2 ']):
            self.assertEqual(setup.wireguard_preflight(cfg), 'utun8')
        with patch.object(setup, 'output', return_value=' interface: en0\n'):
            with self.assertRaises(ValueError):
                setup.wireguard_preflight(cfg)
        with patch.object(setup, 'output', side_effect=[' interface: utun4\n', ' inet 10.2.0.2 --> 10.2.0.2 ']):
            with self.assertRaises(ValueError):
                setup.wireguard_preflight(cfg)

    def test_real_policy_keeps_local_candidate_and_denies_tools(self):
        cfg = {'model_list': []}
        policy = {'decision_plane': {'mode': 'deterministic', 'jev_enabled': False},
                  'resolved_routes': {}, 'prices': {},
                  'max_input_bytes': 32768, 'max_output_tokens': 1024}
        _, policy = routes.render(cfg, policy, 'http://172.26.0.1:11436')
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'ledger.sqlite3', 0)
            guard = Policy(policy, ledger)
            body = {'model': routes.ALIAS, 'messages': [{'role': 'user', 'content': 'synthetic'}],
                    'max_tokens': 768, 'metadata': {'data_class': 'synthetic', 'allowed_providers': ['ollama']}}
            token, candidates, _ = guard.admit(body, {'allowed_providers': ['ollama']})
            self.assertEqual(candidates, [{'alias': routes.ALIAS, 'model': routes.MODEL}])
            ledger.attempt(token, routes.MODEL)
            with self.assertRaises(Denied):
                ledger.attempt(token, 'openai/example')
            ledger.release(token)
            with self.assertRaisesRegex(Denied, 'tools_not_approved'):
                guard.admit(dict(body, tools=[{'type': 'function'}]))
            with self.assertRaisesRegex(Denied, 'local_provider_unavailable'):
                guard.admit(dict(body, metadata={'data_class': 'local-private'}))

    def test_writes_do_not_overwrite_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'note'
            setup.write_new(target, 'first')
            setup.write_new(target, 'first')
            with self.assertRaises(ValueError):
                setup.write_new(target, 'changed')


if __name__ == '__main__':
    unittest.main()

import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    'local_model_routes', Path(__file__).resolve().parents[1]/'scripts/local_model_routes.py')
routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes)


class LocalRoutesTests(unittest.TestCase):
    def setUp(self):
        self.config = {'model_list': [{'model_name': 'coding-standard',
                                       'litellm_params': {'model': 'openai/test'}}]}
        self.policy = {'decision_plane': {'mode': 'deterministic', 'jev_enabled': False},
                       'resolved_routes': {'coding-standard': [
                           {'alias': 'coding-standard', 'model': 'openai/test'}]},
                       'prices': {'openai/test': {'input_micro_usd': 1,
                                                  'output_micro_usd': 1}}}

    def test_local_aliases_are_separate_and_zero_vendor_spend(self):
        config, policy = routes.render(self.config, self.policy,
                                       'http://172.26.0.1:11435')
        self.assertEqual(len(config['model_list']), 3)
        self.assertEqual(len(self.config['model_list']), 1)
        self.assertEqual(policy['resolved_routes']['coding-standard'],
                         self.policy['resolved_routes']['coding-standard'])
        for alias, model in routes.MODELS.items():
            self.assertEqual(policy['resolved_routes'][alias],
                             [{'alias': alias, 'model': model}])
            self.assertEqual(policy['prices'][model],
                             {'input_micro_usd': 0, 'output_micro_usd': 0})
            self.assertEqual(next(item for item in config['model_list']
                                  if item['model_name'] == alias)['litellm_params'],
                             {'model': model, 'api_base': 'http://172.26.0.1:11435'})

    def test_untrusted_target_and_duplicate_setup_are_denied(self):
        for base in ('http://127.0.0.1:11435', 'https://172.26.0.1:11435',
                     'http://10.176.46.41:11435', 'http://172.26.0.1:11435/x',
                     'http://user:pass@172.26.0.1:11435'):
            with self.subTest(base=base), self.assertRaises(ValueError):
                routes.render(self.config, self.policy, base)
        config, policy = routes.render(self.config, self.policy,
                                       'http://172.26.0.1:11435')
        with self.assertRaisesRegex(ValueError, 'already configured'):
            routes.render(config, policy, 'http://172.26.0.1:11435')


if __name__ == '__main__':
    unittest.main()

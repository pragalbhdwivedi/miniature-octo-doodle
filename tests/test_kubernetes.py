"""Deployment isolation and credential boundary regressions; not runtime proof."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('kubernetes', Path(__file__).resolve().parents[1] / 'scripts/kubernetes.py')
kubernetes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kubernetes)


class KubernetesContract(unittest.TestCase):
    def setUp(self):
        self.items = kubernetes.render({})['items']
        self.deployments = [x for x in self.items if x['kind'] == 'Deployment']

    def test_only_core_and_no_host_authority(self):
        self.assertEqual({x['metadata']['name'] for x in self.deployments}, {'litellm', 'postgres', 'open-webui'})
        for d in self.deployments:
            self.assertEqual(d['spec']['replicas'], 1)
            self.assertEqual(d['spec']['strategy']['type'], 'Recreate')
            pod = d['spec']['template']['spec']
            self.assertFalse(pod['automountServiceAccountToken'])
            self.assertFalse(pod.get('hostNetwork'))
            self.assertTrue(all('hostPath' not in v for v in pod['volumes']))
            for c in pod['containers']:
                self.assertIn('@sha256:', c['image'])
                self.assertFalse(c['securityContext']['allowPrivilegeEscalation'])
                self.assertTrue(c['startupProbe'] and c['readinessProbe'] and c['resources']['limits'])
                self.assertTrue(all('hostPort' not in p for p in c['ports']))

    def test_no_spend_or_cloud_credentials(self):
        for d in self.deployments:
            env = {e['name']: e for e in d['spec']['template']['spec']['containers'][0]['env']}
            self.assertNotIn('TYPESAFE_API_KEY', env)
            if d['metadata']['name'] == 'litellm':
                for name, value in [('GATEWAY_MONTHLY_BUDGET_USD', '0'), ('OPENAI_API_KEY', ''), ('GEMINI_API_KEY', '')]:
                    self.assertEqual(env[name]['value'], value)
            if d['metadata']['name'] == 'open-webui':
                self.assertNotIn('LITELLM_MASTER_KEY', env)
                self.assertNotIn('POSTGRES_PASSWORD', env)
        config, policy = kubernetes.configuration()
        self.assertEqual(policy['decision_plane'], {'mode': 'deterministic', 'jev_enabled': False})
        self.assertEqual(len(config['model_list']), 8)

    def test_network_deny_and_internal_storage(self):
        services = [x for x in self.items if x['kind'] == 'Service']
        self.assertTrue(all(x['spec']['type'] == 'ClusterIP' for x in services))
        policies = {x['metadata']['name']: x['spec'] for x in self.items if x['kind'] == 'NetworkPolicy'}
        self.assertEqual(policies['default-deny'], {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress']})
        self.assertEqual(policies['postgres']['egress'], [])
        self.assertEqual(policies['postgres']['ingress'][0]['from'], [{'podSelector': {'matchLabels': {'app': 'litellm'}}}])
        self.assertTrue(all('ipBlock' not in str(x) for x in policies.values()))
        pvcs = [x for x in self.items if x['kind'] == 'PersistentVolumeClaim']
        self.assertEqual(len(pvcs), 3)
        self.assertTrue(all(x['spec']['storageClassName'] == 'local-path' for x in pvcs))


if __name__ == '__main__':
    unittest.main()

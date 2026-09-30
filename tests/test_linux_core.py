import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('linux_core', Path(__file__).resolve().parents[1] / 'scripts/linux-core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class LinuxConfigurationTests(unittest.TestCase):
    def values(self):
        result = core.template()
        for key in ('POSTGRES_PASSWORD', 'LITELLM_SALT_KEY', 'WEBUI_SECRET_KEY', 'WEBUI_ADMIN_PASSWORD'):
            result[key] = 'a' * 64
        result['LITELLM_MASTER_KEY'] = 'sk-' + 'b' * 64
        result['WEBUI_ADMIN_EMAIL'] = 'admin@gatewayai.local'
        return result

    def test_provider_and_budget_activation_rejected(self):
        for key, value in [('OPENAI_API_KEY', 'synthetic'), ('GEMINI_API_KEY', 'synthetic'),
                           ('TYPESAFE_API_KEY', 'synthetic'), ('GATEWAY_MONTHLY_BUDGET_USD', '100')]:
            with self.subTest(key=key):
                values = self.values()
                values[key] = value
                with self.assertRaises(ValueError):
                    core.validate_values(values)

    def test_shell_cannot_override_secrets_or_compose_files(self):
        values = self.values()
        with patch.dict(os.environ, {'COMPOSE_FILE': 'untrusted.yaml', 'OPENAI_API_KEY': 'untrusted'}):
            env = core.compose_environment(values)
        self.assertNotIn('COMPOSE_FILE', env)
        self.assertEqual(env['OPENAI_API_KEY'], '')

    def test_shared_configuration_has_disabled_jev_and_eight_routes(self):
        config, policy = core.configuration(core.REPO)
        self.assertFalse(policy['decision_plane']['jev_enabled'])
        self.assertEqual(len(config['model_list']), 8)
        self.assertTrue(all(m['litellm_params']['api_key'].startswith('os.environ/') for m in config['model_list']))

    @unittest.skipUnless(os.name == 'posix', 'POSIX ownership and modes')
    def test_initialization_preserves_secrets_and_rejects_unsafe_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'runtime'
            core.initialize(root)
            values = core.load(root)
            with self.assertRaises(ValueError):
                core.initialize(root)
            self.assertEqual(values, core.load(root))
            (root / 'runtime.env').chmod(0o644)
            with self.assertRaises(ValueError):
                core.load(root)

    @unittest.skipUnless(os.name == 'posix', 'POSIX symlinks')
    def test_symlink_runtime_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'link'
            root.symlink_to(Path(directory), target_is_directory=True)
            with self.assertRaises(ValueError):
                core.safe_root(root)


if __name__ == '__main__':
    unittest.main()

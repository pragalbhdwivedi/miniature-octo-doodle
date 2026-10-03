import importlib.util
import json
from pathlib import Path, PurePosixPath
import plistlib
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('autostart', Path(__file__).resolve().parents[1] / 'scripts/mac_gateway_autostart.py')
autostart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(autostart)


class AutostartTests(unittest.TestCase):
    def test_launchd_roundtrip_preserves_spaces_and_uses_absolute_arguments(self):
        runtime = PurePosixPath('/Users/example/Library/Application Support/GatewayAI/mac-test/startup')
        loaded = plistlib.loads(plistlib.dumps(autostart.job(runtime, PurePosixPath('/usr/bin/python3'), '/usr/bin:/bin')))
        self.assertEqual(loaded['ProgramArguments'], ['/usr/bin/python3', '-u',
                         str(runtime / 'mac_gateway_autostart.py'), 'run'])
        self.assertTrue(loaded['KeepAlive'])
        self.assertGreaterEqual(loaded['ThrottleInterval'], 30)
        self.assertNotIn('UserName', loaded)
        self.assertNotIn('sh', loaded['ProgramArguments'])

    def test_vpn_settings_only_change_startup_and_verify_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            backup = Path(folder) / 'before.json'
            before = {'launch-at-startup': False, 'connect-on-launch': 'false', 'security-level': 'preferred'}
            after = dict(before, **{'launch-at-startup': True, 'connect-on-launch': 'true'})
            with patch.object(autostart.subprocess, 'check_output', side_effect=[json.dumps(before), json.dumps(after)]), \
                 patch.object(autostart.subprocess, 'run') as run:
                self.assertTrue(autostart.configure_openvpn(Path('/Applications/OpenVPN Connect'), backup))
            self.assertEqual(run.call_count, 2)
            self.assertEqual(json.loads(backup.read_text()), {'launch-at-startup': False, 'connect-on-launch': 'false'})
            self.assertTrue(all('--value=true' in call.args[0] for call in run.call_args_list))
            self.assertNotIn('security-level', backup.read_text())

    def test_unsupported_client_not_mutated_and_failed_readback_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            backup = Path(folder) / 'before.json'
            with patch.object(autostart.subprocess, 'check_output', return_value='{}'), \
                 patch.object(autostart.subprocess, 'run') as run:
                self.assertFalse(autostart.configure_openvpn(Path('/client'), backup))
                run.assert_not_called()
                self.assertFalse(backup.exists())
            before = {'launch-at-startup': False, 'connect-on-launch': False}
            with patch.object(autostart.subprocess, 'check_output', return_value=json.dumps(before)), \
                 patch.object(autostart.subprocess, 'run'):
                with self.assertRaises(ValueError):
                    autostart.configure_openvpn(Path('/client'), backup)

    def test_atomic_write_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'existing'; target.write_text('preserve')
            link = Path(folder) / 'link'
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('Symlink creation unavailable')
            with self.assertRaises(ValueError):
                autostart.write_owned(link, b'changed')
            self.assertEqual(target.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()

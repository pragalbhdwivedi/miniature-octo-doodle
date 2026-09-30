"""Protected cross-host restore admission tests, without Docker."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('linux_import', Path(__file__).parents[1]/'scripts/linux-import.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipUnless(os.name == 'posix', 'Requires POSIX ownership/mode checks')
class ImportTests(unittest.TestCase):
    def test_private_bundle_and_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            folder = base/'backup'
            folder.mkdir(mode=0o700)
            for name in module.recovery.FILES | {'manifest.json'}:
                p = folder/name
                p.write_text('fixture')
                p.chmod(0o600)
            with patch.object(module.recovery, 'validate_bundle', return_value='validated'):
                self.assertEqual(module.protected_bundle(folder, base), 'validated')
                (folder/'.env').chmod(0o644)
                with self.assertRaises(ValueError): module.protected_bundle(folder, base)

    def test_symlink_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base/'real').mkdir(mode=0o700)
            (base/'link').symlink_to(base/'real', target_is_directory=True)
            with self.assertRaises(ValueError): module.protected_bundle(base/'link', base)


if __name__ == '__main__':
    unittest.main()

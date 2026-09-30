import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

module=None
try:
    spec=importlib.util.spec_from_file_location('encrypted_backup',Path(__file__).parents[1]/'scripts/encrypted-backup.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except ModuleNotFoundError as error:
    if error.name != 'cryptography': raise
    module=None


@unittest.skipUnless(module is not None, 'Existing cryptography dependency required')
class EncryptedBackupTests(unittest.TestCase):
    def test_roundtrip_and_tampering_rejected_before_plaintext_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/'source'
            source.mkdir()
            for name in module.recovery.FILES | {'manifest.json'}: (source/name).write_bytes(name.encode())
            key=module.Fernet.generate_key()
            with patch.object(module.recovery,'validate_bundle'):
                module.seal(source,key,root/'sealed')
                module.unseal(root/'sealed',key,root/'restored')
                for p in source.iterdir(): self.assertEqual(p.read_bytes(),(root/'restored'/p.name).read_bytes())
                with self.assertRaises(FileExistsError): module.unseal(root/'sealed',key,root/'restored')
                payload=bytearray((root/'sealed').read_bytes()); payload[len(payload)//2]^=1
                (root/'sealed').write_bytes(payload)
                with self.assertRaises(Exception): module.unseal(root/'sealed',key,root/'tampered')
                self.assertFalse((root/'tampered').exists())


if __name__=='__main__': unittest.main()

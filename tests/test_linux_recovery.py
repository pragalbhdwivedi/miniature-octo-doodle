import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('linux_recovery', Path(__file__).resolve().parents[1] / 'scripts/linux-recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryArchiveTests(unittest.TestCase):
    def test_archive_roundtrip_and_occupied_target_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'state').write_text('synthetic preserved state')
            archive = root / 'archive.tar.gz'
            recovery.archive(source, archive)
            recovery.unpack(archive, root / 'restored')
            self.assertEqual(recovery.tree_hashes(source), recovery.tree_hashes(root / 'restored'))
            with self.assertRaises(ValueError):
                recovery.unpack(archive, root / 'restored')

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'bad.tar'
            with tarfile.open(archive, 'w') as stream:
                entry = tarfile.TarInfo('../escape')
                entry.size = 4
                stream.addfile(entry, io.BytesIO(b'nope'))
            with self.assertRaises(tarfile.FilterError):
                recovery.unpack(archive, root / 'restored')
            self.assertFalse((root / 'escape').exists())

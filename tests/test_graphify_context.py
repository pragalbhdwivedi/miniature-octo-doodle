import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    'graphify_context', Path(__file__).resolve().parents[1]/'scripts/graphify_context.py')
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


class GraphContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.remote = root/'remote.git'
        self.repo = root/'source'
        self.repo.mkdir()
        self.index = root/'index'
        subprocess.run(['git', 'init', '-q', '--bare', str(self.remote)], check=True)
        self.git('init', '-q', '-b', 'main')
        self.git('remote', 'add', 'origin', str(self.remote))
        (self.repo/'example.py').write_text('VALUE = 1\n', encoding='utf-8')
        self.git('add', 'example.py')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-q', '-m', 'fixture')
        self.git('push', '-q', 'origin', 'main')

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def build(self, mutate=False):
        def extractor(*args, timeout, cwd):
            if args[1] == 'extract':
                target = Path(args[-1])/'graphify-out'
                target.mkdir()
                (target/'graph.json').write_text(json.dumps({
                    'source': (self.repo/'example.py').read_text(encoding='utf-8')}),
                    encoding='utf-8')
                if mutate:
                    (self.repo/'example.py').write_text('VALUE = 3\n', encoding='utf-8')
            return b''
        return context.build(self.repo, self.index, 'graphify', runner=extractor)

    def test_stale_checkout_and_modified_graph_are_denied(self):
        original = context.REPOSITORY
        context.REPOSITORY = str(self.remote).removesuffix('.git')
        self.addCleanup(setattr, context, 'REPOSITORY', original)
        self.build()
        with self.assertRaisesRegex(context.ContextError, 'role'):
            context.query(self.repo, self.index, 'graphify', 'example', 'private-worker')
        (self.index/'graphify-out'/'graph.json').write_text('{"nodes":[1]}',
                                                            encoding='utf-8')
        with self.assertRaisesRegex(context.ContextError, 'provenance'):
            context.query(self.repo, self.index, 'graphify', 'example')
        self.build()
        (self.repo/'example.py').write_text('VALUE = 2\n', encoding='utf-8')
        with self.assertRaisesRegex(context.ContextError, 'clean'):
            context.query(self.repo, self.index, 'graphify', 'example')

    def test_new_remote_main_denies_old_graph(self):
        original = context.REPOSITORY
        context.REPOSITORY = str(self.remote).removesuffix('.git')
        self.addCleanup(setattr, context, 'REPOSITORY', original)
        self.build()
        (self.repo/'example.py').write_text('VALUE = 2\n', encoding='utf-8')
        self.git('add', 'example.py')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-q', '-m', 'advance')
        self.git('push', '-q', 'origin', 'main')
        with self.assertRaisesRegex(context.ContextError, 'provenance'):
            context.query(self.repo, self.index, 'graphify', 'example')

    def test_build_binds_extraction_to_source_and_rejects_midbuild_change(self):
        original = context.REPOSITORY
        context.REPOSITORY = str(self.remote).removesuffix('.git')
        self.addCleanup(setattr, context, 'REPOSITORY', original)
        self.build()
        old_manifest = (self.index/'source.json').read_bytes()
        old_graph = (self.index/'graphify-out'/'graph.json').read_bytes()
        with self.assertRaisesRegex(context.ContextError, 'clean'):
            self.build(mutate=True)
        self.assertEqual((self.index/'source.json').read_bytes(), old_manifest)
        self.assertEqual((self.index/'graphify-out'/'graph.json').read_bytes(), old_graph)


if __name__ == '__main__':
    unittest.main()

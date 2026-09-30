import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile
import unittest

spec = importlib.util.spec_from_file_location('worker', Path(__file__).resolve().parents[1]/'scripts/worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((worker.REPO/'config/worker/projects.json').read_text())
        self.job = {'project': 'gatewayai', 'ref': 'refs/heads/main',
                    'commands': [['python3', '-c', 'print("ok")']],
                    'write_paths': ['docs/worker-check.txt'], 'timeout_seconds': 30, 'model_budget_usd': 0}

    def test_default_allows_only_named_public_repository_and_zero_spend(self):
        self.assertEqual(worker.validate_job(self.job, self.registry)['default_branch'], 'main')
        for field, value in [('project', 'aadi'), ('ref', 'refs/heads/other'),
                             ('timeout_seconds', 121), ('timeout_seconds', True),
                             ('model_budget_usd', 1), ('commands', [['sh']]*9)]:
            job = {**self.job, field: value}
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                worker.validate_job(job, self.registry)

    def test_source_credentials_local_urls_and_flag_injection_rejected(self):
        for url in ['file:///root/keys', 'https://token@github.com/x/y.git',
                    'https://github.com.evil/x/y.git', 'ext::sh -c id']:
            registry = copy.deepcopy(self.registry)
            registry['gatewayai']['url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                worker.validate_job(self.job, registry)

    def test_path_traversal_git_and_ambiguous_paths_rejected(self):
        for path in ['../secret', '/etc/passwd', '.git/config', 'docs//a', 'docs/./a', 'x\\y']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                worker.validate_job({**self.job, 'write_paths': [path]}, self.registry)

    def test_container_has_no_authority_or_unbounded_writable_host_mount(self):
        argv = worker.docker_args('sha256:'+'a'*64, 'b'*32, PurePosixPath('/private/run/input'))
        for expected in ['--network=none', '--read-only', '--cap-drop=ALL', '--memory=768m',
                         '--memory-swap=768m', '--pids-limit=64', '--cpus=1', '--pull=never',
                         '--user=65532:65532', '--log-driver=none', '--restart=no']:
            self.assertIn(expected, argv)
        self.assertEqual(argv.count('--mount'), 1)
        self.assertEqual(argv[argv.index('--mount')+1], 'type=bind,src=/private/run/input,dst=/input,readonly')
        self.assertNotIn('--privileged', argv)
        with self.assertRaises(ValueError):
            worker.docker_args('python:latest', 'b'*32, PurePosixPath('/private/run/input'))

    def test_archive_rejects_symlinks_hardlinks_and_special_files(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE]:
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as tar:
                member = tarfile.TarInfo('escape');member.type=kind;member.linkname='/etc/passwd';tar.addfile(member)
            stream.seek(0)
            with tarfile.open(fileobj=stream) as tar, self.assertRaises(ValueError):
                worker.sandbox.source_files(tar)

    def test_wrong_image_or_missing_independent_deadline_rejected(self):
        config = {'User': '65532:65532', 'WorkingDir': '/workspace', 'Volumes': None,
                  'Entrypoint': ['timeout', '--signal=KILL', '150', 'python3', '-I', '/opt/gatewayai-worker/sandbox.py']}
        worker.validate_image({'Config': config})
        for field, value in [('User', 'root'), ('Volumes', {'/data': {}}),
                             ('Entrypoint', ['python3']), ('WorkingDir', '/')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                worker.validate_image({'Config': {**config, field: value}})

    def test_artifact_compares_to_immutable_source_and_exact_write_scope(self):
        source = {'docs/a.txt': (b'old\n', 0o644)}
        change = {'path': 'docs/a.txt', 'before_sha256': hashlib.sha256(b'old\n').hexdigest(),
                  'content_base64': base64.b64encode(b'new\n').decode(), 'mode': 0o644}
        diff = worker.artifacts({'changes': [change]}, source, ['docs/a.txt'])
        self.assertIn('-old\n+new\n', diff)
        for bad in [{**change, 'before_sha256': '0'*64}, {**change, 'path': 'docs/other.txt'},
                    {**change, 'mode': 0o4755}]:
            with self.assertRaises(ValueError):
                worker.artifacts({'changes': [bad]}, source, ['docs/a.txt'])

    @unittest.skipUnless(os.name == 'posix', 'POSIX process boundaries')
    def test_wall_time_kills_process_group(self):
        with self.assertRaises(TimeoutError):
            worker.bounded([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=0.1)

    def test_no_final_newline_has_explicit_patch_marker(self):
        change = {'path': 'new.txt', 'before_sha256': None,
                  'content_base64': base64.b64encode(b'no newline').decode(), 'mode': 0o644}
        diff = worker.artifacts({'changes': [change]}, {}, ['new.txt'])
        self.assertTrue(diff.endswith('+no newline\n\\ No newline at end of file\n'))

    @unittest.skipUnless(os.name == 'posix', 'POSIX process boundaries')
    def test_output_flood_is_bounded(self):
        with self.assertRaises(ValueError):
            worker.bounded([sys.executable, '-c', 'print("x"*100000)'], limit=100)


if __name__ == '__main__':
    unittest.main()

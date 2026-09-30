import concurrent.futures
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).resolve().parents[1]/'scripts/worker_publish.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
worker = publisher.worker
coding = worker.coding


class CodingTests(unittest.TestCase):
    def setUp(self):
        self.job = {'project': 'gatewayai', 'ref': 'refs/heads/main', 'commands': [['true']],
                    'write_paths': ['out.py'], 'timeout_seconds': 60, 'model_budget_usd': 1,
                    'coding': {'task': 'Create a greeting function', 'read_paths': ['README.md'],
                               'alias': 'coding-fast', 'max_output_tokens': 512}}
        self.policy_patch = patch.object(coding, 'check_gateway_policy')
        self.policy_patch.start()
        self.addCleanup(self.policy_patch.stop)
        self.original = {'README.md': (b'Public source', 0o644)}
        self.response = {'choices': [{'finish_reason': 'stop', 'message': {'content':
                            json.dumps({'files': [{'path': 'out.py', 'content': 'def greet(): return "Hello"\n'}]})}}]}

    def test_context_and_gateway_contract(self):
        registry = json.loads((worker.REPO/'config/worker/projects.json').read_text())
        worker.validate_job(self.job, registry)
        calls = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(coding, 'private_config', return_value={
                'gateway_url': 'http://127.0.0.1:4000', 'gateway_key': 'synthetic', 'policy_file':'/unused-policy'}):
            def transport(url, token, body):
                calls.append((url, body))
                return self.response
            payload, debit = coding.generate(self.job, self.original, 'a'*32, Path(tmp), Path('/unused'), worker.sandbox.relative, transport)
            worker.artifacts(payload, self.original, self.job['write_paths'])
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], 'http://127.0.0.1:4000/v1/chat/completions')
            self.assertNotIn('tools', calls[0][1])
            self.assertLessEqual(debit, 1000000)

    def test_budget_exhaustion_replay_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'budget.sqlite3'
            with self.assertRaises(ValueError): coding.reserve(p, 'a'*32, 10, 11, 'hash')
            coding.reserve(p, 'a'*32, 100, 90, 'hash')
            with self.assertRaises(sqlite3.IntegrityError): coding.reserve(p, 'a'*32, 100, 1, 'changed')
            with closing(sqlite3.connect(p)) as db:
                self.assertEqual(db.execute('SELECT debit FROM runs').fetchone()[0], 90)

    def test_concurrent_same_run_debits_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'budget.sqlite3'
            def attempt(_):
                try:
                    coding.reserve(p, 'a'*32, 100, 99, 'hash')
                    return True
                except sqlite3.IntegrityError:
                    return False
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(attempt, range(16))), 1)

    def test_failed_http_is_not_refunded(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(coding, 'private_config', return_value={
                'gateway_url': 'http://127.0.0.1:4000', 'gateway_key': 'synthetic', 'policy_file':'/unused-policy'}):
            def transport(*args): raise TimeoutError('ambiguous')
            with self.assertRaises(TimeoutError):
                coding.generate(self.job, self.original, 'b'*32, Path(tmp), Path('/unused'), worker.sandbox.relative, transport)
            with closing(sqlite3.connect(Path(tmp)/'coding-budget.sqlite3')) as db:
                self.assertGreater(db.execute('SELECT debit FROM runs').fetchone()[0], 0)

    def test_budget_invalid_values(self):
        for value in (True, -1, float('nan'), float('inf'), 2, 0.0000001):
            with self.subTest(value=value), self.assertRaises(ValueError): coding.micros(value)

    def test_missing_or_oversized_context(self):
        with self.assertRaises(ValueError): coding.messages_for(self.job, {})
        with self.assertRaises(ValueError): coding.messages_for(self.job, {'README.md': (b'x'*32768, 0o644)})

    def test_model_cannot_expand_paths_or_actions(self):
        for value in ({'files': [{'path': '../escape', 'content': 'x'}]},
                      {'files': [{'path': 'README.md', 'content': 'x'}]},
                      {'files': [{'path': 'out.py', 'content': 'x', 'command': 'evil'}]},
                      {'files': [{'path': 'out.py', 'content': None}]}):
            self.response['choices'][0]['message']['content'] = json.dumps(value)
            with self.assertRaises(ValueError): coding.proposal(self.response, self.original, ['out.py'], worker.sandbox.relative)
        self.response['choices'][0]['finish_reason'] = 'length'
        with self.assertRaises(ValueError): coding.proposal(self.response, self.original, ['out.py'], worker.sandbox.relative)

    def test_provider_url_and_redirect_denial(self):
        with patch.object(coding, 'private_config', return_value={'gateway_url': 'https://api.openai.com', 'gateway_key': 'synthetic', 'policy_file':'/unused-policy'}):
            with self.assertRaises(ValueError):
                coding.generate(self.job, self.original, 'a'*32, Path('/unused'), Path('/unused'), worker.sandbox.relative)
        with self.assertRaises(ValueError): coding.NoRedirect().redirect_request(None)


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.value = {'repository': 'owner/repo', 'base': 'main', 'head': 'worker/'+'a'*32,
                      'run_id': 'a'*32, 'source_sha': 'b'*40, 'artifact_sha256': 'c'*64,
                      'changes': [{'path': 'out.py', 'content_base64': 'eAo=', 'mode': 0o644}]}
        self.config = {'repository': 'owner/repo', 'github_token': 'synthetic'}
        self.calls = []

    def api(self, url, token, body):
        path = url.removeprefix('https://api.github.com/repos/owner/repo')
        self.calls.append((path, body))
        if path == '': return {'private': False, 'default_branch': 'main'}
        if path == '/git/ref/heads/main': return {'object': {'sha': 'b'*40}}
        if path == '/git/commits/'+'b'*40: return {'tree': {'sha': 'd'*40}}
        if path == '/pulls': return {'draft': True, 'head': {'ref': self.value['head']},
                                   'base': {'ref': 'main'}, 'html_url': 'https://github.com/owner/repo/pull/1', 'number': 1}
        return {'sha': 'e'*40}

    def test_only_new_run_branch_and_draft_pr(self):
        result = publisher.publish(self.value, self.config, self.api)
        self.assertTrue(result['draft'])
        refs = [b for p, b in self.calls if p == '/git/refs']
        self.assertEqual(refs, [{'ref': 'refs/heads/'+self.value['head'], 'sha': 'e'*40}])
        self.assertFalse(any(p.endswith('/merge') or p.startswith('/git/refs/') for p, _ in self.calls))
        self.assertEqual(next(b for p,b in self.calls if p == '/git/trees')['tree'][0]['mode'], '100644')

    def test_wrong_repository_and_stale_base_denied(self):
        with self.assertRaises(ValueError): publisher.publish(self.value, {**self.config, 'repository': 'other/repo'}, self.api)
        self.value['source_sha'] = 'f'*40
        with self.assertRaises(ValueError): publisher.publish(self.value, self.config, self.api)
        self.assertFalse(any(b is not None for _, b in self.calls))

    def test_default_branch_or_empty_credentials_denied_before_http(self):
        with self.assertRaises(ValueError):
            publisher.publish(self.value, {**self.config, 'github_token': ''}, self.api)
        self.value['head'] = 'main'
        with self.assertRaises(ValueError): publisher.publish(self.value, self.config, self.api)
        self.assertEqual(self.calls, [])

    def test_partial_failure_never_updates_ref(self):
        def api(url, token, body):
            if url.endswith('/git/refs'): raise RuntimeError('existing branch')
            return self.api(url, token, body)
        with self.assertRaises(RuntimeError): publisher.publish(self.value, self.config, api)
        self.assertFalse(any(p == '/pulls' for p, _ in self.calls))

    def test_plan_binds_approval_to_run_and_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/('a'*32); (folder/'input').mkdir(parents=True)
            archive = folder/'input/source.tar'
            with tarfile.open(archive, 'w') as tar:
                info = tarfile.TarInfo('README.md'); info.size=1
                tar.addfile(info, io.BytesIO(b'x'))
            job = {'project':'gatewayai', 'ref':'refs/heads/main', 'commands':[['true']],
                   'write_paths':['out.py'], 'model_budget_usd':0, 'timeout_seconds':30, 'branch':self.value['head']}
            job_file = folder/'input/job.json'; job_file.write_text(json.dumps(job))
            payload = {'changes':[{**self.value['changes'][0], 'before_sha256':None}]}
            artifact=folder/'changes.json'; artifact.write_text(json.dumps(payload))
            digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
            record={'status':'review_required','container_removed':True,'run_id':'a'*32,
                    'artifact_sha256':digest,'job_sha256':hashlib.sha256(job_file.read_bytes()).hexdigest(),
                    'source_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                    'source_sha':'b'*40,'project':'gatewayai','ref':'refs/heads/main','branch':self.value['head']}
            (folder/'result.json').write_text(json.dumps(record))
            self.assertEqual(publisher.plan(folder,digest)['head'], self.value['head'])
            with self.assertRaises(ValueError): publisher.plan(folder,'0'*64)
            job_file.write_text('{}')
            with self.assertRaises(ValueError): publisher.plan(folder,digest)


class PolicyCeilingTests(unittest.TestCase):
    def test_price_and_attempt_drift_fail_closed(self):
        policy = {'resolved_routes': {'coding-fast': [{'model':'openai/test'}]},
                  'prices': {'openai/test': {'input_micro_usd':10,'output_micro_usd':100}}}
        with patch.object(coding, 'private_config', return_value=policy):
            coding.check_gateway_policy('/unused','coding-fast')
            policy['prices']['openai/test']['input_micro_usd']=11
            with self.assertRaises(ValueError): coding.check_gateway_policy('/unused','coding-fast')
            policy['prices']['openai/test']['input_micro_usd']=10
            policy['resolved_routes']['coding-fast'] *= 3
            with self.assertRaises(ValueError): coding.check_gateway_policy('/unused','coding-fast')


if __name__ == '__main__': unittest.main()

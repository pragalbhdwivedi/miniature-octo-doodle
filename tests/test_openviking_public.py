import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    'openviking_public', Path(__file__).resolve().parents[1]/'scripts/openviking_public.py')
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class PublicWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'account.json').write_text(json.dumps({'result': {'user_key': 'fixture'}}))
        self.sha = 'a'*40
        self.posts = []
        self.task_states = {}

    def api(self, key, method, path, body=None):
        self.assertEqual(key, 'fixture')
        if method == 'POST' and path == '/api/v1/resources':
            self.assertEqual(body['processing_mode'], 'vectors_only')
            self.assertIn('/'+self.sha+'/', body['path'])
            task_id = '1'*35+str(len(self.posts))
            self.posts.append(body)
            self.task_states[task_id] = 'running'
            return {'task_id': task_id}
        if method == 'GET' and path.startswith('/api/v1/tasks/'):
            return {'status': self.task_states[path.rsplit('/', 1)[-1]]}
        if method == 'POST' and path == '/api/v1/search/find':
            self.assertEqual(body['context_type'], 'resource')
            return {'resources': [{'uri': body['target_uri']+'PROJECT.md',
                                   'abstract': 'Public project rule'}]}
        if method == 'GET' and path.startswith('/api/v1/content/read?'):
            return 'Public document content'
        raise AssertionError((method, path))

    def test_resumes_tasks_and_never_serves_incomplete_or_stale_context(self):
        first = workflow.sync(self.root, sha_reader=lambda: self.sha, api=self.api, pause=lambda _: None)
        self.assertEqual(first['status'], 'building')
        self.assertEqual(len(self.posts), 1)
        with self.assertRaisesRegex(workflow.ContextError, 'unavailable'):
            workflow.find(self.root, self.sha, 'project rules', sha_reader=lambda: self.sha, api=self.api)
        self.task_states['1'*35+'0'] = 'completed'
        for n in range(1, len(workflow.DOCS)):
            result = workflow.sync(self.root, sha_reader=lambda: self.sha,
                                   api=self.api, pause=lambda _: None)
            self.assertEqual(result['status'], 'building')
            self.task_states['1'*35+str(n)] = 'completed'
        ready = workflow.sync(self.root, sha_reader=lambda: self.sha, api=self.api, pause=lambda _: None)
        self.assertEqual(ready['status'], 'ready')
        self.assertEqual(len(self.posts), len(workflow.DOCS))
        result = workflow.find(self.root, self.sha, 'project rules', sha_reader=lambda: self.sha, api=self.api)
        self.assertEqual(result['hits'][0]['abstract'], 'Public project rule')
        self.assertTrue(result['advisory_only'])
        def no_abstract(key, method, path, body=None):
            if method == 'POST':
                return {'resources': [{'uri': workflow.destination(self.sha, 'PROJECT.md'),
                                       'abstract': ''}]}
            return self.api(key, method, path, body)
        self.assertEqual(workflow.find(self.root, self.sha, 'project rules',
                         sha_reader=lambda: self.sha, api=no_abstract)['hits'][0]['abstract'],
                         'Public document content')
        with self.assertRaisesRegex(workflow.ContextError, 'stale'):
            workflow.find(self.root, self.sha, 'project rules', sha_reader=lambda: 'b'*40, api=self.api)
        self.assertFalse(workflow.sync(self.root, sha_reader=lambda: self.sha, api=self.api)['changed'])

    def test_denies_cross_scope_result_and_failed_task(self):
        workflow.sync(self.root, sha_reader=lambda: self.sha, api=self.api, pause=lambda _: None)
        self.task_states['1'*35+'0'] = 'failed'
        with self.assertRaisesRegex(workflow.ContextError, 'failed'):
            workflow.sync(self.root, sha_reader=lambda: self.sha, api=self.api, pause=lambda _: None)
        self.assertEqual(workflow.load(self.root)['status'], 'failed')
        state = {'schema': 'gatewayai.openviking-public.v1', 'source_sha': self.sha,
                 'status': 'ready', 'entries': {name: {'status': 'completed',
                 'uri': workflow.destination(self.sha, name)} for name in workflow.DOCS}}
        workflow.save(self.root/'public-main.json', state)
        def outside(key, method, path, body):
            return {'resources': [{'uri': 'viking://user/private/secret', 'abstract': 'deny'}]}
        with self.assertRaisesRegex(workflow.ContextError, 'Out-of-scope'):
            workflow.find(self.root, self.sha, 'public', sha_reader=lambda: self.sha, api=outside)


if __name__ == '__main__':
    unittest.main()

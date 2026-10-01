import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import supervisor_mcp as mcp
import test_local_agent as fixture


class SupervisorMCPTests(unittest.TestCase):
    command = fixture.LocalAgentTests.command

    def setUp(self):
        fixture.LocalAgentTests.setUp(self)
        self.env = patch.dict(os.environ, {'LOCALAPPDATA': str(self.repo.parent)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.remote_patch = patch.object(mcp.desktop.agent, 'REPOSITORY',
                                         str(self.remote).removesuffix('.git'))
        self.remote_patch.start()
        self.addCleanup(self.remote_patch.stop)
        self.calls = []
        def chat(*args):
            self.calls.append(args)
            return {'verdict': 'revise', 'findings': ['The proposed constant is incorrect.']}
        self.bridge = mcp.Bridge(self.repo, self.repo.parent/'evidence', chat=chat)

    def prepare(self):
        return self.bridge.call('prepare_review', {'task': 'Return 42', 'paths': ['example.py']})

    def test_roundtrip_records_exact_candidate_without_source_changes(self):
        task = self.prepare()
        candidate = {'summary': 'Return 43', 'proposal': 'A deliberately wrong proposal',
                     'changes': [{'path': 'example.py', 'content': 'def answer():\n    return 43\n'}]}
        result = self.bridge.call('review_proposal', {'task_id': task['task_id'], 'candidate': candidate})
        self.assertEqual(result['critique']['verdict'], 'revise')
        self.assertEqual(self.calls[0][0], mcp.MODEL)
        self.assertEqual(result['actions_executed'], [])
        self.assertEqual((self.repo/'example.py').read_text(), 'def answer():\n    return 41\n')
        audit = json.loads((self.repo.parent/'evidence'/(result['audit_id']+'.json')).read_text())
        self.assertEqual(audit['candidate'], candidate)
        self.assertEqual(audit['transport'], 'mcp-stdio')

    def test_unknown_task_path_escape_and_extra_authority_denied(self):
        for args in ({'task_id': '../secret', 'candidate': {}},
                     {'task_id': [], 'candidate': {}}):
            with self.assertRaises(mcp.desktop.agent.AgentError):
                self.bridge.call('review_proposal', args)
        for paths in (['../private.py'], ['creds/key.json'], ['untracked.py'], [42]):
            with self.assertRaises(mcp.desktop.agent.AgentError):
                self.bridge.call('prepare_review', {'task': 'Read', 'paths': paths})
        with self.assertRaises(mcp.desktop.agent.AgentError):
            self.bridge.call('prepare_review', {'task': 'x', 'paths': ['example.py'], 'repo': 'other'})
        self.assertEqual(self.calls, [])

    def test_stale_source_rejected_before_inference(self):
        task = self.prepare()
        (self.repo/'example.py').write_text('changed')
        with self.assertRaises(mcp.desktop.agent.AgentError):
            self.bridge.call('review_proposal', {'task_id': task['task_id'], 'candidate': {}})
        self.assertEqual(self.calls, [])

    def test_protocol_errors_notifications_and_oversize(self):
        messages = [[], {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                    {'jsonrpc': '2.0', 'method': 'tools/call',
                     'params': {'name': 'prepare_review', 'arguments': {'task': 'x', 'paths': ['example.py']}}},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'initialize',
                     'params': {'protocolVersion': '2025-06-18'}},
                    {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list'},
                    {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'shell'}}]
        source = io.BytesIO(b'bad json\n' + b''.join((json.dumps(m)+'\n').encode() for m in messages))
        sink = io.BytesIO()
        mcp.serve(self.bridge, source, sink)
        replies = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual([r['error']['code'] for r in replies[:3]], [-32700, -32600, -32000])
        self.assertEqual(len(replies[4]['result']['tools']), 3)
        self.assertTrue(replies[5]['result']['isError'])
        self.assertEqual(self.bridge.tasks, {})
        sink = io.BytesIO()
        mcp.serve(self.bridge, io.BytesIO(b'x'*(mcp.LIMIT+2)+b'\n'), sink)
        self.assertEqual(len(sink.getvalue().splitlines()), 1)

    def test_actual_stdio_process_handshake_and_status(self):
        requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                     'params': {'protocolVersion': '2025-06-18'}},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                     'params': {'name': 'supervisor_status', 'arguments': {}}}]
        result = subprocess.run([sys.executable, mcp.__file__, '--repo', str(self.repo),
                                 '--output-root', str(self.repo.parent/'evidence')],
                                input=''.join(json.dumps(r)+'\n' for r in requests),
                                text=True, capture_output=True, timeout=10, check=True)
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(replies), 2)
        value = json.loads(replies[-1]['result']['content'][0]['text'])
        self.assertFalse(value['cloud_fallback'])
        self.assertFalse(value['source_writes'])
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()

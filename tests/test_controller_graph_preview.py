import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


scripts = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location('controller_graph_preview', scripts/'controller_graph_preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class ControllerGraphPreviewTests(unittest.TestCase):
    def test_exact_revision_only_and_no_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            plan_path = Path(temp)/'plan.json'
            plan = {'project': 'gatewayai', 'repository': 'pragalbhdwivedi/miniature-octo-doodle',
                    'ref': 'refs/heads/main', 'source_sha': 'a'*40, 'run_id': 'b'*32}
            plan_path.write_text(json.dumps(plan), encoding='utf-8')
            graph = {'source_sha': 'a'*40, 'advisory_only': True, 'result': 'public symbols'}
            with patch.object(preview.graph, 'query', return_value=graph) as query:
                result = preview.preview(plan_path, temp, temp, 'graphify', 'publishing')
            query.assert_called_once_with(temp, temp, 'graphify', 'publishing',
                                          role='operator', token_budget=300)
            self.assertEqual(result['source_sha'], plan['source_sha'])
            self.assertEqual(result['authority'], 'advisory_only')
            self.assertEqual(result['actions_executed'], [])
            with patch.object(preview.graph, 'query', return_value={**graph, 'source_sha': 'c'*40}):
                with self.assertRaisesRegex(ValueError, 'differ'):
                    preview.preview(plan_path, temp, temp, 'graphify', 'publishing')
            plan['project'] = 'private-project'
            plan_path.write_text(json.dumps(plan), encoding='utf-8')
            with patch.object(preview.graph, 'query') as query:
                with self.assertRaisesRegex(ValueError, 'public GatewayAI'):
                    preview.preview(plan_path, temp, temp, 'graphify', 'publishing')
            query.assert_not_called()


if __name__ == '__main__':
    unittest.main()

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ongoing_local as local
import ongoing_state as state
import pilot_state


class LocalCoderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.payload={'model':local.MODEL,'done':True,'done_reason':'stop',
            'message':{'content':json.dumps({'summary':'Test','proposal':'Not executed','method_source':'def test_edge(self):\n    self.assertTrue(True)'})},
            'prompt_eval_count':100,'eval_count':20,'total_duration':1000}

    def call(self):
        opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(self.payload).encode())
        return local.run('Small admitted task',self.root,opener=opener),opener

    def test_loopback_tool_free_generation_reports_local_usage_and_denies_replay(self):
        result,opener=self.call()
        request=opener.open.call_args.args[0];body=json.loads(request.data)
        self.assertEqual(request.full_url,'http://127.0.0.1:11434/api/chat')
        self.assertNotIn('tools',body)
        self.assertEqual(body['options']['num_predict'],512)
        self.assertEqual(result['usage']['cloud_tokens'],0)
        self.assertEqual(result['usage']['output_tokens'],20)
        with self.assertRaisesRegex(ValueError,'replay'):self.call()

    def test_development_explanations_are_bounded_and_saved_for_recovery(self):
        self.payload['message']['content']=json.dumps({'summary':'x'*601,'proposal':'brief','changes':[]})
        opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(self.payload).encode())
        with self.assertRaisesRegex(ValueError,'compact contract'):
            local.run('Compact source task',self.root,opener=opener,development=True)
        self.assertTrue((self.root/'local-response.json').exists())
        body=json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(body['format']['properties']['summary']['maxLength'],600)
        self.assertEqual(body['format']['properties']['proposal']['maxLength'],400)

    def test_truncated_generation_stays_held(self):
        self.payload['done_reason']='length'
        with self.assertRaisesRegex(ValueError,'incomplete'):self.call()
        self.assertTrue((self.root/'local-intent.json').exists())

    def test_development_uses_bounded_full_file_schema_without_tools(self):
        value={'summary':'Confidence: 8/10; small change','proposal':'Not executed',
               'changes':[{'path':'src/example.py','content':'VALUE = 2\n'}]}
        self.payload['message']['content']=json.dumps(value)
        opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(self.payload).encode())
        result=local.run('Immutable development task',self.root,opener=opener,development=True)
        body=json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(body['format'],local.DEVELOPMENT_SCHEMA)
        self.assertEqual(body['options']['num_predict'],3072)
        self.assertEqual(body['options']['num_ctx'],8192)
        self.assertNotIn('tools',body);self.assertEqual(result['candidate'],value)

    def test_explicit_installed_instruct_coder_keeps_selected_model_identity(self):
        selected='qwen3:4b-instruct'
        self.payload['model']=selected
        self.payload['message']['content']=json.dumps({'summary':'Complete','proposal':'No execution',
            'changes':[{'path':'src/example.py','content':'VALUE = 2\n'}]})
        opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(self.payload).encode())
        result=local.run('Compact admitted task',self.root,model=selected,opener=opener,development=True)
        self.assertEqual(json.loads(opener.open.call_args.args[0].data)['model'],selected)
        self.assertEqual(result['route']['model'],selected)
        self.assertEqual(result['usage']['cloud_tokens'],0)

    def test_model_identity_mismatch_is_held_without_alternate_inference(self):
        opener=Mock();opener.open.return_value=io.BytesIO(json.dumps(self.payload).encode())
        with self.assertRaisesRegex(ValueError,'wrong model'):
            local.run('Compact admitted task',self.root,model='qwen3:4b-instruct',opener=opener,development=True)
        opener.open.assert_called_once()
        with self.assertRaisesRegex(ValueError,'replay'):
            local.run('Compact admitted task',self.root,model='qwen3:4b-instruct',opener=opener,development=True)
        opener.open.assert_called_once()

    def test_method_placement_preserves_baseline_and_rejects_extra_code(self):
        before='import unittest\nclass Checks(unittest.TestCase):\n    def test_old(self):\n        self.assertTrue(True)\n\nif __name__=="__main__":\n    unittest.main()\n'
        method='def test_new(self):\n    self.assertEqual(1, 1)'
        import ongoing_worker
        after=local.apply_method(before,method)
        self.assertEqual(ongoing_worker.validate_additions(before,after),['test_new'])
        for invalid in ('import os\n'+method,method.replace('test_new','test_old'),'@decorator\n'+method):
            with self.assertRaises(ValueError):local.apply_method(before,invalid)
        recovered=local.proposal(before,{'summary':'New test','method_source':'user','proposal':method},'test.py')
        self.assertEqual(recovered['changes'][0]['content'],after)
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            local.proposal(before,{'summary':'Two methods','method_source':method,'proposal':method.replace('test_new','test_other')},'test.py')

    def test_uninstalled_model_and_oversized_context_never_start(self):
        with self.assertRaises(ValueError):local.run('task',self.root,model='download-me')
        with self.assertRaises(ValueError):local.run('x'*(local.MAX_PROMPT_BYTES+1),self.root)
        self.assertFalse((self.root/'local-intent.json').exists())

    def test_third_local_owner_does_not_consume_cloud_generation_allowance(self):
        s=pilot_state.make_state('a'*40);s['batch']['state']='completed'
        jobs=[{'id':owner,'owner':owner,'title':owner,'risk':'reversible','operation':'test_addition',
            'write_paths':['tests/'+owner+'.py'],'transport':'cli' if owner=='gemini' else 'sidecar'} for owner in ('gemini','codex','local')]
        state.install(s,jobs);s['ongoing']['planned']=True
        for j in jobs:
            work=state.work(s)
            state.finish(s,{'action':'ongoing_finish','token':work['token'],
                'result':{'child_id':j['id'],'issue':{}}})
        work=state.work(s)
        self.assertEqual(work['action'],'parallel_code')
        self.assertEqual(len(work['jobs']),3)
        self.assertEqual(s['ongoing']['calls'],2)
        self.assertIsNone(work['job'])
        s['ongoing']['lease']=None;s['ongoing']['calls']=12
        self.assertEqual(state.work(s)['action'],'local')
        self.assertEqual(s['ongoing']['calls'],12)

import base64
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('pipeline',Path(__file__).resolve().parents[1]/'scripts/controller_pipeline.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

def response(value):return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.job=json.loads((p.ROOT/'config/worker/smoke-job.json').read_text())
        self.root={'run_id':'a'*32,'state':'review_required','request':{'job':self.job},'project':'gatewayai'}
        self.spec={'run_id':'a'*32,'source_sha':'b'*40,'artifact_sha256':'c'*64,'requirements':'Write the requested synthetic text.',
                   'read_paths':[],'test_commands':[['python3','-c','print("ok")']],'budget_micro_usd':1000000,'max_repairs':1}
        self.original={'PROJECT.md':(b'Rules',0o644),'AGENTS.md':(b'Rules',0o644)}
        self.proposal={'changes':[{'path':'docs/worker-smoke.txt','before_sha256':None,'content_base64':base64.b64encode(b'bad').decode(),'mode':0o644}]}
        self.config={'runtime':'/private','worker_runtime':'/private/worker','coding_config':'/private/key'}
        self.store=Mock()
        self.store.step_pipeline.side_effect=lambda id,old,new,evidence:{'run_id':id,'state':new,'evidence':evidence}

    def execute(self,replies,tests):
        with patch.object(p,'eligible'),patch.object(p.d,'result_evidence',return_value=('review_required',{})),\
             patch.object(p,'load_candidate',return_value=({'source_sha':'b'*40},self.original,self.proposal)),\
             patch.object(p.d,'private_json',return_value={}),patch.object(p,'test_candidate',side_effect=tests),\
             patch.object(p,'model_call',side_effect=replies) as calls:
            result=p.execute(self.store,self.root,self.spec,p.d.digest(self.spec),self.config)
        return result,calls

    def test_independent_approval_requires_successful_tests(self):
        result,calls=self.execute([response({'verdict':'approve','findings':[]})],[(True,'d'*32,'e'*64)])
        self.assertEqual(result['state'],'approved');self.assertEqual(calls.call_count,1)
        self.store.begin_pipeline.assert_called_once()

    def test_one_repair_then_new_independent_review(self):
        result,calls=self.execute([response({'verdict':'revise','findings':['Wrong text']}),
            response({'files':[{'path':'docs/worker-smoke.txt','content':'correct'}]}),
            response({'verdict':'approve','findings':[]})],[(False,'d'*32,None),(True,'e'*32,'f'*64)])
        self.assertEqual(result['state'],'approved')
        self.assertEqual([x.args[2] for x in calls.call_args_list],['review0','repair','review1'])
        self.assertEqual([x.args[2] for x in self.store.step_pipeline.call_args_list],['repairing','re_reviewing','approved'])

    def test_second_rejection_stops_at_bound(self):
        self.spec['max_repairs']=0
        result,calls=self.execute([response({'verdict':'approve','findings':[]})],[(False,'d'*32,None)])
        self.assertEqual(result['state'],'rejected');self.assertEqual(calls.call_count,1)

    def test_malformed_review_and_scope_expansion_stop(self):
        for value in [{'verdict':'approve','findings':['oops']},{'verdict':'approve','findings':[],'command':'publish'},
                      {'verdict':'approve','findings':'none'}]:
            with self.assertRaises(ValueError):p.review_result(response(value))
        with self.assertRaises(ValueError):
            self.execute([response({'verdict':'revise','findings':['fix']}),
                          response({'files':[{'path':'secrets/key','content':'bad'}]})],[(False,'d'*32,None)])
        self.assertEqual(self.store.step_pipeline.call_args.args[2],'uncertain')

    def test_spec_and_approval_bounds(self):
        for field,value in [('max_repairs',2),('budget_micro_usd',1000001),('max_repairs',True)]:
            with self.assertRaises(ValueError):p.validate_spec({**self.spec,field:value})
        with self.assertRaises(ValueError):p.execute(self.store,self.root,self.spec,'f'*64,self.config)
        self.store.begin_pipeline.assert_not_called()

    def test_large_or_missing_context_not_silently_truncated(self):
        with self.assertRaises(ValueError):p.messages(self.spec,{},self.proposal,'review')
        self.original['PROJECT.md']=(b'x'*17000,0o644)
        with self.assertRaises(ValueError):p.messages(self.spec,self.original,self.proposal,'review')

    def test_review_prompt_has_no_implementer_conversation_or_edit_authority(self):
        prompt=p.messages(self.spec,self.original,self.proposal,'review')
        self.assertEqual([x['role'] for x in prompt],['system','user'])
        self.assertIn('Never edit',prompt[0]['content'])
        self.assertIn('untrusted',prompt[0]['content'])

    def test_budget_denial_precedes_http(self):
        config={'gateway_url':'http://127.0.0.1:4000','gateway_key':'synthetic','policy_file':'/private/policy'}
        transport=Mock();self.store.reserve_pipeline.side_effect=RuntimeError('budget or replay')
        with patch.object(p.w.coding,'private_config',return_value=config),patch.object(p.w.coding,'check_gateway_policy'),self.assertRaises(RuntimeError):
            p.model_call(self.store,self.spec,'review0',[{'role':'user','content':'public'}],Path('/private/config'),transport)
        transport.assert_not_called()

    def test_publish_needs_exact_review_artifact_and_fresh_ownership(self):
        row={'state':'approved','run_id':'a'*32,'spec':self.spec,'approval_sha256':'0'*64,
             'evidence':{'tests_passed':True,'review':{'verdict':'approve'},'candidate_run':'d'*32,'artifact_sha256':'e'*64,'review_sha256':'f'*64}}
        with self.assertRaises(ValueError):p.publish(self.store,self.root,row,'0'*64,self.config,Path('/key'))
        receipt=p.publication_receipt(row)
        with patch.object(p.d,'private_json',return_value={}),\
             patch.object(p,'eligible',side_effect=ValueError('ownership changed')),self.assertRaises(ValueError):
            p.publish(self.store,self.root,row,p.d.digest(receipt),self.config,Path('/key'))
        self.store.step_pipeline.assert_not_called()
        row['state']='rejected'
        with self.assertRaises(ValueError):p.publication_receipt(row)

    def test_publication_failure_stays_ambiguous_and_never_retries(self):
        row={'state':'approved','run_id':'a'*32,'spec':self.spec,'approval_sha256':'0'*64,
             'evidence':{'tests_passed':True,'review':{'verdict':'approve'},'candidate_run':'d'*32,'artifact_sha256':'e'*64,'review_sha256':'f'*64}}
        self.root['request']['plan']={'issue':21}
        with patch.object(p,'eligible'),patch.object(p.d,'private_json',return_value={}),\
             patch.object(p.publisher,'plan',return_value={'source_sha':'b'*40}),\
             patch.object(p.publisher,'publish_reviewed',side_effect=TimeoutError()) as call,self.assertRaises(TimeoutError):
            p.publish(self.store,self.root,row,p.d.digest(p.publication_receipt(row)),self.config,Path('/key'))
        self.assertEqual(call.call_count,1)
        self.assertEqual([x.args[2] for x in self.store.step_pipeline.call_args_list],['publishing','uncertain'])


if __name__=='__main__':unittest.main()

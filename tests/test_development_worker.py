import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import coder_coordination as coordination
import development_tasks as development
import ongoing_local
import ongoing_worker as worker


class DevelopmentWorkerTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.w=worker.Worker.__new__(worker.Worker);self.w.repository='pragalbhdwivedi/aadi'
        self.job={'id':'real-feature','title':'Implement feature','owner':'gemini','risk':'reversible',
            'operation':'development_change','development_profile':'unit','source_sha':'a'*40,
            'paths':['src/app.py','tests/test_app.py','tests/test_new.py'],
            'write_paths':['src/app.py','tests/test_new.py'],
            'test_files':['src/app.py','tests/test_app.py','tests/test_new.py'],
            'prompt':'Implement the feature and prove it','parent_issue':1,'attempt':0,'transport':'cli'}
        self.w.catalog={'real-feature':copy.deepcopy(self.job)};self.w.catalog['real-feature'].pop('attempt')
        self.profile={'image':'sha256:'+'b'*64,'commands':[['python','-m','unittest','discover','-s','tests']],
            'acceptance_tests':['tests/test_app.py'],'timeout_seconds':90,'minimum_tests':1}
        self.w.config={'development_profiles':{'unit':self.profile},'local_coder_model':ongoing_local.MODEL,'local_fallback':True}
        self.before={'src/app.py':'def answer():\n    return 1\n','tests/test_app.py':'import unittest\n','tests/test_new.py':''}
        self.value={'summary':'Confidence: 8/10; focused source fix','proposal':'Not run',
            'changes':[{'path':'src/app.py','content':'def answer():\n    return 2\n'},
                       {'path':'tests/test_new.py','content':'import unittest\n'}]}
        self.result={'task_id':self.w.child(self.job),'owner':'gemini','source_sha':'a'*40,
            'state':'human_review_required','candidate_sha256':coordination.digest(self.value)}
        self.w.coordinator=SimpleNamespace(root=self.root/'evidence',executable='codex',
            source=Mock(return_value={'sha':'a'*40,'files':self.before}),admit=Mock(),close=Mock())
        folder=self.w.coordinator.root/self.w.child(self.job);folder.mkdir(parents=True)
        (folder/'gemini.json').write_text(json.dumps(self.value),encoding='utf-8')
        (folder/'result.json').write_text(json.dumps(self.result),encoding='utf-8')
        self.w.base=SimpleNamespace(repo=self.root/'source',runner=Mock(return_value=(0,b'Ran 1 test in .1s\nOK\n',b'')))
        self.w.publisher=Mock();self.directory=self.root/'execution';self.directory.mkdir()

    def accepted(self):
        self.job['tests']=self.w.test({'job':self.job},self.directory)
        self.job['review']={'verdict':'pass','candidate_sha256':coordination.digest(self.value)}

    def test_admission_prompt_enables_source_edits_with_regression_coverage(self):
        self.w.admit({'job':self.job},self.directory)
        prompt=self.w.coordinator.admit.call_args.args[1]
        self.assertIn('Implement this feature or fix',prompt)
        self.assertNotIn('Add one or two focused test methods only',prompt)

    def test_worker_tests_actual_source_and_binds_profile(self):
        result=self.w.test({'job':self.job},self.directory)
        self.assertTrue(result['passed']);self.assertEqual(result['operation'],'development_change')
        self.assertEqual(result['candidate_sha256'],coordination.digest(self.value))

    def test_review_receives_source_diff_and_complex_route(self):
        self.accepted()
        answer={'candidate':{'verdict':'pass','findings':[],'confidence':8,'confidence_reason':'Covered'},'route':{},'usage':{}}
        with patch.object(worker.models,'run',return_value=answer) as model:
            self.w.review({'job':self.job},self.directory)
        prompt=model.call_args.args[1]
        self.assertIn('+    return 2',prompt);self.assertIn('untrusted data',prompt)
        self.assertEqual(model.call_args.kwargs['complexity'],'complex')

    def test_profile_drift_blocks_review_and_publish(self):
        self.accepted();self.profile['timeout_seconds']=100
        with patch.object(worker.models,'run') as model,patch.object(worker.github,'publish_candidate') as publisher:
            with self.assertRaises(ValueError):self.w.review({'job':self.job},self.directory)
            with self.assertRaises(ValueError):self.w.publish({'job':self.job},self.directory)
            model.assert_not_called();publisher.assert_not_called()

    def test_local_fallback_preserves_cloud_owner_and_reports_actual_model(self):
        answer={'candidate':self.value,'route':{'model':ongoing_local.MODEL,'provider':'ollama_local'},'usage':{'cloud_tokens':0}}
        def assigned(child,generator):
            self.assertEqual(child,self.w.child(self.job));generator('Immutable packet',self.directory)
            return self.result
        self.w.coordinator.run_gemini=assigned
        with patch.object(ongoing_local,'run',return_value=answer) as local:
            result=self.w.local_fallback({'job':self.job},self.directory)
        self.assertEqual(result['owner'],'gemini');self.assertEqual(result['route']['provider'],'ollama_local')
        self.assertEqual(result['usage']['cloud_tokens'],0);self.assertTrue(local.call_args.kwargs['development'])

    def test_unconfigured_fallback_does_not_start_model(self):
        self.w.config['local_fallback']=False
        with patch.object(ongoing_local,'run') as local:
            with self.assertRaises(ValueError):self.w.local_fallback({'job':self.job},self.directory)
            local.assert_not_called()

    def test_compact_context_preserves_complete_writes_and_explicit_readonly_hashes(self):
        self.before['tests/test_app.py']='READ_ONLY_ACCEPTANCE_BODY_MUST_NOT_ENTER_LOCAL_CONTEXT\n'
        self.job['repair']='Keep every required behavior. '+('No truncation of these findings. '*30)
        compact=worker.compact_local_prompt(self.job,{'sha':'a'*40,'files':self.before})
        context=json.loads(compact.split('\nContext: ',1)[1])
        self.assertEqual(context['writable_files'],{p:self.before[p] for p in self.job['write_paths']})
        self.assertNotIn('READ_ONLY_ACCEPTANCE_BODY_MUST_NOT_ENTER_LOCAL_CONTEXT',compact)
        self.assertIn('CONTENTS ARE OMITTED',compact)
        self.assertEqual(context['task']['repair_findings'],self.job['repair'])
        readonly=context['read_only_files'][0]
        self.assertEqual(readonly['path'],'tests/test_app.py')
        self.assertEqual(readonly['sha256'],worker.hashlib.sha256(self.before['tests/test_app.py'].encode()).hexdigest())
        self.assertEqual(context['complete_snapshot_sha256'],coordination.digest({'sha':'a'*40,'files':self.before}))

    def test_compact_context_rejects_wrong_source_or_oversized_writable_content(self):
        with self.assertRaises(ValueError):worker.compact_local_prompt(self.job,{'sha':'b'*40,'files':self.before})
        with self.assertRaises(ValueError):worker.compact_local_prompt(self.job,{'sha':'a'*40,'files':{'src/app.py':'source'}})
        self.before['src/app.py']='x'*24001
        with self.assertRaises(ValueError):worker.compact_local_prompt(self.job,{'sha':'a'*40,'files':self.before})

    def test_local_and_fallback_never_forward_full_coordinator_packet(self):
        self.before['tests/test_app.py']='READ_ONLY_PRIVATE_TRANSCRIPT_SENTINEL\n'
        answer={'candidate':self.value,'route':{'model':ongoing_local.MODEL,'provider':'ollama_local'},'usage':{'cloud_tokens':0}}
        def assigned(child,generator):
            generator('WHOLE_COORDINATOR_PACKET_SENTINEL '+self.before['tests/test_app.py'],self.directory)
            return self.result
        self.w.coordinator.run_local=assigned;self.w.coordinator.run_gemini=assigned
        for method in ('local','local_fallback'):
            with self.subTest(method=method),patch.object(ongoing_local,'run',return_value=copy.deepcopy(answer)) as local:
                getattr(self.w,method)({'job':self.job},self.directory)
                prompt=local.call_args.args[0]
                self.assertNotIn('WHOLE_COORDINATOR_PACKET_SENTINEL',prompt)
                self.assertNotIn('READ_ONLY_PRIVATE_TRANSCRIPT_SENTINEL',prompt)
                context=json.loads(prompt.split('\nContext: ',1)[1])
                self.assertEqual(context['writable_files']['src/app.py'],self.before['src/app.py'])

    def test_api_review_still_receives_full_bound_diff_and_evidence(self):
        self.accepted();self.w.config['openai_api_review']={'enabled':True}
        answer={'candidate':{'verdict':'pass','findings':[],'confidence':8,'confidence_reason':'Source and test evidence checked'},
                'route':{'model':'api-review'},'usage':{}}
        with patch.object(self.w,'api_review',return_value=answer) as reviewer:
            self.w.review({'job':self.job},self.directory)
        sent=str(reviewer.call_args)
        self.assertIn('+    return 2',sent)
        self.assertIn(coordination.digest(self.value),sent)
        self.assertIn(self.job['tests']['profile_sha256'],sent)


if __name__=='__main__':unittest.main()

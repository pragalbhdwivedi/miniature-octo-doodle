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


if __name__=='__main__':unittest.main()

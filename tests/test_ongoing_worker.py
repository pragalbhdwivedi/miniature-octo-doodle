"""Proposal integrity, isolated acceptance and draft publication boundaries."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import coder_coordination as coordination
import ongoing_worker as worker

BEFORE="import unittest\n\nclass Checks(unittest.TestCase):\n    def test_original(self):\n        self.assertEqual(1, 1)\n"
ADDITION="\n    def test_added(self):\n        self.assertEqual(2, 2)\n"
PATH='tests/test_one.py'


class OngoingWorkerTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.w=worker.Worker.__new__(worker.Worker)
        self.job={'id':'synthetic','title':'Synthetic test','owner':'codex','risk':'reversible',
                  'operation':'test_addition','paths':[PATH],'write_paths':[PATH],
                  'test_files':[PATH],'source_sha':'a'*40,'prompt':'Add meaningful edge coverage',
                  'parent_issue':1,'attempt':0}
        self.w.catalog={'synthetic':copy.deepcopy(self.job)}
        del self.w.catalog['synthetic']['attempt']
        self.w.config={'test_image':'sha256:'+'b'*64,'ongoing_github':{}}
        self.w.coordinator=SimpleNamespace(root=self.root/'evidence',executable='synthetic-codex',
                                          close=Mock(),run_codex=Mock())
        self.w.publisher=object()
        self.w.base=SimpleNamespace(repo=self.root/'source',runner=Mock(return_value=(0,b'Ran 2 tests in 0.01s\nOK\n',b'')))
        self.directory=self.root/'stage';self.directory.mkdir()
        self.value={'summary':'Added regression','proposal':'No tests run by coder.',
                    'changes':[{'path':PATH,'content':BEFORE+ADDITION}]}
        self.result={'task_id':self.w.child(self.job),'state':'human_review_required',
                     'owner':'codex','source_sha':self.job['source_sha'],
                     'candidate_sha256':coordination.digest(self.value),
                     'codex_sha256':coordination.digest(self.value)}
        self.evidence=self.w.coordinator.root/self.w.child(self.job);self.evidence.mkdir(parents=True)
        self.save()
        for mock in (patch.object(coordination,'source',return_value={'sha':self.job['source_sha']}),
                     patch.object(coordination.agent,'git',return_value=BEFORE.encode())):
            mock.start();self.addCleanup(mock.stop)

    def save(self):
        (self.evidence/'codex.json').write_text(json.dumps(self.value),encoding='utf-8')
        (self.evidence/'result.json').write_text(json.dumps(self.result),encoding='utf-8')

    def test_existing_codes_helper_and_numeric_assertions_are_valid_test_calls(self):
        addition="\n    def test_edge(self):\n        self.assertIn('MISSING_EFFECTIVE_DATES', self.codes())\n        self.assertLess(-1, 0)\n"
        self.assertEqual(worker.validate_additions(BEFORE,BEFORE+addition),['test_edge'])

    def accepted(self):
        self.job['tests']={'passed':True,'candidate_sha256':coordination.digest(self.value),
                           'added':['test_added'],'test_count':2}
        self.job['review']={'verdict':'pass','candidate_sha256':coordination.digest(self.value),
                            'findings':[]}

    def test_ast_preserves_every_baseline_node(self):
        self.assertEqual(worker.validate_additions(BEFORE,BEFORE+ADDITION),['test_added'])
        for after in ((BEFORE+ADDITION).replace('assertEqual(1, 1)','assertEqual(0, 0)'),
                      'import os\n'+BEFORE+ADDITION,
                      BEFORE+ADDITION.replace('test_added','helper'),
                      BEFORE+ADDITION.replace('    def test_added','    @unittest.skip("skip")\n    def test_added'),
                      BEFORE):
            with self.subTest(after=after),self.assertRaises(ValueError):
                worker.validate_additions(BEFORE,after)

    def test_ast_denies_test_definition_and_body_execution_escape(self):
        additions=[
            '\n    def test_added(self, bad=__import__("os")._exit(0)):\n        self.assertEqual(1, 1)\n',
            '\n    def test_added(self):\n        import os\n        os._exit(0)\n',
            '\n    def test_added(self):\n        print("Ran 2 tests in 0.1s")\n        raise SystemExit(0)\n']
        for added in additions:
            with self.subTest(added=added),self.assertRaises(ValueError):
                worker.validate_additions(BEFORE,BEFORE+added)

    def test_model_cannot_change_catalog_owner_operation_or_paths(self):
        for key,value in [('owner','gemini'),('risk','destructive'),('operation','delete'),
                          ('write_paths',['src/runtime.py'])]:
            changed={**self.job,key:value}
            with self.subTest(key=key),self.assertRaises(ValueError):self.w.spec(changed)

    def test_candidate_digest_and_complete_writable_scope_are_required(self):
        self.assertEqual(self.w.candidate(self.job)[0],self.value)
        self.value['changes'][0]['content']+='\n# tampered'
        self.save()
        with self.assertRaises(ValueError):self.w.candidate(self.job)
        self.result['candidate_sha256']=coordination.digest(self.value)
        self.value['changes'][0]['path']='src/runtime.py';self.save()
        with self.assertRaises(ValueError):self.w.candidate(self.job)

    def test_result_must_bind_child_owner_source_and_completed_state(self):
        original=copy.deepcopy(self.result)
        for key,value in [('task_id','another-task'),('owner','gemini'),
                          ('source_sha','f'*40),('state','running')]:
            self.result={**original,key:value};self.save()
            with self.subTest(key=key),self.assertRaises(ValueError):self.w.candidate(self.job)

    def test_isolated_test_uses_exact_candidate_and_no_network_or_new_image(self):
        result=self.w.test({'job':self.job},self.directory)
        self.assertTrue(result['passed']);self.assertEqual(result['test_count'],2)
        self.assertEqual(result['candidate_sha256'],coordination.digest(self.value))
        command=self.w.base.runner.call_args.args[0]
        for flag in ('--network=none','--pull=never','--read-only','--cap-drop=ALL',
                     '--security-opt=no-new-privileges','--user=65534:65534'):
            self.assertIn(flag,command)
        self.assertEqual((self.directory/'sandbox'/PATH).read_text(),self.value['changes'][0]['content'])

    def test_failing_test_exit_or_missing_summary_cannot_pass(self):
        for i,response in enumerate([(1,b'Ran 2 tests in 0.1s\n',b''),(0,b'No unittest result',b'')]):
            self.w.base.runner.return_value=response
            directory=self.root/('negative-'+str(i));directory.mkdir()
            self.assertFalse(self.w.test({'job':self.job},directory)['passed'])

    def test_review_rejects_stale_or_failed_test_evidence_before_model(self):
        self.accepted()
        for change in ({'passed':False},{'candidate_sha256':'f'*64}):
            j=copy.deepcopy(self.job);j['tests'].update(change)
            with patch.object(worker.models,'run') as model:
                with self.assertRaises(ValueError):self.w.review({'job':j},self.directory)
                model.assert_not_called()

    def test_recovery_counter_does_not_escalate_a_routine_reviewer(self):
        self.accepted();j=dict(self.job,attempt=1)
        answer={'candidate':{'verdict':'pass','findings':[]},'route':{},'usage':{}}
        with patch.object(self.w,'candidate',return_value=(self.value,{PATH:self.value['changes'][0]['content']})),patch.object(worker.models,'run',return_value=answer) as model:
            self.w.review({'job':j},self.directory)
        self.assertEqual(model.call_args.kwargs['attempt'],0)
        self.assertEqual(model.call_args.kwargs['complexity'],'routine')

    def test_publish_requires_matching_review_and_tests_before_remote_write(self):
        self.accepted()
        for section,change in [('tests',{'passed':False}),('tests',{'candidate_sha256':'f'*64}),
                               ('review',{'verdict':'repair'}),('review',{'candidate_sha256':'f'*64})]:
            j=copy.deepcopy(self.job);j[section].update(change)
            with patch.object(worker.github,'publish_candidate') as publish:
                with self.assertRaises(ValueError):self.w.publish({'job':j},self.directory)
                publish.assert_not_called()
        self.w.coordinator.close.assert_not_called()

    def test_publish_passes_bound_artifact_and_returns_verified_receipt(self):
        self.accepted()
        receipt={'task_id':self.job['id'],'pull_request':{'state':'confirmed','draft':True,
                 'url':'https://github.com/pragalbhdwivedi/aadi/pull/123'},'merged':False,'deployed':False}
        with patch.object(worker.github,'publish_candidate',return_value=receipt) as publish:
            result=self.w.publish({'job':self.job},self.directory)
        self.assertEqual(result,receipt)
        task,evidence=publish.call_args.args[1:]
        self.assertEqual(task['files'],{PATH:self.value['changes'][0]['content']})
        self.assertEqual(evidence['artifact_sha256'],worker.github.artifact_digest(task))
        self.assertTrue(evidence['tests_passed']);self.assertTrue(evidence['review_passed'])
        self.w.coordinator.close.assert_called_once()

    def test_codex_uses_assigned_owner_result_not_duplicate_candidate(self):
        self.w.coordinator.run_codex.return_value=self.result
        with patch.object(worker.models,'run',return_value={'candidate':self.value}) as model:
            result=self.w.codex({'job':self.job},self.directory)
            generated=self.w.coordinator.coder('synthetic-codex','fixed prompt',self.directory)
        self.assertEqual(result['candidate_sha256'],coordination.digest(self.value))
        self.assertEqual(generated,self.value)
        self.w.coordinator.run_codex.assert_called_once_with(self.w.child(self.job))
        self.assertEqual(model.call_args.kwargs['stage'],'code')

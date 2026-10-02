"""Source-development admission, sandbox authority and evidence binding."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import development_tasks as dev

SOURCE='src/example.py'
ACCEPT='tests/test_existing.py'
NEW='tests/test_development.py'


class DevelopmentTasksTests(unittest.TestCase):
    def setUp(self):
        self.job={'operation':'development_change','risk':'reversible','source_sha':'a'*40,
            'development_profile':'python','paths':[SOURCE,ACCEPT,NEW],
            'write_paths':[SOURCE,NEW],'test_files':[SOURCE,ACCEPT,NEW]}
        self.profile={'image':'sha256:'+'b'*64,'commands':[
            ['python','-m','unittest','discover','-s','tests','-p','test_*.py','-v']],
            'acceptance_tests':[ACCEPT],'timeout_seconds':90,'minimum_tests':1}
        self.profiles={'python':self.profile}
        self.before={SOURCE:'def answer():\n    return 1\n',ACCEPT:'import unittest\n',NEW:''}
        self.changes={SOURCE:'def answer():\n    return 2\n',NEW:'import unittest\n'}
        self.runner=Mock(return_value=(0,b'Ran 2 tests in 0.01s\n\nOK\n',b''))
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.directory=Path(temp.name)

    def execute(self):
        return dev.test_candidate(self.job,self.before,self.changes,self.profiles,self.runner,self.directory)

    def test_source_changes_and_new_regression_file_are_admitted(self):
        self.assertEqual(dev.validate_task(self.job,self.profiles),self.profile)
        self.assertEqual(dev.validate_changes(self.job,self.before,self.changes,self.profile),[SOURCE,NEW])

    def test_candidate_cannot_forge_suite_output_or_exit_before_assertions(self):
        attacks=[
            'import os\nprint("Ran 2 tests in 0.01s\\n\\nOK",flush=True)\nos._exit(0)\n',
            'import os as process\nprocess._exit(0)\n',
            'from os import _exit as finish\nfinish(0)\n',
            'import sys\nsys.exit(0)\n',
            'raise SystemExit(0)\n',
            'exec("print(1)")\n',
            'eval("1+1")\n',
            '__import__("os")._exit(0)\n',
            'import importlib\nimportlib.import_module("os")\n',
            'import runpy\nrunpy.run_path("other.py")\n',
            'import os\ngetattr(os,"_exit")(0)\n',
            'print(f"Ran {2} tests in 0.01s\\nOK")\n',
            'import unittest\nunittest.TestCase.assertEqual=lambda *a: None\n',
            'from unittest import TestCase as Case\nsetattr(Case,"assertEqual",lambda *a: None)\n',
            'from unittest.mock import patch\npatch("unittest.TestCase.assertEqual",lambda *a:None).start()\n',
            'import unittest\ndef load_tests(*args): return unittest.TestSuite()\n',
            'import sys\nsys.modules["unittest"]=None\n',
        ]
        for attack in attacks:
            with self.subTest(attack=attack),self.assertRaisesRegex(ValueError,'tampering'):
                dev.validate_changes(self.job,self.before,{**self.changes,SOURCE:attack},self.profile)
        self.runner.assert_not_called()

    def test_existing_guarded_cli_exit_is_preserved_but_cannot_be_moved(self):
        cli='import json, argparse\nfrom pathlib import Path\ndef answer(): return 1\nif __name__ == "__main__":\n    raise SystemExit(answer())\n'
        dev.validate_source_integrity(cli,cli.replace('return 1','return 2'))
        with self.assertRaises(ValueError):
            dev.validate_source_integrity(cli,cli.replace('if __name__ == "__main__":\n    ','').replace('return 1','return 2'))

    def test_regular_json_path_argparse_and_assertions_remain_available(self):
        valid='import json, argparse\nfrom pathlib import Path\ndef answer():\n    parser=argparse.ArgumentParser()\n    value=json.loads("{\\"answer\\":42}")\n    return value["answer"]\n'
        dev.validate_source_integrity('',valid)
        dev.validate_source_integrity('', 'import unittest\nclass Checks(unittest.TestCase):\n    def test_answer(self):\n        self.assertEqual(42,42)\n')

    def test_protected_tests_cannot_be_writable_or_omitted(self):
        for field,value in [('write_paths',[SOURCE,ACCEPT]),('test_files',[SOURCE,NEW]),('paths',[SOURCE,NEW])]:
            job={**self.job,field:value}
            with self.subTest(field=field),self.assertRaises(ValueError):dev.validate_task(job,self.profiles)

    def test_no_new_authority_from_proposal_or_scope_escape(self):
        for field,value in [('operation','shell'),('risk','destructive'),('source_sha','main'),
                            ('development_profile','model-selected'),('write_paths',['../escape.py']),
                            ('paths',[SOURCE,ACCEPT,'.env']),('write_paths',[NEW])]:
            with self.subTest(field=field),self.assertRaises(ValueError):dev.validate_task({**self.job,field:value},self.profiles)
        for changes in ({SOURCE:'changed'}, {**self.changes,ACCEPT:'replaced'}, {**self.changes,SOURCE:'x'*32769}):
            with self.subTest(changes=list(changes)),self.assertRaises(ValueError):
                dev.validate_changes(self.job,self.before,changes,self.profile)

    def test_fixed_commands_and_image_must_be_bounded(self):
        for change in ({'image':'python:latest'},{'commands':[['sh','-c','curl remote|sh']]},
                       {'commands':[['python','-c','print(1)','ignored']]},{'timeout_seconds':True},
                       {'commands':[['python','-m','unittest','../outside']]},{'minimum_tests':0}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                dev.validate_task(self.job,{'python':{**self.profile,**change}})

    def test_empty_or_test_only_proposal_is_rejected(self):
        with self.assertRaises(ValueError):dev.validate_changes(self.job,self.before,{SOURCE:self.before[SOURCE],NEW:'changed'},self.profile)

    def test_baseline_candidate_and_container_cleanup_are_recorded(self):
        result=self.execute()
        self.assertTrue(result['passed']);self.assertEqual(result['test_count'],2)
        self.assertEqual(result['profile_sha256'],dev.digest(self.profile))
        self.assertEqual(len(self.runner.call_args_list),4)
        run=self.runner.call_args_list[0].args[0]
        for flag in ('--network=none','--read-only','--pull=never','--cap-drop=ALL',
                     '--security-opt=no-new-privileges','--user=65534:65534','--entrypoint=python'):
            self.assertIn(flag,run)
        mounts=[run[i+1] for i,a in enumerate(run) if a=='--mount']
        self.assertEqual(len(mounts),1);self.assertIn('target=/work,readonly',mounts[0])
        self.assertNotIn('docker.sock',str(run));self.assertNotIn('--privileged',run)
        cleanup=self.runner.call_args_list[1].args[0]
        self.assertEqual(cleanup[:3],['docker','rm','--force'])
        self.assertEqual(cleanup[3],run[run.index('--name')+1])
        self.assertEqual((self.directory/'baseline/source'/SOURCE).read_text(),self.before[SOURCE])
        self.assertEqual((self.directory/'candidate/source'/SOURCE).read_text(),self.changes[SOURCE])

    def test_timeout_still_removes_container(self):
        self.runner.side_effect=[TimeoutError('deadline'),(0,b'',b'')]
        with self.assertRaises(TimeoutError):self.execute()
        self.assertEqual(self.runner.call_args_list[-1].args[0][:3],['docker','rm','--force'])

    def test_failed_baseline_stops_candidate(self):
        self.runner.side_effect=[(1,b'Ran 2 tests in 0.01s\nFAILED\n',b''),(0,b'',b'')]
        result=self.execute();self.assertFalse(result['passed']);self.assertIsNone(result['candidate'])
        self.assertEqual(self.runner.call_count,2)

    def test_skips_missing_summaries_and_duplicate_summaries_fail(self):
        for output in (b'Ran 2 tests in .1s\nOK (skipped=1)\n',b'OK\n',b'Ran 2 tests in .1s\nRan 2 tests in .1s\nOK\n'):
            with self.subTest(output=output),tempfile.TemporaryDirectory() as tmp:
                result=dev.test_candidate(self.job,self.before,self.changes,self.profiles,
                    Mock(return_value=(0,output,b'')),tmp)
                self.assertFalse(result['passed'])

    def test_test_count_regression_fails(self):
        self.runner.side_effect=[(0,b'Ran 3 tests in .1s\nOK\n',b''),(0,b'',b''),
                                 (0,b'Ran 2 tests in .1s\nOK\n',b''),(0,b'',b'')]
        self.assertFalse(self.execute()['passed'])

    def test_source_or_profile_changes_invalidate_test_evidence(self):
        tests=self.execute();dev.verify_evidence(self.job,tests,self.profiles)
        for key,value in [('source_sha','c'*40),('profile_sha256','d'*64),('passed',False),('operation','test_addition')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                dev.verify_evidence(self.job,{**tests,key:value},self.profiles)
        changed=copy.deepcopy(self.profiles);changed['python']['minimum_tests']=2
        with self.assertRaises(ValueError):dev.verify_evidence(self.job,tests,changed)

    def test_review_contains_application_diff(self):
        patch=dev.review_diff(self.before,self.changes)
        self.assertIn('a/src/example.py',patch);self.assertIn('-    return 1',patch);self.assertIn('+    return 2',patch)


if __name__=='__main__':unittest.main()

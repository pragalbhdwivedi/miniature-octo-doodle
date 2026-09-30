import copy
import importlib.util
import json
import hashlib
import tarfile
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('dispatch',Path(__file__).resolve().parents[1]/'scripts/controller_dispatch.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.job=json.loads((d.ROOT/'config/worker/smoke-job.json').read_text())
        self.plan={'status':'awaiting_operator_review','authority':'plan-only','project':'gatewayai',
                   'task_id':'example','source_sha':'a'*40,'job':self.job}
        self.request=d.make_request(self.plan,'sha256:'+'b'*64)

    def test_exact_request_and_fresh_source_required(self):
        d.validate_request(self.request,d.digest(self.request),self.plan)
        for field,value in [('source_sha','c'*40),('status','blocked'),('task_id','changed')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                d.validate_request(self.request,d.digest(self.request),{**self.plan,field:value})
        changed=copy.deepcopy(self.request);changed['job']['commands']=[['id']]
        with self.assertRaises(ValueError):d.validate_request(changed,d.digest(self.request),self.plan)
        with self.assertRaises(ValueError):d.validate_request(changed,d.digest(changed),self.plan)

    def test_budget_image_and_blocked_plan_denials(self):
        for budget in (True,-1,1.01,float('nan')):
            with self.assertRaises(ValueError):d.make_request(self.plan,self.request['image'],budget)
        with self.assertRaises(ValueError):d.make_request(self.plan,'python:latest')
        with self.assertRaises(ValueError):d.make_request({**self.plan,'status':'blocked'},self.request['image'])
        plan={**self.plan,'job':json.loads((d.ROOT/'config/worker/coding-job.json').read_text())}
        with self.assertRaises(ValueError):d.make_request(plan,self.request['image'],0)
        self.assertEqual(d.make_request(plan,self.request['image'],1)['job']['model_budget_usd'],1)

    def test_no_execution_without_committed_claim(self):
        store=Mock();store.claim.side_effect=RuntimeError('duplicate or unavailable')
        run=Mock()
        with self.assertRaises(RuntimeError):
            d.dispatch(self.request,d.digest(self.request),self.plan,store,Path('/private'),runner=run)
        run.assert_not_called();store.finish.assert_not_called()

    def test_one_attempt_is_bound_to_reserved_id_and_source(self):
        store=Mock();store.claim.return_value={'state':'dispatching','request_sha256':d.digest(self.request)}
        run=Mock()
        with patch.object(d,'result_evidence',return_value=('review_required',{'artifact_sha256':'d'*64})):
            d.dispatch(self.request,d.digest(self.request),self.plan,store,Path('/private'),runner=run)
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.kwargs,{'run_id':self.request['run_id'],'expected_source_sha':'a'*40})
        self.assertEqual(store.finish.call_args.args[1],'review_required')

    def test_worker_or_evidence_failure_becomes_uncertain_without_retry(self):
        store=Mock();store.claim.return_value={'state':'dispatching','request_sha256':d.digest(self.request)}
        run=Mock(side_effect=TimeoutError())
        d.dispatch(self.request,d.digest(self.request),self.plan,store,Path('/private'),runner=run)
        self.assertEqual(run.call_count,1);self.assertEqual(store.finish.call_args.args[1],'uncertain')

    def test_completion_database_failure_never_reruns_worker(self):
        store=Mock();store.claim.return_value={'state':'dispatching','request_sha256':d.digest(self.request)}
        store.finish.side_effect=RuntimeError('lost response');run=Mock()
        with patch.object(d,'result_evidence',return_value=('review_required',{})),self.assertRaises(RuntimeError):
            d.dispatch(self.request,d.digest(self.request),self.plan,store,Path('/private'),runner=run)
        self.assertEqual(run.call_count,1)

    def test_sql_payload_cannot_escape_to_sql_or_psql(self):
        payload="'); DROP DATABASE litellm; --\n\\! id"
        encoded=d.state.literal(payload)
        self.assertNotIn('DROP',encoded);self.assertNotIn('\\!',encoded)
        with self.assertRaises(ValueError):d.state.Store('-option','gatewayai_controller')
        with self.assertRaises(ValueError):d.state.Store('postgres','litellm')

    def test_artifact_job_and_cleanup_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/self.request['run_id'];(folder/'input').mkdir(parents=True)
            with tarfile.open(folder/'input/source.tar','w'):pass
            job={**self.job,'branch':'worker/'+self.request['run_id']}
            (folder/'input/job.json').write_text(json.dumps(job))
            (folder/'changes.json').write_text(json.dumps({'changes':[]}))
            sha=lambda path:hashlib.sha256((folder/path).read_bytes()).hexdigest()
            record={'run_id':self.request['run_id'],'project':'gatewayai','ref':self.job['ref'],
                    'image_id':self.request['image'],'source_sha':'a'*40,'status':'review_required',
                    'container_removed':True,'container_started':True,
                    'job_sha256':sha('input/job.json'),'source_archive_sha256':sha('input/source.tar'),
                    'artifact_sha256':sha('changes.json'),
                    'commands':[{'argv':argv,'exit_code':0} for argv in self.job['commands']]}
            with patch.object(d,'private_json',side_effect=lambda _:record):
                self.assertEqual(d.result_evidence(self.request,root)[0],'review_required')
                record['container_removed']=False
                self.assertEqual(d.result_evidence(self.request,root)[0],'uncertain')
                record['container_removed']=True
                (folder/'changes.json').write_text('{"changes": [], "tampered": true}')
                with self.assertRaises(ValueError):d.result_evidence(self.request,root)

    def test_worker_source_pin_rejects_before_archive_or_container(self):
        # Real worker path through fetch; mock only daemon/network CLI boundaries.
        image={'Config':{'User':'65532:65532','WorkingDir':'/workspace',
                        'Entrypoint':['timeout','--signal=KILL','150','python3','-I','/opt/gatewayai-worker/sandbox.py']}}
        def checked(argv,**kwargs):
            if 'info' in argv:return json.dumps({'OSType':'linux','SecurityOptions':['name=seccomp,profile=builtin'],'DockerRootDir':'/'}).encode()
            if 'inspect' in argv:return json.dumps([image]).encode()
            if 'rev-parse' in argv:return ('c'*40).encode()
            if 'archive' in argv or 'run' in argv:self.fail('executed beyond source mismatch')
            return b''
        if not hasattr(d.worker.os,'geteuid'):self.skipTest('POSIX worker')
        with tempfile.TemporaryDirectory() as tmp,patch.object(d.worker.os,'geteuid',return_value=0),\
                patch.object(d.worker,'private_root'),patch.object(d.worker,'checked',side_effect=checked),\
                patch.object(d.worker.shutil,'disk_usage',return_value=Mock(free=100*1024**3)):
            result=d.worker.run(self.job,self.request['image'],Path(tmp),expected_source_sha='a'*40,run_id=self.request['run_id'])
        self.assertEqual(result['status'],'failed');self.assertFalse(result['container_started'])


if __name__=='__main__':unittest.main()

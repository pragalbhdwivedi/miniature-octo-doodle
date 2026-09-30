"""Opt-in real PostgreSQL acceptance; only a dedicated throwaway test database."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import re
import unittest
import uuid

spec=importlib.util.spec_from_file_location('state',Path(__file__).resolve().parents[1]/'scripts/controller_state.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


@unittest.skipUnless(os.environ.get('GATEWAYAI_CONTROLLER_TEST_CONFIG'),'Opt-in PostgreSQL target required')
class PostgresTests(unittest.TestCase):
    def test_pipeline_budget_transitions_and_replay(self):
        config=json.loads(Path(os.environ['GATEWAYAI_CONTROLLER_TEST_CONFIG']).read_text())
        self.assertRegex(config['database'],r'^gatewayai_controller_test_[a-f0-9]{8}$')
        store=s.Store(**config)
        version=store.query('SELECT to_jsonb(version) FROM controller.schema_version;')
        if version not in (2,3):self.skipTest('Review pipeline schema not applied')
        run=uuid.uuid4().hex
        req={'run_id':run,'plan':{'project':'synthetic','task_id':run,'source_sha':'a'*40}}
        store.claim(req,uuid.uuid4().hex*2);store.finish(run,'review_required',{'artifact_sha256':'c'*64})
        spec={'source_sha':'a'*40,'artifact_sha256':'c'*64,'budget_micro_usd':1000}
        store.begin_pipeline(run,spec,'d'*64,100)
        with self.assertRaises(RuntimeError):store.begin_pipeline(run,spec,'d'*64,100)
        other={'run_id':uuid.uuid4().hex,'plan':{'project':'synthetic','task_id':uuid.uuid4().hex,'source_sha':'a'*40}}
        with self.assertRaises(RuntimeError):store.claim(other,'e'*64)
        store.reserve_pipeline(run,'review0',200,'f'*64)
        with self.assertRaises(RuntimeError):store.reserve_pipeline(run,'review0',200,'f'*64)
        store.step_pipeline(run,'reviewing','repairing',{})
        store.reserve_pipeline(run,'repair',400,'f'*64)
        store.step_pipeline(run,'repairing','re_reviewing',{})
        with self.assertRaises(RuntimeError):store.reserve_pipeline(run,'review1',301,'f'*64)
        store.reserve_pipeline(run,'review1',300,'f'*64)
        self.assertEqual(store.pipeline(run)['debit'],1000)
        store.step_pipeline(run,'re_reviewing','approved',{})
        with self.assertRaises(RuntimeError):store.step_pipeline(run,'approved','repairing',{})
        store.step_pipeline(run,'approved','publishing',{})
        store.step_pipeline(run,'publishing','published',{'synthetic':True})
        self.assertEqual(store.get(run)['state'],'published')
        with self.assertRaises(RuntimeError):store.step_pipeline(run,'published','publishing',{})

    def test_telegram_exact_decision_and_atomic_publication_gate(self):
        config=json.loads(Path(os.environ['GATEWAYAI_CONTROLLER_TEST_CONFIG']).read_text())
        self.assertRegex(config['database'],r'^gatewayai_controller_test_[a-f0-9]{8}$')
        store=s.Store(**config)
        if store.query('SELECT to_jsonb(version) FROM controller.schema_version;')!=3:
            self.skipTest('Telegram approval schema not applied')
        run=uuid.uuid4().hex;identity=uuid.uuid4().hex
        req={'run_id':run,'plan':{'project':'synthetic','task_id':identity,'source_sha':'a'*40}}
        store.claim(req,uuid.uuid4().hex*2)
        store.finish(run,'review_required',{'artifact_sha256':'c'*64})
        store.begin_pipeline(run,{'source_sha':'a'*40,'artifact_sha256':'c'*64,'budget_micro_usd':1000},'d'*64,0)
        store.step_pipeline(run,'reviewing','approved',{'tests_passed':True})
        approval_id=uuid.uuid4().hex;digest='e'*64;update_id=uuid.uuid4().int%(2**62)
        for lifetime in (0,3601):
            with self.assertRaises(RuntimeError):
                store.request_approval(uuid.uuid4().hex,run,digest,12345,12345,lifetime)
        self.assertEqual(store.request_approval(approval_id,run,digest,12345,12345,900)['state'],'pending')
        with self.assertRaises(RuntimeError):store.request_approval(uuid.uuid4().hex,run,digest,12345,12345,900)
        with self.assertRaises(RuntimeError):store.decide_approval(approval_id,digest,'approved',12346,12345,update_id)
        with self.assertRaises(RuntimeError):store.decide_approval(approval_id,'f'*64,'approved',12345,12345,update_id)
        self.assertEqual(store.decide_approval(approval_id,digest,'approved',12345,12345,update_id)['state'],'approved')
        with self.assertRaises(RuntimeError):store.decide_approval(approval_id,digest,'rejected',12345,12345,update_id)
        with self.assertRaises(RuntimeError):store.consume_approval(approval_id,run,'f'*64,{})
        self.assertEqual(store.consume_approval(approval_id,run,digest,{'receipt':'reviewed'})['state'],'consumed')
        self.assertEqual(store.pipeline(run)['state'],'publishing')
        with self.assertRaises(RuntimeError):store.consume_approval(approval_id,run,digest,{})
        store.step_pipeline(run,'publishing','published',{})
        self.assertEqual(store.get(run)['state'],'published')

    def test_atomic_claims_audit_restart_and_replay(self):
        config=json.loads(Path(os.environ['GATEWAYAI_CONTROLLER_TEST_CONFIG']).read_text())
        self.assertRegex(config['database'],r'^gatewayai_controller_test_[a-f0-9]{8}$')
        store=s.Store(config['container'],config['database'])
        def request(task=None):
            return {'run_id':uuid.uuid4().hex,'plan':{'project':'synthetic','task_id':task or uuid.uuid4().hex,'source_sha':'a'*40}}
        def claim(req):
            try:return store.claim(req,uuid.uuid4().hex*2)
            except RuntimeError:return None
        req=request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(claim,[req,req]))
        self.assertEqual(sum(r is not None for r in rows),1)
        row=next(r for r in rows if r)
        # New client/process connection sees the committed row and crash ambiguity.
        self.assertEqual(s.Store(**config).get(req['run_id'])['state'],'dispatching')
        self.assertIsNone(claim(request()))  # Host single-flight.
        store.finish(req['run_id'],'uncertain',{'synthetic':'interrupted'})
        self.assertIsNone(claim(request()))  # No lease expiration/retry.
        store.finish(req['run_id'],'failed',{'synthetic':'operator evidence'})
        with self.assertRaises(RuntimeError):store.finish(req['run_id'],'dispatching',{})
        with self.assertRaises(RuntimeError):store.finish(req['run_id'],'failed',{})
        repeat=request(req['plan']['task_id'])
        self.assertIsNone(claim(repeat))  # Permanent project/task/source identity.
        req2=request();self.assertIsNotNone(claim(req2))
        store.finish(req2['run_id'],'review_required',{'synthetic':'artifact'})
        advanced=request(req2['plan']['task_id']);advanced['plan']['source_sha']='b'*40
        self.assertIsNone(claim(advanced))  # Pending review still owns task.
        events=store.query('SELECT jsonb_agg(state ORDER BY sequence) FROM controller.events WHERE run_id='+s.literal(req['run_id'])+" #>> '{}';")
        self.assertEqual(events,['dispatching','uncertain','failed'])
        for sql in ['DELETE FROM controller.events;', 'UPDATE controller.runs SET state=\'failed\';',
                    'CREATE TABLE controller.unauthorized(id int);']:
            with self.assertRaises(RuntimeError):store.query(sql)
        self.assertEqual(store.get(req['run_id'])['request_sha256'],row['request_sha256'])


if __name__=='__main__':unittest.main()

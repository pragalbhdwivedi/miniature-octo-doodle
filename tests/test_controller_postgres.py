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

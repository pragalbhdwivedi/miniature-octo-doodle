"""External completion releases a local claim without altering failed evidence."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import release_sup_000016_claim as operator
import reconcile_sup_000016 as original


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.dbpath=Path(temp.name)/'coordination.sqlite3'
        @contextmanager
        def connect():
            db=sqlite3.connect(self.dbpath)
            try:
                db.row_factory=sqlite3.Row
                with db:yield db
            finally:db.close()
        self.coordinator=SimpleNamespace(connect=connect)
        self.packet={'repository':'https://github.com/'+original.REPO,'branch':'main','owner':'gemini','source':{'sha':original.SOURCE},
                     'write_paths':['gateway/jev.py']}
        with connect() as db:
            db.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,state TEXT,packet TEXT,result TEXT,error TEXT)')
            db.execute('INSERT INTO tasks VALUES(?,?,?,?,?)',(operator.CHILD,'human_review_required',
                json.dumps(self.packet),'saved failed candidate','original error'))
        self.snapshot={'ongoing':{'lease_active':False},'jobs':[
            {'id':original.JOB,'supervisor_id':original.TASK,'state':'blocked','attempt':0,
             'child_id':operator.CHILD,'source_sha':original.SOURCE,'write_paths':['gateway/jev.py']}],
            'supervision':{'revision':44,'by_key':{original.JOB:original.TASK},'tasks':{
                original.TASK:{'history':[{'state':'blocked','attempt':0,'evidence_digest':original.FAILED_DIGEST}],
                    'external_resolution':{'kind':'operator_merged_pr','source_sha':original.SOURCE,
                        'url':original.URL,'merge_sha':original.MERGE,
                        'failed_evidence_digest':original.FAILED_DIGEST,'failed_receipt_sha256':original.FAILED_RECEIPT}}}}}

    def row(self):
        with self.coordinator.connect() as db:return dict(db.execute('SELECT * FROM tasks').fetchone())

    def test_preview_then_release_keeps_row_evidence_and_audits_original(self):
        before=self.row();snapshot=copy.deepcopy(self.snapshot)
        self.assertEqual(operator.release(self.coordinator,self.snapshot)['state'],'preview')
        self.assertEqual(self.row(),before)
        result=operator.release(self.coordinator,self.snapshot,apply=True,expected_revision=44)
        self.assertEqual(result['state'],'released')
        self.assertEqual(self.row(),{**before,'state':'closed'})
        self.assertEqual(self.snapshot,snapshot)
        with self.coordinator.connect() as db:
            receipt=json.loads(db.execute('SELECT record FROM external_claim_releases').fetchone()[0])
        self.assertEqual(receipt['original_row'],before)
        self.assertEqual(operator.release(self.coordinator,self.snapshot)['state'],'already_released')

    def test_stale_revision_running_claim_and_active_lease_fail_closed(self):
        before=self.row()
        with self.assertRaises(ValueError):operator.release(self.coordinator,self.snapshot,apply=True,expected_revision=43)
        self.assertEqual(self.row(),before)
        self.snapshot['ongoing']['lease_active']=True
        with self.assertRaises(ValueError):operator.release(self.coordinator,self.snapshot)
        self.snapshot['ongoing']['lease_active']=False
        with self.coordinator.connect() as db:db.execute('UPDATE tasks SET state="coding"')
        with self.assertRaises(ValueError):operator.release(self.coordinator,self.snapshot)

    def test_wrong_source_or_resolution_retains_original_claim(self):
        before=self.row()
        self.snapshot['jobs'][0]['source_sha']='f'*40
        with self.assertRaises(ValueError):operator.release(self.coordinator,self.snapshot,apply=True,expected_revision=44)
        self.assertEqual(self.row(),before)

    def test_foreign_repository_or_branch_cannot_release_claim(self):
        for field,value in (('repository','https://example.com/'+original.REPO),('branch','other')):
            with self.subTest(field=field):
                packet={**self.packet,field:value}
                with self.coordinator.connect() as db:
                    db.execute('UPDATE tasks SET packet=?',(json.dumps(packet),))
                before=self.row()
                with self.assertRaises(ValueError):operator.release(self.coordinator,self.snapshot,apply=True,expected_revision=44)
                self.assertEqual(self.row(),before)


if __name__=='__main__':unittest.main()

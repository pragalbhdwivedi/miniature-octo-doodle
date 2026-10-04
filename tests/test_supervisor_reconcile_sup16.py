"""Operator reconciliation exercises the real board reducer without network or VM state."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import reconcile_sup_000016 as operator
import supervisor_board as board


class Store:
    def __init__(self, state):
        self.value=state

    def read(self):
        return {'value':copy.deepcopy(self.value)}

    def mutate(self, operation):
        return operation(self.value)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.state={'ongoing':{'enabled':True,'lease':None,'jobs':[
            {'id':operator.JOB,'repo':'gatewayai','state':'queued','attempt':0,
             'owner':'gemini','title':'Validate choice route','source_sha':operator.SOURCE,
             'prompt':'Validate non-string route.','write_paths':['gateway/jev.py']}],
            'policy':{}},'questions':[]}
        board.ensure(self.state,now='2026-10-03T18:07:46+00:00')
        ledger=self.state['supervision']
        meta=ledger['tasks'].pop('SUP-000001')
        meta['id']=operator.TASK
        ledger['tasks'][operator.TASK]=meta
        ledger['by_key'][operator.JOB]=operator.TASK
        ledger['next_id']=17
        job=self.state['ongoing']['jobs'][0]
        job['supervisor_id']=operator.TASK
        job.update(state='blocked',error='Source validation failed; no replay.',
                   coding={'proposal':'invalid candidate'},tests={'passed':False})
        board.record(self.state,now='2026-10-03T18:09:28+00:00')
        self.digest=meta['history'][-1]['evidence_digest']
        self.store=Store(self.state)

    def test_preview_then_apply_preserves_failed_candidate_and_audit(self):
        original=copy.deepcopy(self.state)
        with patch.object(operator,'verify_github'),patch.object(operator,'FAILED_DIGEST',self.digest):
            preview=operator.run(self.store)
            self.assertEqual(preview['state'],'preview')
            self.assertEqual(self.state,original)
            result=operator.run(self.store,apply=True,expected_revision=preview['revision'])
        self.assertTrue(result['original_attempt_preserved'])
        self.assertEqual(self.state['ongoing']['jobs'],original['ongoing']['jobs'])
        self.assertEqual(self.state['supervision']['tasks'][operator.TASK]['history'],
                         original['supervision']['tasks'][operator.TASK]['history'])
        task=next(t for t in board.snapshot(self.state)['tasks'] if t['id']==operator.TASK)
        self.assertEqual(task['state'],'completed')
        self.assertEqual(task['review_state'],'merged_external')
        self.assertEqual(task['error'],'Source validation failed; no replay.')
        self.assertFalse(task['progress']['draft_recorded'])

    def test_stale_revision_has_no_effect(self):
        original=copy.deepcopy(self.state)
        with patch.object(operator,'verify_github'),patch.object(operator,'FAILED_DIGEST',self.digest):
            with self.assertRaises(board.ConflictError):
                operator.run(self.store,apply=True,
                             expected_revision=self.state['supervision']['revision']-1)
        self.assertEqual(self.state,original)


if __name__=='__main__':
    unittest.main()

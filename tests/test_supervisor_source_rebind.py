"""Pre-inference recovery preserves original failures and cannot replay a coder."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import rebind_sup_000023 as operator
import supervisor_board as board


class RebindTests(unittest.TestCase):
    def setUp(self):
        self.state={'ongoing':{'enabled':True,'lease':None,'jobs':[{'id':operator.JOB,
            'state':'blocked','blocked_stage':'admit','attempt':0,'source_sha':'a'*40,
            'owner':'gemini','title':'Unstarted task','error':'Original admission failure'}],'policy':{}},'questions':[]}
        board.ensure(self.state)
        ledger=self.state['supervision'];meta=ledger['tasks'].pop('SUP-000001');meta['id']=operator.TASK
        ledger['tasks'][operator.TASK]=meta;ledger['by_key'][operator.JOB]=operator.TASK
        self.state['ongoing']['jobs'][0]['supervisor_id']=operator.TASK
        self.fields={'expected_revision':ledger['revision'],'old_sha':'a'*40,'new_sha':'b'*40,'paths_sha256':'c'*64}

    def test_new_attempt_keeps_complete_failed_job_and_history(self):
        job=copy.deepcopy(self.state['ongoing']['jobs'][0])
        history=copy.deepcopy(self.state['supervision']['tasks'][operator.TASK]['history'])
        result=operator.rebind(self.state,**self.fields)
        self.assertEqual(result['attempt'],1)
        meta=self.state['supervision']['tasks'][operator.TASK]
        self.assertEqual(meta['source_rebindings'][0]['original_job'],job)
        self.assertEqual(meta['history'],history)
        self.assertEqual(self.state['ongoing']['jobs'][0]['state'],'queued')

    def test_stale_revision_or_existing_model_evidence_cannot_rebind(self):
        for updates in ({'child_id':'child'},{'coding':{'candidate':'saved'}},{'attempt':1},{'state':'ready_test'}):
            with self.subTest(updates=updates):
                candidate=copy.deepcopy(self.state);candidate['ongoing']['jobs'][0].update(updates)
                before=copy.deepcopy(candidate)
                with self.assertRaises(ValueError):operator.rebind(candidate,**self.fields)
                self.assertEqual(candidate,before)
        before=copy.deepcopy(self.state)
        with self.assertRaises(ValueError):operator.rebind(self.state,**{**self.fields,'expected_revision':-1})
        self.assertEqual(self.state,before)


if __name__=='__main__':unittest.main()

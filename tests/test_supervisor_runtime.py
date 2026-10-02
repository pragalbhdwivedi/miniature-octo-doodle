"""Offline board integration contracts; no GitHub or Telegram transports."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import supervisor_board as board
import supervisor_runtime as runtime
import test_supervisor_board as fixture


class SupervisorRuntimeTests(unittest.TestCase):
    def setUp(self):
        base=fixture.SupervisorBoardTests();base.setUp();self.s=base.s
        self.s.update(outbox=[],events=[])
        self.s['ongoing'].update(calls=0,day='2026-10-02')
        self.j=self.s['ongoing']['jobs'][0]
        self.j.update(repository='pragalbhdwivedi/aadi',state='draft_ready',
            coding={'route':{'model':'actual-coder'},'confidence':7},tests={'passed':True},
            review={'route':{'model':'actual-reviewer'},'verdict':'pass','confidence':8},
            publication={'commit':'c'*40,'pull_request':{'number':17,
                'url':'https://github.com/pragalbhdwivedi/aadi/pull/17','head_sha':'c'*40,
                'draft':True,'base':'Dev','branch':'supervisor/identity-one'}})
        board.record(self.s)

    def observation(self,**kw):
        return {'repository':'pragalbhdwivedi/aadi','number':17,
            'url':'https://github.com/pragalbhdwivedi/aadi/pull/17','state':'draft','head_sha':'c'*40,
            'head_ref':'supervisor/identity-one','base':'Dev','draft':True,'merged':False,
            'review_decisions':{},'requested_changes':[],**kw}

    def sync(self,p=None):
        return runtime.rpc(self.s,{'action':'ongoing_pr_sync','job_id':'identity-one',
                                  'result':p or self.observation()})

    def correction(self):
        return board.action(self.s,{'action':'request_changes','task_id':'SUP-000001',
            'text':'Add the missing assertion.','request_id':'owner-review',
            'revision':self.s['supervision']['revision']})

    def consume(self,verified_jobs=None):
        return runtime.rpc(self.s,{'action':'ongoing_consume_corrections',
            'verified_jobs':['identity-one'] if verified_jobs is None else verified_jobs})

    def review(self,**kw):
        return {'id':99,'actor':'pragalbhdwivedi','actor_type':'User','state':'CHANGES_REQUESTED',
                'body':'Add the missing assertion.','at_head':True,'commit_id':'c'*40,
                'body_truncated':False,**kw}

    def test_pr_identity_repository_number_url_head_validation(self):
        for delta in ({'repository':'pragalbhdwivedi/miniature-octo-doodle'},
                      {'url':'https://github.com/pragalbhdwivedi/aadi/pull/18'},
                      {'number':18},{'head_sha':'invalid'},{'state':'unknown'}):
            with self.subTest(delta=delta),self.assertRaises(ValueError):
                self.sync(self.observation(**delta))
        self.assertNotIn('pr_observation',self.j)
        self.assertTrue(self.sync()['changed'])
        before=copy.deepcopy(self.s)
        self.assertFalse(self.sync()['changed'])
        self.assertEqual(self.s['supervision'],before['supervision'])
        self.assertEqual(self.j['pr_observation'],before['ongoing']['jobs'][0]['pr_observation'])

    def test_untrusted_actor_and_bot_reviews_do_not_create_work_or_approval(self):
        for actor,kind in [('untrusted','User'),('pragalbhdwivedi','Bot')]:
            for verdict in ('APPROVED','CHANGES_REQUESTED'):
                review=self.review(actor=actor,actor_type=kind,state=verdict)
                self.sync(self.observation(review_decisions={actor:review},
                    requested_changes=[review] if verdict=='CHANGES_REQUESTED' else []))
                self.assertFalse(self.s['supervision']['corrections'])
                self.assertEqual(self.s['supervision']['tasks']['SUP-000001']['review_state'],'not_reviewed')
                self.assertEqual(self.j['state'],'draft_ready')

    def test_trusted_current_review_is_idempotent_and_old_or_truncated_reviews_held(self):
        review=self.review()
        self.sync(self.observation(review_decisions={review['actor']:review},requested_changes=[review]))
        self.assertEqual(len(self.s['supervision']['corrections']),1)
        self.assertEqual(self.s['supervision']['corrections'][0]['state'],'rerun_waiting')
        self.sync(self.observation(review_decisions={review['actor']:review},requested_changes=[review]))
        self.assertEqual(len(self.s['supervision']['corrections']),1)
        for idx,fields in enumerate(({'at_head':False,'commit_id':'d'*40},{'body_truncated':True}),100):
            review=self.review(id=idx,**fields)
            self.sync(self.observation(review_decisions={review['actor']:review},requested_changes=[review]))
            self.assertEqual(self.s['supervision']['corrections'][-1]['state'],'reconciliation_required')

    def test_observed_approval_or_merge_never_grants_execution_authority(self):
        review=self.review(state='APPROVED')
        self.sync(self.observation(review_decisions={review['actor']:review}))
        self.assertEqual(self.s['supervision']['tasks']['SUP-000001']['review_state'],'reviewed')
        self.assertFalse(self.s['supervision']['corrections'])
        self.sync(self.observation(state='merged',merged=True,draft=False))
        self.assertEqual(self.s['supervision']['tasks']['SUP-000001']['review_state'],'merged')
        self.assertEqual(self.j['state'],'draft_ready')
        self.assertFalse(self.s['supervision']['corrections'])
        self.assertIsNone(self.s['ongoing']['lease'])

    def test_correction_consumption_is_durable_once_and_preserves_original_evidence(self):
        self.sync();self.correction()
        correction=self.s['supervision']['corrections'][0]
        old=self.s['supervision']['evidence'][correction['evidence_digest']]
        result=self.consume()
        self.assertEqual(result['consumed'],1)
        self.assertEqual(self.j['state'],'queued')
        self.assertEqual(self.j['attempt'],1)
        self.assertEqual(correction['state'],'running')
        self.assertNotIn('coding',self.j)
        self.assertEqual(old['coding']['route']['model'],'actual-coder')
        self.assertEqual(self.consume()['consumed'],0)
        self.assertEqual(self.j['attempt'],1)
        self.assertEqual(self.s['outbox'][-1]['task_id'],'SUP-000001')

    def test_failed_current_observation_does_not_consume_cached_pr_state(self):
        self.sync();self.correction()
        self.assertEqual(self.consume(verified_jobs=[])['consumed'],0)
        self.assertEqual(self.j['state'],'draft_ready')
        self.assertEqual(self.j['attempt'],0)

    def test_pauses_and_any_active_lease_hold_correction(self):
        self.sync();self.correction()
        for delta in ({'enabled':False},{'lease':{'token':'private','job_id':'gateway-one'}}):
            before=copy.deepcopy(self.s['ongoing'])
            self.s['ongoing'].update(delta)
            self.assertEqual(self.consume()['consumed'],0)
            self.assertEqual(self.j['attempt'],0)
            self.s['ongoing'].update(before)
            self.j=self.s['ongoing']['jobs'][0]
        board.action(self.s,{'action':'pause','task_id':'SUP-000001','request_id':'pause',
            'revision':self.s['supervision']['revision']})
        self.assertEqual(self.consume()['consumed'],0)

    def test_non_draft_stale_head_scope_and_attempt_drift_require_reconciliation(self):
        for change in ('open','head','scope','attempt','repository','blocked'):
            with self.subTest(change=change):
                self.setUp();self.sync();self.correction()
                if change=='open': self.j['pr_observation']['state']='open'
                elif change=='head': self.j['pr_observation']['head_sha']='d'*40
                elif change=='scope': self.j['write_paths']=['tests/other.py']
                elif change=='repository': self.j['repository']='pragalbhdwivedi/miniature-octo-doodle'
                elif change=='attempt': self.j['attempt']=1
                else:self.j['state']='blocked'
                before_attempt=self.j['attempt']
                self.assertEqual(self.consume()['consumed'],0)
                self.assertEqual(self.j['attempt'],before_attempt)
                self.assertNotEqual(self.s['supervision']['corrections'][0]['state'],'running')

    def test_notice_and_telegram_reply_stay_bound_to_task(self):
        runtime.notice(self.s,self.j,'Draft ready for review.')
        item=self.s['outbox'][-1]
        self.assertEqual(item['task_id'],'SUP-000001')
        self.assertIn('actual-coder',item['text'])
        self.assertIn('actual-reviewer',item['text'])
        self.s['supervision']['message_tasks']={'50':'SUP-000001'}
        update={'update_id':10,'message':{'text':'Explain this result.','reply_to_message':{'message_id':50}}}
        self.assertTrue(runtime.conversation(self.s,update))
        self.assertEqual(self.s['questions'][-1]['task_id'],'SUP-000001')
        count=len(self.s['questions'])
        # Parent Telegram offset reducer rejects duplicate updates before this
        # function. Even a direct invalid replay cannot enqueue another question.
        with self.assertRaises(board.ConflictError):runtime.conversation(self.s,update)
        self.assertEqual(len(self.s['questions']),count)

    def test_telegram_changes_cancel_and_exact_task_token(self):
        self.assertTrue(runtime.conversation(self.s,{'update_id':10,'callback_query':{'data':'st:SUP-000001:changes'}}))
        self.assertTrue(runtime.conversation(self.s,{'update_id':11,'message':{'text':'/cancel'}}))
        self.assertNotIn('pending_reply',self.s['supervision'])
        self.assertFalse(runtime.conversation(self.s,{'update_id':12,'message':{'text':'SUP-0000010 is a different task'}}))
        runtime.conversation(self.s,{'update_id':13,'callback_query':{'data':'st:SUP-000001:changes'}})
        runtime.conversation(self.s,{'update_id':14,'message':{'text':'Please revise the assertion.'}})
        self.assertEqual(self.s['supervision']['corrections'][-1]['task_id'],'SUP-000001')
        self.assertFalse(self.s['questions'])


if __name__=='__main__':unittest.main()

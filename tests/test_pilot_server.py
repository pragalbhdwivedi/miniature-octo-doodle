"""Offline pilot transport/state contracts; never contact a provider or database."""
import base64
import copy
from datetime import datetime, timedelta, timezone
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import pilot_server as server
import pilot_state as state


class FakeStore(server.Store):
    """Exercise the actual mutate CAS retry loop with an in-memory SQL boundary."""
    def __init__(self, value, trace=None):
        self.value=copy.deepcopy(value)
        self.revision=0
        self.trace=trace if trace is not None else []
        self.conflict=False

    def query(self, sql):
        if sql=='SELECT controller.pilot_read();':
            self.trace.append('read')
            return {'revision':self.revision,'value':copy.deepcopy(self.value)}
        match=re.fullmatch(r"SELECT to_jsonb\(controller\.pilot_cas\((\d+),convert_from\(decode\('([A-Za-z0-9+/=]+)','base64'\),'UTF8'\)::jsonb\)\);",sql)
        if not match: raise AssertionError('Unexpected SQL')
        self.trace.append('cas')
        if self.conflict:
            self.conflict=False
            self.revision+=1
            state.event(self.value,'Concurrent operator event')
            return False
        if int(match[1])!=self.revision: return False
        self.value=json.loads(base64.b64decode(match[2]))
        self.revision+=1
        return True


class PilotServerTests(unittest.TestCase):
    def test_local_questions_remain_available_after_coding_deadline(self):
        value=state.make_state('a'*40)
        value['batch']['deadline']=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        value['batch']['state']='expired'
        value['questions'].append({'id':'abcd','kind':'ask','state':'pending','question':'What finished?'})
        result=state.work(value)
        self.assertEqual(result['action'],'ask')
        self.assertEqual(value['batch']['gpt_calls'],0)

    def test_uncertain_delivery_notifies_once_and_retains_exact_task(self):
        value=state.make_state('a'*40)
        value['tasks'][0].update(state='coding',coordination_task_id='child')
        request={'action':'observed','batch_id':value['batch']['id'],'task_id':'t1',
                 'coordination_task_id':'child','result':{'state':'delivery_uncertain'}}
        state.rpc(value,request);state.rpc(value,request)
        self.assertEqual(len(value['questions']),1)
        self.assertEqual(len(value['outbox']),1)
        self.assertEqual(value['tasks'][0]['state'],'coding')

    def setUp(self):
        self.config={'user_id':11,'chat_id':22,'signing_key_hex':'01'*32}
        self.key=self.config['signing_key_hex']
        self.s=state.make_state('a'*40)
        self.trace=[]
        self.store=FakeStore(self.s,self.trace)

    def callback(self, data, uid=100, user=11, chat=22, kind='private'):
        return {'update_id':uid,'callback_query':{'id':'query-'+str(uid),'data':data,
                'from':{'id':user},'message':{'chat':{'id':chat,'type':kind}}}}

    def call(self, config, method, payload):
        self.trace.append(method)
        if method=='sendMessage':
            return {'message_id':123,'chat':{'id':22}}
        if method!='answerCallbackQuery': raise AssertionError('Unexpected external action')
        return True

    def started(self):
        state.decide(self.s,state.signed(self.s,'start',self.key),self.key)
        self.store=FakeStore(self.s,self.trace)
        return self.store

    def work(self):
        return self.store.mutate(lambda s:state.rpc(s,{'action':'work'}))

    def finish(self, work, result, action='finish'):
        request={'action':action,'batch_id':work['batch']['id'],'stage':work['action'],
                 'token':work['token'],'task_id':work.get('task',{}).get('id'),'result':result}
        return self.store.mutate(lambda s:state.rpc(s,request))

    def publication(self):
        self.s['batch'].update(state='awaiting_publication',
            deadline=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
        self.s['publication']={'passed':True,'source_sha':'a'*40,'sha256':'b'*64}
        self.s['publication_digest']=state.digest(self.s['publication'])

    def test_every_button_acknowledged_before_database_and_followup(self):
        buttons=['p:'+view+':'+level for view in server.views.VIEWS for level in server.views.LEVELS]
        buttons += ['p:pause:brief','p:resume:brief','p:report:full','p:invalid:brief',
                    'not-a-control',state.signed(self.s,'start',self.key)]
        self.publication()
        buttons.append(state.signed(self.s,'publish',self.key))
        for data in buttons:
            with self.subTest(data=data):
                self.trace.clear()
                self.store=FakeStore(self.s,self.trace)
                server.process(self.store,self.config,self.callback(data),call=self.call)
                self.assertEqual(self.trace[0],'answerCallbackQuery')
                self.assertTrue(self.store.value['outbox'])

    def test_unauthorized_has_no_business_effects_and_gets_private_ack(self):
        for user,chat,kind in [(12,22,'private'),(11,23,'private'),(11,22,'group'),(True,22,'private')]:
            self.store=FakeStore(self.s,self.trace)
            update=self.callback(state.signed(self.s,'start',self.key),user=user,chat=chat,kind=kind)
            server.process(self.store,self.config,update,call=self.call)
            expected=copy.deepcopy(self.s);expected['offset']=101
            self.assertEqual(self.store.value,expected)
        self.assertNotIn('sendMessage',self.trace)

    def test_duplicate_update_acknowledged_without_repeating_action(self):
        self.started()
        update=self.callback('p:pause:brief')
        server.process(self.store,self.config,update,call=self.call)
        before=copy.deepcopy(self.store.value)
        server.process(self.store,self.config,update,call=self.call)
        self.assertEqual(self.store.value,before)
        self.assertEqual(self.trace.count('answerCallbackQuery'),2)

    def test_expired_ack_does_not_discard_action(self):
        def expired(*args):
            self.trace.append('answerCallbackQuery')
            raise RuntimeError('Expired query')
        server.process(self.store,self.config,self.callback('p:status:brief'),call=expired)
        self.assertEqual(self.store.value['offset'],101)
        self.assertTrue(self.store.value['outbox'])

    def test_signed_scope_cannot_change_or_be_replayed(self):
        decision=state.signed(self.s,'start',self.key)
        original=copy.deepcopy(self.s)
        self.s['tasks'][0]['prompt']='Different scope'
        with self.assertRaises(ValueError): state.decide(self.s,decision,self.key)
        self.assertEqual(self.s['batch']['state'],'awaiting_scope')
        state.decide(original,decision,self.key)
        with self.assertRaises(ValueError): state.decide(original,decision,self.key)

    def test_publication_binds_artifact_and_deadline(self):
        self.publication()
        decision=state.signed(self.s,'publish',self.key)
        original=copy.deepcopy(self.s)
        self.s['publication']['sha256']='c'*64
        with self.assertRaises(ValueError): state.decide(self.s,decision,self.key)
        original['batch']['deadline']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError): state.decide(original,decision,self.key)
        self.publication()
        state.decide(self.s,state.signed(self.s,'publish',self.key),self.key)
        self.s['publication']['sha256']='d'*64
        with self.assertRaises(ValueError): state.work(self.s)

    def test_cas_conflict_has_one_committed_lease_and_no_external_effect(self):
        self.started();self.store.conflict=True
        work=self.work()
        self.assertEqual(work['action'],'plan')
        self.assertEqual(list(self.store.value['leases']),[work['token']])
        self.assertEqual(self.store.value['batch']['gpt_calls'],1)
        self.assertEqual(self.trace.count('cas'),2)
        self.assertNotIn('sendMessage',self.trace)
        self.assertEqual(self.work()['action'],'idle')

    def test_finish_replay_and_invalid_result_leave_committed_state_unchanged(self):
        self.started();work=self.work()
        before=copy.deepcopy(self.store.value)
        with self.assertRaises(ValueError): self.finish(work,{'prompts':[]})
        self.assertEqual(self.store.value,before)
        self.finish(work,{'prompts':['One','Two','Three']})
        before=copy.deepcopy(self.store.value)
        with self.assertRaises(ValueError): self.finish(work,{'prompts':['One','Two','Three']})
        self.assertEqual(self.store.value,before)

    def test_pause_allows_inflight_completion_but_no_new_stage(self):
        self.started();work=self.work()
        server.process(self.store,self.config,self.callback('p:pause:brief'),call=self.call)
        self.finish(work,{'prompts':['One','Two','Three']})
        self.assertEqual(self.store.value['batch']['state'],'paused')
        self.assertEqual(self.work()['action'],'idle')
        server.process(self.store,self.config,self.callback('p:resume:brief',101),call=self.call)
        self.assertEqual(self.work()['action'],'dispatch')

    def test_deadline_and_resume_do_not_restart_inflight_or_expired_work(self):
        self.started();work=self.work()
        self.store.value['batch']['deadline']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        self.assertEqual(self.work()['action'],'idle')
        self.finish(work,{'prompts':['One','Two','Three']})
        self.assertEqual(self.store.value['batch']['state'],'expired')
        self.store.value['batch']['state']='paused'
        server.process(self.store,self.config,self.callback('p:resume:brief'),call=self.call)
        self.assertEqual(self.store.value['batch']['state'],'expired')
        self.assertEqual(self.work()['action'],'idle')

    def test_paused_publication_preparation_does_not_resume_pilot(self):
        self.started();self.store.value['batch']['state']='running'
        for task in self.store.value['tasks']: task['state']='verified'
        work=self.work()
        self.assertEqual(work['action'],'prepare_publication')
        server.process(self.store,self.config,self.callback('p:pause:brief'),call=self.call)
        self.finish(work,{'passed':True,'sha256':'b'*64})
        self.assertEqual(self.store.value['batch']['state'],'paused')
        self.assertEqual(self.store.value['batch']['resume_state'],'awaiting_publication')
        self.assertEqual(self.work()['action'],'idle')

    def test_test_failure_vetoes_model_pass_and_one_repair_is_bounded(self):
        self.started();self.store.value['batch']['state']='running'
        task=self.store.value['tasks'][0]
        task.update(state='ready_review',results={'candidates':{'codex':{'passed':False}}})
        review=self.work()
        self.finish(review,{'review':{'selected':'codex','verdict':'pass','findings':[]}})
        self.assertEqual(self.store.value['batch']['state'],'blocked')
        self.assertEqual(self.store.value['tasks'][0]['state'],'waiting_input')
        self.store.value['batch']['state']='running'
        self.store.value['tasks'][0]['state']='ready_review'
        review=self.work()
        self.finish(review,{'review':{'selected':'none','verdict':'repair','findings':['Fix test']}})
        self.assertEqual(self.store.value['tasks'][0]['attempt'],1)
        self.store.value['tasks'][0]['state']='ready_review'
        review=self.work()
        self.finish(review,{'review':{'selected':'none','verdict':'repair','findings':['Fix again']}})
        self.assertEqual(self.store.value['tasks'][0]['attempt'],1)
        self.assertEqual(self.store.value['batch']['state'],'blocked')

    def test_observed_result_binds_child_and_source_and_rejects_replay(self):
        self.started();self.store.value['batch']['state']='running'
        task=self.store.value['tasks'][0]
        task.update(state='coding',coordination_task_id='pilot-child')
        request={'action':'observed','batch_id':self.store.value['batch']['id'],'task_id':'t1',
                 'coordination_task_id':'wrong','result':{'state':'human_review_required','source_sha':'a'*40}}
        with self.assertRaises(ValueError): self.store.mutate(lambda s:state.rpc(s,request))
        request['coordination_task_id']='pilot-child';request['result']['source_sha']='b'*40
        with self.assertRaises(ValueError): self.store.mutate(lambda s:state.rpc(s,request))
        request['result']['source_sha']='a'*40
        self.store.mutate(lambda s:state.rpc(s,request))
        self.assertEqual(self.store.value['tasks'][0]['state'],'ready_test')
        with self.assertRaises(ValueError): self.store.mutate(lambda s:state.rpc(s,request))

    def test_call_budget_stops_before_reserving_work(self):
        self.started();self.store.value['batch']['gpt_calls']=10
        self.assertEqual(self.work()['action'],'idle')
        self.assertFalse(self.store.value['leases'])
        self.assertEqual(self.store.value['batch']['state'],'blocked')

    def test_delivery_reserved_before_send_and_ambiguous_delivery_never_retried(self):
        state.message(self.store.value,'Test message')
        def fail(config,method,payload):
            self.assertEqual(self.store.value['outbox'][0]['state'],'sending')
            self.trace.append(method)
            raise RuntimeError('Ambiguous transport')
        self.assertTrue(server.deliver(self.store,self.config,call=fail))
        self.assertEqual(self.store.value['outbox'][0]['state'],'uncertain')
        self.assertFalse(server.deliver(self.store,self.config,call=fail))
        self.assertEqual(self.trace.count('sendMessage'),1)

    def test_usage_snapshot_retains_records_in_comprehensive_report(self):
        self.s['totals']['2026-10-02T01:02:03Z']={'input_tokens':321,'output_tokens':87}
        snapshot=state.snapshot(self.s)
        report=server.views.report(snapshot)
        self.assertIn('321',report)
        self.assertIn('87',report)
        self.assertIn('Gpt calls',report)

    def test_worker_last_seen_only_advances_on_work_rpc(self):
        self.assertEqual(state.snapshot(self.s)['worker'],{})
        state.rpc(self.s,{'action':'work'})
        timestamp=state.snapshot(self.s)['worker']['last_seen']
        self.assertTrue(timestamp)
        state.rpc(self.s,{'action':'status'})
        self.assertEqual(self.s['worker']['last_seen'],timestamp)
        self.assertIn(timestamp,server.views.render('status','brief',state.snapshot(self.s)))

    def test_publication_evidence_and_commit_visible_in_report_and_outputs(self):
        self.publication()
        self.s['publication_result']={'published':True,'commit':'c'*40,'source_sha':'a'*40}
        snapshot=state.snapshot(self.s)
        for text in (server.views.report(snapshot),server.views.render('outputs','full',snapshot)):
            self.assertIn('c'*40,text)
            self.assertIn('a'*40,text)
            self.assertIn('Publication result',text)


if __name__=='__main__':
    unittest.main()

"""Future queue controls retain scheduling, scope and inference ownership."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import supervisor_board as board
import supervisor_future_runtime as runtime
import test_supervisor_board as fixture


def entry(index=1):
    return {'id':f'FUT-{index:06d}','project':'GatewayAI','title':f'Validate route type {index}',
        'prompt':f'Implement safe validation for route field {index} and cover its error result.',
        'scope_id':'gateway-choice-validation','priority':3,'evidence':['gateway/jev.py'],
        'acceptance':['Invalid input returns a deterministic reason.'],'dependencies':[],'risk':'routine'}


class FutureIntegrationTests(unittest.TestCase):
    def setUp(self):
        f=fixture.SupervisorBoardTests();f.setUp();self.s=f.s
        self.s['ongoing'].update(enabled=True,calls=0,day='2026-10-02',lease=None)
        self.s['ongoing']['policy']['max_calls_per_day']=80
        self.s.update(outbox=[],events=[])

    def command(self,action,rid='request-one'):
        return board.action(self.s,{'action':action,'request_id':rid,
            'revision':self.s['supervision']['revision']})

    def test_idle_not_paused(self):
        for job in self.s['ongoing']['jobs']:job['state']='draft_ready'
        self.assertEqual(board.snapshot(self.s)['work_status']['state'],'idle')
        self.s['ongoing']['enabled']=False
        self.assertEqual(board.snapshot(self.s)['work_status']['state'],'paused')

    def test_override_retains_claims_budget_and_task_pause(self):
        self.s['ongoing'].update(enabled=False,calls=80,lease={'stage':'review','token':'private'})
        self.s['ongoing']['jobs'][0].update(state='blocked',child_id='held')
        self.s['supervision']['tasks']['SUP-000001']['paused']=True
        old=copy.deepcopy(self.s['ongoing'])
        self.command('override_start')
        self.assertTrue(self.s['ongoing']['enabled'])
        self.assertEqual(self.s['ongoing']['lease'],old['lease'])
        self.assertEqual(self.s['ongoing']['calls'],80)
        self.assertEqual(self.s['ongoing']['jobs'][0]['state'],'blocked')
        self.assertTrue(self.s['supervision']['tasks']['SUP-000001']['paused'])

    def test_seed_and_next_ten_intake_are_idempotent(self):
        rows=[entry(i) for i in range(1,101)]
        runtime.rpc(self.s,{'action':'ongoing_future_seed','entries':rows})
        req={'action':'ongoing_future_prepare','scope_ids':['gateway-choice-validation']}
        runtime.rpc(self.s,req);runtime.rpc(self.s,req)
        future_intake=[i for i in self.s['supervision']['intake'] if i.get('future_id')]
        self.assertEqual(len(future_intake),10)
        self.assertEqual(len({i['future_id'] for i in future_intake}),10)
        self.assertEqual(len(board.snapshot(self.s)['future']['tasks']),100)
        self.assertIn('FUT',board.documents(self.s)['future_supervisor_tasks.md'])

    def test_generation_reserves_once_and_cannot_spend_when_paused(self):
        self.command('generate_future')
        req={'action':'ongoing_future_begin','request_id':'request-one'}
        self.s['ongoing']['enabled']=False
        self.assertFalse(runtime.rpc(self.s,req)['execute'])
        self.s['ongoing']['enabled']=True
        self.assertTrue(runtime.rpc(self.s,req)['execute'])
        self.assertFalse(runtime.rpc(self.s,req)['execute'])
        self.assertEqual(self.s['ongoing']['calls'],2)

    def test_http_controls_do_not_accept_operator_seed(self):
        with self.assertRaises(ValueError):self.command('ongoing_future_seed')

    def test_committed_backlog_has_at_least_100_valid_distinct_tasks(self):
        import supervisor_future as f
        rows=json.loads((Path(__file__).resolve().parents[1]/'config/supervisor/future_tasks.json').read_text())
        result=f.seed(self.s,rows,'2026-10-02T15:00:00+00:00')
        self.assertGreaterEqual(result['total'],100)
        self.assertEqual(len(result['added']),len(rows))
        self.assertEqual(f.seed(self.s,rows,'2026-10-02T15:01:00+00:00')['added'],[])

    def test_reject_linked_proposal_requires_pause_and_no_admitted_job(self):
        runtime.rpc(self.s,{'action':'ongoing_future_seed','entries':[entry()]})
        runtime.rpc(self.s,{'action':'ongoing_future_prepare','scope_ids':['gateway-choice-validation']})
        task=self.s['supervision']['future']['tasks'][0]
        intake=next(i for i in self.s['supervision']['intake'] if i['id']==task['intake_id'])
        req={'action':'ongoing_future_cancel','task_id':task['id'],'reason':'Already implemented in the supplied code.'}
        with self.assertRaises(ValueError):runtime.rpc(self.s,req)
        intake['paused']=True
        self.s['ongoing']['jobs'].append({'id':'admitted-future','intake_id':intake['id']})
        with self.assertRaises(ValueError):runtime.rpc(self.s,req)
        self.s['ongoing']['jobs'].pop()
        self.assertEqual(runtime.rpc(self.s,req)['state'],'cancelled')
        self.assertEqual(intake['state'],'cancelled')

    def test_review_ready_and_blocked_free_slots_without_completing_dependencies(self):
        import supervisor_future as f
        now='2026-10-02T15:00:00+00:00'
        f.seed(self.s,[entry(1),entry(2)],now)
        f.promote(self.s,['gateway-choice-validation'],now)
        for index in (1,2):
            sid=f'SUP-00010{index}'
            self.s['supervision']['intake'].append({'id':sid,'state':'admitted'})
            f.mark_intake(self.s,f'FUT-{index:06d}',sid,now)
            self.s['ongoing']['jobs'].append({'id':f'future-{index}','intake_id':sid,
                'state':'draft_ready' if index==1 else 'blocked'})
        runtime.reconcile(self.s,now)
        tasks=self.s['supervision']['future']['tasks']
        self.assertEqual([t['state'] for t in tasks],['review_ready','blocked'])
        self.s['ongoing']['jobs'][-2]['pr_observation']={'state':'merged'}
        runtime.reconcile(self.s,now)
        self.assertEqual(tasks[0]['state'],'completed')


if __name__=='__main__':unittest.main()

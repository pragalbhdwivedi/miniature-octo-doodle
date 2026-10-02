"""Read-only activity projection: reservations are distinct from saved results."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import supervisor_board as board


class SupervisorActivityTests(unittest.TestCase):
    at='2026-10-02T08:00:00+00:00'

    def setUp(self):
        self.s={'ongoing':{'enabled':True,'lease':None,'day':'2026-10-02','calls':0,
            'policy':{'max_calls_per_day':12},'jobs':[
                {'id':'local-check','owner':'local','title':'Local check','state':'local_ready',
                 'attempt':1,'repo':'aadi','source_sha':'a'*40},
                {'id':'cloud-check','owner':'codex','title':'Cloud check','state':'codex_ready',
                 'attempt':0,'repo':'gatewayai','source_sha':'b'*40},
                {'id':'gemini-check','owner':'gemini','title':'Gemini check','state':'antigravity_ready',
                 'attempt':0,'repo':'aadi','source_sha':'a'*40}]}}
        board.ensure(self.s,now=self.at)

    def tasks(self):return {t['key']:t for t in board.snapshot(self.s,now=self.at)['tasks']}

    def lease(self,stage,job='local-check',**extra):
        self.s['ongoing']['lease']={'stage':stage,'job_id':job,'started_at':self.at,
                                   'token':'PRIVATE-RESERVATION-TOKEN',**extra}

    def test_reserved_local_step_is_working_without_mutation_or_previous_model_claim(self):
        self.s['ongoing']['jobs'][0]['coding']={'route':{'model':'previous-attempt-model'},'confidence':8}
        self.lease('local')
        saved=copy.deepcopy(self.s)
        task=self.tasks()['local-check']
        self.assertEqual(task['state'],'local_ready')
        self.assertEqual(task['display_state'],'coding')
        self.assertEqual(task['execution']['stage'],'local')
        self.assertEqual(task['execution']['host'],'Laptop · local model')
        self.assertEqual(task['execution']['basis'],'reserved_stage')
        self.assertIsNone(task['execution']['model'])
        self.assertEqual(task['execution']['model_status'],'not_yet_reported')
        self.assertEqual(task['coder_model'],'previous-attempt-model')
        self.assertEqual(self.s,saved)
        self.assertNotIn('PRIVATE-RESERVATION-TOKEN',json.dumps(board.snapshot(self.s,now=self.at)))

    def test_exact_reserved_stage_changes_display_without_claiming_inference(self):
        for stage,display,model_status in [('admit','working','not_applicable'),
                ('test','testing','not_applicable'),('review','reviewing','not_yet_reported'),
                ('publish','publishing','not_applicable'),('codex','coding','not_yet_reported'),
                ('antigravity','coding','not_yet_reported')]:
            with self.subTest(stage=stage):
                self.lease(stage)
                task=self.tasks()['local-check']
                self.assertEqual(task['display_state'],display)
                self.assertEqual(task['execution']['model_status'],model_status)
                self.assertEqual(task['state'],'local_ready')
                self.assertNotIn('execution',self.tasks()['cloud-check'])

    def test_parallel_reservations_bind_only_listed_jobs_and_their_own_lane(self):
        self.lease('parallel_code',None,job_ids=['local-check','cloud-check'])
        tasks=self.tasks()
        self.assertEqual(tasks['local-check']['execution']['stage'],'local')
        self.assertEqual(tasks['cloud-check']['execution']['stage'],'codex')
        self.assertEqual(tasks['cloud-check']['execution']['host'],'Laptop · cloud CLI')
        self.assertNotIn('execution',tasks['gemini-check'])
        self.lease('plan',None)
        self.assertTrue(all('execution' not in t for t in self.tasks().values()))

    def test_pause_during_owned_work_affects_next_step_not_current_projection(self):
        self.lease('local')
        meta=self.s['supervision']['tasks']['SUP-000001']
        meta['paused']=True
        task=self.tasks()['local-check']
        self.assertTrue(task['paused'])
        self.assertTrue(task['execution']['pause_after_step'])
        self.assertEqual(task['display_state'],'coding')
        meta['paused']=False;self.s['ongoing']['enabled']=False
        self.assertTrue(self.tasks()['local-check']['execution']['pause_after_step'])
        self.s['ongoing']['lease']=None
        self.assertNotIn('execution',self.tasks()['local-check'])

    def test_exhausted_cloud_budget_does_not_label_local_work_or_next_day_as_waiting(self):
        self.s['ongoing']['calls']=12
        tasks=self.tasks()
        self.assertEqual(tasks['cloud-check']['display_state'],'waiting_budget')
        self.assertIn('Daily cloud-work budget',tasks['cloud-check']['wait_reason'])
        self.assertEqual(tasks['gemini-check']['display_state'],'waiting_budget')
        self.assertEqual(tasks['local-check']['display_state'],'local_ready')
        self.s['ongoing']['jobs'][0]['state']='ready_review'
        self.assertEqual(self.tasks()['local-check']['display_state'],'waiting_budget')
        self.s['ongoing']['day']='2026-10-01'
        self.assertFalse(any('wait_reason' in t for t in self.tasks().values()))

    def test_budget_wait_never_overrides_owned_work_or_explicit_pause(self):
        self.s['ongoing']['calls']=12
        self.lease('codex','cloud-check')
        self.assertEqual(self.tasks()['cloud-check']['display_state'],'coding')
        self.assertNotIn('wait_reason',self.tasks()['gemini-check'])
        self.s['ongoing']['lease']=None
        self.s['supervision']['tasks']['SUP-000002']['paused']=True
        self.assertEqual(self.tasks()['cloud-check']['display_state'],'codex_ready')
        self.s['ongoing']['enabled']=False
        self.assertFalse(any('wait_reason' in t for t in self.tasks().values()))

    def test_finishing_step_clears_live_projection_and_exposes_new_recorded_model(self):
        self.lease('local')
        self.assertIn('execution',self.tasks()['local-check'])
        self.s['ongoing']['lease']=None
        self.s['ongoing']['jobs'][0].update(state='ready_test',coding={
            'route':{'model':'synthetic-local-model'},'confidence':7})
        task=self.tasks()['local-check']
        self.assertNotIn('execution',task)
        self.assertEqual(task['display_state'],'ready_test')
        self.assertEqual((task['coder_model'],task['coder_confidence']),('synthetic-local-model',7))

    def test_test_count_and_pass_are_evidence_only_not_confidence(self):
        job=self.s['ongoing']['jobs'][0]
        before=self.tasks()['local-check']
        self.assertIsNone(before['tests_passed']);self.assertIsNone(before['test_count'])
        job['tests']={'passed':True,'test_count':17}
        result=self.tasks()['local-check']
        self.assertTrue(result['tests_passed']);self.assertEqual(result['test_count'],17)
        self.assertIsNone(result['coder_confidence']);self.assertIsNone(result['reviewer_confidence'])
        job['tests']={'passed':False,'test_count':4}
        self.assertFalse(self.tasks()['local-check']['tests_passed'])
        for bad in (True,-1,'17',1.5):
            job['tests']={'passed':'yes','test_count':bad}
            self.assertIsNone(self.tasks()['local-check']['tests_passed'])
            self.assertIsNone(self.tasks()['local-check']['test_count'])


if __name__=='__main__':unittest.main()

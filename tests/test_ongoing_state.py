"""Ongoing policy acceptance contracts; no providers, credentials or network."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import ongoing_state as state
import pilot_state


def job(name='gemini-tests', owner='gemini', path='tests/test_one.py'):
    return {'id':name,'title':'Synthetic '+name,'owner':owner,'risk':'reversible',
            'operation':'test_addition','paths':[path],'write_paths':[path],
            'test_files':[path],'source_sha':'a'*40,'prompt':'Add one meaningful edge test.',
            'parent_issue':1}


class OngoingStateTests(unittest.TestCase):
    def setUp(self):
        self.s=pilot_state.make_state('a'*40)
        self.s['batch']['state']='completed'
        self.catalog=[job(),job('codex-tests','codex','tests/test_two.py')]
        state.install(self.s,self.catalog)

    def finish(self,work,result):
        state.rpc(self.s,{'action':'ongoing_finish','token':work['token'],'result':result})

    def planned(self):
        work=state.work(self.s)
        self.finish(work,{'order':[j['id'] for j in self.catalog],'reason':'Independent subtasks'})

    def test_technical_hold_is_not_presented_as_owner_approval(self):
        self.s['ongoing']['jobs'][0]['state']='blocked'
        text=state.decisions(self.s)
        self.assertIn('No approval is being requested',text)
        self.assertIn(self.catalog[0]['title'],text)
        self.assertIn('technical recovery',text)
        import pilot_server,pilot_views
        pilot_server.show(self.s,'questions','brief','a'*64)
        self.assertIn('No approval is being requested',self.s['outbox'][-1]['text'])
        self.s['ongoing']['lease']={'token':'PRIVATE-LEASE-MUST-NOT-APPEAR'}
        snapshot=pilot_state.snapshot(self.s)
        report=pilot_views.report(snapshot)
        self.assertIn('Ongoing assigned work',report)
        self.assertNotIn('PRIVATE-LEASE-MUST-NOT-APPEAR',report)

    def test_catalog_sync_admits_once_and_preserves_existing_claims(self):
        original=copy.deepcopy(self.s['ongoing']['jobs'])
        extra=job('local-tests','local','tests/test_three.py')
        request={'action':'ongoing_sync','catalog':self.catalog+[extra]}
        self.assertEqual(state.rpc(self.s,request),{'added':1})
        self.assertEqual(state.rpc(self.s,request),{'added':0})
        self.assertEqual(self.s['ongoing']['jobs'][:2],original)
        request['catalog'][0]=dict(request['catalog'][0],prompt='Changed existing work')
        with self.assertRaises(ValueError):state.rpc(self.s,request)
        with self.assertRaises(ValueError):state.rpc(self.s,{'action':'ongoing_sync','catalog':[extra]})

    def admit(self):
        work=state.work(self.s)
        self.assertEqual(work['action'],'admit')
        self.finish(work,{'child_id':'ongoing-'+work['job']['id']+'-a0',
                         'issue':{'state':'confirmed','url':'https://github.com/example/issues/1','number':1}})
        return work

    def test_parallel_distinct_owner_admission_before_codex_call(self):
        self.planned()
        first=self.admit();second=self.admit()
        self.assertEqual({first['job']['owner'],second['job']['owner']},{'gemini','codex'})
        self.assertFalse(set(first['job']['write_paths'])&set(second['job']['write_paths']))
        self.assertEqual(state.work(self.s)['action'],'codex')
        self.assertEqual([j['state'] for j in self.s['ongoing']['jobs']],['coding','codex_ready'])

    def test_lease_blocks_repeated_poll_and_wrong_or_replayed_finish(self):
        work=state.work(self.s)
        calls=self.s['ongoing']['calls']
        self.assertEqual(state.work(self.s)['action'],'idle')
        self.assertEqual(self.s['ongoing']['calls'],calls)
        with self.assertRaises(ValueError):
            self.finish({**work,'token':'wrong'}, {'order':[j['id'] for j in self.catalog]})
        self.finish(work,{'order':[j['id'] for j in self.catalog]})
        with self.assertRaises(ValueError):
            self.finish(work,{'order':[j['id'] for j in self.catalog]})

    def test_planner_cannot_replace_scope_or_policy(self):
        work=state.work(self.s)
        original=copy.deepcopy(self.s['ongoing']['jobs'])
        with self.assertRaises(ValueError):
            self.finish(work,{'order':['delete-data','codex-tests'],'policy':{'destructive':'automatic'}})
        self.assertEqual(self.s['ongoing']['jobs'],original)
        self.assertEqual(self.s['ongoing']['policy']['destructive'],'owner_required')
        self.finish(work,{'order':[j['id'] for j in self.catalog],
                          'jobs':[job('unapproved')], 'policy':{'destructive':'automatic'}})
        self.assertEqual(self.s['ongoing']['jobs'],original)
        self.assertEqual(self.s['ongoing']['policy']['destructive'],'owner_required')

    def test_destructive_catalog_and_duplicate_ids_rejected(self):
        for catalog in ([{**job(),'risk':'destructive'}],[{**job(),'operation':'delete_data'}],
                        [job(),job()]):
            s=pilot_state.make_state('a'*40);s['batch']['state']='completed'
            with self.assertRaises(ValueError):state.install(s,catalog)
            self.assertNotIn('ongoing',s)

    def test_daily_budget_prevents_new_model_stage_and_resets_next_day(self):
        self.planned()
        o=self.s['ongoing'];o['jobs'][0]['state']='blocked';o['jobs'][1]['state']='codex_ready'
        o['calls']=o['policy']['max_calls_per_day']
        self.assertEqual(state.work(self.s),{'action':'idle','reason':'daily_model_limit'})
        self.assertIsNone(o['lease'])
        o['day']=(datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat()
        self.assertEqual(state.work(self.s)['action'],'codex')
        self.assertEqual(o['calls'],1)
        self.assertEqual(state.work(self.s)['action'],'idle')
        self.assertEqual(o['calls'],1)

    def test_only_one_repair_then_hold(self):
        self.planned();self.admit();self.admit()
        j=self.s['ongoing']['jobs'][0]
        j['state']='ready_test'
        self.finish(state.work(self.s),{'passed':False,'summary':'Assertion failed'})
        self.assertEqual((j['state'],j['attempt']),('queued',1))
        j['state']='ready_test'
        self.finish(state.work(self.s),{'passed':False,'summary':'Still failed'})
        self.assertEqual((j['state'],j['attempt']),('blocked',1))
        self.assertEqual(state.work(self.s)['action'],'codex')

    def test_overlapping_paths_do_not_run_together(self):
        self.s['ongoing']['jobs'][1]['write_paths']=['tests/test_one.py']
        self.planned();self.admit()
        work=state.work(self.s)
        self.assertEqual(work['action'],'observe')
        self.assertEqual(self.s['ongoing']['jobs'][1]['state'],'queued')

    def test_observed_child_identity_must_match(self):
        self.planned();self.admit()
        j=self.s['ongoing']['jobs'][0]
        with self.assertRaises(ValueError):
            state.rpc(self.s,{'action':'ongoing_observed','job_id':j['id'],
                       'child_id':'other-child','result':{'state':'human_review_required'}})
        self.assertEqual(j['state'],'coding')

    def test_publication_receipt_shows_actual_confirmed_pr_url(self):
        self.planned()
        j=self.s['ongoing']['jobs'][0];j.update(state='ready_publish',tests={'passed':True},review={'verdict':'pass'})
        self.s['ongoing']['jobs'][1]['state']='blocked'
        receipt={'task_id':j['id'],'source_sha':j['source_sha'],'artifact_sha256':'b'*64,
                 'commit':'c'*40,'branch':'supervisor/synthetic','merged':False,'deployed':False,
                 'pull_request':{'state':'confirmed','draft':True,'base':'Dev','branch':'supervisor/synthetic',
                    'url':'https://github.com/pragalbhdwivedi/aadi/pull/123','number':123}}
        self.finish(state.work(self.s),receipt)
        self.assertEqual(j['state'],'draft_ready')
        self.assertIn(receipt['pull_request']['url'],self.s['outbox'][-1]['text'])
        self.assertIn(receipt['pull_request']['url'],state.summary(self.s))

    def test_unconfirmed_publication_receipt_never_marks_draft_ready(self):
        self.planned()
        j=self.s['ongoing']['jobs'][0];j.update(state='ready_publish',tests={'passed':True},review={'verdict':'pass'})
        self.s['ongoing']['jobs'][1]['state']='blocked'
        work=state.work(self.s)
        with self.assertRaises(ValueError):self.finish(work,{'merged':True})
        self.assertEqual(j['state'],'ready_publish')

    def test_gemini_admission_reserves_cloud_budget_but_local_plan_does_not(self):
        self.planned()
        o=self.s['ongoing']
        self.assertEqual(o['calls'],0)
        self.admit()
        self.assertEqual(o['calls'],1)
        self.admit()
        self.assertEqual(o['calls'],1)
        state.work(self.s)
        self.assertEqual(o['calls'],2)

    def test_case_alias_write_paths_do_not_admit_together(self):
        self.s['ongoing']['jobs'][1]['write_paths']=['tests/TEST_ONE.py']
        self.planned();self.admit()
        self.assertEqual(state.work(self.s)['action'],'observe')

    def test_missing_and_cyclic_dependencies_rejected_at_install(self):
        first=job();second=job('codex-tests','codex','tests/test_two.py')
        for catalog in ([{**first,'depends_on':['missing']}],
                        [{**first,'depends_on':[second['id']]},{**second,'depends_on':[first['id']]}]):
            s=pilot_state.make_state('a'*40);s['batch']['state']='completed'
            with self.assertRaises(ValueError):state.install(s,catalog)
            self.assertNotIn('ongoing',s)

    def test_receipt_wrong_source_non_draft_or_foreign_link_denied(self):
        self.planned()
        j=self.s['ongoing']['jobs'][0]
        j.update(state='ready_publish',tests={'passed':True},review={'verdict':'pass'})
        self.s['ongoing']['jobs'][1]['state']='blocked'
        receipt={'task_id':j['id'],'source_sha':j['source_sha'],'artifact_sha256':'b'*64,
                 'commit':'c'*40,'branch':'supervisor/synthetic','merged':False,'deployed':False,
                 'pull_request':{'state':'confirmed','draft':True,'base':'Dev','branch':'supervisor/synthetic',
                    'url':'https://github.com/pragalbhdwivedi/aadi/pull/123','number':123}}
        work=state.work(self.s)
        for section,key,value in [(None,'source_sha','f'*40),(None,'task_id','other'),
                                  (None,'merged',True),('pull_request','draft',False),
                                  ('pull_request','url','https://example.invalid/pull/123')]:
            altered=copy.deepcopy(receipt)
            (altered[section] if section else altered)[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.finish(work,altered)
            self.assertEqual(j['state'],'ready_publish')

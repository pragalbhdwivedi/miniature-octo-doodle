"""Cross-project supervisor boundaries; synthetic filesystem and mocked Git only."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import coder_coordination as coordination
import ongoing_state as state
import ongoing_worker as worker
import pilot_state
import supervisor_board as board

AADI = 'pragalbhdwivedi/aadi'
GATEWAY = 'pragalbhdwivedi/miniature-octo-doodle'
SHA = 'a'*40
PATH = 'tests/test_synthetic.py'


def job(name='gateway-edge', repository=GATEWAY, owner='codex'):
    return {'id':name, 'title':'Synthetic '+name, 'repository':repository,
            'owner':owner, 'risk':'reversible', 'operation':'test_addition',
            'paths':[PATH], 'write_paths':[PATH], 'test_files':[PATH],
            'source_sha':SHA, 'prompt':'Add synthetic edge coverage.', 'parent_issue':1}


def installed(catalog):
    ledger=pilot_state.make_state(SHA)
    ledger['batch']['state']='completed'
    state.install(ledger, catalog)
    ledger['ongoing']['planned']=True
    return ledger


class ProjectSourceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.repo=Path(temp.name).resolve()
        self.remote='https://github.com/'+GATEWAY+'.git'
        self.branch='main'
        self.calls=[]
        def git(repo,*args):
            self.calls.append(args)
            replies={('rev-parse','--show-toplevel'):str(self.repo),
                     ('remote','get-url','origin'):self.remote,
                     ('status','--porcelain'):'',('rev-parse','HEAD'):SHA,
                     ('ls-remote','origin','refs/heads/'+self.branch):SHA+'\trefs/heads/'+self.branch}
            if args not in replies:raise AssertionError('Unexpected Git operation: '+repr(args))
            return replies[args].encode()
        for mocked in (patch.object(coordination.agent,'git',side_effect=git),
                       patch.object(coordination.agent,'source_files',return_value={PATH:'synthetic'})):
            mocked.start();self.addCleanup(mocked.stop)

    def test_gateway_main_source_uses_exact_admitted_remote_and_branch(self):
        result=coordination.source(self.repo,[PATH],'https://github.com/'+GATEWAY,'main')
        self.assertEqual(result,{'sha':SHA,'files':{PATH:'synthetic'}})
        self.assertIn(('ls-remote','origin','refs/heads/main'),self.calls)
        self.assertNotIn(('ls-remote','origin','refs/heads/Dev'),self.calls)

    def test_gateway_dev_aadi_main_and_unadmitted_repo_are_denied_before_git(self):
        for repository,branch in [(GATEWAY,'Dev'),(AADI,'main'),('other/repo','main')]:
            with self.subTest(repository=repository),self.assertRaises(coordination.agent.AgentError):
                coordination.source(self.repo,[PATH],'https://github.com/'+repository,branch)
        self.assertEqual(self.calls,[])

    def test_another_remote_cannot_supply_gateway_source(self):
        self.remote='https://github.com/'+AADI+'.git'
        with self.assertRaises(coordination.agent.AgentError):
            coordination.source(self.repo,[PATH],'https://github.com/'+GATEWAY,'main')
        self.assertFalse(any(call[0]=='ls-remote' for call in self.calls))

    def test_aadi_default_retains_dev_boundary(self):
        self.remote='https://github.com/'+AADI+'.git';self.branch='Dev'
        self.assertEqual(coordination.source(self.repo,[PATH])['sha'],SHA)
        self.assertIn(('ls-remote','origin','refs/heads/Dev'),self.calls)

    def test_saved_packet_cannot_cross_project_or_base(self):
        coordinator=coordination.Coordinator.__new__(coordination.Coordinator)
        coordinator.repository='https://github.com/'+GATEWAY;coordinator.branch='main'
        coordinator.source=Mock(return_value={'sha':SHA,'files':{PATH:'synthetic'}})
        packet={'repository':coordinator.repository,'branch':'main','paths':[PATH],
                'source':{'sha':SHA,'files':{PATH:'synthetic'}}}
        coordinator.fresh(packet)
        for change in ({'repository':'https://github.com/'+AADI},{'branch':'Dev'},
                       {'source':{'sha':'b'*40,'files':{PATH:'synthetic'}}}):
            with self.subTest(change=change),self.assertRaises(coordination.agent.AgentError):
                coordinator.fresh({**packet,**change})


class ProjectWorkerTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.w=worker.Worker.__new__(worker.Worker)
        self.w.repository=AADI;self.w.project_workers={};self.w.remote=Mock(return_value={})
        self.catalog_path=self.root/'catalog.json'
        self.catalog_path.write_text('[]')
        self.w.config={'source_repo':'aadi-source','output_root':'aadi-evidence',
            'ongoing_catalog':str(self.catalog_path),'ongoing_github':{'repository':AADI},
            'projects':{GATEWAY:{'source_repo':'gateway-source','output_root':'gateway-evidence',
                                   'ongoing_github':{'repository':GATEWAY,'base':'main'}}}}
        self.w.catalog={}

    def test_for_job_uses_operator_config_without_mutating_parent(self):
        original=copy.deepcopy(self.w.config)
        child=SimpleNamespace(repository=GATEWAY,catalog={})
        method=worker.Worker.for_job
        with patch.object(worker,'Worker',return_value=child) as factory:
            self.assertIs(method(self.w,job()),child)
            self.assertIs(method(self.w,job()),child)
            self.assertEqual(factory.call_count,1)
            cfg=factory.call_args.args[0]
            self.assertEqual(cfg['source_repo'],'gateway-source')
            self.assertEqual(cfg['ongoing_github'],{'repository':GATEWAY,'base':'main'})
            self.assertNotIn('projects',cfg)
            self.assertIs(factory.call_args.kwargs['remote'],self.w.remote)
        self.assertEqual(self.w.config,original)
        self.assertIs(self.w.for_job(job(repository=AADI)),self.w)
        with self.assertRaises(ValueError):self.w.for_job(job(repository='unconfigured/repo'))

    def test_project_spec_preserves_catalog_scope_and_pinned_source(self):
        self.w.repository=GATEWAY
        admitted=job();self.w.catalog={admitted['id']:copy.deepcopy(admitted)}
        self.w.coordinator=SimpleNamespace(source=Mock(return_value={'sha':SHA}))
        active={**admitted,'attempt':0,'state':'codex_ready'}
        self.assertEqual(self.w.spec(active),admitted)
        for key,value in [('repository',AADI),('source_sha','b'*40),('owner','gemini'),
                          ('write_paths',['src/production.py']),('prompt','Replace admitted scope')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.w.spec({**active,key:value})
        self.w.coordinator.source.return_value={'sha':'c'*40}
        with self.assertRaisesRegex(ValueError,'Source advanced'):self.w.spec(active)

    def test_new_catalog_task_reaches_cached_project_after_observer_tick(self):
        self.w.root=self.root/'worker';self.w.root.mkdir()
        self.w.config['supervision_enabled']=True
        admitted=job();active={**admitted,'attempt':0,'state':'queued'}
        child=worker.Worker.__new__(worker.Worker)
        child.repository=GATEWAY;child.catalog={};child.config={**self.w.config}
        child.coordinator=SimpleNamespace(source=Mock(return_value={'sha':SHA}))
        def admit(work,directory):
            child.spec(work['job'])
            return {'child_id':'ongoing-'+admitted['id']+'-a0','issue':{'number':1}}
        child.admit=admit
        self.w.project_workers[GATEWAY]=child
        def remote(request):
            return {'action':'admit','job':active,'token':'synthetic-lease'} if request['action']=='ongoing_work' else {'ok':True}
        self.w.remote=Mock(side_effect=remote)
        def observe():self.catalog_path.write_text(json.dumps([admitted]))
        with patch('supervisor_observer.Observer') as observer:
            observer.return_value.tick.side_effect=observe
            result=self.w.tick()
        self.assertEqual(result,{'state':'finished','stage':'admit'})
        self.assertTrue(any(c.args[0]['action']=='ongoing_finish' for c in self.w.remote.call_args_list))

    def test_sidecar_completion_is_observed_in_the_job_project_ledger(self):
        self.w.root=self.root/'worker';self.w.root.mkdir()
        admitted=job(owner='gemini');self.w.catalog={admitted['id']:admitted}
        active={**admitted,'attempt':0,'state':'coding','child_id':'ongoing-gateway-edge-a0'}
        self.w.coordinator=SimpleNamespace(status=Mock(side_effect=AssertionError('Wrong project ledger')))
        receipt={'state':'human_review_required','task_id':active['child_id'],'owner':'gemini','source_sha':SHA}
        child=SimpleNamespace(catalog={},coordinator=SimpleNamespace(status=Mock(return_value={'tasks':[
            {'id':active['child_id'],'state':'human_review_required','result':receipt}]})))
        self.w.project_workers[GATEWAY]=child
        self.w.remote=Mock(side_effect=lambda request: {'action':'observe','jobs':[active]}
                           if request['action']=='ongoing_work' else {'ok':True})
        self.assertEqual(self.w.tick(),{'state':'observed','model_calls':0})
        observed=[call.args[0] for call in self.w.remote.call_args_list if call.args[0]['action']=='ongoing_observed']
        self.assertEqual(observed,[{'action':'ongoing_observed','job_id':admitted['id'],
                                   'child_id':active['child_id'],'result':receipt}])
        self.w.coordinator.status.assert_not_called()


class ProjectStateTests(unittest.TestCase):
    def publication(self, repository=GATEWAY):
        ledger=installed([job(repository=repository)])
        j=ledger['ongoing']['jobs'][0]
        j.update(state='ready_publish',tests={'passed':True},review={'verdict':'pass'})
        lease=state.work(ledger)
        receipt={'task_id':j['id'],'source_sha':SHA,'artifact_sha256':'b'*64,'commit':'c'*40,
                 'repository':repository,'base':'main' if repository==GATEWAY else 'Dev',
                 'branch':'supervisor/synthetic','merged':False,'deployed':False,
                 'pull_request':{'state':'confirmed','draft':True,'base':'main' if repository==GATEWAY else 'Dev',
                    'branch':'supervisor/synthetic','url':'https://github.com/'+repository+'/pull/123','number':123}}
        return ledger,j,lease,receipt

    def test_each_project_requires_its_own_base_remote_and_exact_task_receipt(self):
        for repository in (AADI,GATEWAY):
            ledger,j,lease,receipt=self.publication(repository)
            for invalid in [dict(receipt,source_sha='f'*40),dict(receipt,task_id='different-task'),
                            dict(receipt,pull_request={**receipt['pull_request'],'base':'main' if repository==AADI else 'Dev'}),
                            dict(receipt,pull_request={**receipt['pull_request'],'url':'https://github.com/'+(GATEWAY if repository==AADI else AADI)+'/pull/123'})]:
                with self.subTest(repository=repository),self.assertRaises(ValueError):
                    state.finish(ledger,{'action':'ongoing_finish','token':lease['token'],'result':invalid})
                self.assertEqual(j['state'],'ready_publish')
            state.finish(ledger,{'action':'ongoing_finish','token':lease['token'],'result':receipt})
            self.assertEqual(j['state'],'draft_ready')

    def test_same_relative_path_can_run_in_distinct_projects_but_not_same_repo(self):
        for repository,expected in [(GATEWAY,'admit'),(AADI,'observe')]:
            ledger=installed([job('aadi-edge',AADI,'gemini'),job('second-edge',repository,'codex')])
            active=ledger['ongoing']['jobs'][0]
            active.update(state='coding',child_id='ongoing-aadi-edge-a0')
            self.assertEqual(state.work(ledger)['action'],expected)

    def test_task_pause_holds_future_stage_without_stopping_other_project(self):
        ledger=installed([job('aadi-edge',AADI,'gemini'),job('gateway-edge',GATEWAY,'codex')])
        board.ensure(ledger)
        paused=ledger['ongoing']['jobs'][0]
        board.action(ledger,{'request_id':'synthetic-pause','revision':ledger['supervision']['revision'],
                            'action':'pause','task_id':paused['supervisor_id'],
                            'actor':'Internal network operator (no individual login)'})
        for stage in ('queued','antigravity_ready','ready_test','ready_review','ready_publish'):
            clone=copy.deepcopy(ledger)
            clone['ongoing']['jobs'][0]['state']=stage
            work=state.work(clone)
            self.assertEqual(work['action'],'admit')
            self.assertEqual(work['job']['repository'],GATEWAY)
        self.assertTrue(board.snapshot(ledger)['tasks'][0]['paused'])
        self.assertEqual(ledger['supervision']['events'][-1]['actor'],'Internal network operator (no individual login)')

    def test_unknown_confidence_stays_unassessed_without_inference_from_tests(self):
        ledger=installed([job()]);j=ledger['ongoing']['jobs'][0]
        j.update(tests={'passed':True},review={'verdict':'pass'})
        board.ensure(ledger)
        entry=board.snapshot(ledger)['tasks'][0]
        self.assertIsNone(entry['coder_confidence']);self.assertIsNone(entry['reviewer_confidence'])
        j['coding']={'confidence':8,'confidence_reason':'Recorded synthetic model report'}
        j['review'].update(confidence=9,confidence_reason='Recorded review report')
        board.record(ledger)
        entry=board.snapshot(ledger)['tasks'][0]
        self.assertEqual((entry['coder_confidence'],entry['reviewer_confidence']),(8,9))


if __name__=='__main__':unittest.main()

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('controller',Path(__file__).resolve().parents[1]/'scripts/controller.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.job=json.loads((c.REPO/'config/worker/coding-job.json').read_text())
        self.registry=json.loads((c.REPO/'config/worker/projects.json').read_text())
        self.task={'id':'bounded-example','issue':20,'state':'ready','priority':10,'depends_on':[], 'job':self.job}
        self.snapshot={'repository':'pragalbhdwivedi/miniature-octo-doodle','ref':'refs/heads/main','source_sha':'a'*40,
                       'issues':[{'number':20,'state':'open','assignees':[],'labels':[{'name':'gatewayai:ready'}]}],'pulls':[]}
        self.files={name:(b'Public governance',0o644) for name in c.GOVERNANCE}

    def plan(self,tasks=None):
        if tasks is None: tasks=[self.task]
        self.files['config/controller/tasks.json']=(json.dumps({'version':1,'tasks':tasks}).encode(),0o644)
        return c.choose('gatewayai',self.snapshot,self.files,self.registry)

    def test_ready_task_is_review_plan_with_zero_authority(self):
        p=self.plan()
        self.assertEqual(p['status'],'awaiting_operator_review')
        self.assertEqual(p['authority'],'plan-only')
        self.assertEqual(p['source_sha'],'a'*40)
        self.assertEqual(p['job']['model_budget_usd'],0)
        self.assertEqual(p['provider_calls'],0)
        self.assertEqual(len(p['governance_sha256']),len(c.GOVERNANCE))

    def test_missing_governance_and_manifest_pause(self):
        p=c.choose('gatewayai',self.snapshot,{},self.registry)
        self.assertEqual(p['status'],'blocked')
        self.assertIn('no_committed_task_manifest',p['reasons'])
        self.assertIn('missing_governance:AGENTS.md',p['reasons'])

    def test_existing_issue_or_pr_owner_blocks(self):
        self.snapshot['issues'][0]['assignees']=[{'login':'someone'}]
        self.assertIn('bounded-example:existing_issue_owner',self.plan()['reasons'])
        self.snapshot['issues'][0]['assignees']=[]
        self.snapshot['pulls']=[{'title':'Fixes #20','body':None}]
        self.assertIn('bounded-example:existing_pull_request_owner',self.plan()['reasons'])

    def test_labels_and_closed_issue_do_not_grant_authority(self):
        self.snapshot['issues'][0]['labels']=[]
        self.assertEqual(self.plan()['status'],'blocked')
        self.snapshot['issues'][0]['state']='closed'
        self.assertIn('bounded-example:issue_not_open',self.plan()['reasons'])

    def test_dependencies_need_manifest_and_github_completion(self):
        dep={**self.task,'id':'dependency','issue':21,'state':'done'}
        self.task['depends_on']=['dependency']
        self.assertIn('bounded-example:dependency_not_completed',self.plan([self.task,dep])['reasons'])
        self.snapshot['issues'].append({'number':21,'state':'closed'})
        self.assertEqual(self.plan([self.task,dep])['status'],'awaiting_operator_review')

    def test_cycle_unknown_duplicate_dependency_ownership_rejected(self):
        for dep in ('bounded-example','unknown'):
            self.task['depends_on']=[dep]
            with self.assertRaises(ValueError): self.plan()
        self.task['depends_on']=[]
        with self.assertRaises(ValueError): self.plan([self.task,copy.deepcopy(self.task)])

    def test_deterministic_priority_selection(self):
        second={**self.task,'id':'earlier','priority':1,'issue':21}
        self.snapshot['issues'].append({**self.snapshot['issues'][0],'number':21})
        self.assertEqual(self.plan([self.task,second])['task_id'],'earlier')

    def test_empty_backlog_is_blocked_not_fabricated_work(self):
        p=self.plan([])
        self.assertEqual(p['status'],'blocked');self.assertNotIn('job',p)

    def test_spend_cross_project_and_cross_ref_denied(self):
        for key,value in [('model_budget_usd',1),('project','aadi'),('ref','refs/heads/other')]:
            old=self.job[key];self.job[key]=value
            with self.assertRaises(ValueError):self.plan()
            self.job[key]=old

    def test_pagination_is_complete_or_fails_closed(self):
        pages=[]
        def get(url):
            pages.append(url)
            return [{}]*100 if len(pages)==1 else [{'number':101}]
        self.assertEqual(len(c.collection('https://example.invalid?state=open',get)),101)
        with self.assertRaises(ValueError):c.collection('https://example.invalid?state=open',lambda _: [{}]*100)

    def test_unapproved_or_private_project_never_fetches(self):
        registry={'gatewayai':{'repository':'owner/repo','branch':'main','enabled':False}}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): c.refresh('gatewayai',registry,Path(tmp),lambda _: self.fail('network'))
            registry['gatewayai']['enabled']=True
            with self.assertRaises(ValueError):c.refresh('gatewayai',registry,Path(tmp),lambda _: {'private':True,'default_branch':'main'})


if __name__=='__main__':unittest.main()

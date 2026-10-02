"""Local allowance fallback and exact new-file coordination use real task claims."""
import copy
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import coder_coordination as coordination
import ongoing_state as ongoing
import pilot_state
import test_local_agent as fixture


class DevelopmentFallbackTests(unittest.TestCase):
    def state(self,count=1):
        s=pilot_state.make_state('a'*40);s['batch']['state']='completed'
        jobs=[{'id':'development-'+str(n),'title':'Implement feature '+str(n),'owner':'gemini' if n==0 else 'codex',
            'operation':'development_change','development_profile':'unit','risk':'reversible',
            'write_paths':['src/module'+str(n)+'.py'],'transport':'cli','source_sha':'a'*40} for n in range(count)]
        ongoing.install(s,jobs);o=s['ongoing'];o['planned']=True
        o['policy'].update(max_calls_per_day=80,local_coding_fallback=True)
        for j in o['jobs']:j.update(state='antigravity_ready' if j['owner']=='gemini' else 'codex_ready',child_id=j['id']+'-a0')
        return s

    def test_daily_cloud_limit_moves_generation_to_local_without_charge(self):
        s=self.state();s['ongoing']['calls']=80
        result=ongoing.work(s)
        self.assertEqual(result['action'],'local_fallback');self.assertEqual(s['ongoing']['calls'],80)
        self.assertEqual(result['job']['owner'],'gemini')
        candidate={'state':'human_review_required','owner':'gemini','task_id':result['job']['child_id'],
            'source_sha':'a'*40,'route':{'model':'devstral-small-2:24b','provider':'ollama_local'}}
        ongoing.finish(s,{'action':'ongoing_finish','token':result['token'],'result':candidate})
        self.assertEqual(s['ongoing']['jobs'][0]['state'],'ready_test')
        self.assertEqual(s['ongoing']['jobs'][0]['coding']['route']['provider'],'ollama_local')

    def test_parallel_cloud_exhaustion_uses_one_local_fallback(self):
        s=self.state(2);s['ongoing']['calls']=80
        result=ongoing.work(s)
        self.assertEqual(result['action'],'local_fallback');self.assertEqual(s['ongoing']['calls'],80)
        self.assertEqual(s['ongoing']['lease']['job_id'],result['job']['id'])

    def test_confirmed_pre_generation_quota_denial_refunds_cloud_reservation(self):
        s=self.state();result=ongoing.work(s);self.assertEqual(s['ongoing']['calls'],1)
        quota={'state':'quota_wait','inference_started':False,
            'retry_at':(datetime.now(timezone.utc)+timedelta(hours=5)).isoformat()}
        ongoing.finish(s,{'action':'ongoing_finish','token':result['token'],'result':quota})
        self.assertEqual(s['ongoing']['calls'],0)
        self.assertEqual(s['ongoing']['jobs'][0]['state'],'local_fallback_ready')
        self.assertEqual(ongoing.work(s)['action'],'local_fallback')

    def test_inference_started_quota_response_cannot_release_claim(self):
        s=self.state();work=ongoing.work(s);lease=copy.deepcopy(s['ongoing']['lease'])
        with self.assertRaises(ValueError):
            ongoing.finish(s,{'action':'ongoing_finish','token':work['token'],'result':{
                'state':'quota_wait','inference_started':True,'retry_at':datetime.now(timezone.utc).isoformat()}})
        self.assertEqual(s['ongoing']['calls'],1);self.assertEqual(s['ongoing']['lease'],lease)

    def test_independent_review_does_not_become_unreviewed_local_approval(self):
        s=self.state();s['ongoing']['calls']=80;s['ongoing']['jobs'][0]['state']='ready_review'
        result=ongoing.work(s)
        self.assertEqual(result,{'action':'idle','reason':'daily_model_limit'})
        self.assertIsNone(s['ongoing']['lease'])

    def test_fallback_disabled_preserves_quota_wait(self):
        s=self.state();s['ongoing']['calls']=80;s['ongoing']['policy']['local_coding_fallback']=False
        self.assertEqual(ongoing.work(s)['action'],'idle');self.assertIsNone(s['ongoing']['lease'])


class DevelopmentNewFileTests(unittest.TestCase):
    command=fixture.LocalAgentTests.command

    def setUp(self):
        fixture.LocalAgentTests.setUp(self)
        self.command('push','-q','origin','HEAD:Dev')
        self.new_path='tests/test_new_feature.py'
        for p in (patch.object(coordination,'REPOSITORY',str(self.remote).removesuffix('.git')),
                  patch.dict(os.environ,{'LOCALAPPDATA':str(self.repo.parent)})):
            p.start();self.addCleanup(p.stop)
        self.config={'repo':str(self.repo),'output_root':str(self.repo.parent/'evidence'),
                     'codex':sys.executable,'allowed_new_paths':[self.new_path]}
        self.c=coordination.Coordinator(self.config)

    def test_only_declared_new_paths_receive_an_empty_source_baseline(self):
        snapshot=self.c.source(['example.py',self.new_path])
        self.assertEqual(snapshot['files'][self.new_path],'')
        with self.assertRaises(coordination.agent.AgentError):self.c.source(['example.py','tests/unapproved.py'])
        self.assertFalse((self.repo/self.new_path).exists())

    def test_real_git_claim_accepts_new_file_proposal_without_source_write(self):
        self.c.admit('feature-with-test','Implement a feature and regression test',['example.py',self.new_path],
                     owner='gemini',write_paths=['example.py',self.new_path],transport='cli')
        candidate={'summary':'Confidence: 8/10; implemented feature','proposal':'Tests not run by coder',
            'changes':[{'path':'example.py','content':'def answer():\n    return 42\n'},
                       {'path':self.new_path,'content':'import unittest\nfrom example import answer\nclass Feature(unittest.TestCase):\n    def test_answer(self):\n        self.assertEqual(answer(), 42)\n'}]}
        result=self.c.run_gemini('feature-with-test',lambda prompt,folder:candidate)
        self.assertEqual(result['state'],'human_review_required')
        self.assertEqual(result['candidate_sha256'],coordination.digest(candidate))
        self.assertFalse((self.repo/self.new_path).exists())
        self.assertIn('return 41',(self.repo/'example.py').read_text())
        self.assertTrue((self.c.root/'feature-with-test/gemini'/self.new_path).is_file())
        self.command('apply','--check',str(self.c.root/'feature-with-test/gemini.patch'))

    def test_existing_untracked_new_destination_is_rejected(self):
        path=self.repo/self.new_path;path.parent.mkdir();path.write_text('private untracked contents')
        with self.assertRaises(coordination.agent.AgentError):self.c.source(['example.py',self.new_path])
        self.assertEqual(path.read_text(),'private untracked contents')

    def test_complete_development_instruction_is_retained_and_oversize_denied(self):
        instruction='Preserve requirements. '*80+' FINAL REQUIREMENT'
        self.c.admit('full-instruction',instruction,['example.py'],owner='gemini',transport='cli')
        observed=[]
        value={'summary':'Unchanged proposal','proposal':'No execution',
               'changes':[{'path':'example.py','content':'def answer():\n    return 41\n'}]}
        self.c.run_gemini('full-instruction',lambda prompt,folder:(observed.append(prompt) or value))
        self.assertIn(instruction,observed[0])
        with self.assertRaises(coordination.agent.AgentError):
            self.c.admit('too-long','x'*4001,['example.py'],owner='local')


if __name__=='__main__':unittest.main()

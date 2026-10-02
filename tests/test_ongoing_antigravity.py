import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ongoing_antigravity as a
import ongoing_state as s
import pilot_state


class NativeTests(unittest.TestCase):
    def quotas(self,g=100,c=100):
        return a.parse_quotas('\n'.join(f'{group}\t{window}\t{percent}%\t2026-10-03T00:00:00Z'
            for group,percent in [('Gemini Models',g),('Claude and GPT models',c)]
            for window in ('Weekly Limit Remaining','Five Hour Limit Remaining')))

    def test_shared_pool_exhaustion_selects_other_provider_and_all_exhausted_waits(self):
        available={'gemini-3.8-flash-medium','gemini-3.7-flash-medium','claude-sonnet-4-6'}
        self.assertEqual(a.select_model(available,self.quotas(0,80))['model'],'claude-sonnet-4-6')
        with self.assertRaises(a.QuotaWait):a.select_model(available,self.quotas(0,0))

    def test_weekly_limit_blocks_even_when_five_hour_available(self):
        q=self.quotas();q['Gemini Models']['Weekly Limit Remaining']['remaining']=0
        r=a.select_model({'gemini-3.8-flash-medium','gpt-oss-120b-medium'},q)
        self.assertEqual(r['model'],'gpt-oss-120b-medium')

    def test_missing_quota_cannot_be_treated_as_unlimited(self):
        with self.assertRaises(ValueError):a.parse_quotas('Gemini Models\tWeekly Limit Remaining\t100%\t2026-10-03T00:00:00Z')

    def test_exhausted_preflight_waits_without_consuming_inference_budget(self):
        value=pilot_state.make_state('a'*40);value['batch']['state']='completed'
        s.install(value,[{'id':'gemini','owner':'gemini','title':'Test','risk':'reversible',
            'operation':'test_addition','write_paths':['test.py'],'transport':'cli'}])
        o=value['ongoing'];o['planned']=True;o['jobs'][0]['state']='antigravity_ready'
        w=s.work(value)
        s.finish(value,{'action':'ongoing_finish','token':w['token'],'result':{
            'state':'quota_wait','retry_at':'2099-10-03T00:00:00+00:00','inference_started':False}})
        self.assertEqual(o['calls'],0)
        self.assertEqual(s.work(value)['action'],'idle')
        o['jobs'][0]['retry_at']='2000-01-01T00:00:00+00:00'
        self.assertEqual(s.work(value)['action'],'antigravity')

    def test_wrong_model_tools_or_failed_response_rejected(self):
        events=[{'event':'init','init':{'model':'gemini-3.8-flash-medium','agent':'aadi-proposal','tools':[],'permission_mode':'strict'}},
                {'event':'result','result':{'status':'SUCCESS','num_turns':1,'structured_output':{'changes':[]},'usage':{'input_tokens':10}}}]
        encode=lambda:('\n'.join(json.dumps(e) for e in events)).encode()
        route={'model':'gemini-3.8-flash-medium'}
        self.assertEqual(a.parse_result(encode(),route)['usage']['input_tokens'],10)
        events.append({'event':'step_update','step_update':{'step_type':'tool','tool_name':'run_command'}})
        with self.assertRaises(ValueError):a.parse_result(encode(),route)
        events.pop();events[0]['init']['model']='other'
        with self.assertRaises(ValueError):a.parse_result(encode(),route)

    def test_two_cli_owners_have_one_durable_parallel_lease_and_partial_success(self):
        value=pilot_state.make_state('a'*40);value['batch']['state']='completed'
        jobs=[{'id':owner,'owner':owner,'title':owner,'risk':'reversible','operation':'test_addition',
               'write_paths':['tests/'+owner+'.py'],'transport':'cli' if owner=='gemini' else 'sidecar'} for owner in ('gemini','codex')]
        s.install(value,jobs);value['ongoing']['planned']=True
        for j in value['ongoing']['jobs']:
            w=s.work(value);s.finish(value,{'action':'ongoing_finish','token':w['token'],
                'result':{'child_id':j['id'],'issue':{'url':'https://example.test'}}})
        w=s.work(value);self.assertEqual(w['action'],'parallel_code');self.assertEqual(value['ongoing']['calls'],2)
        self.assertEqual(s.work(value)['action'],'idle')
        s.finish(value,{'action':'ongoing_finish','token':w['token'],'result':{
            'gemini':{'state':'human_review_required'},'codex':{'state':'blocked'}}})
        self.assertEqual([j['state'] for j in value['ongoing']['jobs']],['ready_test','blocked'])

    def test_interrupted_parallel_stage_is_not_reissued(self):
        self.test_two_cli_owners_have_one_durable_parallel_lease_and_partial_success()
        value=pilot_state.make_state('a'*40);value['ongoing']={'jobs':[{'id':'x','state':'codex_ready','title':'x'}],
            'lease':{'stage':'parallel_code','job_id':None,'job_ids':['x'],'token':'abc'}}
        s.finish(value,{'action':'ongoing_fail','token':'abc','result':{}})
        self.assertEqual(value['ongoing']['jobs'][0]['state'],'blocked')


if __name__=='__main__':unittest.main()

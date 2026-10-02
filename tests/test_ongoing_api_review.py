from contextlib import closing
import concurrent.futures
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ongoing_api_review as api


class ApiReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.config={'enabled':True,'gateway_config':'protected.json','expected_model':'openai/gpt-5.4-mini',
            'daily_token_cap':20000,'max_output_tokens':512,'ledger_path':str(Path(self.temp.name)/'ledger.sqlite3')}
        self.request={'request_id':'test-one','prompt':'Review public function f returning 1.',
            'data_class':'synthetic','candidate_sha256':'a'*64}
        self.policy={'resolved_routes':{'review':[{'model':'openai/gpt-5.4-mini'},{'model':'gemini/test'}]},
            'max_input_bytes':32768,'max_output_tokens':1024}
        self.creds={'gateway_url':'http://127.0.0.1:4000','gateway_key':'synthetic-key','policy_file':'policy.json'}
        self.value={'verdict':'pass','findings':[],'confidence':9,'confidence_reason':'Synthetic evidence coherent'}
        self.response={'id':'synthetic-response','model':'gpt-5.4-mini-2026-03-17','choices':[{'finish_reason':'stop',
            'message':{'content':json.dumps(self.value)}}],
            'usage':{'prompt_tokens':99,'completion_tokens':30,'total_tokens':129}}
        self.transport=Mock(return_value=self.response)
        self.day=datetime(2026,10,2,tzinfo=timezone.utc)

    def run_review(self,request=None,config=None):
        return api.run(config or self.config,request or self.request,transport=self.transport,
            load=lambda path:self.creds if path=='protected.json' else self.policy,clock=lambda:self.day)

    def test_review_uses_gateway_openai_only_and_observed_usage(self):
        result=self.run_review()
        url,key,body=self.transport.call_args.args
        self.assertEqual(url,'http://127.0.0.1:4000/v1/chat/completions')
        self.assertEqual(body['metadata']['allowed_providers'],['openai'])
        self.assertNotIn('tools',body)
        self.assertEqual(result['candidate_sha256'],'a'*64)
        self.assertEqual(result['usage']['total_tokens'],129)
        self.assertFalse(result['free_usage_verified'])
        self.assertGreater(result['budget']['reserved_tokens'],129)

    def test_completed_replay_returns_receipt_without_network(self):
        result=self.run_review();self.assertEqual(self.run_review(),result)
        self.assertEqual(self.transport.call_count,1)
        with self.assertRaises(api.ReviewError):self.run_review(dict(self.request,prompt='Different content'))
        self.assertEqual(self.transport.call_count,1)

    def test_uncertain_timeout_is_never_replayed_even_next_day(self):
        self.transport.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError):self.run_review()
        self.day+=timedelta(days=1)
        with self.assertRaisesRegex(api.ReviewError,'uncertain'):self.run_review()
        self.assertEqual(self.transport.call_count,1)

    def test_atomic_daily_reservations_and_utc_rollover(self):
        path=Path(self.config['ledger_path'])
        def reserve(n):
            try:api.reserve(path,str(n),'a','2026-10-02',6000,10000);return True
            except api.ReviewError:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(reserve,range(2)))
        self.assertEqual(sum(results),1)
        self.assertIsNone(api.reserve(path,'next-day','b','2026-10-03',6000,10000))

    def test_disabled_zero_or_boolean_budget_denied_before_http(self):
        for change in ({'enabled':False},{'daily_token_cap':0},{'daily_token_cap':True},{'max_output_tokens':True}):
            with self.subTest(change=change),self.assertRaises(api.ReviewError):self.run_review(config={**self.config,**change})
        self.transport.assert_not_called()

    def test_small_budget_prevents_inference(self):
        with self.assertRaisesRegex(api.ReviewError,'Daily'):self.run_review(config={**self.config,'daily_token_cap':1})
        self.transport.assert_not_called()

    def test_private_and_expanded_requests_denied(self):
        for change in ({'data_class':'private'},{'data_class':'local-private'},{'tools':['shell']},
                       {'candidate_sha256':'invalid'},{'prompt':'x'*24001},{'request_id':'../escape'}):
            with self.subTest(change=change),self.assertRaises(api.ReviewError):self.run_review({**self.request,**change})
        self.transport.assert_not_called()

    def test_route_drift_denied(self):
        self.policy['resolved_routes']['review'][0]['model']='openai/unreviewed'
        with self.assertRaises(api.ReviewError):self.run_review()
        self.transport.assert_not_called()

    def test_external_gateway_denied(self):
        self.creds['gateway_url']='https://api.openai.com'
        with self.assertRaises(api.ReviewError):self.run_review()
        self.transport.assert_not_called()

    def test_other_model_and_incomplete_answer_retained_without_retry(self):
        self.response['model']='gemini-test'
        with self.assertRaises(api.ReviewError):self.run_review()
        with self.assertRaisesRegex(api.ReviewError,'uncertain'):self.run_review()
        self.assertEqual(self.transport.call_count,1)

    def test_response_schema_usage_tools_and_finish_are_checked(self):
        for change in ({'verdict':'merge'},{'confidence':True},{'findings':['x'*1001]},{'confidence_reason':''}):
            response={**self.response,'choices':[{'finish_reason':'stop','message':{'content':json.dumps({**self.value,**change})}}]}
            with self.subTest(change=change),self.assertRaises(api.ReviewError):api.validate_response(response,self.config['expected_model'])
        for response in ({**self.response,'usage':{}},
            {**self.response,'choices':[{'finish_reason':'length','message':{'content':json.dumps(self.value)}}]},
            {**self.response,'choices':[{'finish_reason':'stop','message':{'content':json.dumps(self.value),'tool_calls':[{}]}}]}):
            with self.assertRaises(api.ReviewError):api.validate_response(response,self.config['expected_model'])

    def test_excess_usage_blocks_acceptance(self):
        self.response['usage']={'prompt_tokens':100000,'completion_tokens':30,'total_tokens':100030}
        with self.assertRaises(api.ReviewError):self.run_review()
        with self.assertRaisesRegex(api.ReviewError,'uncertain'):self.run_review()

    def test_invalid_response_is_saved_for_reconciliation_without_inference_replay(self):
        self.response['choices'][0]['finish_reason']='length'
        with self.assertRaisesRegex(api.ReviewError,'Incomplete'):self.run_review()
        with closing(sqlite3.connect(self.config['ledger_path'])) as db:
            state,receipt=db.execute('SELECT state,receipt FROM reviews WHERE id=?',(self.request['request_id'],)).fetchone()
        self.assertEqual(state,'received')
        self.assertEqual(json.loads(receipt)['raw_response'],self.response)
        with self.assertRaisesRegex(api.ReviewError,'uncertain'):self.run_review()
        self.assertEqual(self.transport.call_count,1)

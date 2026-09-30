"""Synthetic Phase 8 transport and exact decision checks; no live bot token."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('controller_telegram',Path(__file__).resolve().parents[1]/'scripts/controller_telegram.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.config={'bot_token':'123456:'+('A'*35),'user_id':12345,'chat_id':12345,'signing_key_hex':'ab'*32}
        self.approval='a'*32;self.digest='b'*64
        self.store=Mock();self.store.approval.return_value={
            'approval_id':self.approval,'payload_sha256':self.digest,'state':'pending'}
        self.store.decide_approval.return_value={'state':'approved'}

    def update(self,data,user=12345,chat=12345,kind='private',number=7):
        return {'update_id':number,'callback_query':{'id':'callback-1','from':{'id':user},
            'message':{'chat':{'id':chat,'type':kind}},'data':data}}

    def test_signed_callback_is_bounded_and_tamper_resistant(self):
        signed=t.callback(self.config,self.approval,'approve',self.digest)
        self.assertLessEqual(len(signed.encode()),64)
        self.assertEqual(t.decode_callback(self.config,signed,self.store.approval.return_value),'approve')
        self.assertEqual(t.decode_callback(self.config,t.callback(self.config,self.approval,'reject',self.digest),
                                           self.store.approval.return_value),'reject')
        for bad in (signed[:-1]+('0' if signed[-1]!='0' else '1'),signed.replace(self.approval,'c'*32)):
            if bad==signed:continue
            with self.assertRaises(ValueError):t.decode_callback(self.config,bad,self.store.approval.return_value)

    def test_only_approved_private_identity_can_decide(self):
        data=t.callback(self.config,self.approval,'approve',self.digest)
        for update in (self.update(data,user=9),self.update(data,chat=9),self.update(data,kind='group'),
                       self.update(data[:-1]+'0'),self.update(data,number=-1)):
            with self.assertRaises(ValueError):t.apply_update(self.store,self.config,update)
        self.store.decide_approval.assert_not_called()
        result=t.apply_update(self.store,self.config,self.update(data))
        self.assertEqual(result['state'],'approved')
        self.store.decide_approval.assert_called_once_with(self.approval,self.digest,'approved',12345,12345,7)

    def test_replay_and_rejection(self):
        data=t.callback(self.config,self.approval,'reject',self.digest)
        self.store.decide_approval.return_value={'state':'rejected'}
        self.assertEqual(t.apply_update(self.store,self.config,self.update(data))['state'],'rejected')
        self.store.approval.return_value['state']='rejected'
        with self.assertRaises(ValueError):t.apply_update(self.store,self.config,self.update(data))
        self.assertEqual(self.store.decide_approval.call_count,1)

    def test_request_binds_final_receipt_before_sending(self):
        receipt={'run_id':'a'*32,'source_sha':'b'*40,'artifact_sha256':'c'*64,'candidate_run':'c'*32}
        row={'state':'approved'};root={'run_id':'a'*32,'state':'review_required'}
        config={'runtime':'/private','worker_runtime':'/worker','telegram_approval_config':'/private/telegram.json'}
        self.store.request_approval.return_value={'state':'pending','expires_at':'tomorrow'}
        with patch.object(t.p,'publication_receipt',return_value=receipt),\
             patch.object(t.p,'eligible'),patch.object(t.p.publisher,'plan',return_value={'source_sha':'b'*40}),\
             patch.object(t.d,'private_json',return_value=self.config),\
             patch.object(t,'bot_call',return_value={'chat':{'id':12345},'message_id':5}) as send:
            result=t.request_approval(self.store,root,row,config)
        self.assertEqual(result['payload_sha256'],t.d.digest(receipt))
        self.assertEqual(send.call_args.args[1],'sendMessage')
        self.assertEqual(send.call_args.args[2]['chat_id'],12345)
        self.assertEqual(self.store.request_approval.call_args.args[-1],900)

    def test_pipeline_requires_and_consumes_telegram_approval_when_enabled(self):
        row={'state':'approved','run_id':'a'*32,'spec':{'source_sha':'b'*40},'approval_sha256':'d'*64,
             'evidence':{'tests_passed':True,'review':{'verdict':'approve'},'candidate_run':'c'*32,
                         'artifact_sha256':'e'*64,'review_sha256':'f'*64}}
        root={'run_id':'a'*32,'request':{'plan':{'issue':21}}}
        config={'runtime':'/private','worker_runtime':'/worker','telegram_approval_config':'/private/telegram.json'}
        digest=t.d.digest(t.p.publication_receipt(row))
        with patch.object(t.p,'eligible'),patch.object(t.p.d,'private_json',return_value={}),\
             patch.object(t.p.publisher,'plan',return_value={'source_sha':'b'*40}):
            with self.assertRaises(ValueError):t.p.publish(self.store,root,row,digest,config,Path('/key'))
        self.store.consume_approval.assert_not_called()
        with patch.object(t.p,'eligible'),patch.object(t.p.d,'private_json',return_value={}),\
             patch.object(t.p.publisher,'plan',return_value={'source_sha':'b'*40}),\
             patch.object(t.p.publisher,'publish_reviewed',return_value={'draft':True}):
            t.p.publish(self.store,root,row,digest,config,Path('/key'),'1'*32)
        self.store.consume_approval.assert_called_once()
        self.assertEqual(self.store.consume_approval.call_args.args[2],digest)

    def test_poll_skips_foreign_callback_and_records_approved_update(self):
        data=t.callback(self.config,self.approval,'approve',self.digest)
        batch=[self.update(data,user=9,number=7),self.update(data,number=8)]
        class Reply:
            def __init__(self,value):self.value=value
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,_):return json.dumps({'ok':True,'result':self.value}).encode()
        seen=[]
        def transport(request,timeout):
            method=request.full_url.rsplit('/',1)[-1]
            seen.append(method)
            return Reply(batch if method=='getUpdates' else True)
        with tempfile.TemporaryDirectory() as folder:
            offset=Path(folder)/'offset.json'
            result=t.poll_once(self.store,self.config,offset,transport)
            self.assertEqual(json.loads(offset.read_text())['next_update_id'],9)
        self.assertEqual(result,[{'approval_id':self.approval,'state':'approved'}])
        self.assertEqual(seen,['getUpdates','answerCallbackQuery'])

if __name__=='__main__':unittest.main()

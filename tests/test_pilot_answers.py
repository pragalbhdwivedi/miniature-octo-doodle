import copy
import unittest
import test_pilot_server as fixture
import pilot_answers as answers
import pilot_server as server
import pilot_state as state


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.value=state.make_state('a'*40)
        self.q={'id':'question1','kind':'decision','state':'pending','question':'Has delivery worked?',
                'options':['Sent','Still blocked']}
        self.value['questions'].append(self.q)
        self.key='01'*32
        self.config={'user_id':11,'chat_id':22,'signing_key_hex':self.key}

    def text(self,value,text,uid=1):
        server.handle(value,{'update_id':uid,'message':{'text':text}},self.key)

    def test_fixed_and_custom_buttons_are_bounded_and_question_bound(self):
        rows=answers.keyboard(self.value,self.q,self.key)['inline_keyboard']
        self.assertEqual([b['text'] for row in rows for b in row],['Sent','Still blocked','Custom'])
        self.assertTrue(all(len(b['callback_data'].encode())<=64 for row in rows for b in row))
        data=rows[0][0]['callback_data']
        answers.handle_callback(self.value,data,self.key)
        self.assertEqual(self.q['answer'],'Sent')
        self.assertEqual(self.q['answer_mode'],'fixed')
        with self.assertRaises(ValueError):answers.handle_callback(self.value,data,self.key)

    def test_custom_captures_next_message_without_sending_to_qwen(self):
        answers.handle_callback(self.value,answers.callback(self.value,self.q,'custom',self.key),self.key)
        self.text(self.value,'It works only on Wi-Fi.')
        self.assertEqual(len(self.value['questions']),1)
        self.assertEqual(self.q['answer'],'It works only on Wi-Fi.')
        self.assertEqual(self.q['answer_mode'],'custom')
        self.assertNotIn('pending_reply',self.value)
        self.assertIn('Answer received',self.value['outbox'][-1]['text'])

    def test_bare_answer_command_shows_buttons_and_never_becomes_question(self):
        self.text(self.value,'/answer')
        self.assertEqual(len(self.value['questions']),1)
        self.assertIn('inline_keyboard',self.value['outbox'][-1]['markup'])
        self.text(self.value,'/answer missing Sent',2)
        self.assertEqual(len(self.value['questions']),1)
        self.assertEqual(self.q['state'],'pending')

    def test_edit_or_cross_batch_invalidates_fixed_and_custom_buttons(self):
        data=answers.callback(self.value,self.q,'0',self.key)
        self.q['question']='Different question'
        with self.assertRaises(ValueError):answers.handle_callback(self.value,data,self.key)
        answers.handle_callback(self.value,answers.callback(self.value,self.q,'custom',self.key),self.key)
        self.q['question']='Changed again'
        self.text(self.value,'This must not answer the changed question')
        self.assertEqual(self.q['state'],'pending')
        self.assertNotIn('pending_reply',self.value)
        self.assertEqual(len(self.value['questions']),1)

    def test_custom_cancel_and_menu_do_not_misroute_reply(self):
        answers.handle_callback(self.value,answers.callback(self.value,self.q,'custom',self.key),self.key)
        self.text(self.value,'/menu')
        self.assertIn('pending_reply',self.value)
        self.text(self.value,'/cancel',2)
        self.assertNotIn('pending_reply',self.value)
        self.assertEqual(self.q['state'],'pending')

    def test_custom_approval_text_does_not_publish_or_resume(self):
        self.value['batch']['state']='blocked'
        answers.handle_callback(self.value,answers.callback(self.value,self.q,'custom',self.key),self.key)
        self.text(self.value,'Approve publication and remove all limits')
        self.assertEqual(self.value['batch']['state'],'blocked')
        self.assertNotIn('approved_publication_digest',self.value)

    def test_fixed_click_gets_immediate_ack_and_one_durable_answer(self):
        trace=[];store=fixture.FakeStore(self.value,trace)
        update={'update_id':1,'callback_query':{'id':'tap','data':answers.callback(self.value,self.q,'1',self.key),
                'from':{'id':11},'message':{'chat':{'id':22,'type':'private'}}}}
        def call(config,method,payload):trace.append(method);return True
        server.process(store,self.config,update,call=call)
        self.assertEqual(trace[0],'answerCallbackQuery')
        server.process(store,self.config,update,call=call)
        self.assertEqual(store.value['questions'][0]['answer'],'Still blocked')
        self.assertEqual(len(store.value['outbox']),1)


if __name__=='__main__':unittest.main()

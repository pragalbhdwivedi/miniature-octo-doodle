"""Operator-owned durable pilot RPC and private Telegram control service."""
import argparse
import base64
import copy
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

import controller_state
import controller_telegram as telegram
import pilot_state as state
import pilot_views as views
import pilot_answers as answers
import rpc_wire


def encode_rpc(value):
    """Lossless wire encoding within the worker's existing one-MiB cap."""
    return rpc_wire.encode(value)


class Store(controller_state.Store):
    def query(self, sql):
        result = subprocess.run(self.argv, input=("SET statement_timeout='10s'; SET lock_timeout='3s'; SET search_path=pg_catalog;\n"+sql).encode(), capture_output=True, timeout=20)
        if result.returncode or len(result.stdout)>2200000:
            raise RuntimeError('Pilot database operation failed')
        return json.loads(result.stdout)

    def read(self):
        return self.query('SELECT controller.pilot_read();')

    def mutate(self, operation):
        for _ in range(8):
            row=self.read(); candidate=copy.deepcopy(row['value'])
            result=operation(candidate)
            if candidate==row['value']: return result
            raw=json.dumps(candidate,allow_nan=False).encode()
            if len(raw)>1900000: raise ValueError('Pilot storage limit reached')
            encoded=base64.b64encode(raw).decode()
            sql="SELECT to_jsonb(controller.pilot_cas("+str(int(row['revision']))+",convert_from(decode('"+encoded+"','base64'),'UTF8')::jsonb));"
            if self.query(sql): return result
        raise RuntimeError('Pilot state contention')


def authorized(config, update):
    item=update.get('callback_query') or update.get('message') or {}
    message=item.get('message',{}) if 'callback_query' in update else item
    user_id=item.get('from',{}).get('id');chat_id=message.get('chat',{}).get('id')
    return (type(user_id) is int and type(chat_id) is int and user_id==config['user_id'] and
            chat_id==config['chat_id'] and
            message.get('chat',{}).get('type')=='private')


def show(s, view, level, key):
    markup=views.keyboard(view,level)
    text=views.render(view,level,state.snapshot(s))
    if s.get('ongoing'):
        import ongoing_state
        markup['inline_keyboard'].insert(0,[{'text':'Ongoing work','callback_data':'p:ongoing:brief'},
            {'text':'Pause ongoing','callback_data':'p:ongoing-pause:brief'},
            {'text':'Resume ongoing','callback_data':'p:ongoing-resume:brief'}])
        if view in ('status','outputs'):text=ongoing_state.summary(s)
        if view=='questions':text=ongoing_state.decisions(s)+'\n\n'+text
        if view=='usage':text=ongoing_state.usage(s)
        if view=='inputs':text='Ongoing assignments\n'+'\n\n'.join(j['title']+'\n'+j['prompt'] for j in s['ongoing']['jobs'])
    if view=='questions':
        if s['batch']['state']=='awaiting_scope':
            text=('Start this pilot?\nThree synthetic identity regression tests: case-sensitive system names, spaces inside external IDs, and case-sensitive IDs. Both coders propose; isolated tests and independent GPT review verify.\nLimit: 3 tasks, 60 minutes, 10 GPT calls, one repair per task. No paid API fallback. Publishing to Dev requires another exact-result approval.\n\n'+text)[:3500]
            markup['inline_keyboard'].insert(0,[{'text':'Approve and start pilot','callback_data':state.signed(s,'start',key)}])
        elif s['batch']['state']=='awaiting_publication':
            text=('Approve the verified combined test file for Dev?\nArtifact: '+s['publication_digest']+'\nMain and production remain unchanged.\n\n'+text)[:3500]
            markup['inline_keyboard'].insert(0,[{'text':'Publish verified result to Dev','callback_data':state.signed(s,'publish',key)}])
            markup['inline_keyboard'].insert(1,[{'text':'Keep unpublished','callback_data':'p:defer:brief'},
                                               {'text':'Custom','callback_data':'p:feedback:brief'}])
    state.message(s,text,markup)
    if view=='questions':answers.show_pending(s,key)


def handle(s, update, key):
    """Pure action reducer; offset and outcome persist in the same CAS commit."""
    uid=update['update_id']
    if uid<s['offset']: return 'already handled'
    s['offset']=uid+1
    if s.get('supervision'):
        import supervisor_runtime
        if supervisor_runtime.conversation(s,update):return 'recorded'
    query=update.get('callback_query')
    if query:
        data=query.get('data','')
        try:
            if data.startswith('q:'):answers.handle_callback(s,data,key)
            elif data.startswith('p!'): state.decide(s,data,key)
            elif data.startswith('p:'):
                _,view,level=data.split(':')
                if level not in ('brief','detailed','full'): raise ValueError('Unknown detail level')
                if view=='pause':
                    if s['batch']['state'] not in ('paused','completed','awaiting_scope','awaiting_publication','expired','blocked'):
                        s['batch']['resume_state']=s['batch']['state'];s['batch']['state']='paused'
                    state.message(s,'Pause recorded. No new coding stage will start. Any stage already running may finish and save its result.');state.event(s,'Owner requested pause.')
                elif view=='resume':
                    if s['batch']['state']=='paused':
                        if state.deadline_reached(s):
                            s['batch']['state']='expired'
                            state.message(s,'Resume received, but the original pilot deadline has passed. No new stage will start.')
                            return 'recorded'
                        previous=s['batch'].pop('resume_state','running')
                        s['batch']['state']='running' if previous=='planning' and not any(x['state']=='running' for x in s['leases'].values()) else previous
                        state.message(s,'Resume recorded. Work will continue within the original time and usage limits.')
                    else: state.message(s,'Resume was received. The pilot is not paused; open Status or Decisions to see what it needs.')
                elif view=='report': state.message(s,'Your comprehensive report is attached.',report=True)
                elif view in ('ongoing','ongoing-pause','ongoing-resume'):
                    import ongoing_state
                    if not s.get('ongoing'):raise ValueError('Ongoing work is not configured')
                    if view!='ongoing':
                        if s.get('supervision'):
                            import supervisor_board
                            supervisor_board.action(s,{'request_id':'tg-'+str(uid),'revision':s['supervision']['revision'],
                                'action':'resume' if view=='ongoing-resume' else 'pause','actor':'Owner via Telegram'})
                        else:s['ongoing']['enabled']=view=='ongoing-resume'
                    state.message(s,ongoing_state.summary(s))
                elif view=='ask': state.message(s,'What would you like to know? Reply to a task message or include its SUP task ID, and Qwen will answer from its saved evidence. You can add work and request corrections from the task controls.')
                elif view=='defer':
                    if s['batch']['state']!='awaiting_publication':raise ValueError('There is no current publication decision to defer')
                    state.message(s,'Received: keep the result unpublished. Nothing was published. You can review Outputs and return to Decisions later.')
                    state.event(s,'Owner chose to leave the current result unpublished.')
                elif view=='feedback':
                    if s['batch']['state']!='awaiting_publication':raise ValueError('There is no current publication decision')
                    q={'id':secrets.token_hex(4),'kind':'decision','state':'pending',
                       'question':'What would you like changed or explained before publication?',
                       'options':['Explain the changes','Show test evidence','Keep unpublished'],
                       'context_digest':s.get('publication_digest')}
                    existing=next((x for x in s['questions'] if x.get('state')=='pending' and x.get('context_digest')==s.get('publication_digest') and x.get('question')==q['question']),None)
                    if existing:q=existing
                    else:s['questions'].append(q)
                    answers.handle_callback(s,answers.callback(s,q,'custom',key),key)
                elif view in ('status','inputs','outputs','questions','controls','usage'): show(s,view,level,key)
                else: raise ValueError('Unknown button')
            else: raise ValueError('This button is no longer active')
        except ValueError as error: state.message(s,'Click received. '+str(error)+'. Use /menu for current buttons.')
    else:
        text=update.get('message',{}).get('text','').strip()[:3000]
        if text in ('/start','/menu','/status'): show(s,'status',s.get('detail_level','brief'),key)
        elif text=='/cancel':
            s.pop('pending_reply',None);state.message(s,'Custom entry cancelled. Open Decisions to choose an answer.')
        elif text=='/answer':
            if not answers.show_pending(s,key):state.message(s,'There is no pending question to answer. Use Ask / follow-up for a new question.')
        elif text.startswith('/answer '):
            bits=text.split(' ',2)
            q=next((q for q in s['questions'] if len(bits)==3 and q['id']==bits[1] and q.get('kind')=='decision'),None)
            if q and q.get('state')=='pending':answers.record(s,q,bits[2],'custom')
            else:state.message(s,'That question is missing or already answered. Open Decisions for current answer buttons.')
        elif text.startswith('/'):
            state.message(s,'Command not recognized. Use /menu or /answer; choose Custom on a question to type your own reply.')
        elif text and answers.custom_text(s,text):pass
        elif text:
            pending=sum(q.get('state') in ('pending','answering') for q in s['questions'] if q.get('kind')=='ask')
            if pending>=5: state.message(s,'Your earlier questions are still queued. Please wait for an answer before adding more.')
            else:
                s['questions'].append({'id':secrets.token_hex(4),'kind':'ask','state':'pending','question':text,'timestamp':state.stamp()})
                state.message(s,'Question received. Qwen will answer from the saved pilot evidence when the laptop worker is available.')
        else: state.message(s,'Message received. Please send text, or use /menu for the controls.')
    return 'recorded'


def document(config, content):
    boundary='pilot'+secrets.token_hex(12)
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{config["chat_id"]}\r\n--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="pilot-report.md"\r\nContent-Type: text/markdown\r\n\r\n').encode()+content.encode()+f'\r\n--{boundary}--\r\n'.encode()
    if len(body)>500000: raise ValueError('Report limit reached')
    request=urllib.request.Request('https://api.telegram.org/bot'+config['bot_token']+'/sendDocument',body,{'Content-Type':'multipart/form-data; boundary='+boundary})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),telegram.p.w.coding.NoRedirect())
    try:
        with opener.open(request,timeout=20) as response: result=json.loads(response.read(262144))
        if result.get('ok') is not True: raise RuntimeError()
        return result['result']
    except Exception: raise RuntimeError('Report delivery uncertain') from None


def deliver(store, config, call=telegram.bot_call):
    def reserve(s):
        item=next((x for x in s['outbox'] if x['state']=='pending'),None)
        if item:
            item['state']='sending';item['attempted_at']=state.stamp()
            return copy.deepcopy(item),state.snapshot(s)
    reserved=store.mutate(reserve)
    if not reserved: return False
    item,snapshot=reserved
    try:
        if item['report']: result=document(config,views.report(snapshot))
        else:
            payload={'chat_id':config['chat_id'],'text':item['text']}
            if snapshot.get('supervision') and not payload['text'].startswith(('Observer ·','Qwen ·')):
                payload['text']='Observer · Control VM\n'+payload['text']
            q=next((q for q in snapshot['questions'] if q['id']==item.get('question_id') and q.get('state')=='pending'),None)
            payload['reply_markup']=answers.keyboard(snapshot,q,config['signing_key_hex']) if q else (item['markup'] or views.keyboard('status','brief'))
            result=call(config,'sendMessage',payload)
        if result.get('chat',{}).get('id')!=config['chat_id'] or not isinstance(result.get('message_id'),int): raise RuntimeError('Uncertain delivery identity')
        status='sent'
    except Exception: status='uncertain'
    def complete(s):
        row=next(x for x in s['outbox'] if x['id']==item['id']);row['state']=status
        if status=='sent' and s.get('supervision') and item.get('task_id'):
            s['supervision'].setdefault('message_tasks',{})[str(result['message_id'])]=item['task_id']
        if status=='uncertain': state.event(s,'Telegram delivery uncertain; not automatically resent. Use Status to recover the current result.')
        # Keep pending/uncertain evidence, and the latest 60 sent messages.
        sent=[x['id'] for x in s['outbox'] if x['state']=='sent'][-60:]
        s['outbox']=[x for x in s['outbox'] if x['state']!='sent' or x['id'] in sent]
    store.mutate(complete)
    return True


def process(store, config, update, legacy_store=None, call=telegram.bot_call):
    if type(update.get('update_id')) is not int: raise ValueError('Invalid update')
    allowed=authorized(config,update)
    query=update.get('callback_query')
    # Answer first, before database work or any slow stage. Also answer repeated taps.
    if query and isinstance(query.get('id'),str):
        try: call(config,'answerCallbackQuery',{'callback_query_id':query['id'],'text':'Click received - checking your request.' if allowed else 'This control is private.'})
        except RuntimeError: pass  # an expired toast must not discard the durable action
    if not allowed:
        store.mutate(lambda s:s.update(offset=max(s['offset'],update['update_id']+1)));return
    if update['update_id']<store.read()['value']['offset']: return
    if query and str(query.get('data','')).startswith(('a:','r:')):
        try:
            result=telegram.apply_update(legacy_store,config,update)
            outcome='Publication decision recorded: '+result['state']
        except ValueError: outcome='That publication decision is expired, already handled, or invalid. Request a current decision.'
        def legacy(s):
            if update['update_id']>=s['offset']:
                s['offset']=update['update_id']+1;state.message(s,outcome)
        store.mutate(legacy)
    else: store.mutate(lambda s:handle(s,update,config['signing_key_hex']))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('init','rpc','serve','status'))
    parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    if os.name!='posix' or os.geteuid()!=0: raise ValueError('Linux operator only')
    os.umask(0o077)
    config=telegram.d.private_json(args.config)
    dispatch=telegram.d.private_json(Path(config['dispatch_config']))
    store=Store(dispatch['container'],dispatch['database'])
    if args.action=='rpc':
        raw=sys.stdin.buffer.read(350001)
        if len(raw)>350000: raise ValueError('RPC limit')
        request=json.loads(raw)
        if request.get('action')=='ongoing_future_archive':
            import supervisor_future_archive
            print(encode_rpc(supervisor_future_archive.run(store,request,config.get('supervisor_archive',{}))))
            return
        if request.get('action') in ('ongoing_archive','ongoing_archive_history'):
            import supervisor_archive_operator
            print(encode_rpc(supervisor_archive_operator.run(store,request,config.get('supervisor_archive',{}))))
            return
        print(encode_rpc(store.mutate(lambda s:state.rpc(s,request))));return
    if args.action=='status': print(json.dumps(state.snapshot(store.read()['value'])));return
    bot=telegram.validate_config(telegram.d.private_json(Path(dispatch['telegram_approval_config'])))
    offset_path=Path(dispatch['runtime'])/'telegram-offset.json'
    if args.action=='init':
        def initialize(s):
            if s: raise ValueError('Pilot already initialized')
            s.update(state.make_state(config['source_sha']))
            if offset_path.exists(): s['offset']=telegram.d.private_json(offset_path)['next_update_id']
            state.message(s,'Your pilot control panel is ready. Every button gets an immediate acknowledgement and a follow-up result. Use Brief, Detailed or Comprehensive to choose how much you see. Open Decisions to review and start the three-task pilot.',views.keyboard('status','brief'))
            show(s,'questions','brief',bot['signing_key_hex'])
        store.mutate(initialize);return
    import fcntl
    with (Path(dispatch['runtime'])/'telegram-consumer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        legacy_store=controller_state.Store(dispatch['container'],dispatch['database'])
        while True:
            try:
                for _ in range(5):
                    if not deliver(store,bot): break
                offset=store.read()['value']['offset']
                updates=telegram.bot_call(bot,'getUpdates',{'offset':offset,'limit':10,'timeout':10,'allowed_updates':['message','callback_query']})
                if not isinstance(updates,list): raise ValueError('Invalid Telegram batch')
                for update in updates: process(store,bot,update,legacy_store)
                offset=store.read()['value']['offset']
                temp=offset_path.with_suffix('.pilot.tmp')
                with temp.open('w') as stream:
                    json.dump({'next_update_id':offset},stream);stream.flush();os.fsync(stream.fileno())
                os.replace(temp,offset_path)
            except Exception as error:
                print('Pilot transport waiting after '+type(error).__name__,file=sys.stderr,flush=True)
                time.sleep(5)


if __name__=='__main__':
    try: main()
    except Exception as error: raise SystemExit('Pilot stopped: '+type(error).__name__) from None

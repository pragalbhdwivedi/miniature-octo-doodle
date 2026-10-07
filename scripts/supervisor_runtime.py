"""Board integration, task-bound Telegram conversation and verified PR observations."""
import copy
import hashlib
import secrets
import re
import pilot_state as pilot
import supervisor_board as board


def notice(s,j,text):
    board.ensure(s)
    sid=j['supervisor_id']
    coder=j.get('coding',{});review=j.get('review',{})
    def model(item):return item.get('route',{}).get('model','not yet recorded')
    lines=['Observer · Control VM | '+sid,text,
           'Performed by: '+model(coder)+(' · Laptop/local' if coder.get('route',{}).get('provider')=='ollama_local' or j['owner']=='local' else ' · Laptop/cloud CLI'),
           'Checked by: '+model(review)+(' · OpenAI API via gateway' if review.get('route',{}).get('provider')=='openai_api_via_gateway' else '')]
    if j.get('publication'):lines.append(j['publication'].get('pull_request',{}).get('url',''))
    if review.get('confidence') is not None:lines.append('Reviewer confidence: '+str(review['confidence'])+'/10 · '+review.get('confidence_reason',''))
    markup={'inline_keyboard':[[{'text':'Explain','callback_data':'st:'+sid+':ask'},
        {'text':'Request changes','callback_data':'st:'+sid+':changes'},
        {'text':'Custom','callback_data':'st:'+sid+':custom'}],
        [{'text':'Open task controls','url':'https://control.aadi.dgoi.local/'}]]}
    pilot.message(s,'\n'.join(lines),markup)
    s['outbox'][-1]['task_id']=sid


def record(s):
    if not s.get('supervision'):return
    result=board.record(s)
    if result['digest_due']:
        data=board.snapshot(s);counts={}
        for j in data['tasks']:counts[j['state']]=counts.get(j['state'],0)+1
        pilot.message(s,'Observer · Control VM\nYour hourly work update: '+', '.join(str(v)+' '+k.replace('_',' ') for k,v in counts.items())+
                      '.\nI will send completions and blockers as they happen. Reply with a task ID to ask about it.')


def rpc(s,r):
    board.ensure(s)
    action=r['action']
    if action=='ongoing_board_data':return {'jobs':copy.deepcopy(s['ongoing']['jobs']),'supervision':copy.deepcopy(s['supervision']),
        'ongoing':{**{k:copy.deepcopy(s['ongoing'][k]) for k in ('enabled','calls','day','policy')},
                   'lease_active':bool(s['ongoing'].get('lease'))}}
    if action=='ongoing_intake_hold':
        item=next(i for i in s['supervision']['intake'] if i['id']==r['task_id'])
        if item['state']=='needs_scope':return {'ok':True}
        if item['state']!='planned':raise ValueError('Intake is no longer pending')
        item.update(state='needs_scope',error=str(r['reason'])[:800],updated_at=pilot.stamp())
        pilot.message(s,item['id']+': '+item['error']+' Reply with this task ID and the missing project/module details.')
        s['supervision']['revision']+=1
        return {'ok':True}
    if action=='ongoing_documents':return {'documents':board.documents(s)}
    if action=='ongoing_board_snapshot':return board.snapshot(s)
    if action=='ongoing_board_action':return board.action(s,r['request'])
    if action=='ongoing_pr_sync':
        j=next(j for j in s['ongoing']['jobs'] if j['id']==r['job_id']);p=r['result']
        saved=j.get('publication',{}).get('pull_request',{})
        if (p.get('url')!=saved.get('url') or p.get('repository')!=j.get('repository','pragalbhdwivedi/aadi')
            or p.get('number')!=int(saved.get('url','/0').rsplit('/',1)[1])
            or not re.fullmatch('[0-9a-f]{40}',p.get('head_sha',''))
            or p.get('state') not in ('draft','open','closed','merged')):
            raise ValueError('PR observation differs from the published task')
        meta=s['supervision']['tasks'][j['supervisor_id']]
        old=j.get('pr_observation',{})
        j['pr_observed_at']=pilot.stamp()
        if old==p:return {'ok':True,'changed':False}
        j['pr_observation']=copy.deepcopy(p)
        if p['state'] in ('merged','closed'):meta['review_state']=p['state']
        elif any(x.get('state')=='CHANGES_REQUESTED' and x.get('actor_type')=='User'
                 and x.get('actor') in s['supervision'].get('reviewers',['pragalbhdwivedi'])
                 for x in p.get('review_decisions',{}).values()):meta['review_state']='changes_requested'
        elif any(x.get('state')=='APPROVED' and x.get('at_head') and x.get('actor_type')=='User'
                 and x.get('actor') in s['supervision'].get('reviewers',['pragalbhdwivedi'])
                 for x in p.get('review_decisions',{}).values()):meta['review_state']='reviewed'
        else:meta['review_state']='not_reviewed'
        # Only the explicitly admitted owner account can create correction work.
        for review in p.get('requested_changes',[]):
            if review.get('actor') not in s['supervision'].get('reviewers',['pragalbhdwivedi']) or review.get('actor_type')!='User':continue
            rid='github-review-'+str(review['id'])
            if rid in s['supervision']['requests']:continue
            request={'request_id':rid,'revision':s['supervision']['revision'],'action':'request_changes',
                     'task_id':j['supervisor_id'],'actor':'GitHub: '+review['actor'],
                     'text':review.get('body') or 'Review requested changes; inspect linked GitHub review before rerun.'}
            if len(request['text'])>2000:request['text']=request['text'][:1990]+' [shortened]'
            board.action(s,request)
            # A review on old bytes is retained, but cannot silently rerun the new head.
            if not review.get('at_head') or review.get('body_truncated'):
                s['supervision']['corrections'][-1]['state']='reconciliation_required'
        b=s['supervision'];b['revision']+=1
        b['events'].append({'sequence':len(b['events'])+1,'timestamp':pilot.stamp(),'actor':'GitHub observer',
            'task_id':j['supervisor_id'],'action':'pr_review_sync','detail':'PR '+str(p['number'])+' '+p['state']+'; head '+p['head_sha']})
        return {'ok':True,'changed':True}
    if action=='ongoing_consume_corrections':
        if s['ongoing'].get('lease') or not s['ongoing']['enabled']:return {'consumed':0}
        consumed=0
        for c in s['supervision']['corrections']:
            if c['state']!='rerun_waiting':continue
            j=next(j for j in s['ongoing']['jobs'] if j['id']==c['key'])
            if j['id'] not in r.get('verified_jobs',[]):continue
            if j['state']!='draft_ready' or j.get('supervision_paused'):continue
            current_scope=board._hash({k:j.get(k) for k in ('id','owner','repo','repository','project','operation','development_profile','paths','write_paths','test_files','source_sha','prompt')})
            if current_scope!=c['scope_digest'] or c['requested_attempt']!=j['attempt']+1:
                c['state']='reconciliation_required';continue
            observed=j.get('pr_observation',{})
            publication=j.get('publication',{})
            expected=publication.get('commit') or publication.get('pull_request',{}).get('head_sha')
            if observed.get('state')!='draft' or not expected or observed.get('head_sha')!=expected:
                c['state']='reconciliation_required';continue
            board.record(s)
            j.update(state='queued',attempt=j['attempt']+1,repair=c['text'],repair_start=j['attempt']+1)
            for k in ('coding','tests','review','error'):j.pop(k,None)
            c.update(state='running',started_at=pilot.stamp(),actual_attempt=j['attempt'])
            notice(s,j,'Your correction is queued. I will update the same PR after fresh tests and review.')
            consumed+=1
        record(s);return {'consumed':consumed}
    raise ValueError('Unknown board RPC')


def conversation(s,update):
    """Called only after Telegram owner/chat authorization and offset deduplication."""
    if not s.get('supervision'):return False
    query=update.get('callback_query',{});data=query.get('data','')
    message=update.get('message',{});text=message.get('text','').strip()
    if data.startswith('st:'):
        _,sid,mode=data.split(':')
        if sid not in s['supervision']['tasks']:raise ValueError('Task is no longer available')
        if mode=='ask':
            board.action(s,{'action':'ask','task_id':sid,'text':'Explain this task, its result, confidence and what happens next.',
                'request_id':'tg-'+str(update['update_id']),'revision':s['supervision']['revision'],'actor':'Owner via Telegram'})
            pilot.message(s,'Click received. I’m preparing an explanation for '+sid+'.')
        elif mode in ('changes','custom'):
            s['supervision']['pending_reply']={'task_id':sid,'mode':mode}
            pilot.message(s,'Click received. Reply with '+('the correction you want for ' if mode=='changes' else 'your question about ')+sid+'. Use /cancel to cancel.')
        return True
    if not text:return False
    pending=s['supervision'].get('pending_reply')
    if text=='/cancel' and pending:
        s['supervision'].pop('pending_reply');pilot.message(s,'Task reply cancelled.');return True
    target=None
    if not pending and message.get('reply_to_message'):
        mid=message['reply_to_message']['message_id']
        target=s['supervision'].get('message_tasks',{}).get(str(mid))
    if not pending and not target:
        ids=set(re.findall(r'(?i)\bSUP-[0-9]{6}\b',text))
        target=next((sid for sid in s['supervision']['tasks'] if sid in {x.upper() for x in ids}),None) if len(ids)==1 else None
    if pending or target:
        sid=pending['task_id'] if pending else target
        command='request_changes' if pending and pending['mode']=='changes' else 'ask'
        result=board.action(s,{'action':command,'task_id':sid,'text':text,'request_id':'tg-'+str(update['update_id']),
            'revision':s['supervision']['revision'],'actor':'Owner via Telegram'})
        s['supervision'].pop('pending_reply',None)
        pilot.message(s,'Received for '+sid+'. '+('Your correction is recorded; I’ll check the saved PR and queue the rerun.' if command=='request_changes' else 'Qwen will reply using this task’s saved evidence.'))
        return True
    return False

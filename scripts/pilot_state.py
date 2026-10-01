"""Bounded pilot state machine. Models cannot change scope or stage authority."""
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
import secrets


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def event(s, text):
    s['events'].append({'timestamp': stamp(), 'summary': text})
    s['events'] = s['events'][-100:]


def message(s, text, markup=None, report=False, question_id=None):
    s['outbox'].append({'id': secrets.token_hex(8), 'state': 'pending',
                        'text': text[:3500], 'markup': markup, 'report': report,'question_id':question_id})


def begin_recovery(s, evidence):
    """Operator invokes after fresh owner approval; not exposed through model RPC."""
    b=s['batch']
    if b['state'] not in ('blocked','expired') or s.get('recovery'):
        raise ValueError('Recovery is not available or was already authorized')
    if any(x['state']=='running' for x in s['leases'].values()):
        raise ValueError('An in-flight stage must be reconciled first')
    tasks=s['tasks']
    if len(tasks)!=3 or any(t['state']!='verified' for t in tasks[:2]) or tasks[2]['state']!='blocked':
        raise ValueError('Recovery requires exactly the saved third task')
    task=tasks[2]
    if (evidence.get('task_id')!=task.get('coordination_task_id')
            or evidence.get('source_sha')!=task['source_sha']
            or evidence.get('state')!='human_review_required'
            or evidence.get('advisory_status')!='unavailable'):
        raise ValueError('Recovery evidence mismatch')
    s['recovery']={'authorized_at':stamp(),'previous_deadline':b['deadline'],
                   'starting_gpt_calls':b['gpt_calls'],'max_new_gpt_calls':2,'minutes':15,
                   'new_coder_runs':False}
    b.update(state='running',deadline=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),max_gpt_calls=b['gpt_calls']+2)
    task.update(state='ready_test',coordination_result=copy.deepcopy(evidence))
    event(s,'Owner authorized 15-minute saved-proposal recovery with at most two GPT reviews and no coder reruns.')
    message(s,'Recovery started: I will test task 3’s saved proposals, independently review the selected result, then check the combined file. Limit: 15 minutes and two GPT reviews. No coder regeneration. Publication still needs your Telegram approval.')


def make_state(sha):
    batch_id = secrets.token_hex(6)
    tasks = []
    for i, (title, mutation, detail) in enumerate([
        ('Keep source-system names case-sensitive', 'system-case',
         "Use identical mappings with source_system 'hikcentral' and 'HikCentral'."),
        ('Preserve spaces inside external IDs', 'id-space',
         "Use otherwise identical mappings with source_record_id 'ID 7' and 'ID7'."),
        ('Keep external IDs case-sensitive', 'id-case',
         "Use otherwise identical mappings with source_record_id 'abc' and 'ABC'."),
    ], 1):
        prompt = ('Add exactly one focused unittest to tests/test_identity_contract.py. '
                  'Preserve all existing tests and imports. '+detail+
                  ' Deep-copy the fixture. Assert two mappings and two verified mappings, '
                  'no input mutation in either order, and equal receipts after reversing mappings. '
                  'The added test must detect normalization of the relevant field in the scope tuple. '
                  'Only this test file may change; no dependencies or production code. Do not claim tests ran. '
                  'Use straight-line deepcopy, validate_snapshot, assertEqual, append/reverse/update calls; '
                  'no helpers, decorators, imports or loops. Use a distinct descriptive test name.')
        tasks.append({'id': 't'+str(i), 'title': title, 'mutation': mutation, 'prompt': prompt,
                      'source_sha': sha, 'paths': ['tests/test_identity_contract.py'],
                      'state': 'pending', 'attempt': 0})
    return {'batch': {'id': batch_id, 'goal': 'Verify three synthetic identity regression tasks through both coders, isolated tests and independent GPT review.',
                     'state': 'awaiting_scope', 'created_at': stamp(), 'deadline': None,
                     'max_tasks': 3, 'gpt_calls': 0, 'max_gpt_calls': 10},
            'tasks': tasks, 'events': [], 'questions': [], 'inbox': [], 'outbox': [],
            'offset': 0, 'leases': {}, 'totals': {},
            'limits': {'minutes': 60, 'max_tasks': 3, 'repairs_per_task': 1,
                       'gpt_calls': 10, 'paid_api_fallback': False, 'publication': 'explicit Telegram approval'}}


def scope_digest(s):
    return digest({'batch': s['batch']['id'], 'tasks': [{k:t[k] for k in
                    ('id','title','prompt','source_sha','paths','mutation')} for t in s['tasks']],
                   'limits': s['limits']})


def signed(s, action, key):
    payload = scope_digest(s) if action == 'start' else s.get('publication_digest', '')
    raw = s['batch']['id']+':'+action+':'+payload
    return 'p!'+action+':'+hmac.new(bytes.fromhex(key),raw.encode(),hashlib.sha256).hexdigest()[:24]


def decide(s, data, key):
    action = data.split(':')[0].removeprefix('p!')
    if action not in ('start','publish') or not hmac.compare_digest(data, signed(s,action,key)):
        raise ValueError('Invalid or outdated decision')
    b=s['batch']
    if action=='start':
        if b['state']!='awaiting_scope': raise ValueError('This scope decision was already handled')
        b['state']='ready_plan'
        b['deadline']=(datetime.now(timezone.utc)+timedelta(minutes=60)).isoformat()
        event(s,'Owner approved the three-task pilot scope.')
        message(s,'Pilot approved. I will prepare the task prompts, then send task 1 to both coders. You can pause from Controls.')
    else:
        if b['state']!='awaiting_publication' or not s.get('publication_digest'):
            raise ValueError('No exact verified publication awaits approval')
        if deadline_reached(s): raise ValueError('Pilot deadline reached; publication remains stopped')
        if digest(s.get('publication')) != s['publication_digest']:
            raise ValueError('Publication artifact changed; a new verified decision is required')
        b['state']='ready_publish'
        s['approved_publication_digest']=s['publication_digest']
        event(s,'Owner approved the exact combined publication artifact.')
        message(s,'Publication approved for the verified artifact. I will recheck the source before updating Dev.')


def active(s):
    return s['batch']['state'] not in ('paused','awaiting_scope','completed','expired','blocked','awaiting_publication')


def deadline_reached(s):
    deadline=s['batch'].get('deadline')
    return bool(deadline and datetime.now(timezone.utc)>=datetime.fromisoformat(deadline))


def work(s):
    b=s['batch']
    # Local questions remain available after the coding pilot time limit.
    for q in s['questions']:
        if q.get('kind')=='ask' and q['state']=='pending' and not any(x['state']=='running' for x in s['leases'].values()):
            q['state']='answering'; return reserve(s,'ask',question=q)
    if deadline_reached(s):
        if active(s):
            b['state']='expired'; message(s,'The pilot reached its 60-minute limit. No new stage will start. In-flight results will be retained; use Status for details.')
        return {'action':'idle'}
    if not active(s): return {'action':'idle'}
    if any(x['state']=='running' for x in s['leases'].values()): return {'action':'idle'}
    if b['state']=='ready_plan': return reserve(s,'plan')
    if b['state']=='ready_publish': return reserve(s,'publish')
    for task in s['tasks']:
        if task['state']=='verified': continue
        if task['state']=='pending':
            task['state']='ready'
        if task['state']=='ready': return reserve(s,'dispatch',task)
        if task['state']=='coding':
            return {'action':'observe','batch':copy.deepcopy(b),'task':copy.deepcopy(task)}
        if task['state']=='ready_test': return reserve(s,'test',task)
        if task['state']=='ready_review': return reserve(s,'review',task)
        return {'action':'idle'}
    if b['state']=='running': return reserve(s,'prepare_publication')
    return {'action':'idle'}


def reserve(s, stage, task=None, question=None):
    b=s['batch']
    if s.get('recovery') and stage in ('plan','dispatch'):
        b['state']='blocked';message(s,'Recovery stopped: the approved recovery does not allow new coder runs.')
        return {'action':'idle'}
    if stage!='ask' and deadline_reached(s): return {'action':'idle'}
    if stage=='publish' and (not s.get('approved_publication_digest')
            or digest(s.get('publication'))!=s['approved_publication_digest']
            or s.get('publication_digest')!=s['approved_publication_digest']):
        raise ValueError('Publication artifact differs from the approved result')
    if stage in ('plan','dispatch','review','prepare_publication'):
        if b['gpt_calls']>=b['max_gpt_calls']:
            b['state']='blocked'; message(s,'The GPT call limit is reached. The pilot is paused; results are saved.')
            return {'action':'idle'}
        b['gpt_calls']+=1
    token=secrets.token_hex(16)
    s['leases'][token]={'stage':stage,'task_id':task['id'] if task else None,
                        'question_id':question['id'] if question else None,'state':'running','started_at':stamp()}
    if task: task['state']=stage
    elif stage=='plan': b['state']='planning'
    labels={'plan':'Preparing the three task prompts','dispatch':'Sending to Gemini Pro and independent Codex',
            'test':'Running isolated tests and defect-detection checks','review':'Independent GPT verification',
            'prepare_publication':'Checking the combined result before asking to publish','publish':'Publishing the approved result'}
    if stage in labels:
        text=(task['title']+'\n' if task else '')+labels[stage]+'.'
        event(s,text); message(s,text+'\nNo input is needed right now.')
    reply={'action':stage,'token':token,'batch':copy.deepcopy(b),'tasks':copy.deepcopy(s['tasks'])}
    if task: reply['task']=copy.deepcopy(task)
    if question: reply.update(question=copy.deepcopy(question),snapshot=snapshot(s))
    if stage=='publish': reply.update(publication=s.get('publication'),publication_digest=s.get('approved_publication_digest'))
    return reply


def finish(s, request):
    if request.get('batch_id')!=s['batch']['id']: raise ValueError('Wrong batch')
    lease=s['leases'].get(request.get('token'))
    if not lease or lease['state']!='running' or lease['stage']!=request.get('stage') or lease['task_id']!=request.get('task_id'):
        raise ValueError('Stage ownership mismatch or replay')
    result=request.get('result',{})
    if not isinstance(result,dict) or len(json.dumps(result))>300000: raise ValueError('Result too large')
    lease['state']='finished';lease['finished_at']=stamp()
    task=next((t for t in s['tasks'] if t['id']==lease['task_id']),None)
    stage=lease['stage'];b=s['batch']
    if request['action']=='fail':
        if stage=='ask':
            q=next(q for q in s['questions'] if q['id']==lease['question_id']);q['state']='blocked'
            message(s,'I could not answer that question because the local model or worker is unavailable. Your question is saved; Status and Inputs/Outputs remain available.')
        else:
            if task: task['state']='blocked'
            b['state']='blocked';message(s,'The pilot stopped at '+stage+'. No automatic retry will occur. Evidence is saved for review; use Outputs for details.')
        event(s,'Stage failed: '+stage); return
    if stage=='plan':
        prompts=result.get('prompts')
        if not isinstance(prompts,list) or len(prompts)!=3 or any(not isinstance(x,str) or not 1<=len(x)<=1000 for x in prompts): raise ValueError('Invalid plan')
        for t,p in zip(s['tasks'],prompts):
            # The model's wording is advisory; the admitted scope stays exact.
            t['planner_note']=p
        if b['state']=='paused': b['resume_state']='running'
        elif b['state']!='expired': b['state']='running'
        message(s,'The task plan is ready. Qwen coordination will work through the three approved tasks in order.')
    elif stage=='dispatch':
        child=result.get('coordination_task_id')
        expected='pilot-'+b['id']+'-'+task['id']+'-a'+str(task['attempt'])
        if child!=expected: raise ValueError('Wrong delegated identity')
        if result.get('source_sha')!=task['source_sha']: raise ValueError('Delegated source changed')
        task['coordination_task_id']=child;task['state']='coding'
    elif stage=='test':
        task['results']=result;task['tests']=result;task['state']='ready_review'
    elif stage=='review':
        review=result.get('review',result);task['review']=review
        choice=review.get('selected');verdict=review.get('verdict')
        evidence=task.get('results',{}).get('candidates',{}).get(choice,{})
        if verdict=='pass' and choice in ('gemini','codex') and evidence.get('passed') is True:
            task['selected']=choice;task['state']='verified';task['result']=evidence
            message(s,task['title']+'\nVerified: the selected proposal passed isolated tests and independent GPT review. It is not published yet.')
        elif verdict=='repair' and task['attempt']<1 and not s.get('recovery'):
            task['attempt']+=1;task['state']='ready'
            task['prompt']=(task['prompt']+' Repair the prior proposal using these bounded findings: '+json.dumps(review.get('findings',[])))[:1000]
            message(s,task['title']+'\nA repair is needed. I will allow one repair attempt within the existing scope.')
        else:
            task['state']='waiting_input';b['state']='blocked'
            q={'id':secrets.token_hex(4),'kind':'decision','state':'pending','task_id':task['id'],
               'question':'Verification needs your decision: '+json.dumps(review.get('findings',[]))[:1400]}
            q['options']=['Keep stopped','Request a repair']
            s['questions'].append(q);message(s,q['question']+'\nChoose an answer below, or Custom to type your own. Answers are recorded for review; they do not authorize an uncertain rerun.',question_id=q['id'])
    elif stage=='ask':
        q=next(q for q in s['questions'] if q['id']==lease['question_id'])
        answer=result.get('answer','')
        if not isinstance(answer,str) or not answer: raise ValueError('Missing answer')
        q.update(state='answered',answer=answer[:8000])
        message(s,'Qwen answer (advisory, based on saved task evidence):\n'+answer[:3200])
    elif stage=='prepare_publication':
        if result.get('passed') is not True: raise ValueError('Combined acceptance did not pass')
        s['publication']=result;s['publication_digest']=digest(result)
        if b['state']=='paused': b['resume_state']='awaiting_publication'
        elif b['state']!='expired': b['state']='awaiting_publication'
        message(s,'All three tasks are verified, and the combined test file passed its checks. Publication requires your approval. Open Decisions to approve this exact result or leave it unpublished.')
    elif stage=='publish':
        if result.get('published') is not True: raise ValueError('Publication not established')
        b['state']='completed';s['publication_result']=result
        message(s,'Pilot complete. The approved development result was published. Main and production deployment were not changed. Use Outputs or Comprehensive for the evidence.')
    if isinstance(result.get('usage'),dict):
        s['totals'][lease['started_at']]=result['usage']
    event(s,'Completed '+stage+((' for '+task['title']) if task else ''))


def snapshot(s):
    value={k:copy.deepcopy(s[k]) for k in ('batch','tasks','events','questions','totals','limits')}
    value.update({k:copy.deepcopy(s.get(k,{})) for k in ('publication','publication_result','worker','recovery')})
    value['totals']={'gpt_calls':s['batch']['gpt_calls'],
                     'records':[{'started_at':at,'usage':copy.deepcopy(usage)} for at,usage in s['totals'].items()]}
    return value


def rpc(s, request):
    action=request.get('action')
    if action=='work':
        s['worker']={'last_seen':stamp()}
        return work(s)
    if action in ('finish','fail'): finish(s,request);return {'ok':True}
    if action=='observed':
        if request.get('batch_id')!=s['batch']['id']: raise ValueError('Wrong batch')
        task=next(t for t in s['tasks'] if t['id']==request.get('task_id'))
        if task['state']!='coding': raise ValueError('Wrong observed state')
        if request.get('coordination_task_id')!=task.get('coordination_task_id'):
            raise ValueError('Wrong observed delegated task')
        result=request.get('result',{})
        if result.get('state')=='delivery_uncertain':
            if not task.get('delivery_notice'):
                task['delivery_notice']=True
                q={'id':'delivery-'+task['id'],'kind':'decision','state':'pending','task_id':task['id'],
                   'question':'Antigravity delivery was not confirmed. Open AADI Two-Coder Acceptance Task and send: Run next queued task. The exact-task claim prevents duplicate coding.'}
                s['questions'].append(q)
                event(s,'Antigravity delivery uncertain for '+task['title']+'; no automatic resend.')
                q['options']=['Sent','Still blocked']
                message(s,'Input needed: '+q['question']+' Choose your answer below. Coding will continue when the saved task is claimed.',question_id=q['id'])
            return {'ok':True}
        if result.get('state')=='human_review_required':
            if result.get('source_sha')!=task['source_sha']: raise ValueError('Observed source changed')
            task['coordination_result']=result;task['state']='ready_test'
            for q in s['questions']:
                if q.get('task_id')==task['id'] and q['id'].startswith('delivery'): q['state']='resolved'
            event(s,'Both candidates received for '+task['title'])
        elif result.get('state')=='blocked':
            task['state']='blocked';s['batch']['state']='blocked';message(s,'A coder or local review stopped. I retained its claim and will not retry automatically.')
        return {'ok':True}
    if action=='status': return snapshot(s)
    raise ValueError('Unknown pilot operation')

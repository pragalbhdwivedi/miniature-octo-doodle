"""Durable ongoing draft-work policy. No model can grant destructive authority."""
import copy
import re
import secrets
from datetime import datetime, timezone, timedelta
import pilot_state as pilot

TERMINAL = {'draft_ready', 'blocked', 'needs_owner'}


def install(s, catalog):
    if s.get('ongoing'):
        raise ValueError('Ongoing controller already installed')
    if s['batch']['state'] != 'completed':
        raise ValueError('Finish or reconcile the pilot first')
    jobs=[]
    for item in catalog:
        if (not re.fullmatch('[a-z0-9-]{1,48}', item['id']) or
                item['owner'] not in ('gemini','codex','local') or item.get('risk')!='reversible' or
                item.get('operation')!='test_addition' or not item.get('write_paths')):
            raise ValueError('Only admitted reversible test additions are enabled')
        if any(j['id']==item['id'] for j in jobs):raise ValueError('Duplicate task')
        jobs.append({**copy.deepcopy(item),'state':'queued','attempt':0})
    known={j['id'] for j in jobs}
    for j in jobs:
        if any(d not in known or d==j['id'] for d in j.get('depends_on',[])):raise ValueError('Invalid dependency')
    done=set()
    while len(done)<len(jobs):
        ready={j['id'] for j in jobs if set(j.get('depends_on',[]))<=done}
        if ready<=done:raise ValueError('Cyclic dependencies')
        done|=ready
    s['ongoing']={'enabled':True,'jobs':jobs,'lease':None,'created_at':pilot.stamp(),
        'policy':{'max_active':3,'max_calls_per_day':12,'repairs':1,'publication':'draft_pr',
                  'routine_decisions':'automatic','destructive':'owner_required'},
        'day':datetime.now(timezone.utc).date().isoformat(),'calls':0,'planned':False}
    pilot.message(s,'Ongoing work enabled: separate subtasks for cloud and local coders; routine choices are automatic. Tested results go to draft PRs for your later review. Destructive actions stay pending. Idle checks use no models.')


def reserve(s, stage, job=None):
    o=s['ongoing'];today=datetime.now(timezone.utc).date().isoformat()
    if today!=o['day']:o.update(day=today,calls=0)
    charge=1 if stage in ('codex','antigravity','review') or (stage=='admit' and job['owner']=='gemini' and job.get('transport','sidecar')=='sidecar') else 0
    if stage=='parallel_code':charge=sum(j['owner']!='local' for j in job)
    if o['calls']+charge>o['policy']['max_calls_per_day']:return {'action':'idle','reason':'daily_model_limit'}
    o['calls']+=charge
    token=secrets.token_hex(16)
    o['lease']={'stage':stage,'job_id':job['id'] if isinstance(job,dict) else None,'token':token,'started_at':pilot.stamp()}
    return {'action':stage,'job':copy.deepcopy(job) if isinstance(job,dict) else None,'token':token,
            'jobs':copy.deepcopy(o['jobs']) if stage=='plan' else []}


def work(s):
    o=s.get('ongoing')
    if not o:return {'action':'idle'}
    o['last_seen']=pilot.stamp()
    if not o['enabled'] or o.get('lease'):return {'action':'idle'}
    if not o['planned']:return reserve(s,'plan')
    for j in o['jobs']:
        if j['state']=='waiting_quota' and datetime.fromisoformat(j['retry_at'])<=datetime.now(timezone.utc):
            j['state']='antigravity_ready'
    # Admit both owners before starting a blocking Codex CLI call.
    active=[j for j in o['jobs'] if j['state'] not in TERMINAL|{'queued'}]
    for j in o['jobs']:
        if j['state']!='queued' or len(active)>=o['policy']['max_active']:continue
        if any(x['owner']==j['owner'] or {p.casefold() for p in x['write_paths']}&{p.casefold() for p in j['write_paths']} for x in active):continue
        if any(next(x for x in o['jobs'] if x['id']==d)['state']!='draft_ready' for d in j.get('depends_on',[])):continue
        return reserve(s,'admit',j)
    ready_code=[j for j in o['jobs'] if j['state'] in ('codex_ready','antigravity_ready','local_ready')]
    if len(ready_code)>=2:
        result=reserve(s,'parallel_code',ready_code)
        if result['action']!='idle':
            o['lease']['job_ids']=[j['id'] for j in ready_code];result['jobs']=copy.deepcopy(ready_code)
        else:
            local=next((j for j in ready_code if j['owner']=='local'),None)
            if local:return reserve(s,'local',local)
        return result
    budget_wait=False
    for stage,ready in [('test','ready_test'),('review','ready_review'),('publish','ready_publish'),('codex','codex_ready'),('antigravity','antigravity_ready'),('local','local_ready')]:
        for j in o['jobs']:
            if j['state']==ready:
                reserved=reserve(s,stage,j)
                if reserved['action']!='idle':return reserved
                budget_wait=True
    coding=[copy.deepcopy(j) for j in o['jobs'] if j['state']=='coding']
    return {'action':'observe','jobs':coding} if coding else ({'action':'idle','reason':'daily_model_limit'} if budget_wait else {'action':'idle'})


def finish(s, request):
    o=s['ongoing'];lease=o.get('lease')
    if not lease or not secrets.compare_digest(lease['token'],str(request.get('token',''))):raise ValueError('Stage ownership mismatch')
    result=request.get('result',{});stage=lease['stage']
    j=next((j for j in o['jobs'] if j['id']==lease['job_id']),None)
    if request['action']=='ongoing_fail':
        if j:j.update(state='blocked',error=result.get('error','Stage failed; retained for reconciliation'))
        elif stage=='parallel_code':
            for task in o['jobs']:
                if task['id'] in lease['job_ids']:task.update(state='blocked',error='Parallel stage interrupted; reconcile saved claims before any retry.')
        else:o['planned']=True
        pilot.message(s,'Technical recovery needed: '+(j['title'] if j else 'Local planning')+'. This is not an approval request; no answer is required from you. Saved evidence is held for recovery; other independent work can continue.')
    elif stage=='plan':
        ids=result.get('order',[])
        if len(ids)!=len(o['jobs']) or set(ids)!={j['id'] for j in o['jobs']}:raise ValueError('Planner changed admitted scope')
        o['jobs'].sort(key=lambda j:ids.index(j['id']));o['planned']=True;o['planning']=result
    elif stage=='admit':
        next_state=('local_ready' if j['owner']=='local' else 'codex_ready' if j['owner']=='codex' else ('antigravity_ready' if j.get('transport')=='cli' else 'coding'))
        j.update(state=next_state,child_id=result['child_id'],issue=result['issue'])
        pilot.message(s,j['owner'].capitalize()+' assigned: '+j['title']+'. '+result['issue'].get('url',''))
    elif stage in ('codex','antigravity','local'):
        if stage=='antigravity' and result.get('state')=='quota_wait':quota_wait(s,j,result)
        else:j.update(state='ready_test',coding=result)
    elif stage=='parallel_code':
        if set(result)!=set(lease['job_ids']):raise ValueError('Parallel result scope mismatch')
        for task in o['jobs']:
            if task['id'] not in result:continue
            item=result[task['id']]
            if item.get('state')=='quota_wait' and task['owner']=='gemini':quota_wait(s,task,item)
            elif item.get('state')=='human_review_required':task.update(state='ready_test',coding=item)
            else:
                task.update(state='blocked',error='Assigned coder stopped; evidence retained.')
                pilot.message(s,'Technical recovery needed: '+task['title']+'. No approval or answer is required from you. Saved evidence is held; other completed work continues.')
    elif stage=='test':
        j['tests']=result
        if result.get('passed'):j['state']='ready_review'
        else:repair(s,j,'Automated tests failed. '+result.get('summary',''))
    elif stage=='review':
        j['review']=result
        if result.get('verdict')=='pass' and j.get('tests',{}).get('passed'):j['state']='ready_publish'
        else:repair(s,j,'Review requested repair. '+'; '.join(result.get('findings',[])))
    elif stage=='publish':
        if not j.get('tests',{}).get('passed') or j.get('review',{}).get('verdict')!='pass':raise ValueError('Missing acceptance')
        pr=result.get('pull_request',{})
        if (result.get('task_id')!=j['id'] or result.get('source_sha')!=j['source_sha'] or
                result.get('merged') is not False or result.get('deployed') is not False or
                pr.get('state')!='confirmed' or pr.get('draft') is not True or pr.get('base')!='Dev' or
                pr.get('branch')!=result.get('branch') or not result.get('branch','').startswith('supervisor/') or
                not pr.get('url','').startswith('https://github.com/pragalbhdwivedi/aadi/pull/')):
            raise ValueError('Publication receipt does not match a draft for this task')
        j.update(state='draft_ready',publication=result)
        pilot.message(s,'Ready for your later review: '+j['title']+'\n'+result.get('pull_request',{}).get('url','')+'\nTests and review passed. Saved as a draft PR; no project integration was performed.')
    else:raise ValueError('Unknown ongoing stage')
    o['lease']=None
    pilot.event(s,'Ongoing '+stage+' finished'+(' for '+j['id'] if j else ''))


def quota_wait(s,j,result):
    instant=datetime.fromisoformat(result['retry_at'])
    if instant.tzinfo is None or result.get('inference_started') is not False:
        raise ValueError('Quota wait requires pre-inference evidence and observed reset')
    s['ongoing']['calls']-=1
    j.update(state='waiting_quota',retry_at=result['retry_at'])
    display=instant.astimezone(timezone(timedelta(hours=5,minutes=30))).strftime('%d %b, %I:%M %p IST')
    pilot.message(s,'The available model allowances are used up. '+j['title']+
        ' is waiting until '+display+'. No generation started. I will recheck automatically; no answer is required.')


def repair(s,j,reason):
    if j['attempt']<s['ongoing']['policy']['repairs']:
        j.update(state='queued',attempt=j['attempt']+1,repair=reason[:1500])
        pilot.message(s,'Automatic repair: '+j['title']+'. Returning only this subtask to its owner; one repair is allowed.')
    else:
        j.update(state='blocked',error=reason[:1500])
        pilot.message(s,'Repair limit reached: '+j['title']+'. Saved for technical review; no approval or answer is required from you. Other work continues.')


def rpc(s,r):
    if r['action']=='ongoing_sync':
        catalog=r['catalog'];o=s['ongoing']
        if not isinstance(catalog,list) or len(catalog)>100:raise ValueError('Catalog bound exceeded')
        existing={j['id']:j for j in o['jobs']}
        if not set(existing)<={j['id'] for j in catalog}:raise ValueError('Catalog cannot remove retained work')
        for item in catalog:
            if item['id'] in existing and any(existing[item['id']].get(k)!=v for k,v in item.items()):
                raise ValueError('Existing catalog task changed; use a new ID')
        probe=copy.deepcopy(s);probe.pop('ongoing');install(probe,catalog)
        added=[j for j in probe['ongoing']['jobs'] if j['id'] not in existing]
        if added:
            o['jobs'].extend(added);o['catalog_updated_at']=pilot.stamp()
            pilot.message(s,'Received '+str(len(added))+' new admitted task(s) from the timestamped operator catalog. Routine assignment and draft review will continue automatically.')
        return {'added':len(added)}
    if r['action']=='ongoing_work':return work(s)
    if r['action'] in ('ongoing_finish','ongoing_fail'):finish(s,r);return {'ok':True}
    if r['action']=='ongoing_observed':
        j=next(j for j in s['ongoing']['jobs'] if j['id']==r['job_id'])
        if j['state']!='coding' or j['child_id']!=r['child_id']:raise ValueError('Observed task mismatch')
        if r['result'].get('state')=='human_review_required':j.update(state='ready_test',coding=r['result'])
        elif r['result'].get('state')=='blocked':j.update(state='blocked',error='Coder stopped; claim retained')
        return {'ok':True}
    raise ValueError('Unknown ongoing RPC')


def summary(s):
    o=s.get('ongoing')
    if not o:return 'Ongoing work is not configured.'
    lines=['Ongoing work: '+('enabled' if o['enabled'] else 'paused'),
           'Different subtasks; automatic routine decisions; draft PRs for later review.',
           'Daily cloud-work budget: '+str(o['calls'])+' of '+str(o['policy']['max_calls_per_day'])+' steps reserved']
    for j in o['jobs']:
        lines.append(j['owner'].capitalize()+': '+j['title']+' — '+j['state'].replace('_',' '))
        if j.get('coding',{}).get('route'):
            lines.append('Actual coder model: '+j['coding']['route']['model'])
            if j['coding']['route'].get('operator_correction'):lines.append('Saved proposal includes an operator correction before acceptance.')
        if j.get('review',{}).get('route'):
            lines.append('Reviewer model: '+j['review']['route']['model'])
        if j.get('publication'):lines.append(j['publication'].get('pull_request',{}).get('url',''))
    if all(j['state'] in TERMINAL for j in o['jobs']):lines.append('Admitted backlog finished or held. No model calls while waiting for more work.')
    return '\n'.join(lines)


def decisions(s):
    jobs=s.get('ongoing',{}).get('jobs',[])
    held=[j for j in jobs if j['state']=='blocked']
    drafts=[j for j in jobs if j['state']=='draft_ready']
    lines=['Ongoing work decisions']
    if held:
        lines.append('No approval is being requested. These tasks need technical recovery, not your answer:')
        lines.extend('- '+j['title'] for j in held)
        lines.append('Their saved evidence is retained. Routine recovery is delegated; destructive action would require a separate explicit decision.')
    else:lines.append('No answer is required from you for ongoing work right now. Routine choices are delegated.')
    if drafts:
        lines.append('Draft PRs are available for your later review; they are not merged automatically.')
        lines.extend(j['publication']['pull_request']['url'] for j in drafts)
    return '\n'.join(lines)


def public(s):
    """Allowlisted Telegram/Qwen evidence, excluding lease tokens and local paths."""
    o=s.get('ongoing',{})
    if not o:return {}
    keys=('id','title','owner','state','prompt','write_paths','source_sha','attempt',
          'issue','coding','tests','review','publication','retry_at','error')
    return {'enabled':o['enabled'],'last_seen':o.get('last_seen'),'policy':copy.deepcopy(o['policy']),
            'cloud_stage_reservations':o['calls'],'day':o['day'],
            'jobs':[{k:copy.deepcopy(j[k]) for k in keys if k in j} for j in o['jobs']]}


def usage(s):
    o=s['ongoing'];lines=['Ongoing model usage: latest saved result for each task, not an account-wide total.',
        'Cloud stage reservations: '+str(o['calls'])+'/'+str(o['policy']['max_calls_per_day'])+' for '+o['day']]
    for j in o['jobs']:
        for kind in ('coding','review'):
            item=j.get(kind,{})
            if not item.get('route'):continue
            u=item.get('usage',{});r=item['route']
            lines.append(j['title']+' / '+kind+': '+r['model']+
                '; input '+str(u.get('input_tokens','unknown'))+', output '+str(u.get('output_tokens','unknown'))+
                ('; local, no cloud generation quota' if r.get('provider')=='ollama_local' else ''))
    lines.append('Earlier failed attempts may have unreported usage. These are observed tokens, not a price estimate. Idle checks use no model calls.')
    return '\n'.join(lines)

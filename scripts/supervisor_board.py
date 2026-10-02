"""Pure supervisor board over the existing ongoing-work ledger.

Contract: call ensure/record inside the same durable CAS transaction as worker
changes. Commands require request_id and snapshot revision; authentication and
CSRF checks belong to the caller. Retrying the exact request returns its saved
result. No transport, execution, merge, or catalog admission happens here.

Worker integration must honor supervision_paused/supervision_priority. Correction
requests preserve immutable job scope and evidence; even rerun_waiting is only a
queue entry. A worker must reconcile claims, validate catalog/source scope and
consume the correction under its lock before advancing job.attempt. Intake is
planned work, never executable. record() emits one digest_due audit event per
elapsed hour while enabled work is outstanding; delivery is the caller's job.

Audit/requests/evidence are never silently evicted. The entire ledger is capped
at 1,900,000 encoded bytes; overflow rejects the whole mutation for explicit
operator archival. Display limits are reported. Snapshots use admitted metadata
and heuristic credential redaction, not comprehensive secret detection.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import re

from pilot_views import _redact

MAX_BYTES = 1900000
TERMINAL = {'draft_ready', 'reviewed', 'completed', 'cancelled'}
SAFE_CORRECTION = {'queued', 'draft_ready', 'reviewed', 'completed'}
EVIDENCE = ('coding', 'tests', 'review', 'publication')


class ConflictError(ValueError):
    pass


class StorageLimitError(ValueError):
    pass


def _instant(value=None):
    value = value or datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('An aware timestamp is required')
    return value.astimezone(timezone.utc)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _safe(value, limit=800):
    if value is None:
        return ''
    if not isinstance(value, (str, int, float, bool)):
        return ''
    text = _redact(str(value))
    return text if len(text) <= limit else text[:limit]+' [display shortened]'


def _project(job):
    name = str(job.get('project', job.get('repo', job.get('repository', 'aadi')))).lower().rstrip('/').removesuffix('.git')
    if name in ('aadi', 'pragalbhdwivedi/aadi', 'https://github.com/pragalbhdwivedi/aadi'):
        return 'AADI'
    if name in ('gatewayai', 'miniature-octo-doodle', 'pragalbhdwivedi/miniature-octo-doodle', 'https://github.com/pragalbhdwivedi/miniature-octo-doodle'):
        return 'GatewayAI'
    return 'unverified'


def _confidence(evidence):
    route = evidence.get('route', {}) if isinstance(evidence.get('route'), dict) else {}
    score = evidence.get('confidence', route.get('confidence'))
    if isinstance(score, dict):
        score = score.get('value')
    reason=_safe(evidence.get('confidence_reason',route.get('confidence_reason','')),400)
    if type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 10:
        return score, 'Recorded model-reported confidence (0 to 10); uncalibrated. '+reason
    return None, 'No valid confidence observation recorded. '+reason


def _model(evidence):
    route = evidence.get('route', {}) if isinstance(evidence.get('route'), dict) else {}
    return _safe(route.get('model', evidence.get('model', 'unknown')), 160)


def _projection(job, meta):
    coding = job.get('coding') if isinstance(job.get('coding'), dict) else {}
    review = job.get('review') if isinstance(job.get('review'), dict) else {}
    tests = job.get('tests') if isinstance(job.get('tests'), dict) else {}
    publication = job.get('publication') if isinstance(job.get('publication'), dict) else {}
    pr = publication.get('pull_request') if isinstance(publication.get('pull_request'), dict) else {}
    url = pr.get('url', '')
    if not isinstance(url, str) or not re.fullmatch(r'https://github\.com/pragalbhdwivedi/(aadi|miniature-octo-doodle)/pull/[1-9][0-9]*', url):
        url = ''
    confidence, reason = _confidence(coding)
    reviewer_confidence, reviewer_reason = _confidence(review)
    return {'id':meta['id'], 'key':_safe(job['id'],128), 'project':_project(job),
            'title':_safe(job.get('title'),300), 'state':_safe(job.get('state','unknown'),80),
            'owner':_safe(job.get('owner','unassigned'),80), 'coder_model':_model(coding),
            'reviewer_model':_model(review), 'coder_confidence':confidence,
            'reviewer_confidence':reviewer_confidence,
            'confidence_reason':reason+' Reviewer: '+reviewer_reason,
            'attempt':job.get('attempt',0), 'priority':meta['priority'], 'paused':meta['paused'],
            'pr_url':url, 'pr_number':int(url.rsplit('/',1)[1]) if url else None,
            'review_state':meta.get('review_state','not_reviewed'),
            'review_note':_safe(meta.get('review_note'),2000), 'reviewed_at':meta.get('reviewed_at'),
            'created_at':meta['created_at'], 'updated_at':meta['updated_at'],
            'prompt':_safe(job.get('prompt'),1200), 'error':_safe(job.get('error'),600),
            'tests_passed':tests.get('passed') if type(tests.get('passed')) is bool else None,
            'test_count':tests.get('test_count') if type(tests.get('test_count')) is int and tests['test_count']>=0 else None,
            'progress':{'candidate_recorded':bool(coding), 'tests_passed':tests.get('passed') is True,
                        'review_passed':review.get('verdict')=='pass', 'draft_recorded':bool(url)},
            'source_sha':_safe(job.get('source_sha'),64)}


def _event(board, at, actor, task, action, detail):
    board['revision'] += 1
    board['events'].append({'sequence':len(board['events'])+1, 'timestamp':at,
                            'actor':_safe(actor,80), 'task_id':task,
                            'action':action, 'detail':_safe(detail,2000)})


def _allocate(board):
    result='SUP-'+str(board['next_id']).zfill(6)
    board['next_id'] += 1
    return result


def _ensure(s, at):
    ongoing=s.get('ongoing',{})
    jobs=ongoing.get('jobs',[])
    if not isinstance(jobs,list) or any(not isinstance(j,dict) or not isinstance(j.get('id'),str) for j in jobs):
        raise ValueError('Invalid ongoing job catalog')
    if len({j['id'] for j in jobs})!=len(jobs):
        raise ValueError('Duplicate legacy job IDs')
    board=s.setdefault('supervision',{'version':1,'revision':0,'next_id':1,'tasks':{},
        'by_key':{},'events':[],'requests':{},'corrections':[],'intake':[],
        'evidence':{},'last_digest_at':at})
    if board.get('version')!=1: raise ValueError('Unknown supervisor board version')
    for job in jobs:
        task_id=board['by_key'].get(job['id'])
        if task_id is None:
            intake=next((i for i in board['intake'] if i['id']==job.get('intake_id')),None)
            if job.get('intake_id') and (not intake or intake['project']!=_project(job) or intake['state'] not in ('planned','admitted')):
                raise ValueError('Intake lineage does not match the admitted project')
            if intake and (intake.get('job_id',job['id'])!=job['id'] or intake['id'] in board['tasks']):
                raise ValueError('Intake is already bound to another job')
            task_id=intake['id'] if intake else _allocate(board)
            if intake:intake.update(state='admitted',job_id=job['id'],updated_at=at)
            board['by_key'][job['id']]=task_id
            meta={'id':task_id,'key':job['id'],'revision':0,'created_at':at,'updated_at':at,
                  'priority':intake['priority'] if intake else 3,'paused':intake['paused'] if intake else False,'history':[],'review_state':'not_reviewed'}
            board['tasks'][task_id]=meta
            _event(board,at,'system',task_id,'registered','Registered existing admitted catalog task.')
        meta=board['tasks'][task_id]
        job['supervisor_id']=task_id
        job['supervision_paused']=meta['paused']
        job['supervision_priority']=meta['priority']
        if 'observed' not in meta:
            _observe(board,job,meta,at,'system',initial=True)
    return board


def _observe(board,job,meta,at,actor,initial=False):
    evidence={k:copy.deepcopy(job[k]) for k in EVIDENCE if k in job}
    evidence_digest=_hash(evidence)
    fingerprint=_hash({'state':job.get('state'),'attempt':job.get('attempt',0),
                        'evidence':evidence_digest,'error':job.get('error'),'source_sha':job.get('source_sha')})
    if fingerprint==meta.get('fingerprint'): return False
    previous=meta.get('observed',{}).get('state','unobserved')
    # Content-addressed evidence avoids repeated copies, preserving previous attempts.
    if evidence:
        board['evidence'].setdefault(evidence_digest,evidence)
    meta['history'].append({'timestamp':at,'state':job.get('state','unknown'),
                            'attempt':job.get('attempt',0),'evidence_digest':evidence_digest})
    meta.update(fingerprint=fingerprint,updated_at=at,revision=meta['revision']+1)
    meta['observed']=_projection(job,meta)
    if not initial:
        _event(board,at,actor,meta['id'],'transition',
               previous+' -> '+str(job.get('state','unknown'))+'; evidence '+evidence_digest)
    return True


def _transaction(s, operation):
    candidate=copy.deepcopy(s)
    result=operation(candidate)
    if len(json.dumps(candidate,allow_nan=False).encode())>MAX_BYTES:
        raise StorageLimitError('Ledger limit reached; archive explicitly before accepting more work. No audit was discarded.')
    # Preserve references held by the surrounding reducer after validation.
    # Board operations never reorder existing lists: retain element identity
    # at each position, append new items, and remove explicitly deleted values.
    def commit(target, source):
        if isinstance(target,dict) and isinstance(source,dict):
            for key in list(target):
                if key not in source: del target[key]
            for key,value in source.items():
                if key in target and isinstance(target[key],(dict,list)) and type(target[key]) is type(value):
                    commit(target[key],value)
                else: target[key]=value
        else:
            for index,value in enumerate(source):
                if index<len(target):
                    if isinstance(target[index],(dict,list)) and type(target[index]) is type(value):
                        commit(target[index],value)
                    else: target[index]=value
                else: target.append(value)
            del target[len(source):]
    commit(s,candidate)
    return result


def ensure(s, now=None):
    at=_instant(now).isoformat()
    return _transaction(s,lambda candidate:copy.deepcopy(_ensure(candidate,at)))


def record(s, actor='worker', now=None):
    instant=_instant(now);at=instant.isoformat()
    def change(candidate):
        board=_ensure(candidate,at);o=candidate.get('ongoing',{})
        changed=[]
        for job in o.get('jobs',[]):
            if _observe(board,job,board['tasks'][job['supervisor_id']],at,actor):
                changed.append(job['supervisor_id'])
        active=bool(o.get('enabled') and any(j.get('state') not in TERMINAL|{'blocked','needs_owner'}
                                           for j in o.get('jobs',[]) if not j.get('supervision_paused')))
        due=active and (instant-_instant(board['last_digest_at'])).total_seconds()>=3600
        if due:
            board['last_digest_at']=at
            _event(board,at,'supervisor',None,'digest_due','Hourly progress digest due; no model inference or delivery performed.')
        return {'revision':board['revision'],'changed':changed,'digest_due':bool(due)}
    return _transaction(s,change)


def _leased(ongoing, job):
    lease=ongoing.get('lease')
    if not lease: return False
    return (not lease.get('job_id') and not lease.get('job_ids') or
            lease.get('job_id')==job['id'] or job['id'] in lease.get('job_ids',[]))


def action(s, request, now=None):
    """Commands: pause/resume, priority (1..5; default 3; 5 highest), request_changes, mark_reviewed,
    add_task {project,title,text}, ask {task_id,text}. task_id omitted/'all'
    means all only for pause/resume. Corrections never increment job.attempt.
    """
    if not isinstance(request,dict): raise ValueError('Command must be an object')
    rid=request.get('request_id')
    if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',rid): raise ValueError('Invalid request ID')
    if type(request.get('revision')) is not int: raise ConflictError('A snapshot revision is required')
    at=_instant(now).isoformat();fingerprint=_hash(request)
    def change(candidate):
        board=_ensure(candidate,at)
        prior=board['requests'].get(rid)
        if prior:
            if prior['fingerprint']!=fingerprint: raise ConflictError('Request ID reused with a different command')
            return copy.deepcopy(prior['result'])
        if request['revision']!=board['revision']: raise ConflictError('Supervisor revision changed; refresh before applying this command')
        command=request.get('action');task_id=request.get('task_id') or 'all'
        actor=_safe(request.get('actor','owner'),80)
        jobs=candidate.get('ongoing',{}).get('jobs',[])
        job=next((j for j in jobs if j['supervisor_id']==task_id),None)
        meta=board['tasks'].get(task_id)
        intake=next((i for i in board['intake'] if i['id']==task_id),None)
        result={'ok':True,'task_id':None if task_id=='all' else task_id,'action':command}
        detail=''
        if command in ('generate_future','override_start'):
            if task_id!='all':raise ValueError('This control applies to the supervisor')
            import supervisor_future as future
            if command=='generate_future':
                result['generation']=future.request_generation(candidate,rid,at)
                detail='Request received. A higher-capability planner will generate repository-grounded future tasks; execution still requires admitted scope.'
            else:
                candidate.setdefault('ongoing',{})['enabled']=True
                future.request_override(candidate,at)
                detail='Start override received. Scheduling resumes on the next worker check; existing leases, scope, quota and recovery holds remain enforced.'
            result['message']=detail
        elif command in ('pause','resume'):
            paused=command=='pause'
            if task_id=='all': candidate.setdefault('ongoing',{})['enabled']=not paused
            elif meta and job:
                meta['paused']=paused;job['supervision_paused']=paused
            elif intake: intake['paused']=paused
            else: raise ValueError('Unknown task')
            detail='Paused future stages; existing claims retained.' if paused else 'Resume requested within existing scope; blocked claims are not retried.'
        elif command=='priority':
            priority=request.get('priority')
            if type(priority) is not int or not 1<=priority<=5: raise ValueError('Priority must be an integer from 1 to 5')
            if meta and job: meta['priority']=priority;job['supervision_priority']=priority
            elif intake: intake['priority']=priority
            else: raise ValueError('Unknown task')
            detail='Priority set to '+str(priority)+'; scope and ownership unchanged.'
        elif command in ('request_changes','mark_reviewed','add_task','ask'):
            text=request.get('text')
            if not isinstance(text,str) or not 1<=len(text.strip())<=2000: raise ValueError('A bounded nonempty instruction is required')
            text=_redact(text.strip())
            if command=='add_task':
                project=request.get('project');title=request.get('title')
                if project not in ('AADI','GatewayAI') or not isinstance(title,str) or not 1<=len(title.strip())<=240: raise ValueError('An admitted project and short title are required')
                task_id=_allocate(board)
                board['intake'].append({'id':task_id,'project':project,'title':_redact(title.strip()),
                    'prompt':text,'state':'planned','created_at':at,'updated_at':at,'priority':3,'paused':False,'owner':'unassigned'})
                result.update(task_id=task_id,state='planned')
                detail='Task received; the supervisor will select a configured development scope automatically.'
            elif command=='ask':
                if not(meta or intake): raise ValueError('Unknown task')
                question={'id':'board-'+_hash(rid)[:24],'kind':'ask','task_id':task_id,'state':'pending','question':text,'timestamp':at}
                candidate.setdefault('questions',[]).append(question)
                result['question_id']=question['id'];detail='Task question queued; no work authorization granted.'
            else:
                if not(meta and job): raise ValueError('An admitted task is required')
                _observe(board,job,meta,at,actor)
                if command=='request_changes':
                    safe=job.get('state') in SAFE_CORRECTION and not _leased(candidate['ongoing'],job)
                    correction={'id':'COR-'+str(len(board['corrections'])+1).zfill(6),'task_id':task_id,
                        'key':job['id'],'text':text,'created_at':at,'actor':actor,
                        'state':'rerun_waiting' if safe else 'reconciliation_required',
                        'attempt':job.get('attempt',0),'requested_attempt':job.get('attempt',0)+1 if safe else None,
                        'evidence_digest':meta['history'][-1]['evidence_digest'],
                        'scope_digest':_hash({k:job.get(k) for k in ('id','owner','repo','repository','project','operation','development_profile','paths','write_paths','test_files','source_sha','prompt')})}
                    board['corrections'].append(correction)
                    meta['review_state']='changes_requested'
                    result.update(correction_id=correction['id'],state=correction['state'])
                    if safe: meta['revision']+=1
                    detail='Correction '+correction['id']+' saved as '+correction['state']+'. Prior evidence retained; worker admission required.'
                else:
                    meta['review_state']='reviewed';meta['review_note']=text;meta['reviewed_at']=at
                    result['state']='reviewed';detail=text
        else: raise ValueError('Unknown supervisor action')
        if meta and command not in ('add_task','ask'):
            meta['updated_at']=at
            meta['observed']=_projection(job,meta)
        if intake: intake['updated_at']=at
        _event(board,at,actor,None if task_id=='all' else task_id,command,detail)
        result['revision']=board['revision']
        board['requests'][rid]={'fingerprint':fingerprint,'result':copy.deepcopy(result),'timestamp':at}
        return result
    return _transaction(s,change)


def _execution_projection(job, ongoing, paused, instant):
    """Expose reserved work without rewriting its durable ready state.

    A lease proves ownership of a stage, not the selected provider/model or a
    live process heartbeat. Never reuse a previous attempt's model as its live
    model, or expose the private lease token in a public snapshot.
    """
    lease=ongoing.get('lease') or {}
    active=(lease.get('job_id')==job['id'] or job['id'] in lease.get('job_ids',[]))
    stage=lease.get('stage') if active else None
    if stage=='parallel_code':
        stage={'local':'local','gemini':'antigravity','codex':'codex'}.get(job.get('owner'))
    stages={
        'admit':('working','Preparing the task','Laptop · task coordinator',False),
        'local':('coding','Local coding step in progress','Laptop · local model',True),
        'codex':('coding','Cloud coding step in progress','Laptop · cloud CLI',True),
        'antigravity':('coding','Cloud coding step in progress','Laptop · cloud CLI',True),
        'test':('testing','Isolated tests in progress','Laptop · isolated test container',False),
        'review':('reviewing','Independent review in progress','Laptop · cloud CLI',True),
        'publish':('publishing','Preparing the reviewed draft PR','Laptop · GitHub publisher',False),
    }
    if stage in stages:
        display,label,host,uses_model=stages[stage]
        return {'display_state':display,'execution':{
            'stage':stage,'label':label,'host':host,'started_at':_safe(lease.get('started_at'),80),
            'model':None,'model_status':'not_yet_reported' if uses_model else 'not_applicable',
            'basis':'reserved_stage','pause_after_step':bool(paused or not ongoing.get('enabled'))}}
    maximum=ongoing.get('policy',{}).get('max_calls_per_day')
    calls=ongoing.get('calls')
    cloud_ready=job.get('state') in ('codex_ready','antigravity_ready','ready_review')
    if (not lease and not paused and ongoing.get('enabled') and cloud_ready
            and ongoing.get('day')==instant.date().isoformat()
            and type(maximum) is int and type(calls) is int and calls>=maximum):
        return {'display_state':'waiting_budget','wait_reason':'Daily cloud-work budget reached; waiting for the next budget day.'}
    return {'display_state':_safe(job.get('state','unknown'),80)}


def _public(s, now=None, limit=200):
    # snapshot is read-only: callers explicitly persist ensure/record first.
    board=s.get('supervision',{});o=s.get('ongoing',{});instant=_instant(now)
    live={j['id']:j for j in o.get('jobs',[])}
    tasks=[]
    for meta in board.get('tasks',{}).values():
        job=live.get(meta['key'])
        task=_projection(job,meta) if job else copy.deepcopy(meta.get('observed',{}))
        if not job: task.update(state='retained_missing',error='Catalog entry missing; historical evidence retained.')
        else:task.update(_execution_projection(job,o,meta['paused'],instant))
        tasks.append(task)
    for item in board.get('intake',[]):
        if item.get('state')=='admitted':continue
        tasks.append({**copy.deepcopy(item),'key':None,'attempt':0,'coder_model':'unknown','reviewer_model':'unknown',
            'coder_confidence':None,'reviewer_confidence':None,'confidence_reason':'No model observation recorded.',
            'review_state':'not_reviewed','pr_url':'','pr_number':None,'error':''})
    tasks.sort(key=lambda t:t['id'])
    events=board.get('events',[])
    policy={k:_safe(v,200) if not isinstance(v,(bool,int)) else v for k,v in o.get('policy',{}).items()
            if k in ('max_active','max_calls_per_day','repairs','publication','routine_decisions','destructive')}
    from supervisor_archive import history_index
    from supervisor_future import public as future_public
    future=future_public(s,instant)
    runnable=[t for t in tasks if t['state'] not in TERMINAL|{'blocked','needs_owner','needs_scope'} and not t.get('paused')]
    if not o.get('enabled'):
        work_status={'state':'paused','label':'Work is paused','reason':'Scheduling was paused. Override start resumes eligible work.'}
    elif o.get('lease'):
        work_status={'state':'working','label':'Work is running','reason':'A worker stage owns the current lease.'}
    elif runnable:
        work_status={'state':'waiting','label':'Waiting for the next worker step','reason':'Queued work is subject to scope, capacity, dependencies and model allowance.'}
    else:
        work_status={'state':'idle','label':'Enabled · waiting for eligible work','reason':'No coding task is active. The supervisor checks the future backlog every five minutes.'}
    return {'revision':board.get('revision',0),'enabled':bool(o.get('enabled')),
            'future':future,'work_status':work_status,
            'archived':history_index(s,limit=100),
            'tasks':tasks[:limit] if limit else tasks,'tasks_omitted':max(0,len(tasks)-limit) if limit else 0,
            'events':copy.deepcopy(events[-100:] if limit else events),
            'events_omitted':max(0,len(events)-100) if limit else 0,
            'corrections':[{k:_safe(v,2000) if isinstance(v,str) else copy.deepcopy(v) for k,v in c.items()
                            if k in ('id','task_id','key','text','state','created_at','actor','attempt','requested_attempt')}
                           for c in board.get('corrections',[])][-100:] if limit else copy.deepcopy(board.get('corrections',[])),
            'corrections_omitted':max(0,len(board.get('corrections',[]))-100) if limit else 0,
            'policy':policy,'server_time':instant.isoformat()}


def snapshot(s, now=None):
    return _public(s,now)


def _md(value):
    return re.sub(r'([\\`*_{}\[\]<>()#+.!|>-])',r'\\\1',_safe('unknown' if value is None else value,10000)).replace('\n','  \n')


def documents(s):
    """Return five Markdown documents without writing them or dropping audit."""
    data=_public(s,limit=None)
    def task_text(task):
        fields=('project','key','state','owner','created_at','updated_at','attempt','priority','paused',
                'coder_model','coder_confidence','reviewer_model','reviewer_confidence','confidence_reason',
                'review_state','review_note','reviewed_at','pr_url','prompt','error')
        return '## '+_md(task['id'])+' — '+_md(task['title'])+'\n\n'+'\n'.join(
            '- '+key.replace('_',' ').capitalize()+': '+_md(task.get(key,'unknown')) for key in fields)+'\n'
    groups={'future_supervisor_tasks.md':('Future supervisor tasks',[t for t in data['tasks'] if t['state'] in ('queued','planned')]),
            'active_supervisor_tasks.md':('Active supervisor tasks',[t for t in data['tasks'] if t['state'] not in TERMINAL|{'queued','planned'}]),
            'completed_supervisor_tasks.md':('Completed supervisor tasks',[t for t in data['tasks'] if t['state'] in TERMINAL])}
    output={name:'# '+title+'\n\nDraft-ready means ready for review, not merged or deployed.\n\n'+
            ('\n'.join(task_text(t) for t in tasks) if tasks else 'No tasks in this view.\n') for name,(title,tasks) in groups.items()}
    future=data.get('future',{})
    output['future_supervisor_tasks.md']+='\n## Repository development backlog\n\nNext batch: up to 10 tasks. The scheduler checks every five minutes; times are earliest eligibility, not promised completion.\n\n'+''.join(
        '### '+_md(t['id'])+' — '+_md(t['title'])+'\n\n'+
        '\n'.join('- '+k.replace('_',' ').capitalize()+': '+_md(t.get(k,'')) for k in ('project','state','priority','scope_id','created_at','updated_at','not_before','reason','prompt'))+'\n\n'
        for t in future.get('tasks',[]))
    output['rerun_supervision_tasks.md']='# Rerun supervision tasks\n\nCorrection requests preserve task lineage and require worker reconciliation/admission. No automatic retry is authorized here.\n\n'+('\n\n'.join(
        '## '+_md(c['id'])+' / '+_md(c['task_id'])+'\n\n'+'\n'.join('- '+k.replace('_',' ').capitalize()+': '+_md(v) for k,v in c.items() if k not in ('id','task_id'))
        for c in data['corrections']) or 'No correction requests.\n')
    output['supervisor_audit.md']='# Supervisor audit\n\nRevision: '+str(data['revision'])+'\n\nConfidence is unknown unless observed; model-reported confidence is uncalibrated. No audit events are omitted from this document.\n\n'+('\n'.join(
        '- '+str(e['sequence'])+' | '+_md(e['timestamp'])+' | '+_md(e['actor'])+' | '+_md(e['task_id'] or 'all')+' | '+_md(e['action'])+' | '+_md(e['detail']) for e in data['events']) or 'No audit events.\n')
    archived=data.get('archived',{})
    if archived.get('total'):
        output['completed_supervisor_tasks.md']+='\n## Verified archived tasks\n\n'+str(archived['total'])+' archived; use the paginated archive history for all summaries and operator archives for full evidence.\n\n'+''.join('- '+_md(t['id'])+' | '+_md(t.get('title'))+' | '+_md(t['state'])+' | '+_md(t.get('pr_url'))+'\n' for t in archived['tasks'])
        if archived.get('omitted'):output['completed_supervisor_tasks.md']+='\n'+str(archived['omitted'])+' additional archived summaries are available through pagination.\n'
    return output

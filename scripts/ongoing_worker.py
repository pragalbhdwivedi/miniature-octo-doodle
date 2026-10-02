"""Assigned-subtask worker: local planning, isolated checks, reviewed draft PRs."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
from concurrent.futures import ThreadPoolExecutor

import coder_coordination as coordination
import ongoing_github as github
import ongoing_models as models
import pilot_worker as pilot

REVIEW={'type':'object','properties':{'verdict':{'type':'string','enum':['pass','repair']},
    'confidence':{'type':'integer','minimum':0,'maximum':10},
    'confidence_reason':{'type':'string'},
    'findings':{'type':'array','items':{'type':'string'},'maxItems':5}},
    'required':['verdict','findings','confidence','confidence_reason'],'additionalProperties':False}


def routing_attempt(job):
    """Escalate within one repair cycle, not across the task's audit history."""
    attempt, start = job['attempt'], job.get('repair_start', 0)
    if (type(attempt) is not int or type(start) is not int or start < 0
            or attempt - start not in (0, 1)):
        raise ValueError('Invalid routing repair cycle')
    return attempt - start


def validate_additions(before,after):
    """Candidate may only add unittest methods, preserving every baseline node."""
    old,new=ast.parse(before),ast.parse(after)
    originals={n.name:n for n in old.body if isinstance(n,ast.ClassDef)}
    additions=[]
    for node in new.body:
        if not isinstance(node,ast.ClassDef) or node.name not in originals:continue
        names={n.name for n in originals[node.name].body if isinstance(n,ast.FunctionDef)}
        extra=[n for n in node.body if isinstance(n,ast.FunctionDef) and n.name not in names]
        if any(not n.name.startswith('test_') or n.decorator_list for n in extra):raise ValueError('Only undecorated tests may be added')
        for n in extra:
            if (n.args.defaults or n.args.kw_defaults or n.args.vararg or n.args.kwarg or
                    n.args.kwonlyargs or n.args.posonlyargs or len(n.args.args)!=1 or
                    n.args.args[0].arg!='self' or n.args.args[0].annotation or n.returns):
                raise ValueError('Alternate test signatures are denied')
            allowed=(ast.FunctionDef,ast.arguments,ast.arg,ast.Expr,ast.Assign,ast.Call,ast.Name,
                ast.Load,ast.Store,ast.Attribute,ast.Constant,ast.Subscript,ast.List,ast.Tuple,ast.Dict,
                ast.keyword,ast.With,ast.withitem,ast.For,ast.Compare,ast.Eq,ast.NotEq,ast.In,
                ast.NotIn,ast.UnaryOp,ast.USub,ast.BinOp,ast.Add,ast.Sub,ast.Set)
            named={'deepcopy','validate_snapshot','reconcile_extract','summarize_source','dict','list',
                   'tuple','set','datetime','timedelta','Actor','frozenset','normalize_choice','select_route'}
            methods={'append','reverse','update','to_dict','candidate_json','summarize','reconcile','validate','codes',
                'assertEqual','assertNotEqual','assertTrue','assertFalse','assertIsNone','assertIsNotNone',
                'assertIn','assertNotIn','assertRaises','assertLess','assertLessEqual','assertGreater','assertGreaterEqual','subTest','check'}
            protected=named|{'self','json','unittest','ContractError','ScopeDenied','MODULE','ValueError'}
            for child in ast.walk(n):
                if not isinstance(child,allowed):raise ValueError('Unsupported executable test construct')
                if isinstance(child,ast.Name) and (child.id.startswith('_') or isinstance(child.ctx,ast.Store) and child.id in protected):raise ValueError('Protected binding')
                if isinstance(child,ast.Attribute) and (child.attr.startswith('_') or isinstance(child.ctx,ast.Store)):raise ValueError('Unsafe attribute access')
                if isinstance(child,ast.Call):
                    if isinstance(child.func,ast.Name):
                        if child.func.id not in named:raise ValueError('Unsupported test call')
                    elif isinstance(child.func,ast.Attribute):
                        if child.func.attr not in methods:raise ValueError('Unsupported test method')
                    else:raise ValueError('Indirect test call')
            node.body.remove(n);additions.append(n.name)
    if not 1<=len(additions)<=2 or len(set(additions))!=len(additions) or ast.dump(old)!=ast.dump(new):
        raise ValueError('Baseline preservation or test-addition limit failed')
    return additions


class Worker:
    def __init__(self,config,remote=None):
        self.base=pilot.Worker(config,remote=remote);self.config=config
        self.root=self.base.root/'ongoing';self.root.mkdir(exist_ok=True)
        self.remote=self.base.remote;self.coordinator=self.base.coordinator
        self.catalog={x['id']:x for x in pilot.read_json(config['ongoing_catalog'])}
        self.publisher=github.Github(config['ongoing_github'])
        self.repository=config['ongoing_github'].get('repository','pragalbhdwivedi/aadi')
        self.project_workers={}

    def for_job(self,j):
        repository=j.get('repository','pragalbhdwivedi/aadi')
        if repository==self.repository:return self
        if repository not in self.config.get('projects',{}):raise ValueError('Unconfigured project')
        if repository not in self.project_workers:
            cfg={**self.config,**self.config['projects'][repository]};cfg.pop('projects',None)
            self.project_workers[repository]=Worker(cfg,remote=self.remote)
        self.project_workers[repository].catalog=self.catalog
        return self.project_workers[repository]

    def spec(self,j):
        expected=self.catalog.get(j['id'])
        if not expected or any(j.get(k)!=v for k,v in expected.items()):raise ValueError('Task differs from operator catalog')
        if j['operation']!='test_addition' or j['risk']!='reversible':raise ValueError('Operation requires owner review')
        if j.get('repository','pragalbhdwivedi/aadi')!=self.repository:raise ValueError('Wrong project worker')
        if self.coordinator.source(j['paths'])['sha']!=j['source_sha']:raise ValueError('Source advanced; preserve work for review')
        return expected

    def child(self,j):return 'ongoing-'+j['id']+'-a'+str(j['attempt'])

    def candidate(self,j):
        self.spec(j)
        value=pilot.read_json(self.coordinator.root/self.child(j)/(j['owner']+'.json'))
        result=pilot.read_json(self.coordinator.root/self.child(j)/'result.json')
        if (result.get('candidate_sha256')!=coordination.digest(value) or
                result.get('task_id')!=self.child(j) or result.get('owner')!=j['owner'] or
                result.get('source_sha')!=j['source_sha'] or result.get('state')!='human_review_required'):
            raise ValueError('Saved candidate provenance mismatch')
        changes={x['path']:x['content'] for x in value['changes']}
        if set(changes)!=set(j['write_paths']):raise ValueError('Candidate write scope mismatch')
        return value,changes

    def plan(self,work,directory):
        ids=[j['id'] for j in work['jobs']]
        schema={'type':'object','properties':{'order':{'type':'array','items':{'type':'string'}},
            'reason':{'type':'string'}},'required':['order','reason'],'additionalProperties':False}
        prompt='Order these admitted independent subtasks by usefulness. Return each ID exactly once. No new tasks or policy changes. '+json.dumps([
            {'id':j['id'],'title':j['title'],'owner':j['owner']} for j in work['jobs']])
        try:
            value=self.base.chat(coordination.mcp.MODEL,[{'role':'user','content':prompt}],schema,300)
            if set(value['order'])!=set(ids) or len(value['order'])!=len(ids):raise ValueError()
            return {**value,'model':coordination.mcp.MODEL,'fallback':False}
        except Exception:
            return {'order':ids,'reason':'Local planner unavailable; using the operator catalog order.','fallback':True}

    def admit(self,work,directory):
        j=work['job'];self.spec(j)
        if j['attempt']:
            previous='ongoing-'+j['id']+'-a'+str(j['attempt']-1)
            self.coordinator.close(previous,'Bounded automatic repair after failed tests/review; saved evidence retained.')
        issue=self.publisher.ensure_issue(j['id'],j['title'],j['prompt']+'\n\nRelated backlog: #'+str(j['parent_issue'])+'\nAssigned owner: '+j['owner']+'. Draft PR only; no integration or deployment.')
        prompt=(j['prompt']+' Preserve all existing AST nodes. Add one or two focused test methods only. '
            'Read-only context paths are not editable. Return complete replacement of the writable test file only. '
            'No imports/helpers/decorators or external calls. No tools beyond coordination MCP. Do not claim tests ran. Start summary with Confidence: N/10 and a short evidence-based reason.')
        if j.get('repair'):prompt+=' Repair findings: '+j['repair'][:500]
        prompt=prompt[:1000]
        self.coordinator.admit(self.child(j),prompt,j['paths'],owner=j['owner'],write_paths=j['write_paths'],transport=j.get('transport','sidecar'))
        return {'child_id':self.child(j),'issue':issue}

    def codex(self,work,directory):
        j=work['job'];self.spec(j)
        reports=[]
        def generate(executable,prompt,folder):
            try:r=models.run(executable,prompt,folder,complexity=j.get('complexity','routine'),stage='code',attempt=routing_attempt(j))
            except Exception:
                if not models.confirmed_quota_denial(folder):raise
                import ongoing_antigravity
                r=ongoing_antigravity.run(self.config['antigravity_cli'],prompt,folder/'quota-fallback',
                    complexity=j.get('complexity','routine'),attempt=routing_attempt(j),prefer_group='Claude and GPT models')
                r['route']['reason']='Confirmed Codex quota denial before generation'
            reports.append(r)
            return r['candidate']
        self.coordinator.coder=generate
        result=self.coordinator.run_codex(self.child(j))
        if reports:result.update(route=reports[0]['route'],usage=reports[0]['usage'])
        return result

    def antigravity(self,work,directory):
        import ongoing_antigravity
        j=work['job'];self.spec(j)
        reports=[]
        try:route=ongoing_antigravity.prepare(self.config['antigravity_cli'],directory/'preflight',
                    complexity=j.get('complexity','routine'),attempt=routing_attempt(j))
        except ongoing_antigravity.QuotaWait as exc:
            return {'state':'quota_wait','retry_at':exc.reset_at,'inference_started':False}
        def generate(prompt,folder):
            r=ongoing_antigravity.run(self.config['antigravity_cli'],prompt,folder,
                complexity=j.get('complexity','routine'),attempt=routing_attempt(j),prepared=route);reports.append(r)
            return r['candidate']
        result=self.coordinator.run_gemini(self.child(j),generate)
        if reports:result.update(route=reports[0]['route'],usage=reports[0]['usage'])
        return result

    def parallel_code(self,work,directory):
        def run(j):
            folder=directory/j['id'];folder.mkdir()
            try:
                worker=self.for_job(j)
                result={'gemini':worker.antigravity,'codex':worker.codex,'local':worker.local}[j['owner']]({'job':j},folder)
                pilot.write_json(folder/'result.json',result)
                return result
            except Exception as exc:
                pilot.write_json(folder/'failure.json',{'type':type(exc).__name__,'detail':str(exc)[:500]})
                return {'state':'blocked'}
        with ThreadPoolExecutor(max_workers=3) as pool:
            values=list(pool.map(run,work['jobs']))
        return {j['id']:v for j,v in zip(work['jobs'],values)}

    def local(self,work,directory):
        import ongoing_local
        j=work['job'];self.spec(j);reports=[]
        def generate(prompt,folder):
            if len(j['write_paths'])!=1:raise ValueError('Local compact lane requires one test file')
            path=j['write_paths'][0]
            before=coordination.agent.git(self.base.repo,'show',j['source_sha']+':'+path).decode('utf-8')
            compact=('Return JSON with a short summary, a short plain-English proposal, and method_source containing '
                'one new unittest method, starting with def test_...(self): at column zero. '
                'Use existing imports/helpers. No tools or execution. Do not return the whole file. Start summary with Confidence: N/10 and a short reason. '
                'Task: '+j['prompt']+(' Repair findings: '+j['repair'][:500] if j.get('repair') else '')+
                '\nExisting test file:\n'+before)
            result=ongoing_local.run(compact,folder,model=self.config['local_coder_model'])
            result['candidate']=ongoing_local.proposal(before,result['candidate'],path)
            validate_additions(before,result['candidate']['changes'][0]['content'])
            reports.append(result);return result['candidate']
        result=self.coordinator.run_local(self.child(j),generate)
        result.update(route=reports[0]['route'],usage=reports[0]['usage'])
        return result

    def test(self,work,directory):
        j=work['job'];value,changes=self.candidate(j)
        files={p:coordination.agent.git(self.base.repo,'show',j['source_sha']+':'+p).decode('utf-8') for p in j['test_files']}
        try:
            added=[]
            for path,content in changes.items():added.extend(validate_additions(files[path],content))
        except ValueError as e:return {'passed':False,'summary':str(e),'candidate_sha256':coordination.digest(value)}
        files.update(changes);stage=directory/'sandbox';stage.mkdir()
        for path,content in files.items():
            target=stage/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content,encoding='utf-8',newline='\n')
        command=['docker','run','--rm','--pull=never','--network=none','--read-only',
            '--cap-drop=ALL','--security-opt=no-new-privileges','--user=65534:65534',
            '--pids-limit=64','--memory=256m','--cpus=1','--tmpfs=/tmp:rw,noexec,nosuid,size=32m',
            '--mount','type=bind,source='+str(stage)+',target=/work,readonly',
            '--workdir=/work','--env=PYTHONPATH=/work/src','--env=PYTHONDONTWRITEBYTECODE=1',
            self.config['test_image'],'python','-m','unittest','discover','-s','tests','-p','test_*.py','-v']
        code,out,err=self.base.runner(command,timeout=90,limit=262144)
        output=(out+err).decode('utf-8',errors='replace');(directory/'tests.txt').write_text(output,encoding='utf-8')
        match=re.search(r'Ran (\d+) tests? in',output)
        return {'passed':code==0 and bool(match),'test_count':int(match[1]) if match else None,
            'added':added,'candidate_sha256':coordination.digest(value),'summary':output[-1600:]}

    def review(self,work,directory):
        j=work['job'];value,changes=self.candidate(j)
        if not j['tests']['passed'] or j['tests']['candidate_sha256']!=coordination.digest(value):raise ValueError('Tests do not bind candidate')
        # Only changed test methods plus the fixed requirement/evidence; no transcript duplication.
        pieces=[]
        for path,content in changes.items():
            tree=ast.parse(content)
            for cls in tree.body:
                if isinstance(cls,ast.ClassDef):
                    for method in cls.body:
                        if isinstance(method,ast.FunctionDef) and method.name in j['tests']['added']:
                            pieces.append(ast.get_source_segment(content,method))
        prompt='Independently review this synthetic test-only task. Return pass or repair and concise findings. Existing AST preservation and isolated suite were mechanically checked; do not claim you ran them. Check assertions meet the task, meaningful edge coverage and no invented acceptance. Task: '+j['prompt']+'\nAdded tests:\n'+'\n'.join(pieces)+'\nEvidence:'+json.dumps(j['tests'])
        try:answer=models.run(self.coordinator.executable,prompt,directory,schema=REVIEW,
                          complexity=j.get('complexity','routine'),stage='review',attempt=0)
        except Exception:
            if not models.confirmed_quota_denial(directory):raise
            import ongoing_antigravity
            group=j.get('coding',{}).get('route',{}).get('group')
            answer=ongoing_antigravity.run(self.config['antigravity_cli'],prompt,directory/'quota-fallback',
                schema=REVIEW,complexity='routine',prefer_group='Gemini Models' if group=='Claude and GPT models' else 'Claude and GPT models')
            answer['route']['reason']='Confirmed Codex quota denial before review'
        return {**answer['candidate'],'route':answer['route'],'usage':answer['usage'],
                'candidate_sha256':coordination.digest(value)}

    def publish(self,work,directory):
        j=work['job'];value,changes=self.candidate(j)
        sha=coordination.digest(value)
        if (not j['tests']['passed'] or j['review']['verdict']!='pass' or
                any(x['candidate_sha256']!=sha for x in (j['tests'],j['review']))):raise ValueError('Acceptance does not bind candidate')
        task={'id':j['id'],'source_sha':j['source_sha'],'title':j['title'],
              'body':j['prompt']+'\n\nIsolated tests passed ('+str(j['tests']['test_count'])+'). Independent review passed. Awaiting owner integration review.',
              'files':changes}
        evidence={'source_sha':j['source_sha'],'artifact_sha256':github.artifact_digest(task),
                  'tests_passed':True,'review_passed':True}
        if self.repository!='pragalbhdwivedi/aadi':
            task.update(repository=self.repository,base=self.publisher.base)
            evidence.update(repository=self.repository,base=self.publisher.base,artifact_sha256=github.artifact_digest(task))
        receipt=github.publish_candidate(self.config['ongoing_github'],task,evidence,github=self.publisher)
        self.coordinator.close(self.child(j),'Tested and independently reviewed proposal saved as draft PR; no base merge.')
        return receipt

    def tick(self):
        with pilot.local_lock(self.root) as locked:
            if not locked:return {'state':'worker_busy'}
            if self.config.get('supervision_enabled'):
                from supervisor_observer import Observer
                Observer(self).tick()
                self.catalog={x['id']:x for x in pilot.read_json(self.config['ongoing_catalog'])}
            self.remote({'action':'ongoing_sync','catalog':list(self.catalog.values())})
            work=self.remote({'action':'ongoing_work'});stage=work['action']
            if stage=='idle':return {'state':'idle','model_calls':0}
            if stage=='observe':
                for j in work['jobs']:
                    rows={r['id']:r for r in self.for_job(j).coordinator.status()['tasks']}
                    child=rows.get(j['child_id'])
                    if child and child['state'] in ('human_review_required','blocked'):
                        self.remote({'action':'ongoing_observed','job_id':j['id'],'child_id':j['child_id'],
                                     'result':child['result'] or {'state':'blocked'}})
                return {'state':'observed','model_calls':0}
            if stage not in ('plan','admit','codex','antigravity','local','parallel_code','test','review','publish'):raise ValueError('Unknown stage')
            j=work.get('job');directory=self.root/(j['id'] if j else 'planning')/(str(j['attempt']) if j else '0')/stage
            if stage=='parallel_code':directory=self.root/'parallel'/work['token']
            if directory.exists() and (directory/'result.json').exists() and pilot.read_json(directory/'result.json').get('state')=='quota_wait':
                directory=directory.with_name(stage+'-quota-'+work['token'])
            try:
                directory.mkdir(parents=True,exist_ok=False);pilot.write_json(directory/'work.json',work)
                worker=self.for_job(j) if j else self
                result=getattr(worker,stage)(work,directory);pilot.write_json(directory/'result.json',result)
                self.remote({'action':'ongoing_finish','token':work['token'],'result':result})
                if self.config.get('supervision_enabled'):
                    from supervisor_observer import Observer
                    Observer(self)._mirror({})
                return {'state':'finished','stage':stage}
            except Exception as exc:
                if directory.exists():pilot.write_json(directory/'failure.json',{'type':type(exc).__name__,'detail':str(exc)[:500]})
                self.remote({'action':'ongoing_fail','token':work['token'],'result':{'error':'Stage failed; saved evidence requires reconciliation, no automatic replay.'}})
                return {'state':'blocked','stage':stage}

"""Operator-only exact-request dispatch. No daemon, retry, publishing or merge."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/(''+name+'.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

controller = module('controller')
worker = controller.worker
state = module('controller_state')


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def private_json(path):
    # Existing worker config reader enforces root ownership, no symlinks, 0600.
    if path.stat().st_size > 262144:
        raise ValueError('Request size ceiling')
    if path.resolve().is_relative_to(ROOT):
        raise ValueError('Private operator files must be outside checkout')
    return worker.coding.private_config(path)


def current_plan(project, runtime):
    if shutil.disk_usage(runtime).free < 16*1024**3:
        raise ValueError('Storage reserve reached')
    registry=json.loads((ROOT/'config/controller/projects.json').read_text())
    worker_registry=json.loads((ROOT/'config/worker/projects.json').read_text())
    def expired(*_): raise TimeoutError('Refresh deadline')
    previous=signal.signal(signal.SIGALRM,expired)
    signal.alarm(180)
    try:
        with tempfile.TemporaryDirectory(dir=runtime,prefix='refresh-') as folder:
            snapshot,files=controller.refresh(project,registry,Path(folder))
            return controller.choose(project,snapshot,files,worker_registry)
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,previous)


def make_request(plan, image, budget=0):
    if plan.get('status')!='awaiting_operator_review' or plan.get('authority')!='plan-only':
        raise ValueError('No eligible repository task')
    if not re.fullmatch('sha256:[a-f0-9]{64}',image):
        raise ValueError('Immutable worker image required')
    if type(budget) not in (int,float) or not 0<=budget<=1:
        raise ValueError('Budget must be 0..1 USD')
    job=copy.deepcopy(plan['job'])
    job['model_budget_usd']=budget
    registry=json.loads((ROOT/'config/worker/projects.json').read_text())
    worker.validate_job(job,registry)
    if 'coding' in job and budget==0:
        raise ValueError('Coding dispatch requires an explicitly reviewed positive budget')
    return {'version':1,'run_id':uuid.uuid4().hex,'plan':plan,'job':job,
            'image':image,'max_attempts':1}


def validate_request(request, approved, latest):
    if not re.fullmatch('[a-f0-9]{64}',approved) or digest(request)!=approved:
        raise ValueError('Exact reviewed request hash required')
    if set(request)!={'version','run_id','plan','job','image','max_attempts'}:
        raise ValueError('Unexpected dispatch fields')
    if type(request['version']) is not int or type(request['max_attempts']) is not int or request['version']!=1 or request['max_attempts']!=1:
        raise ValueError('Only one attempt supported')
    if not re.fullmatch('[a-f0-9]{32}',request['run_id']):
        raise ValueError('Invalid reserved run ID')
    if encode(request['plan'])!=encode(latest):
        raise ValueError('Repository task, ownership or source changed; prepare again')
    rebuilt=make_request(latest,request['image'],request['job']['model_budget_usd'])
    if encode(rebuilt['job'])!=encode(request['job']):
        raise ValueError('Job differs from current committed task')


def result_evidence(request, runtime):
    """Bind durable outcome to the broker's private record and immutable artifacts."""
    folder=runtime/request['run_id']
    result=private_json(folder/'result.json')
    if (result['run_id']!=request['run_id'] or result['project']!=request['job']['project']
            or result['ref']!=request['job']['ref'] or result['image_id']!=request['image']):
        raise ValueError('Worker identity mismatch')
    evidence={'result_sha256':digest(result),'worker_status':result['status'],
              'run_id':request['run_id']}
    if result['status']=='review_required' and result.get('container_removed') is True:
        if result['source_sha']!=request['plan']['source_sha']:
            raise ValueError('Worker source mismatch')
        raw=(folder/'input/job.json').read_bytes()
        expected={**request['job'],'branch':'worker/'+request['run_id']}
        if json.loads(raw)!=expected or hashlib.sha256(raw).hexdigest()!=result['job_sha256']:
            raise ValueError('Worker job mismatch')
        import tarfile
        source=(folder/'input/source.tar').read_bytes()
        if hashlib.sha256(source).hexdigest()!=result['source_archive_sha256']:
            raise ValueError('Worker source archive changed')
        with tarfile.open(folder/'input/source.tar') as archive:
            original=worker.sandbox.source_files(archive)
        raw=(folder/'changes.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=result['artifact_sha256']:
            raise ValueError('Worker artifact changed')
        worker.artifacts(json.loads(raw),original,request['job']['write_paths'])
        if ([c['argv'] for c in result['commands']]!=request['job']['commands']
                or any(c['exit_code']!=0 for c in result['commands'])):
            raise ValueError('Incomplete command evidence')
        evidence['artifact_sha256']=result['artifact_sha256']
        return 'review_required',evidence
    if result['status']=='failed' and (result.get('container_started') is False or result.get('container_removed') is True):
        return 'failed',evidence
    return 'uncertain',evidence


def dispatch(request, approved, latest, store, runtime, coding_config=None, runner=None):
    validate_request(request,approved,latest)
    # Durable claim MUST commit before worker invocation. An ambiguous DB response
    # exits without executing; never retry this run under a new identity.
    row=store.claim(request,approved)
    if row['state']!='dispatching' or row['request_sha256']!=approved:
        raise ValueError('Unexpected durable claim')
    try:
        (runner or worker.run)(request['job'],request['image'],runtime,coding_config,
                              expected_source_sha=request['plan']['source_sha'],run_id=request['run_id'])
        outcome,evidence=result_evidence(request,runtime)
    except Exception as error:
        outcome,evidence='uncertain',{'failure_type':type(error).__name__}
    # Failure here deliberately leaves dispatching. Reconcile evidence; no rerun.
    return store.finish(request['run_id'],outcome,evidence)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','dispatch','status','reconcile'])
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--project',default='gatewayai')
    parser.add_argument('--budget-usd',type=float,default=0)
    parser.add_argument('--request',type=Path)
    parser.add_argument('--approve-sha256')
    parser.add_argument('--run-id')
    args=parser.parse_args()
    if os.name!='posix' or os.geteuid()!=0:
        raise ValueError('Linux operator required; never grant this CLI to an agent')
    os.umask(0o077)
    config=private_json(args.config)
    if set(config)!={'container','database','runtime','worker_runtime','image','coding_config'}:
        raise ValueError('Unexpected operator configuration')
    runtime=Path(config['runtime']);worker.private_root(runtime)
    worker_runtime=Path(config['worker_runtime']);worker.private_root(worker_runtime)
    # Same lock used by dispatch and reconciliation; no premature completion while
    # a synchronous worker is still running. Process death releases this lock only.
    import fcntl
    with (runtime/'dispatch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store=state.Store(config['container'],config['database'])
        if args.action=='prepare':
            request=make_request(current_plan(args.project,runtime),config['image'],args.budget_usd)
            target=runtime/(request['run_id']+'.json')
            with target.open('xb') as f: f.write(encode(request))
            print(json.dumps({'request':str(target),'approve_sha256':digest(request),'budget_usd':args.budget_usd}))
        elif args.action=='dispatch':
            request=private_json(args.request)
            if request['image']!=config['image']:
                raise ValueError('Operator image changed')
            latest=current_plan(request['plan']['project'],runtime)
            row=dispatch(request,args.approve_sha256 or '',latest,store,worker_runtime,config['coding_config'])
            print(json.dumps({'run_id':row['run_id'],'state':row['state'],'result':row['result']}))
            if row['state']!='review_required': raise SystemExit(1)
        else:
            if not re.fullmatch('[a-f0-9]{32}',args.run_id or ''): raise ValueError('Run ID required')
            row=store.get(args.run_id)
            if row is None: raise ValueError('Unknown run')
            if args.action=='reconcile':
                if row['state'] not in ('dispatching','uncertain'): raise ValueError('Already terminal')
                try: outcome,evidence=result_evidence(row['request'],worker_runtime)
                except Exception as error: outcome,evidence='uncertain',{'failure_type':type(error).__name__}
                row=store.finish(args.run_id,outcome,evidence)
            print(json.dumps({'run_id':row['run_id'],'state':row['state'],'result':row['result']}))


if __name__=='__main__':
    try: main()
    except Exception as error:
        raise SystemExit('Dispatch rejected: '+type(error).__name__+'; inspect private state, never automatically retry')

"""Phase 7 read-only repository planner. No execution, credentials or publishing."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile
import urllib.request
import uuid

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('worker', REPO/'scripts/worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
GOVERNANCE = ('PROJECT.md', 'AGENTS.md', 'WORK_INSTRUCTIONS.md', 'PROJECT_STATE.md',
              'README.md', 'docs/ARCHITECTURE.md', 'docs/BUILD_STATUS.md', 'docs/ROADMAP.md')


def public_get(url):
    if not url.startswith('https://api.github.com/repos/'):
        raise ValueError('Only public GitHub repository reads')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), worker.coding.NoRedirect())
    request = urllib.request.Request(url, headers={'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28', 'User-Agent':'GatewayAI-read-only-planner'})
    with opener.open(request, timeout=20) as response:
        raw = response.read(2*1024*1024+1)
        if len(raw) > 2*1024*1024:
            raise ValueError('GitHub response ceiling')
        return json.loads(raw)


def collection(url, get):
    rows = []
    for page in range(1, 11):
        batch = get(url+'&per_page=100&page='+str(page))
        if not isinstance(batch, list):
            raise ValueError('Invalid GitHub collection')
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise ValueError('Incomplete GitHub inventory; manual reconciliation required')


def refresh(project, registry, work, get=public_get):
    config = registry.get(project)
    if not config or config['enabled'] is not True:
        raise ValueError('Project not activated')
    name, branch = config['repository'], config['branch']
    if not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name) or not re.fullmatch('[A-Za-z0-9_-]+', branch):
        raise ValueError('Invalid approved repository/ref')
    api = 'https://api.github.com/repos/'+name
    repository = get(api)
    if repository['private'] or repository['default_branch'] != branch:
        raise ValueError('Repository visibility/default branch changed')
    env = {'PATH':'/usr/local/bin:/usr/bin:/bin', 'HOME':str(work), 'GIT_CONFIG_NOSYSTEM':'1',
           'GIT_CONFIG_GLOBAL':'/dev/null', 'GIT_TERMINAL_PROMPT':'0', 'GIT_ALLOW_PROTOCOL':'https', 'LC_ALL':'C'}
    gitdir = work/'source.git'
    worker.checked(['git','init','--bare',str(gitdir)],env=env)
    git = ['git','-c','core.hooksPath=/dev/null','-c','http.followRedirects=false',
           '-c','fetch.unpackLimit=0','--git-dir='+str(gitdir)]
    worker.checked(git+['fetch','--depth=5','--no-tags','https://github.com/'+name+'.git','refs/heads/'+branch],
                   env=env,file_limit=64*1024*1024)
    sha = worker.checked(git+['rev-parse','FETCH_HEAD'],env=env).decode().strip()
    if not re.fullmatch('[a-f0-9]{40}',sha): raise ValueError('Invalid fetched revision')
    archive = worker.checked(git+['archive','--format=tar',sha],env=env,
                             limit=worker.sandbox.MAX_SOURCE,file_limit=64*1024*1024)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        files = worker.sandbox.source_files(stream)
    commits = worker.checked(git+['log','-5','--format=%H','FETCH_HEAD'],env=env).decode().splitlines()
    issues = collection(api+'/issues?state=all',get)
    pulls = collection(api+'/pulls?state=open',get)
    if get(api+'/git/ref/heads/'+branch)['object']['sha'] != sha:
        raise ValueError('Repository advanced during refresh; retry a fresh plan')
    return {'repository':name,'ref':'refs/heads/'+branch,'source_sha':sha,'recent_commits':commits,
            'issues':[x for x in issues if 'pull_request' not in x], 'pulls':pulls}, files


def validate_tasks(value):
    if not isinstance(value, dict) or set(value) != {'version','tasks'} or value['version'] != 1:
        raise ValueError('Invalid task manifest version/fields')
    tasks = value['tasks']
    if not isinstance(tasks, list) or len(tasks)>100:
        raise ValueError('Task count ceiling')
    by_id, issue_ids = {}, set()
    for task in tasks:
        if set(task) != {'id','issue','state','priority','depends_on','job'}:
            raise ValueError('Invalid task fields')
        if not re.fullmatch('[a-z][a-z0-9-]{0,63}',task['id']) or task['id'] in by_id:
            raise ValueError('Invalid/duplicate task ID')
        if type(task['issue']) is not int or task['issue']<1 or task['issue'] in issue_ids:
            raise ValueError('Invalid/duplicate issue ownership')
        if task['state'] not in ('ready','paused','done') or type(task['priority']) is not int or not 1<=task['priority']<=100:
            raise ValueError('Invalid task state/priority')
        if not isinstance(task['depends_on'],list) or any(not isinstance(x,str) for x in task['depends_on']):
            raise ValueError('Invalid dependencies')
        by_id[task['id']]=task;issue_ids.add(task['issue'])
    visited=set()
    def visit(name, ancestors):
        if name not in by_id or name in ancestors:
            raise ValueError('Unknown or cyclic dependency')
        if name in visited: return
        for dep in by_id[name]['depends_on']:
            visit(dep,ancestors|{name})
        visited.add(name)
    for name in by_id: visit(name,set())
    return by_id


def choose(project, snapshot, files, worker_registry):
    if worker_registry.get(project,{}).get('url') != 'https://github.com/'+snapshot['repository']+'.git':
        raise ValueError('Controller/worker repository mismatch')
    base = {'project':project,'source_sha':snapshot['source_sha'],'repository':snapshot['repository'],
            'ref':snapshot['ref'],'status':'blocked','reasons':[], 'authority':'plan-only',
            'provider_calls':0,'spend_usd':0,'governance_sha256':{}}
    for name in GOVERNANCE:
        if name not in files:
            base['reasons'].append('missing_governance:'+name)
        else:
            base['governance_sha256'][name]=hashlib.sha256(files[name][0]).hexdigest()
    manifest = 'config/controller/tasks.json'
    if manifest not in files:
        base['reasons'].append('no_committed_task_manifest')
    if base['reasons']: return base
    base['task_manifest_sha256']=hashlib.sha256(files[manifest][0]).hexdigest()
    tasks = validate_tasks(json.loads(files[manifest][0]))
    issues = {i['number']:i for i in snapshot['issues']}
    for task in sorted(tasks.values(),key=lambda t:(t['priority'],t['id'])):
        name, issue = task['id'], issues.get(task['issue'])
        reason = None
        if task['state'] != 'ready': reason='not_ready'
        elif not issue or issue['state'] != 'open': reason='issue_not_open'
        elif issue.get('assignees'): reason='existing_issue_owner'
        elif 'gatewayai:ready' not in {x['name'] for x in issue.get('labels',[])}: reason='issue_not_approved'
        elif any(tasks[d]['state'] != 'done' or issues.get(tasks[d]['issue'],{}).get('state') != 'closed'
                 for d in task['depends_on']): reason='dependency_not_completed'
        elif any(re.search(r'(?<![A-Za-z0-9])#'+str(task['issue'])+r'\b',
                           (p.get('title') or '')+' '+(p.get('body') or '')) for p in snapshot['pulls']):
            reason='existing_pull_request_owner'
        if reason:
            base['reasons'].append(name+':'+reason);continue
        job=task['job']
        worker.validate_job(job,worker_registry)
        if (job['project']!=project or job['ref']!=snapshot['ref'] or job['model_budget_usd']!=0
                or 'coding' not in job):
            raise ValueError('Task may only propose a zero-budget coding job for this snapshot')
        if any(name not in files for name in job['coding']['read_paths']):
            raise ValueError('Required coding context missing')
        base.update(status='awaiting_operator_review',task_id=name,issue=task['issue'],job=job,
                    max_iterations=1,required_next='Review exact source, job and budget before separate worker execution')
        return base
    base['reasons'].append('no_eligible_task')
    return base


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--output-directory',type=Path,required=True)
    args=parser.parse_args()
    if os.name!='posix': raise ValueError('Linux/WSL planner required')
    os.umask(0o077)
    output=args.output_directory
    if (not output.is_absolute() or output.resolve().is_relative_to(REPO)
            or any(p.is_symlink() for p in (output,*output.parents))):
        raise ValueError('Private output must be outside the checkout')
    output.mkdir(mode=0o700,exist_ok=True)
    info=output.stat()
    if info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700:
        raise ValueError('Expected operator-owned 0700 output directory')
    import shutil
    if shutil.disk_usage(output).free < 16*1024**3: raise ValueError('Storage reserve reached')
    registry=json.loads((REPO/'config/controller/projects.json').read_text())
    worker_registry=json.loads((REPO/'config/worker/projects.json').read_text())
    with tempfile.TemporaryDirectory(prefix='refresh-',dir=output) as temporary:
        import signal
        def expired(*_): raise TimeoutError('Repository refresh deadline')
        previous=signal.signal(signal.SIGALRM,expired)
        signal.alarm(180)
        try:
            snapshot,files=refresh(args.project,registry,Path(temporary))
            result=choose(args.project,snapshot,files,worker_registry)
        finally:
            signal.alarm(0);signal.signal(signal.SIGALRM,previous)
    result.update(run_id=uuid.uuid4().hex,created_utc=datetime.now(timezone.utc).isoformat(),
                  recent_commits=snapshot['recent_commits'],
                  inventory_sha256=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest())
    raw=json.dumps(result,indent=2).encode()
    target=output/(result['run_id']+'.json')
    with target.open('xb') as stream: stream.write(raw)
    print(json.dumps({'status':result['status'],'plan':str(target),'sha256':hashlib.sha256(raw).hexdigest(),
                      'source_sha':result['source_sha'],'reasons':result['reasons']}))


if __name__=='__main__':
    try: main()
    except Exception as error:
        raise SystemExit('Controller plan rejected: '+type(error).__name__+'; no execution or publishing occurred')

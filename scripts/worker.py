"""Operator-only Phase 6 worker broker; no daemon or production access."""
import argparse
import base64
import difflib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
import uuid

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('worker_sandbox', REPO / 'deploy/worker/sandbox.py')
sandbox = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sandbox)
spec = importlib.util.spec_from_file_location('worker_coding', REPO / 'scripts/worker_coding.py')
coding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coding)
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']
MAX_OUTPUT = 2 * 1024 * 1024


def validate_job(job, registry):
    if set(job) - {'coding'} != {'project', 'ref', 'commands', 'write_paths', 'timeout_seconds', 'model_budget_usd'}:
        raise ValueError('Unexpected job fields')
    project = registry.get(job['project'])
    if not project or job['ref'] not in project['refs']:
        raise ValueError('Repository/ref not approved')
    if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git', project['url']):
        raise ValueError('Only approved public GitHub HTTPS repositories')
    if not re.fullmatch(r'refs/heads/[A-Za-z0-9_/-]+', job['ref']) or '..' in job['ref']:
        raise ValueError('Invalid branch ref')
    if type(job['timeout_seconds']) is not int or not 1 <= job['timeout_seconds'] <= 120:
        raise ValueError('Run duration must be 1..120 seconds')
    if 'coding' in job:
        coding.validate(job['coding'], job['model_budget_usd'], sandbox.relative)
    elif type(job['model_budget_usd']) not in (int, float) or job['model_budget_usd'] != 0:
        raise ValueError('Model execution is disabled in this worker milestone')
    if not isinstance(job['write_paths'], list) or not 1 <= len(job['write_paths']) <= 20:
        raise ValueError('Require explicit output paths')
    for path in job['write_paths']:
        sandbox.relative(path)
    if len(set(job['write_paths'])) != len(job['write_paths']):
        raise ValueError('Duplicate output path')
    commands = job['commands']
    if not isinstance(commands, list) or not 1 <= len(commands) <= 8:
        raise ValueError('Command count must be 1..8')
    for argv in commands:
        if (not isinstance(argv, list) or not 1 <= len(argv) <= 32
                or any(not isinstance(a, str) or not a or '\x00' in a for a in argv)
                or sum(map(len, argv)) > 16384):
            raise ValueError('Invalid bounded argv')
    return project


def bounded(args, timeout=60, limit=MAX_OUTPUT, cwd=None, env=None, file_limit=None):
    """Bound wall time and captured bytes; terminate the whole host CLI group."""
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))
        resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               cwd=cwd, env=env, start_new_session=True,
                               preexec_fn=limits if file_limit is not None else None)
    data = bytearray()
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    completed = False
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Command time ceiling')
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ValueError('Command output ceiling')
        process.wait(timeout=max(0.01, deadline-time.monotonic()))
        completed = True
        return process.returncode, bytes(data)
    finally:
        selector.close()
        if not completed:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        process.stdout.close()


def checked(args, **kwargs):
    code, output = bounded(args, **kwargs)
    if code:
        raise RuntimeError('Command failed; private output withheld')
    return output


def docker_args(image, run_id, source):
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise ValueError('Use the locally built immutable worker image ID')
    if not re.fullmatch(r'[a-f0-9]{32}', run_id):
        raise ValueError('Invalid run ID')
    return DOCKER + ['run', '-d', '--pull=never', '--name', 'gatewayai-worker-'+run_id,
        '--label', 'gatewayai.role=isolated-worker', '--network=none', '--read-only',
        '--user=65532:65532', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
        '--pids-limit=64', '--cpus=1', '--memory=768m', '--memory-swap=768m',
        '--ulimit=nofile=256:256', '--ulimit=fsize=16777216:16777216',
        '--restart=no', '--log-driver=none', '--stop-timeout=2',
        '--tmpfs=/workspace:rw,nosuid,nodev,size=268435456,uid=65532,gid=65532,mode=0700',
        '--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=67108864,uid=65532,gid=65532,mode=0700',
        '--mount', 'type=bind,src='+str(source)+',dst=/input,readonly', image]


def artifacts(payload, original, paths):
    if set(payload) != {'changes'} or not isinstance(payload['changes'], list):
        raise ValueError('Invalid worker artifact')
    seen = set()
    diff = []
    size = 0
    for change in payload['changes']:
        if set(change) != {'path', 'before_sha256', 'content_base64', 'mode'}:
            raise ValueError('Invalid change fields')
        name = change['path']
        sandbox.relative(name)
        if name not in paths or name in seen:
            raise ValueError('Unexpected artifact path')
        seen.add(name)
        before = original.get(name)
        digest = hashlib.sha256(before[0]).hexdigest() if before else None
        if change['before_sha256'] != digest:
            raise ValueError('Artifact base mismatch')
        data = base64.b64decode(change['content_base64'], validate=True) if change['content_base64'] is not None else None
        if change['mode'] not in (0o644, 0o755, None) or (data is None) != (change['mode'] is None):
            raise ValueError('Invalid file mode')
        size += len(data or b'')
        if size > sandbox.MAX_ARTIFACT:
            raise ValueError('Artifact size ceiling')
        old = before[0].decode('utf-8').splitlines(keepends=True) if before else []
        new = data.decode('utf-8').splitlines(keepends=True) if data is not None else []
        if any('\x00' in line for line in old + new):
            raise ValueError('Binary change not supported')
        for line in difflib.unified_diff(old, new, fromfile='a/'+name if before else '/dev/null',
                                         tofile='b/'+name if data is not None else '/dev/null'):
            diff.append(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n')
    result = ''.join(diff)
    if len(result.encode('utf-8')) > sandbox.MAX_ARTIFACT:
        raise ValueError('Review patch size ceiling')
    return result


def private_root(path):
    if not path.is_absolute() or path.resolve().is_relative_to(REPO):
        raise ValueError('Runtime must be outside repository')
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError('Symlink runtime path')
    if not path.exists():
        path.mkdir(mode=0o700)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Expected root-owned 0700 runtime')


def validate_image(info):
    config = info['Config']
    expected = ['timeout', '--signal=KILL', '150', 'python3', '-I', '/opt/gatewayai-worker/sandbox.py']
    if (config.get('Volumes') or config.get('User') != '65532:65532'
            or config.get('Entrypoint') != expected or config.get('WorkingDir') != '/workspace'):
        raise ValueError('Image differs from the reviewed worker runtime contract')


def run(job, image, root, coding_config=None):
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise ValueError('Approved Linux operator required; never expose this CLI to agents')
    import fcntl
    registry = json.loads((REPO/'config/worker/projects.json').read_text())
    project = validate_job(job, registry)
    if 'coding' in job and coding_config is None:
        raise ValueError('Operator coding configuration required')
    if coding_config and Path(coding_config).resolve().is_relative_to(REPO):
        raise ValueError('Credentials must remain outside the checkout')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise ValueError('Immutable image ID required')
    os.umask(0o077)
    private_root(root)
    with (root/'operator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Disk and image admission precede fetch/execution. No implicit pulls.
        if shutil.disk_usage(root).free < 16*1024**3:
            raise ValueError('Need 15 GiB floor plus 1 GiB reserve')
        info = json.loads(checked(DOCKER+['info', '--format', '{{json .}}']))
        if info['OSType'] != 'linux' or 'name=seccomp,profile=builtin' not in info['SecurityOptions']:
            raise ValueError('Linux daemon with default seccomp required')
        if shutil.disk_usage(info['DockerRootDir']).free < 16*1024**3:
            raise ValueError('Docker storage needs 15 GiB floor plus 1 GiB reserve')
        image_info = json.loads(checked(DOCKER+['image', 'inspect', image]))[0]
        validate_image(image_info)
        run_id = uuid.uuid4().hex
        folder = root/run_id
        folder.mkdir(mode=0o700)
        source = folder/'input'
        source.mkdir(mode=0o755)
        source.chmod(0o755)
        home = folder/'home'
        home.mkdir(mode=0o700)
        env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(home),
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
               'GIT_TERMINAL_PROMPT': '0', 'GIT_ALLOW_PROTOCOL': 'https', 'LC_ALL': 'C'}
        name = 'gatewayai-worker-'+run_id
        record = {'run_id': run_id, 'project': job['project'], 'ref': job['ref'],
                  'image_id': image, 'model_budget_usd': job['model_budget_usd'], 'provider_calls': 0,
                  'branch': 'worker/'+run_id, 'status': 'failed', 'commands': []}
        created = False
        started = time.monotonic()
        try:
            gitdir = folder/'source.git'
            checked(['git', 'init', '--bare', str(gitdir)], env=env)
            git = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'http.followRedirects=false',
                   '-c', 'fetch.unpackLimit=0', '--git-dir='+str(gitdir)]
            # An approved public fetch only; no repository code, hooks or credentials.
            checked(git+['fetch', '--depth=1', '--no-tags', project['url'], job['ref']],
                    env=env, file_limit=64*1024*1024)
            sha = checked(git+['rev-parse', 'FETCH_HEAD'], env=env).decode().strip()
            if not re.fullmatch('[a-f0-9]{40}', sha):
                raise ValueError('Invalid fetched revision')
            record['source_sha'] = sha
            archive = checked(git+['archive', '--format=tar', sha], env=env,
                              limit=sandbox.MAX_SOURCE, file_limit=64*1024*1024)
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                original = sandbox.source_files(tar)
            (source/'source.tar').write_bytes(archive)
            (source/'job.json').write_text(json.dumps({**job, 'branch': record['branch']}))
            record['source_archive_sha256'] = hashlib.sha256(archive).hexdigest()
            record['job_sha256'] = hashlib.sha256((source/'job.json').read_bytes()).hexdigest()
            for p in source.iterdir():
                p.chmod(0o444)
            proposal = None
            if 'coding' in job:
                proposal, debit = coding.generate(job, original, run_id, root, coding_config, sandbox.relative)
                artifacts(proposal, original, job['write_paths'])
                record['coding_admission_micro_usd'] = debit
                record['gateway_calls'] = 1
                # Provider attempt counts belong to the gateway ledger, not the client.
                record.pop('provider_calls', None)
                (folder/'proposal.json').write_text(json.dumps(proposal))
            created = True
            checked(docker_args(image, run_id, source))
            deadline = time.monotonic()+job['timeout_seconds']
            while True:
                code, _ = bounded(DOCKER+['exec', name, 'test', '-f', '/tmp/ready'], timeout=5)
                if code == 0:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Worker startup ceiling')
                time.sleep(0.1)
            if proposal is not None:
                apply_code = ('import json,base64;from pathlib import Path;'
                    'changes=json.loads(base64.b64decode(__import__("sys").argv[1]))["changes"];'
                    '\nfor c in changes:\n p=Path("/workspace")/c["path"]\n'
                    ' if c["content_base64"] is None: p.unlink()\n'
                    ' else:\n  p.parent.mkdir(parents=True,exist_ok=True)\n'
                    '  p.write_bytes(base64.b64decode(c["content_base64"]))\n  p.chmod(c["mode"])\n')
                checked(DOCKER+['exec', name, 'python3', '-I', '-c', apply_code,
                        base64.b64encode(json.dumps(proposal).encode()).decode()], timeout=10)
            for number, argv in enumerate(job['commands']):
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Run time ceiling')
                code, output = bounded(DOCKER+['exec', '--workdir=/workspace', name, *argv],
                                       timeout=min(30, remaining))
                (folder/('command-'+str(number)+'.log')).write_bytes(output)
                record['commands'].append({'argv': argv, 'exit_code': code, 'output_bytes': len(output)})
                if code:
                    raise RuntimeError('Sandbox command failed')
            payload = json.loads(checked(DOCKER+['exec', name, 'python3', '-I',
                               '/opt/gatewayai-worker/sandbox.py', 'export'], timeout=10))
            diff = artifacts(payload, original, job['write_paths'])
            (folder/'changes.json').write_text(json.dumps(payload, indent=2))
            record['artifact_sha256'] = hashlib.sha256((folder/'changes.json').read_bytes()).hexdigest()
            (folder/'review.patch').write_text(diff)
            record['patch_sha256'] = hashlib.sha256(diff.encode()).hexdigest()
            record['changed_paths'] = [c['path'] for c in payload['changes']]
            record['status'] = 'review_required'
        except Exception as error:
            record['failure_type'] = type(error).__name__
        finally:
            if created:
                # Cleanup precedes budget audit; a damaged ledger must not skip removal.
                code, _ = bounded(DOCKER+['rm', '-f', name], timeout=20)
                record['container_removed'] = code == 0
                if code:
                    record['status'] = 'cleanup_failed'
            if 'coding' in job:
                record.pop('provider_calls', None)
                record['coding_admission_micro_usd'] = 0
                record['gateway_calls_upper_bound'] = 0
                ledger = root/'coding-budget.sqlite3'
                if ledger.exists():
                    import sqlite3
                    from contextlib import closing
                    try:
                        with closing(sqlite3.connect(ledger)) as db:
                            row = db.execute('SELECT debit FROM runs WHERE id=?', (run_id,)).fetchone()
                        record['coding_admission_micro_usd'] = row[0] if row else 0
                        record['gateway_calls_upper_bound'] = 1 if row else 0
                    except sqlite3.Error:
                        record['status'] = 'budget_audit_failed'
                        record['coding_admission_micro_usd'] = None
                        record['gateway_calls_upper_bound'] = 1
            record['elapsed_seconds'] = round(time.monotonic()-started, 2)
            (folder/'result.json').write_text(json.dumps(record, indent=2))
        print(json.dumps({k: v for k, v in record.items() if k != 'commands'}))
        return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--root', type=Path, default=Path('/var/lib/gatewayai-worker'))
    parser.add_argument('--coding-config', type=Path)
    args = parser.parse_args()
    try:
        result = run(json.loads(args.job.read_text()), args.image, args.root, args.coding_config)
        raise SystemExit(0 if result['status'] == 'review_required' else 1)
    except Exception as error:
        raise SystemExit('Worker rejected: '+type(error).__name__+'; no credentials printed')

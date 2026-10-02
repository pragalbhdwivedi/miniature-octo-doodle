"""Operator-admitted source development and bounded offline acceptance.

Models supply UTF-8 replacement files, never commands or sandbox configuration.
The existing Docker daemon receives only disposable public source snapshots.
"""
import ast
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import uuid

MAX_FILE_BYTES = 32768
MAX_TOTAL_BYTES = 65536
PROFILE_KEYS = {'image', 'commands', 'acceptance_tests', 'timeout_seconds', 'minimum_tests'}
FORBIDDEN = {'.git', '.github', '.env', 'secrets', 'creds', 'backups', 'data',
             'models', 'vm_notes', 'local_certificates', 'tmp', 'node_modules'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def relative(path):
    if (not isinstance(path, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]{0,179}', path)
            or any(p in ('', '.', '..') or p.lower() in FORBIDDEN or p.startswith('.') for p in path.split('/'))):
        raise ValueError('Development path must be ordinary public source')
    return path


def paths(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        raise ValueError('Development manifests require one to eight exact paths')
    for path in value:relative(path)
    if len(set(p.casefold() for p in value)) != len(value):raise ValueError('Duplicate development paths')
    return value


def validate_task(task, profiles):
    if task.get('operation') != 'development_change' or task.get('risk') != 'reversible':
        raise ValueError('Development requires an admitted reversible operation')
    if not re.fullmatch(r'[a-f0-9]{40}', task.get('source_sha', '')):raise ValueError('Immutable source required')
    name = task.get('development_profile')
    if not isinstance(name, str) or name not in profiles:raise ValueError('Operator development profile required')
    profile = profiles[name]
    if not isinstance(profile, dict) or set(profile) != PROFILE_KEYS:raise ValueError('Invalid development profile')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', profile['image']):raise ValueError('Locally installed immutable image required')
    for key, low, high in (('timeout_seconds', 1, 120), ('minimum_tests', 1, 10000)):
        if type(profile[key]) is not int or not low <= profile[key] <= high:raise ValueError('Invalid acceptance bound')
    source, writable, staged = (set(paths(task[k])) for k in ('paths', 'write_paths', 'test_files'))
    protected = set(paths(profile['acceptance_tests']))
    if not writable <= staged <= source or not protected <= staged or protected & writable:
        raise ValueError('Source, writable and protected acceptance manifests disagree')
    if all(p.startswith('tests/') for p in writable):raise ValueError('Development task must change application source')
    commands = profile['commands']
    if not isinstance(commands, list) or not 1 <= len(commands) <= 4:raise ValueError('One to four fixed suites required')
    for command in commands:
        if (not isinstance(command, list) or not 4 <= len(command) <= 24 or command[:3] != ['python', '-m', 'unittest']
                or any(not isinstance(a, str) or not a or len(a) > 180 or '\x00' in a or '\n' in a for a in command)):
            raise ValueError('Only operator-fixed Python unittest argv are supported')
        # These are arguments to unittest, never to a shell or Python's evaluator.
        for argument in command[3:]:
            if not re.fullmatch(r'[A-Za-z0-9_.*?/-]+', argument) or '..' in argument:
                raise ValueError('Invalid fixed test argument')
    return profile


def _tampering_signatures(content):
    """Recognize direct harness tampering, not an arbitrary-Python safety proof.

    Preserve pre-existing constructs only in their original lexical context.
    This lets existing guarded CLI exits remain while rejecting moved exits,
    alias-based process termination and newly introduced dynamic execution.
    Independent review remains required for indirect or semantic manipulation.
    """
    tree=ast.parse(content)
    aliases={}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for name in node.names:aliases[name.asname or name.name.split('.')[0]]=name.name if name.asname else name.name.split('.')[0]
        elif isinstance(node,ast.ImportFrom):
            for name in node.names:aliases[name.asname or name.name]=(node.module or '')+'.'+name.name
    def qualified(node):
        if isinstance(node,ast.Name):return aliases.get(node.id,node.id)
        if isinstance(node,ast.Attribute):return qualified(node.value)+'.'+node.attr
        return ''
    def dangerous_reference(name):
        return (name in {'eval','exec','compile','__import__','exit','quit','SystemExit',
                         'builtins.eval','builtins.exec','builtins.compile','builtins.__import__',
                         'builtins.exit','builtins.quit','builtins.SystemExit','sys.exit','os._exit',
                         'os.abort','os.kill','os.killpg','signal.raise_signal','signal.pthread_kill',
                         'importlib.import_module','runpy.run_module','runpy.run_path'}
                or name.startswith(('os.exec','os.spawn'))
                or name.rsplit('.',1)[-1] in {'exec_module','load_module','__globals__','__builtins__','__subclasses__'})
    def harness_reference(node):
        name=qualified(node)
        return (name.startswith(('unittest.','pytest.','builtins.')) or name in {'unittest','pytest','builtins'}
                or isinstance(node,ast.Attribute) and node.attr.startswith('assert'))
    found=Counter()
    def visit(node,context):
        risk=False
        if isinstance(node,(ast.Name,ast.Attribute)) and isinstance(node.ctx,ast.Load):
            risk=dangerous_reference(qualified(node))
        if isinstance(node,ast.Constant) and isinstance(node.value,str):
            risk=bool(re.search(r'(?m)(?:^|\n)\s*Ran\s+.+?\s+tests?\s+in\b',node.value)
                or re.search(r'(?:unittest|pytest)\.[A-Za-z_.]*assert[A-Za-z_]*',node.value))
        if isinstance(node,ast.JoinedStr):
            text=''.join(v.value if isinstance(v,ast.Constant) and isinstance(v.value,str) else '{}' for v in node.values)
            risk=bool(re.search(r'(?m)(?:^|\n)\s*Ran\s+.+?\s+tests?\s+in\b',text))
        if isinstance(node,ast.Attribute) and isinstance(node.ctx,(ast.Store,ast.Del)):
            risk=harness_reference(node) or qualified(node) in {'sys.stdout','sys.stderr','sys.modules'}
        if isinstance(node,ast.Subscript) and isinstance(node.ctx,(ast.Store,ast.Del)):
            risk=qualified(node.value) in {'sys.modules','__builtins__'}
        if isinstance(node,ast.Call):
            call=qualified(node.func)
            if call.rsplit('.',1)[-1] in {'setattr','delattr','getattr'} and len(node.args)>=2:
                attr=node.args[1].value if isinstance(node.args[1],ast.Constant) else None
                risk=risk or (isinstance(attr,str) and (dangerous_reference(qualified(node.args[0])+'.'+attr)
                    or attr.startswith('assert') or attr in {'__dict__','__globals__','__builtins__'}))
                if call.rsplit('.',1)[-1] in {'setattr','delattr'}:
                    risk=risk or harness_reference(node.args[0])
            if call in {'unittest.mock.patch','unittest.mock.patch.object','mock.patch','mock.patch.object'} and node.args:
                target=node.args[0]
                risk=risk or harness_reference(target) or (isinstance(target,ast.Constant) and isinstance(target.value,str)
                    and target.value.startswith(('unittest.','pytest.','builtins.')))
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and (node.name=='load_tests' or node.name.startswith('assert')):
            risk=True
        if risk:found[(context,ast.dump(node,include_attributes=False),qualified(node))]+=1
        child_context=context
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            child_context=context+((type(node).__name__,node.name),)
        elif isinstance(node,ast.If):child_context=context+(('If',ast.dump(node.test,include_attributes=False)),)
        for child in ast.iter_child_nodes(node):visit(child,child_context)
    visit(tree,())
    return found


def validate_source_integrity(before,after):
    try:added=_tampering_signatures(after)-_tampering_signatures(before)
    except SyntaxError as exc:raise ValueError('Invalid Python development source') from exc
    if added:raise ValueError('New test-harness tampering, process termination or dynamic execution requires operator review')


def validate_changes(task, before, changes, profile):
    if set(changes) != set(task['write_paths']) or not set(task['test_files']) <= set(before):
        raise ValueError('Proposal does not match admitted development scope')
    total = 0
    changed = []
    for path, content in changes.items():
        relative(path)
        if not isinstance(content, str) or '\x00' in content:raise ValueError('Text proposal required')
        size = len(content.encode('utf-8'));total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:raise ValueError('Development proposal exceeds byte bound')
        if content != before[path]:
            if path.endswith('.py'):validate_source_integrity(before[path],content)
            changed.append(path)
    if not changed or not any(not p.startswith('tests/') for p in changed):
        raise ValueError('Development proposal must change application source')
    if set(changes) & set(profile['acceptance_tests']):raise ValueError('Protected acceptance test changed')
    return changed


def review_diff(before, changes):
    result = ''.join(''.join(difflib.unified_diff(before[p].splitlines(True), content.splitlines(True),
                      fromfile='a/'+p, tofile='b/'+p)) for p, content in sorted(changes.items()))
    if len(result.encode('utf-8')) > MAX_TOTAL_BYTES:raise ValueError('Review diff exceeds context bound')
    return result


def _suite(runner, profile, files, directory):
    directory.mkdir()
    stage = directory/'source';stage.mkdir()
    total = 0
    for path, content in files.items():
        relative(path)
        if not isinstance(content, str) or '\x00' in content:raise ValueError('Invalid source text')
        size = len(content.encode('utf-8'));total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:raise ValueError('Source snapshot exceeds byte bound')
        target = stage/path;target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')
    receipts = []
    for index, argv in enumerate(profile['commands']):
        name = 'gatewayai-development-'+uuid.uuid4().hex
        command = ['docker', 'run', '--rm', '--pull=never', '--name', name,
            '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--user=65534:65534', '--pids-limit=64', '--memory=512m', '--memory-swap=512m', '--cpus=1',
            '--ulimit=nofile=128:128', '--ulimit=fsize=16777216:16777216', '--log-driver=none',
            '--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=32m',
            '--mount', 'type=bind,source='+str(stage.resolve())+',target=/work,readonly',
            '--workdir=/work', '--env=PYTHONPATH=/work/src:/work', '--env=PYTHONDONTWRITEBYTECODE=1',
            '--entrypoint=python', profile['image'], *argv[1:]]
        try:
            code, out, err = runner(command, timeout=profile['timeout_seconds'], limit=262144)
        finally:
            # Killing a hung Docker client alone would leave candidate code running.
            runner(['docker', 'rm', '--force', name], timeout=10, limit=16384)
        output = (out+err).decode('utf-8', errors='replace')
        (directory/('command-'+str(index)+'.txt')).write_text(output, encoding='utf-8')
        counts = re.findall(r'^Ran (\d+) tests? in ', output, re.MULTILINE)
        count = int(counts[-1]) if len(counts) == 1 else 0
        passed = code == 0 and count >= profile['minimum_tests'] and re.search(r'^OK\s*$', output, re.MULTILINE) is not None
        receipts.append({'argv': argv, 'passed': passed, 'test_count': count, 'exit_code': code,
                         'output_sha256': hashlib.sha256(output.encode()).hexdigest(), 'summary': output[-1000:]})
        if not passed:break
    return {'passed': len(receipts) == len(profile['commands']) and all(r['passed'] for r in receipts),
            'test_count': sum(r['test_count'] for r in receipts), 'commands': receipts}


def test_candidate(task, before, changes, profiles, runner, directory):
    profile = validate_task(task, profiles)
    changed = validate_changes(task, before, changes, profile)
    fixed = {p: before[p] for p in task['test_files']}
    directory = Path(directory)
    baseline = _suite(runner, profile, fixed, directory/'baseline')
    candidate = _suite(runner, profile, {**fixed, **changes}, directory/'candidate') if baseline['passed'] else None
    passed = bool(candidate and candidate['passed'] and candidate['test_count'] >= baseline['test_count'])
    return {'passed': passed, 'test_count': candidate['test_count'] if candidate else 0,
            'operation': 'development_change', 'source_sha': task['source_sha'],
            'profile_sha256': digest(profile), 'snapshot_sha256': digest(fixed),
            'changed': changed, 'baseline': baseline, 'candidate': candidate,
            'summary': 'Fixed baseline and candidate suites passed.' if passed else 'Baseline, candidate or test-count regression failed.'}


def verify_evidence(task, tests, profiles):
    profile = validate_task(task, profiles)
    if (tests.get('operation') != 'development_change' or tests.get('source_sha') != task['source_sha']
            or tests.get('profile_sha256') != digest(profile) or not tests.get('passed')):
        raise ValueError('Development evidence does not bind the current source and acceptance profile')

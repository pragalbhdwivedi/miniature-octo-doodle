"""Cold backup and isolated recovery. Commands never print secrets or raw errors.

Invoke through recovery.ps1 (Windows ACL/preflight). No pulls, overwrites,
volume deletion, provider requests, or automatic cutover.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parent.parent
PROJECT = 'miniature-octo-doodle'
VOLUMES = {'postgres-data': '/var/lib/postgresql/data',
           'open-webui-data': '/app/backend/data', 'policy-data': '/app/policy-data'}
FILES = {'.env', 'compose.json', 'source.tar', 'gateway-config.json', 'policy.json',
         *(name + '.tar' for name in VOLUMES)}


def check(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def run(args, *, env=None, cwd=None):
    result = subprocess.run(args, capture_output=True, env=env, cwd=cwd)
    check(result.returncode == 0, 'Command failed: ' + args[0] + ' (output withheld)')
    return result.stdout.decode('utf-8').strip()


def docker(*args):
    return run(['docker', *map(str, args)])


def env_values(path):
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, value = line.split('=', 1)
        check(re.fullmatch(r'[A-Z][A-Z0-9_]*', key) and key not in values, 'Invalid local configuration')
        values[key] = value.strip()
    return values


def compose(path, *args, env=None):
    return run(['docker', 'compose', '-f', str(path), *args], env=env)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive_index(path):
    """Reject traversal, duplicate files, links, devices and external tablespaces."""
    result = {}
    with tarfile.open(path) as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            check(not name.is_absolute() and '..' not in name.parts and '\\' not in member.name
                  and ':' not in member.name, 'Unsafe archive path')
            check(member.isdir() or member.isfile(), 'Unsupported archive entry (links/devices)')
            key = str(name)
            check(key not in result, 'Duplicate archive entry')
            digest = None
            if member.isfile():
                with archive.extractfile(member) as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            result[key] = [member.mode, member.uid, member.gid, member.size, digest]
    return result


def disk_guard(path, additional):
    check(shutil.disk_usage(path).free - additional >= 15 * 1024**3, 'Critical disk reserve would be crossed')


def recovery_disk_guard(root, additional):
    # Docker can store its VHDX on another drive; check that drive's reserve too.
    paths = [root, Path(os.environ['LOCALAPPDATA'])/'Docker/wsl']
    settings_path = Path(os.environ['APPDATA'])/'Docker/settings-store.json'
    settings = json.loads(settings_path.read_text(encoding='utf-8-sig'))
    paths.extend(Path(settings[key]) for key in ('DataFolder','DiskImageLocation') if settings.get(key))
    for path in paths:
        disk_guard(path, additional)


def helper(image, mounts, *args):
    command = ['run', '--rm', '--pull', 'never', '--network', 'none']
    for mount in mounts:
        command += ['--mount', mount]
    return docker(*command, '--entrypoint', 'sh', image, *args)


def volume_mount(name, readonly=True):
    return 'type=volume,src=' + name + ',dst=/volume' + (',readonly' if readonly else '')


def bind_mount(path, readonly=False):
    check(',' not in str(path), 'Comma in recovery path unsupported')
    return 'type=bind,src=' + str(path) + ',dst=/backup' + (',readonly' if readonly else '')


def validate_bundle(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    check(manifest['format'] == 1 and set(manifest['files']) == FILES, 'Unsupported backup inventory')
    for name, expected in manifest['files'].items():
        file = folder / name
        check(file.is_file() and not file.is_symlink() and sha(file) == expected, 'Backup integrity check failed')
    for name in [*(v + '.tar' for v in VOLUMES), 'source.tar']:
        archive_index(folder / name)
    config = json.loads((folder / 'compose.json').read_text())
    check(config['name'] == PROJECT and set(config['services']) == {'postgres','litellm','open-webui'}, 'Unexpected backup services')
    check(set(config['volumes']) == set(VOLUMES), 'Unexpected backup volumes')
    policy = json.loads((folder / 'policy.json').read_text())
    check(policy['decision_plane'] == {'mode':'deterministic', 'jev_enabled':False}, 'Jev must remain disabled')
    return manifest, config


def backup(root):
    check(not run(['git', 'status', '--porcelain'], cwd=REPO), 'Commit or stash changes before backing up a reproducible source revision')
    values = env_values(REPO / '.env')
    environment = dict(os.environ, **values)
    config = json.loads(compose(REPO / 'compose.yaml', 'config', '--format', 'json', env=environment))
    check(config['name'] == PROJECT and set(config['volumes']) == set(VOLUMES), 'Unexpected source deployment')
    ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT).splitlines()
    containers = json.loads(docker('inspect', *ids)) if ids else []
    check(len(containers) == 3 and all(c['State'].get('Health',{}).get('Status') == 'healthy' for c in containers), 'All three source services must be healthy')
    for container in containers:
        service = container['Config']['Labels']['com.docker.compose.service']
        check(service in config['services'] and container['Config']['Image'] == config['services'][service]['image'], 'Running image differs from configured pin')
    actual_volumes = {m['Name'] for c in containers for m in c['Mounts'] if m['Type'] == 'volume'}
    expected_volumes = {config['volumes'][v]['name'] for v in VOLUMES}
    check(actual_volumes == expected_volumes, 'Source mount inventory mismatch')
    image = config['services']['postgres']['image']
    for service in config['services'].values():
        check('@sha256:' in service['image'], 'Unpinned image')
        docker('image', 'inspect', service['image'])
    size = sum(int(helper(image, [volume_mount(v)], '-c', 'du -sk /volume').split()[0]) * 1024 for v in expected_volumes)
    recovery_disk_guard(root, size * 3 + 1024**3)
    name = 'backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = root / name
    folder.mkdir()  # Never reuse/overwrite an existing backup.
    print('Backup folder:', folder, flush=True)
    shutil.copy2(REPO / '.env', folder / '.env')
    (folder / 'compose.json').write_text(json.dumps(config))
    shutil.copy2(REPO / 'config/litellm/config.local.yaml', folder / 'gateway-config.json')
    shutil.copy2(REPO / 'config/policy/policy.local.json', folder / 'policy.json')
    commit = run(['git', 'rev-parse', 'HEAD'], cwd=REPO)
    run(['git', 'archive', '--format=tar', '-o', str(folder / 'source.tar'), commit], cwd=REPO)
    started = time.monotonic()
    try:
        print('Stopping only core UI/gateway, then PostgreSQL for a consistent snapshot...', flush=True)
        compose(REPO / 'compose.yaml', 'stop', '-t', '120', 'open-webui', 'litellm', env=environment)
        compose(REPO / 'compose.yaml', 'stop', '-t', '60', 'postgres', env=environment)
        states = json.loads(docker('inspect', *ids))
        check(all(not c['State']['Running'] and c['State']['ExitCode'] == 0 for c in states), 'Unclean shutdown; backup rejected')
        for volume in expected_volumes:
            check(not docker('ps','-q','--filter','volume=' + volume), 'A source volume still has a running writer')
        for logical in VOLUMES:
            helper(image, [volume_mount(config['volumes'][logical]['name']), bind_mount(folder)],
                   '-c', 'tar -cpf /backup/' + logical + '.tar -C /volume .')
            archive_index(folder / (logical + '.tar'))
        manifest = {'format':1, 'created_utc':datetime.now(timezone.utc).isoformat(), 'git_commit':commit,
                    'source_bytes':size, 'files':{name:sha(folder/name) for name in sorted(FILES)}}
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        validate_bundle(folder)
        print('PASS: consistent backup, hashes and archive safety verified', flush=True)
    finally:
        print('Resuming original core services...', flush=True)
        compose(REPO / 'compose.yaml', 'start', '--wait', '--wait-timeout', '240', env=environment)
        print('PASS: source services healthy; interruption seconds:', round(time.monotonic()-started, 2), flush=True)
    print('Backup bytes:', sum(p.stat().st_size for p in folder.iterdir()), flush=True)
    return folder


def restore_config(config, work, name, gateway_port, ui_port):
    config = json.loads(json.dumps(config))
    check(re.fullmatch(r'gatewayai-recovery-[a-z0-9][a-z0-9-]{0,35}', name), 'Recovery project name must use gatewayai-recovery- prefix')
    check(gateway_port != ui_port and all(1024 <= p <= 65535 and p not in (3000,4000) for p in (gateway_port,ui_port)), 'Invalid or live-core port')
    config['name'] = name
    for logical, volume in config['volumes'].items():
        volume.clear()
        volume['name'] = name + '_' + logical
    for logical, network in config['networks'].items():
        network.clear()
        network.update(name=name+'_'+logical, internal=True)
    targets = {'/app/config.yaml': work/'gateway-config.json', '/app/policy.json':work/'policy.json',
               '/app/policy-code/gateway':work/'source/gateway'}
    for service, definition in config['services'].items():
        definition['restart'] = 'no'
        definition.pop('container_name', None)
        for mount in definition.get('volumes', []):
            if mount['type'] == 'bind':
                check(mount['target'] in targets, 'Unapproved bind mount')
                # Compose's YAML loader can double Windows backslashes in JSON input.
                mount['source'] = targets[mount['target']].as_posix()
        check(not definition.get('privileged') and not definition.get('network_mode'), 'Unsafe container configuration')
        if service == 'postgres':
            check(not definition.get('ports'), 'Database publication forbidden')
        else:
            definition['ports'] = [{'target':4000 if service=='litellm' else 8080,
                                    'published':str(gateway_port if service=='litellm' else ui_port),
                                    'host_ip':'127.0.0.1','protocol':'tcp'}]
    env = config['services']['litellm']['environment']
    env.update(OPENAI_API_KEY='', GEMINI_API_KEY='', GATEWAY_MONTHLY_BUDGET_USD='0')
    env.pop('TYPESAFE_API_KEY', None)
    config['services']['open-webui']['environment']['WEBUI_URL'] = 'http://127.0.0.1:' + str(ui_port)
    return config


def http(url, key=None, body=None, expected=200):
    headers = {'Content-Type':'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data, headers), timeout=30) as response:
            status, payload = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, payload = error.code, error.read()
    check(status == expected, 'Recovery HTTP assertion failed: ' + str(status))
    return json.loads(payload)


def restore(root, folder, name, gateway_port, ui_port):
    restore_started = time.monotonic()
    manifest, config = validate_bundle(folder)
    name = name or 'gatewayai-recovery-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    work = root / name
    restored = restore_config(config, work, name, gateway_port, ui_port)
    check(not work.exists(), 'Recovery directory already exists')
    check(not docker('ps','-aq','--filter','label=com.docker.compose.project='+name), 'Recovery containers already exist')
    existing = set(docker('volume','ls','-q').splitlines())
    check(not existing & {v['name'] for v in restored['volumes'].values()}, 'Recovery volumes already exist')
    networks = set(docker('network','ls','--format','{{.Name}}').splitlines())
    check(not networks & {v['name'] for v in restored['networks'].values()}, 'Recovery networks already exist')
    for port in (gateway_port, ui_port):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',port))
    recovery_disk_guard(root, manifest['source_bytes'] * 3 + 1024**3)
    for service in config['services'].values():
        docker('image','inspect',service['image'])  # Never pull automatically.
    work.mkdir()
    (work/'source').mkdir()
    with tarfile.open(folder/'source.tar') as archive:
        archive.extractall(work/'source', filter='data')
    for filename in ('policy.json','gateway-config.json'):
        shutil.copy2(folder/filename, work/filename)
    compose_file = work/'compose.json'
    compose_file.write_text(json.dumps(restored))
    compose(compose_file, 'config', '--quiet')
    image = config['services']['postgres']['image']
    print('Restoring into new volumes:', name, flush=True)
    for logical, volume in restored['volumes'].items():
        docker('volume','create','--label','gatewayai.recovery='+name,volume['name'])
        helper(image, [volume_mount(volume['name'], False), bind_mount(folder, True)],
               '-c','tar -xpf /backup/'+logical+'.tar -C /volume')
        # Compare every restored file's bytes, ownership and mode before startup.
        helper(image,[volume_mount(volume['name']),bind_mount(work)],
               '-c','tar -cpf /backup/'+logical+'.tar -C /volume .')
        check(archive_index(work/(logical+'.tar')) == archive_index(folder/(logical+'.tar')), 'Restored volume differs from backup')
    print('PASS: all three restored volume trees match backup exactly', flush=True)
    started = time.monotonic()
    try:
        compose(compose_file,'up','-d','--pull','never','--wait','--wait-timeout','300')
        # Read every PostgreSQL table without exporting rows to the host/output.
        compose(compose_file,'exec','-T','postgres','sh','-c',
                'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /dev/null')
        for service, database in (('open-webui','/app/backend/data/webui.db'),
                                  ('litellm','/app/policy-data/budget.sqlite3')):
            probe = ('import sqlite3; db=sqlite3.connect("file:' + database + '?mode=ro",uri=True); '
                     'assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; db.close()')
            compose(compose_file,'exec','-T',service,'python','-c',probe)
        gateway = 'http://127.0.0.1:'+str(gateway_port)
        ui = 'http://127.0.0.1:'+str(ui_port)
        values = env_values(folder/'.env')
        http(gateway+'/health/liveliness')
        http(gateway+'/v1/models', expected=401)
        models = http(gateway+'/v1/models', values['WEBUI_GATEWAY_KEY'])['data']
        http(gateway+'/key/list', values['WEBUI_GATEWAY_KEY'], expected=403)
        login = http(ui+'/api/v1/auths/signin', body={'email':values['WEBUI_ADMIN_EMAIL'],'password':values['WEBUI_ADMIN_PASSWORD']})
        check(login['role']=='admin', 'Restored admin role mismatch')
        ui_models = http(ui+'/api/models', login['token'])['data']
        check(sorted(m['id'] for m in models)==sorted(m['id'] for m in ui_models), 'Restored discovery mismatch')
        for host in (gateway,ui):
            http(host.replace('127.0.0.1','localhost')+('/health/liveliness' if host==gateway else '/health'))
        if models:
            http(gateway+'/v1/chat/completions', values['WEBUI_GATEWAY_KEY'],
                 {'model':models[0]['id'],'messages':[{'role':'user','content':'Synthetic recovery deny probe'}]},429)
        # Compare ledger bytes after health/login and denied inference: no budget rollback/mutation.
        helper(image,[volume_mount(restored['volumes']['policy-data']['name']),bind_mount(work)],
               '-c','tar -cpf /backup/policy-after.tar -C /volume .')
        check(archive_index(work/'policy-after.tar')==archive_index(folder/'policy-data.tar'), 'Recovery modified retained budget ledger')
        for network in restored['networks'].values():
            check(json.loads(docker('network','inspect',network['name']))[0]['Internal'], 'Recovery egress isolation missing')
        report = {'passed':True,'backup_commit':manifest['git_commit'],'project':name,
                  'seconds_to_validate':round(time.monotonic()-started,2),'model_count':len(models),
                  'total_restore_seconds':round(time.monotonic()-restore_started,2),
                  'postgres_full_read':True,'sqlite_integrity':True,
                  'volume_content_match':True,'restored_admin_login':True,'budget_unchanged':True,
                  'provider_keys_injected':False,'monthly_budget':0,'jev_enabled':False}
        (work/'result.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report),flush=True)
    finally:
        # Preserve recovered data. No down -v / prune / volume deletion.
        compose(compose_file,'stop','-t','60')
        print('Recovery containers stopped; volumes and private evidence retained:',work,flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['backup','restore','verify'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--name')
    parser.add_argument('--gateway-port',type=int,default=4400)
    parser.add_argument('--webui-port',type=int,default=4300)
    args=parser.parse_args()
    expected=(Path(os.environ['LOCALAPPDATA'])/'GatewayAI/recovery/.location').resolve().parent
    check(args.root.resolve()==expected.resolve() and args.root.is_dir(), 'Use the ACL-protected root through recovery.ps1')
    if args.action=='backup':
        backup(args.root)
    else:
        check(args.backup is not None and args.backup.resolve().parent==args.root.resolve(), 'Select a backup directly inside the protected recovery root')
        if args.action=='verify':
            validate_bundle(args.backup)
            print('PASS: backup hashes and archive safety')
        else:
            restore(args.root,args.backup,args.name,args.gateway_port,args.webui_port)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Never expose subprocess arguments, database rows, or upstream response bodies.
        print('FAILED:',str(error) if isinstance(error,RuntimeError) else type(error).__name__,flush=True)
        raise SystemExit(1)

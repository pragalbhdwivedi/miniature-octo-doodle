"""Cold backup and isolated same-VM restore drill for the zero-spend Linux core.

Retains backups and recovery volumes; never migrates live provider data.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

spec = importlib.util.spec_from_file_location('linux_core', Path(__file__).with_name('linux-core.py'))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
BASE = Path('/var/lib/gatewayai-recovery')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive(source, target):
    with tarfile.open(target, 'w:gz') as stream:
        for item in sorted(source.iterdir()):
            stream.add(item, arcname=item.name)
    target.chmod(0o600)


def unpack(source, destination):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Restore destination is occupied')
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tarfile.open(source) as stream:
        # Explicit data filter rejects device files and escaping links/paths.
        stream.extractall(destination, filter='data')


def volume_info(name, project):
    info = json.loads(core.run(['docker', 'volume', 'inspect', name]))[0]
    if info.get('Driver') != 'local' or info.get('Options') or info.get('Labels', {}).get('com.docker.compose.project') != project:
        raise ValueError('Volume ownership/driver mismatch')
    path = Path(info['Mountpoint'])
    if not path.is_absolute() or not path.is_dir() or path.is_symlink():
        raise ValueError('Unexpected volume path')
    return path


def tree_hashes(root):
    result = {}
    for path in root.rglob('*'):
        name = str(path.relative_to(root))
        if path.is_symlink():
            result[name] = ['link', os.readlink(path)]
        elif path.is_file():
            result[name] = ['file', digest(path)]
    return result


def backup(values):
    name = 'backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = BASE / name
    target.mkdir(mode=0o700)
    document = json.loads(core.compose(core.ROOT, values, 'config', '--format', 'json'))
    core.validate_compose(document, core.ROOT, values)
    ids = core.compose(core.ROOT, values, 'ps', '-aq').split()
    if len(ids) != 3:
        raise ValueError('Expected exactly three source containers')
    containers = json.loads(core.run(['docker', 'inspect', *ids]))
    for container in containers:
        service = container['Config']['Labels']['com.docker.compose.service']
        expected = document['services'][service]
        actual_env = dict(item.split('=', 1) for item in container['Config']['Env'])
        if container['State'].get('Health', {}).get('Status') != 'healthy' or container['Config']['Image'] != expected['image']:
            raise ValueError('Source is not healthy or image differs')
        if any(actual_env.get(k) != str(v) for k, v in expected['environment'].items()):
            raise ValueError('Running credentials/configuration differ from source')
    volumes = {key: volume_info(value['name'], core.PROJECT) for key, value in document['volumes'].items()}
    used = sum(p.stat().st_size for root in volumes.values() for p in root.rglob('*') if p.is_file() and not p.is_symlink())
    if shutil.disk_usage(BASE).free - used * 3 - 1024**3 < 15 * 1024**3:
        raise ValueError('Insufficient backup and restore reserve')
    started = time.monotonic()
    source_hashes = tree_hashes(core.REPO)
    try:
        core.compose(core.ROOT, values, 'stop', '--timeout', '60')
        stopped = json.loads(core.run(['docker', 'inspect', *ids]))
        if any(c['State']['Running'] or c['State']['ExitCode'] != 0 for c in stopped):
            raise ValueError('Unclean source shutdown')
        running = core.run(['docker', 'ps', '-q']).split()
        if running:
            others = json.loads(core.run(['docker', 'inspect', *running]))
            sources = {str(path) for path in volumes.values()}
            if any(m.get('Source') in sources for c in others for m in c['Mounts']):
                raise ValueError('Another container still mounts a source volume')
        manifest = {'schema': 1, 'volumes': {}, 'files': {}}
        for key, path in volumes.items():
            manifest['volumes'][key] = tree_hashes(path)
            archive(path, target / (key + '.tar.gz'))
        archive(core.ROOT, target / 'runtime.tar.gz')
        archive(core.REPO, target / 'source.tar.gz')
        if tree_hashes(core.REPO) != source_hashes:
            raise ValueError('Source changed during backup')
        for path in target.iterdir():
            manifest['files'][path.name] = digest(path)
        core.write_private(target / 'manifest.json', json.dumps(manifest, indent=2))
    finally:
        core.compose(core.ROOT, values, 'up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300')
    print(json.dumps({'backup': str(target), 'bytes': sum(p.stat().st_size for p in target.iterdir()),
                      'stop_backup_resume_seconds': round(time.monotonic() - started, 2)}))
    return target


def restore(target, values):
    if target.parent.resolve() != BASE or target.is_symlink():
        raise ValueError('Only local protected backup directories are accepted')
    manifest = json.loads(core.read_private(target / 'manifest.json'))
    if manifest.get('schema') != 1 or set(manifest['volumes']) != {'postgres-data', 'open-webui-data', 'policy-data'}:
        raise ValueError('Unexpected backup manifest')
    expected = {'source.tar.gz', 'runtime.tar.gz'} | {key + '.tar.gz' for key in manifest['volumes']}
    if set(manifest['files']) != expected:
        raise ValueError('Unexpected backup files')
    for name, checksum in manifest['files'].items():
        path = target / name
        if path.is_symlink() or digest(path) != checksum:
            raise ValueError('Backup checksum mismatch')
    work = BASE / ('restore-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    work.mkdir(mode=0o700)
    unpack(target / 'source.tar.gz', work / 'source')
    unpack(target / 'runtime.tar.gz', work / 'runtime')
    # Rebuild exclusively from archived source, credentials and configuration.
    core.REPO = work / 'source'
    core.ROOT = work / 'runtime'
    core.write_private(core.ROOT / 'compose.json', json.dumps(core.compose_override(core.ROOT)), replace=True)
    values = core.load(core.ROOT)
    project = 'gatewayai-drill-' + work.name.removeprefix('restore-').lower()
    document = json.loads(core.compose(core.ROOT, values, 'config', '--format', 'json'))
    core.validate_compose(document, core.ROOT, values)
    document['name'] = project
    for network, data in document['networks'].items():
        data.update(name=project + '_' + network, internal=True)
    for key, data in document['volumes'].items():
        name = project + '_' + key
        if core.run(['docker', 'volume', 'ls', '-q', '--filter', 'name=^' + name + '$']).strip():
            raise ValueError('Recovery volume already exists')
        core.run(['docker', 'volume', 'create', '--label', 'com.docker.compose.project=' + project,
                  '--label', 'com.docker.compose.volume=' + key, name])
        path = volume_info(name, project)
        unpack(target / (key + '.tar.gz'), path)
        if tree_hashes(path) != manifest['volumes'][key]:
            raise ValueError('Restored file contents differ')
        # tarfile data filtering deliberately ignores owner metadata; restore
        # original numeric owners after validating all paths remain in this volume.
        with tarfile.open(target / (key + '.tar.gz')) as stream:
            for member in stream:
                item = path / member.name
                if not item.resolve().is_relative_to(path.resolve()):
                    raise ValueError('Archive link escapes target')
                os.chown(item, member.uid, member.gid, follow_symlinks=False)
        data['name'] = name
    for service in document['services'].values():
        service.pop('ports', None)
        service['restart'] = 'no'
        for mount in service['volumes']:
            if mount['type'] == 'bind':
                original = Path(mount['source'])
                if original.is_relative_to(core.ROOT):
                    mount['source'] = str(work / 'runtime' / original.relative_to(core.ROOT))
                elif original.is_relative_to(core.REPO):
                    mount['source'] = str(work / 'source' / original.relative_to(core.REPO))
                else:
                    raise ValueError('Unexpected restore mount')
    config = work / 'compose.json'
    core.write_private(config, json.dumps(document))
    command = ['docker', 'compose', '-p', project, '-f', str(config)]
    started = time.monotonic()
    try:
        core.run(command + ['up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300'])
        expected = list(core.configuration(work / 'source')[1]['resolved_routes'])
        print(core.run(command + ['exec', '-T', 'open-webui', 'python', '-', json.dumps(expected)],
                       (work / 'source/scripts/test-recovery-runtime.py').read_text()).strip())
        code = "import sqlite3; c=sqlite3.connect('/app/backend/data/webui.db'); assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; print('PASS: restored WebUI SQLite integrity')"
        print(core.run(command + ['exec', '-T', 'open-webui', 'python', '-c', code]).strip())
        core.run(command + ['exec', '-T', 'postgres', 'pg_dump', '-U', values['POSTGRES_USER'], values['POSTGRES_DB']])
        print('PASS: restored PostgreSQL full dump read')
    finally:
        core.run(command + ['stop', '--timeout', '60'])
    print(json.dumps({'restore': str(work), 'project': project, 'seconds': round(time.monotonic() - started, 2),
                      'exact_files': True, 'recovery_containers_stopped': True, 'volumes_retained': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'drill'])
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('Approved root administrator required')
    core.host_guard()
    if not BASE.exists():
        BASE.mkdir(mode=0o700)
    core.safe_root(BASE)
    import fcntl
    with os.fdopen(os.open(core.ROOT / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        values = core.load(core.ROOT)
        target = backup(values)
        if args.action == 'drill':
            restore(target, values)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('Linux recovery failed (' + type(error).__name__ + '); private evidence and volumes retained.')

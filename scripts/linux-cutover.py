"""Administrator-only frozen Windows handoff to a verified Linux restore.

The operator must independently verify the Windows source remains stopped with
restart disabled. Once activated, rollback requires the current VM data/ledger;
the old Windows snapshot must never be restarted against the old allowance.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recovery


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load_module('linux_core', 'linux-core.py')
importer = load_module('linux_import', 'linux-import.py')


def command(work, *args):
    return core.run(['docker', 'compose', '-f', str(work/'compose.json'), *args])


def live_document(staged, original):
    result = json.loads(json.dumps(staged))
    # Keep restored volume names, internal UI/database networks and local binds.
    for service in result['services'].values():
        service['restart'] = 'unless-stopped'
        service.pop('ports', None)
    gateway = result['services']['litellm']
    gateway['environment'] = original['services']['litellm']['environment'].copy()
    if gateway['environment'].get('TYPESAFE_API_KEY'):
        raise ValueError('Jev must remain disabled')
    if gateway['environment']['GATEWAY_MONTHLY_BUDGET_USD'] != '100':
        raise ValueError('Expected the approved existing USD100 allowance')
    result['networks']['provider-egress'] = {'name': result['name']+'_provider-egress'}
    if isinstance(gateway['networks'], list):
        gateway['networks'].append('provider-egress')
    else:
        gateway['networks']['provider-egress'] = None
    return result


def verify_handoff(folder, checksum):
    handoff = json.loads(core.read_private(folder/'handoff.json'))
    if (handoff.get('backup_manifest_sha256') != checksum or recovery.sha(folder/'manifest.json') != checksum
            or handoff.get('source_project') != recovery.PROJECT
            or handoff.get('containers_stopped') is not True or handoff.get('restart_disabled') is not True):
        raise ValueError('Frozen source handoff does not match this backup')


def activate(work, folder, checksum):
    _, original = importer.protected_bundle(folder)
    verify_handoff(folder, checksum)
    result = json.loads(core.read_private(work/'result.json'))
    if not result.get('passed') or not result.get('budget_unchanged'):
        raise ValueError('An isolated restore must pass first')
    # Link the restore to the exact cold snapshot, not merely the same git commit.
    for logical in recovery.VOLUMES:
        if recovery.archive_index(work/(logical+'.tar')) != recovery.archive_index(folder/(logical+'.tar')):
            raise ValueError('Restored data is not the handoff snapshot')
    document = json.loads(core.read_private(work/'compose.json'))
    if document['name'] != result['project'] or (work/'activated.json').exists():
        raise ValueError('Unexpected/already activated restore')
    ids = command(work, 'ps', '-aq').split()
    if len(ids) != 3 or any(c['State']['Running'] for c in json.loads(core.run(['docker','inspect',*ids]))):
        raise ValueError('Expected three stopped validated restore containers')
    # Journal before enabling credentials. A partial activation is never a reason
    # to restart the old ledger. All recovery must use these preserved VM volumes.
    core.write_private(work/'activated.json', json.dumps({'source_manifest_sha256':checksum,
        'created_utc':datetime.now(timezone.utc).isoformat(), 'state':'activation_started'}))
    core.write_private(work/'compose.isolated.json', json.dumps(document))
    core.write_private(work/'compose.json', json.dumps(live_document(document, original)), replace=True)
    command(work, 'up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300')
    # Retain the fresh zero-spend core's volumes and secrets, but stop its containers.
    core.compose(core.ROOT, core.load(core.ROOT), 'stop', '--timeout', '60')
    core.install_loopback(document['name'])
    core.write_private(work/'activated.json', json.dumps({'source_manifest_sha256':checksum,
        'created_utc':datetime.now(timezone.utc).isoformat(), 'state':'active'}), replace=True)
    print('PASS: migrated core healthy; loopback proxy switched; old zero-spend core retained stopped')


def backup(work):
    """Cold live backup using the portable, independently restorable bundle format."""
    document = json.loads(core.read_private(work/'compose.json'))
    ids = command(work, 'ps', '-aq').split()
    containers = json.loads(core.run(['docker','inspect',*ids])) if ids else []
    if len(containers) != 3 or any(c['State'].get('Health',{}).get('Status') != 'healthy' for c in containers):
        raise ValueError('Expected three healthy live containers')
    images = {s['image']:json.loads(core.run(['docker','image','inspect',s['image']]))[0] for s in document['services'].values()}
    recovery.assert_running_config(document, containers, images)
    folder = importer.BASE/('backup-live-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    recovery.disk_guard(importer.BASE, 2*1024**3)
    folder.mkdir(mode=0o700)
    source = Path(json.loads(core.read_private(work/'origin.json'))['backup'])
    shutil.copy2(source/'.env',folder/'.env')
    shutil.copy2(source/'source.tar',folder/'source.tar')
    for name in ('gateway-config.json','policy.json'):
        shutil.copy2(work/name,folder/name)
    portable = json.loads(json.dumps(document))
    portable['name'] = recovery.PROJECT
    core.write_private(folder/'compose.json',json.dumps(portable))
    started=time.monotonic()
    try:
        command(work,'stop','--timeout','60')
        stopped=json.loads(core.run(['docker','inspect',*ids]))
        if any(c['State']['Running'] or c['State']['ExitCode'] != 0 for c in stopped):
            raise ValueError('Unclean source shutdown')
        for logical, data in document['volumes'].items():
            if core.run(['docker','ps','-q','--filter','volume='+data['name']]).strip():
                raise ValueError('Another writer mounts source data')
            recovery.helper(document['services']['postgres']['image'],
                [recovery.volume_mount(data['name']),recovery.bind_mount(folder)],
                '-c','tar -cpf /backup/'+logical+'.tar -C /volume .')
        manifest={'format':1,'created_utc':datetime.now(timezone.utc).isoformat(),
                  'git_commit':json.loads((source/'manifest.json').read_text())['git_commit'],
                  'source_bytes':sum(p.stat().st_size for p in folder.glob('*.tar')),
                  'files':{name:recovery.sha(folder/name) for name in sorted(recovery.FILES)}}
        core.write_private(folder/'manifest.json',json.dumps(manifest,indent=2))
        for p in folder.iterdir(): p.chmod(0o600)
        recovery.validate_bundle(folder)
    finally:
        command(work,'start','--wait','--wait-timeout','300')
        core.install_loopback(document['name'])
    print(json.dumps({'backup':str(folder),'stop_backup_resume_seconds':round(time.monotonic()-started,2)}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['activate','backup','loopback'])
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--handoff-sha256')
    args=parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise ValueError('Approved Linux administrator required')
    os.umask(0o077)
    core.host_guard()
    if args.work.is_symlink() or args.work.resolve().parent != importer.BASE:
        raise ValueError('Expected protected import work directory')
    core.safe_root(args.work)
    import fcntl
    with os.fdopen(os.open(importer.BASE/'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600),'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='activate':
            if not args.backup or not args.handoff_sha256: raise ValueError('Frozen backup/checksum required')
            activate(args.work,args.backup,args.handoff_sha256)
        elif args.action=='backup': backup(args.work)
        else: core.install_loopback(json.loads(core.read_private(args.work/'compose.json'))['name'])


if __name__=='__main__':
    try: main()
    except Exception as error:
        raise SystemExit('Linux cutover failed ('+type(error).__name__+'); retain all data and keep Windows frozen.')

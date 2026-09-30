"""Restore a trusted Windows backup on Linux, isolated and without spending.

This command never activates provider credentials or changes the live service.
Backups must be transferred into the protected import root by an administrator.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recovery

BASE = Path('/var/lib/gatewayai-import')


def protected_bundle(folder, base=BASE):
    if folder.is_symlink() or folder.resolve().parent != base.resolve():
        raise ValueError('Backup must be directly inside the protected import root')
    for directory in (base, folder):
        info = directory.stat()
        if directory.is_symlink() or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Import directories must be owner-only')
    for name in recovery.FILES | {'manifest.json'}:
        path = folder / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('Backup files must be regular owner-only files')
    return recovery.validate_bundle(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise ValueError('Run as the approved Linux administrator')
    os.umask(0o077)
    spec = importlib.util.spec_from_file_location('linux_core', Path(__file__).with_name('linux-core.py'))
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    core.host_guard()
    protected_bundle(args.backup)
    # Linux stores both the protected backup and Docker volumes on this host's
    # root filesystem. Windows-only Docker Desktop location discovery is unused.
    recovery.recovery_disk_guard = recovery.disk_guard
    import fcntl
    with os.fdopen(os.open(BASE / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recovery.restore(BASE, args.backup, args.name)
        core.write_private(BASE/args.name/'origin.json', json.dumps({'backup':str(args.backup),
            'manifest_sha256':recovery.sha(args.backup/'manifest.json')}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('Linux import failed (' + type(error).__name__ + '); private data retained.')

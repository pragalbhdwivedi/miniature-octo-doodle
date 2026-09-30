"""Immutable container helper. Repository commands never execute on the host."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile
import time

MAX_SOURCE = 32 * 1024 * 1024
MAX_ARTIFACT = 1024 * 1024


def relative(name):
    path = PurePosixPath(name)
    if (not name or len(name) > 240 or path.is_absolute() or '\\' in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or any(p in ('', '.', '..', '.git') for p in name.split('/'))):
        raise ValueError('Unsafe workspace path')
    return path


def source_files(archive):
    result = {}
    total = 0
    for member in archive.getmembers():
        name = member.name.rstrip('/')
        relative(name)
        if member.isdir():
            continue
        if not member.isfile() or name in result:
            raise ValueError('Only unique regular source files are supported')
        total += member.size
        if total > MAX_SOURCE or len(result) >= 10000:
            raise ValueError('Source size/count ceiling')
        result[name] = (archive.extractfile(member).read(), 0o755 if member.mode & 0o111 else 0o644)
    return result


def initialize():
    os.umask(0o077)
    with tarfile.open('/input/source.tar') as archive:
        for name, (data, mode) in source_files(archive).items():
            path = Path('/workspace') / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(mode)
    Path('/tmp/home').mkdir()
    job = json.loads(Path('/input/job.json').read_text())
    for args in (['init', '-b', job['branch']], ['config', 'user.name', 'GatewayAI Worker'],
                 ['config', 'user.email', 'worker@invalid'], ['config', 'core.hooksPath', '/dev/null'],
                 ['add', '-A'], ['commit', '-qm', 'Isolated source snapshot']):
        subprocess.run(['git', *args], check=True, stdout=subprocess.DEVNULL)
    Path('/tmp/ready').touch()
    while True:
        time.sleep(60)


def export():
    # Compare against immutable input, not worker-controlled Git history/config.
    with tarfile.open('/input/source.tar') as archive:
        original = source_files(archive)
    job = json.loads(Path('/input/job.json').read_text())
    allowed = set(job['write_paths'])
    current = {}
    total = 0
    for root, dirs, files in os.walk('/workspace', followlinks=False):
        if root == '/workspace':
            dirs[:] = [d for d in dirs if d != '.git']
        for name in dirs + files:
            path = Path(root) / name
            if path.is_symlink():
                raise ValueError('Workspace symlink rejected')
            if path.is_dir():
                continue
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Workspace special file rejected')
            total += info.st_size
            if total > MAX_SOURCE or len(current) >= 10000:
                raise ValueError('Workspace export ceiling')
            name = path.relative_to('/workspace').as_posix()
            relative(name)
            current[name] = (path.read_bytes(), 0o755 if info.st_mode & 0o111 else 0o644)
    changes = []
    size = 0
    for name in sorted(original.keys() | current.keys()):
        if original.get(name) == current.get(name):
            continue
        if name not in allowed:
            raise ValueError('Change outside authorized paths')
        value = current.get(name)
        data = value[0] if value else b''
        size += len(data)
        if size > MAX_ARTIFACT:
            raise ValueError('Artifact ceiling')
        changes.append({'path': name, 'before_sha256': hashlib.sha256(original[name][0]).hexdigest()
                        if name in original else None, 'content_base64': base64.b64encode(data).decode()
                        if value else None, 'mode': value[1] if value else None})
    print(json.dumps({'changes': changes}))


if __name__ == '__main__':
    try:
        if len(sys.argv) == 2 and sys.argv[1] == 'export':
            export()
        elif len(sys.argv) == 1:
            initialize()
        else:
            raise ValueError('Unsupported action')
    except Exception as error:
        raise SystemExit('Worker helper failed: ' + type(error).__name__)

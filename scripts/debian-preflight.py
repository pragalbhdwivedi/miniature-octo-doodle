"""Read-only Linux VM admission checks (Debian 12/13 or Ubuntu 24.04).

Filename retained for compatibility. Never installs or deploys services.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess

GIB = 1024 ** 3


def supported_os(facts):
    return facts.get('system') == 'Linux' and (
        (facts.get('os_id') == 'debian' and facts.get('os_version') in ('12', '13')) or
        (facts.get('os_id') == 'ubuntu' and facts.get('os_version') == '24.04'))


def command(argv):
    """Keep subprocess diagnostics private; failures must never echo configuration."""
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def inspect_local_engine():
    # Reject endpoint overrides before issuing any daemon request, even if the
    # current context happens to be local. A selected SSH/TCP context is rejected too.
    if any(os.environ.get(key) for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')):
        return {'engine_error': 'Remove Docker endpoint/TLS environment overrides before preflight.'}
    context = command(['docker', 'context', 'inspect'])
    try:
        endpoint = json.loads(context)[0]['Endpoints']['docker']['Host']
    except (TypeError, ValueError, KeyError, IndexError):
        return {'engine_error': 'Cannot read the selected Docker context.'}
    if not isinstance(endpoint, str) or not endpoint.startswith('unix:///'):
        return {'engine_error': 'Selected Docker endpoint is not a local Unix socket.'}
    raw = command(['docker', 'info', '--format', '{{json .}}'])
    try:
        info = json.loads(raw)
        root = Path(info['DockerRootDir'])
        if not root.is_absolute() or not root.is_dir():
            raise ValueError('unreadable Docker root')
        free = shutil.disk_usage(root).free / GIB
        containers = info['ContainersRunning']
        if type(containers) is not int:
            raise ValueError('invalid container count')
        return {
            'engine_linux': info['OSType'] == 'linux',
            'engine_desktop': 'docker desktop' in info['OperatingSystem'].lower(),
            'engine_version': info['ServerVersion'],
            'docker_free_gib': free,
            'running_containers': containers,
            'compose_version': command(['docker', 'compose', 'version', '--short']),
            'docker_enabled': command(['systemctl', 'is-enabled', 'docker']) == 'enabled',
            'docker_active': command(['systemctl', 'is-active', 'docker']) == 'active',
        }
    except (TypeError, ValueError, KeyError, OSError):
        return {'engine_error': 'Cannot inspect the local engine and its storage; no privilege changes attempted.'}


def collect(runtime_parent):
    facts = {'system': platform.system()}
    if facts['system'] != 'Linux':
        return facts
    try:
        release = platform.freedesktop_os_release()
        facts.update(os_id=release.get('ID'), os_version=release.get('VERSION_ID'))
    except OSError:
        return facts
    if not supported_os(facts):
        return facts
    facts['virtual_machine'] = bool(command(['systemd-detect-virt', '--vm']))
    facts['container'] = bool(command(['systemd-detect-virt', '--container']))
    facts['wsl'] = 'microsoft' in platform.release().lower()
    if not facts['virtual_machine'] or facts['container'] or facts['wsl']:
        return facts
    facts['cpu_count'] = os.cpu_count() or 0
    try:
        memory = next(line for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))
        facts['memory_gib'] = int(memory.split()[1]) * 1024 / GIB
        parent = Path(runtime_parent)
        facts['runtime_parent_valid'] = parent.is_absolute() and parent.is_dir() and not parent.is_symlink()
        if facts['runtime_parent_valid']:
            facts['runtime_free_gib'] = shutil.disk_usage(parent).free / GIB
    except (OSError, ValueError, StopIteration):
        pass
    facts.update(inspect_local_engine())
    ports = []
    for port in (3000, 4000):
        try:
            # Bind then immediately close; no listen socket or service is created.
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', port))
            ports.append(port)
        except OSError:
            pass
    facts['available_ports'] = ports
    return facts


def evaluate(facts):
    checks = []

    def check(name, passed):
        checks.append({'check': name, 'passed': bool(passed)})

    check('Debian 12/13 or Ubuntu 24.04 on Linux', supported_os(facts))
    check('Dedicated VM candidate, not WSL/container', facts.get('virtual_machine') and not facts.get('container', True) and not facts.get('wsl', True))
    # Suggested VM sizing: 4 vCPU / 8 GiB. Linux reports slightly less than
    # allocated RAM, so the admission floor is 7 GiB, not an exact 8 GiB.
    check('At least 4 vCPU and 7 GiB visible RAM', facts.get('cpu_count', 0) >= 4 and facts.get('memory_gib', 0) >= 7)
    check('Existing absolute runtime parent', facts.get('runtime_parent_valid'))
    for name in ('runtime', 'docker'):
        check(f'{name} storage: retain 15 GiB after 12 GiB core reserve', facts.get(f'{name}_free_gib', 0) - 12 >= 15)
    check('Local Linux Docker Engine, not Desktop', not facts.get('engine_error') and facts.get('engine_linux') and not facts.get('engine_desktop', True))
    check('Docker enabled and active under systemd', facts.get('docker_enabled') and facts.get('docker_active'))
    check('Compose plugin available', facts.get('compose_version'))
    check('Fresh target: no running containers', facts.get('running_containers') == 0)
    check('Loopback ports 3000 and 4000 available', set(facts.get('available_ports', [])) == {3000, 4000})
    warnings = [f'{name} storage would fall below the 25 GiB warning threshold after the reserve.'
                for name in ('runtime', 'docker') if 27 <= facts.get(f'{name}_free_gib', 0) < 37]
    return {'status': 'PASS' if all(row['passed'] for row in checks) else 'BLOCKED',
            'checks': checks, 'warnings': warnings,
            'scope': 'Read-only fresh-host admission only; not deployment, isolation, reboot or recovery acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-parent', default='/srv', help='Existing absolute parent for future private runtime files')
    args = parser.parse_args()
    facts = collect(args.runtime_parent)
    report = evaluate(facts)
    print(json.dumps({'facts': facts, **report}, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

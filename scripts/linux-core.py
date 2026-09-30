"""Operate the dedicated Linux zero-spend Compose core; no live migration switch."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core_configuration import configuration

REPO = Path(__file__).resolve().parent.parent
ROOT = Path('/etc/gatewayai')
PROJECT = 'gatewayai-linux'
SERVICES = {'postgres', 'litellm', 'open-webui'}
spec = importlib.util.spec_from_file_location('linux_preflight', REPO / 'scripts/debian-preflight.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def run(args, payload=None, env=None, timeout=600):
    result = subprocess.run(args, input=payload, text=True, capture_output=True,
                            encoding='utf-8', env=env, timeout=timeout)
    if result.returncode:
        # Resolved Compose, HTTP errors and container logs may contain secrets.
        raise RuntimeError('Command failed; output withheld: ' + args[0])
    return result.stdout


def safe_root(root):
    if not root.is_absolute() or root.resolve().is_relative_to(REPO):
        raise ValueError('Runtime must be an absolute private path outside the checkout')
    for path in (root, *root.parents):
        if path.is_symlink():
            raise ValueError('Runtime path may not contain symlinks')
    if root.exists():
        info = root.stat()
        if not root.is_dir() or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Runtime directory must be owned by the operator with mode 0700')


def read_private(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError('Runtime file ownership/type/mode differs from the private contract')
    return path.read_text(encoding='utf-8')


def write_private(path, text, replace=False):
    if path.is_symlink():
        raise ValueError('Refusing a symlink')
    if path.exists():
        if not replace:
            raise ValueError('Refusing to overwrite an existing runtime file')
        read_private(path)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def template():
    return dict(line.split('=', 1) for line in (REPO / '.env.example').read_text(encoding='utf-8').splitlines()
                if line and not line.startswith('#'))


def validate_values(values):
    defaults = template()
    if set(values) != set(defaults):
        raise ValueError('Unexpected environment keys')
    for key in ('POSTGRES_PASSWORD', 'LITELLM_SALT_KEY', 'WEBUI_SECRET_KEY', 'WEBUI_ADMIN_PASSWORD'):
        if not re.fullmatch(r'[a-f0-9]{64}', values[key]):
            raise ValueError('Invalid generated secret format')
    if not re.fullmatch(r'sk-[a-f0-9]{64}', values['LITELLM_MASTER_KEY']):
        raise ValueError('Invalid master key format')
    if values['WEBUI_GATEWAY_KEY'] and not re.fullmatch(r'sk-[A-Za-z0-9_-]+', values['WEBUI_GATEWAY_KEY']):
        raise ValueError('Invalid scoped key format')
    if any(values[k] for k in ('OPENAI_API_KEY', 'GEMINI_API_KEY', 'TYPESAFE_API_KEY')) or values['GATEWAY_MONTHLY_BUDGET_USD'] != '0':
        raise ValueError('This deployment only accepts blank provider keys and zero spending')
    editable = {'POSTGRES_PASSWORD', 'LITELLM_MASTER_KEY', 'LITELLM_SALT_KEY', 'WEBUI_SECRET_KEY', 'WEBUI_ADMIN_PASSWORD', 'WEBUI_GATEWAY_KEY', 'WEBUI_ADMIN_EMAIL'}
    if any(values[k] != defaults[k] for k in values if k not in editable):
        raise ValueError('Pinned template settings changed')
    if values['WEBUI_ADMIN_EMAIL'] != 'admin@gatewayai.local':
        raise ValueError('Unexpected administrator identity')


def environment_text(values):
    validate_values(values)
    return ''.join(k + '=' + v + '\n' for k, v in values.items())


def compose_override(root):
    return {'services': {'litellm': {'volumes': [
        {'type': 'bind', 'source': str(root / 'config.json'), 'target': '/app/config.yaml', 'read_only': True},
        {'type': 'bind', 'source': str(root / 'policy.json'), 'target': '/app/policy.json', 'read_only': True}]}},
        'networks': {'core': {'internal': True}}}


def initialize(root):
    safe_root(root)
    if root.exists():
        raise ValueError('Runtime already exists; refusing to replace secrets')
    root.mkdir(mode=0o700)
    values = template()
    for key in ('POSTGRES_PASSWORD', 'LITELLM_SALT_KEY', 'WEBUI_SECRET_KEY', 'WEBUI_ADMIN_PASSWORD'):
        values[key] = secrets.token_hex(32)
    values['LITELLM_MASTER_KEY'] = 'sk-' + secrets.token_hex(32)
    values['WEBUI_ADMIN_EMAIL'] = 'admin@gatewayai.local'
    write_private(root / 'runtime.env', environment_text(values))
    config, policy = configuration(REPO)
    for name, data in [('config.json', config), ('policy.json', policy), ('compose.json', compose_override(root))]:
        write_private(root / name, json.dumps(data, indent=2) + '\n')
    write_private(root / 'login.txt', 'WebUI administrator: ' + values['WEBUI_ADMIN_EMAIL'] +
                  '\nPassword: ' + values['WEBUI_ADMIN_PASSWORD'] + '\nVM URL: http://127.0.0.1:3000 (use an SSH tunnel)\n')


def load(root):
    safe_root(root)
    values = dict(line.split('=', 1) for line in read_private(root / 'runtime.env').splitlines())
    validate_values(values)
    config, policy = configuration(REPO)
    for name, expected in [('config.json', config), ('policy.json', policy), ('compose.json', compose_override(root))]:
        if json.loads(read_private(root / name)) != expected:
            raise ValueError('Runtime configuration differs from reviewed source')
    read_private(root / 'login.txt')
    return values


def compose_environment(values):
    # Shell interpolation overrides --env-file. Explicitly control every template
    # value and discard unrelated Compose toggles/profiles/override files.
    env = {k: v for k, v in os.environ.items() if not k.startswith('COMPOSE_') and k not in template()}
    env.update(values)
    return env


def compose(root, values, *args, payload=None):
    return run(['docker', 'compose', '--project-directory', str(REPO), '--project-name', PROJECT,
                '--env-file', str(root / 'runtime.env'), '-f', str(REPO / 'compose.yaml'),
                '-f', str(root / 'compose.json'), *args], payload, compose_environment(values))


def validate_compose(document, root, values):
    services = document['services']
    if set(services) != SERVICES or document['name'] != PROJECT:
        raise ValueError('Unexpected Compose project/services')
    if not all(document['networks'][name].get('internal') for name in ('database', 'core')):
        raise ValueError('Validation networks must be internal')
    for name, service in services.items():
        image_key = {'postgres': 'POSTGRES_IMAGE', 'litellm': 'LITELLM_IMAGE', 'open-webui': 'OPEN_WEBUI_IMAGE'}[name]
        if service['image'] != values[image_key] or '@sha256:' not in service['image']:
            raise ValueError('Image pin mismatch')
        if service.get('privileged') or service.get('network_mode') or service.get('pid') or service.get('cap_add'):
            raise ValueError('Unexpected host authority')
        ports = service.get('ports', [])
        wanted = {'postgres': [], 'litellm': [(4000, '4000')], 'open-webui': [(8080, '3000')]}[name]
        if [(p['target'], p['published']) for p in ports] != wanted or any(p.get('host_ip') != '127.0.0.1' for p in ports):
            raise ValueError('Unexpected published ports')
        allowed = {'litellm': {'/app/config.yaml': root / 'config.json', '/app/policy.json': root / 'policy.json',
                              '/app/policy-code/gateway': REPO / 'gateway'}}.get(name, {})
        binds = {v['target']: v for v in service['volumes'] if v['type'] == 'bind'}
        if set(binds) != set(allowed) or any(Path(binds[k]['source']) != v or not binds[k].get('read_only') for k, v in allowed.items()):
            raise ValueError('Unexpected bind mounts')
    gateway_env = services['litellm']['environment']
    if gateway_env['OPENAI_API_KEY'] or gateway_env['GEMINI_API_KEY'] or gateway_env['GATEWAY_MONTHLY_BUDGET_USD'] != '0' or 'TYPESAFE_API_KEY' in gateway_env:
        raise ValueError('Provider/spend boundary changed')
    ui_env = services['open-webui']['environment']
    if ui_env['OPENAI_API_KEY'] == values['LITELLM_MASTER_KEY'] or 'POSTGRES_PASSWORD' in ui_env:
        raise ValueError('WebUI received privileged credentials')


def host_guard(fresh=False):
    facts = preflight.collect(ROOT.parent)
    checks = preflight.evaluate(facts)['checks']
    ignored = set() if fresh else {'Fresh target: no running containers', 'Loopback ports 3000 and 4000 available'}
    failed = [c['check'] for c in checks if not c['passed'] and c['check'] not in ignored]
    if failed:
        raise RuntimeError('Preflight blocked: ' + '; '.join(failed))


def install_loopback(project=PROJECT):
    """Docker internal-only bridges omit published bindings; proxy on loopback.

    Socket activation uses the systemd-provided proxy, with an unprivileged
    dynamic user and no Docker socket. Refresh targets after container recreation.
    """
    executable = Path('/usr/lib/systemd/systemd-socket-proxyd')
    if not executable.is_file():
        raise RuntimeError('The systemd socket proxy is unavailable')
    units = Path('/etc/systemd/system')
    for service, host_port, target_port in [('open-webui', 3000, 8080), ('litellm', 4000, 4000)]:
        data = json.loads(run(['docker', 'inspect', project + '-' + service + '-1']))[0]
        address = data['NetworkSettings']['Networks'][project + '_core']['IPAddress']
        import ipaddress
        ipaddress.IPv4Address(address)
        name = 'gatewayai-' + service
        marker = '# Managed by GatewayAI linux-core.py\n'
        contents = {
            'socket': marker + '[Unit]\nDescription=GatewayAI loopback ' + service + '\n'
                      '[Socket]\nListenStream=127.0.0.1:' + str(host_port) + '\nNoDelay=true\n'
                      '[Install]\nWantedBy=sockets.target\n',
            'service': marker + '[Unit]\nDescription=GatewayAI loopback proxy ' + service + '\nRequires=docker.service\nAfter=docker.service\n'
                       '[Service]\nExecStart=' + str(executable) + ' ' + address + ':' + str(target_port) + '\n'
                       'DynamicUser=yes\nNoNewPrivileges=yes\nProtectSystem=strict\nProtectHome=yes\nPrivateTmp=yes\n'
                       'CapabilityBoundingSet=\nRestrictAddressFamilies=AF_INET AF_UNIX\n'}
        for suffix, content in contents.items():
            path = units / (name + '.' + suffix)
            if path.exists() and not path.read_text().startswith(marker):
                raise ValueError('Refusing to overwrite an unmanaged systemd unit')
            path.write_text(content)
            path.chmod(0o644)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'stop', name + '.service'])
        run(['systemctl', 'enable', '--now', name + '.socket'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'start', 'test', 'status', 'loopback'])
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('Run as the approved Linux deployment administrator using sudo')
    host_guard(fresh=args.action == 'init')
    if args.action == 'init':
        # Existing volumes can contain application state even if no containers run.
        if run(['docker', 'volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT]).strip():
            raise RuntimeError('Existing project volumes; refusing fresh credentials')
        initialize(ROOT)
        print('Private zero-spend configuration created; no secrets printed.')
        return
    import fcntl
    safe_root(ROOT)
    lock_fd = os.open(ROOT / '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        values = load(ROOT)
        document = json.loads(compose(ROOT, values, 'config', '--format', 'json'))
        validate_compose(document, ROOT, values)
        if args.action == 'start':
            compose(ROOT, values, 'pull', 'postgres', 'litellm', 'open-webui')
            host_guard()
            print('Pinned core images available; storage reserve passed.', flush=True)
            compose(ROOT, values, 'up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300', 'postgres')
            compose(ROOT, values, 'up', '-d', '--no-deps', '--force-recreate', '--pull', 'never', '--wait', '--wait-timeout', '300', 'litellm')
            if not values['WEBUI_GATEWAY_KEY']:
                code = """import json,os,urllib.request
body=json.dumps({'key_alias':'open-webui-linux','models':['all-proxy-models'],'allowed_routes':['/v1/models','/models','/v1/chat/completions','/chat/completions']}).encode()
req=urllib.request.Request('http://127.0.0.1:4000/key/generate',body,{'Content-Type':'application/json','Authorization':'Bearer '+os.environ['LITELLM_MASTER_KEY']})
with urllib.request.urlopen(req,timeout=30) as response: print(json.load(response)['key'])
"""
                values['WEBUI_GATEWAY_KEY'] = compose(ROOT, values, 'exec', '-T', 'litellm', 'python', '-', payload=code).strip()
                write_private(ROOT / 'runtime.env', environment_text(values), replace=True)
            compose(ROOT, values, 'up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '300', 'open-webui')
            install_loopback()
            print('Three core services healthy; provider keys blank, budget zero, Jev disabled.')
        elif args.action == 'loopback':
            install_loopback()
            print('Loopback socket proxies installed/refreshed; container networks remain internal.')
        elif args.action == 'test':
            import urllib.request
            for host in ('127.0.0.1', 'localhost'):
                for port, path in [(3000, '/health'), (4000, '/health/liveliness')]:
                    with urllib.request.urlopen(f'http://{host}:{port}{path}', timeout=10) as response:
                        assert response.status == 200
            print('PASS: host HTTP through localhost and 127.0.0.1')
            expected = list(configuration(REPO)[1]['resolved_routes'])
            print(compose(ROOT, values, 'exec', '-T', 'open-webui', 'python', '-', json.dumps(expected),
                          payload=(REPO / 'scripts/test-recovery-runtime.py').read_text(encoding='utf-8')).strip())
            print(compose(ROOT, values, 'exec', '-T', 'litellm', 'python', '-',
                          payload=(REPO / 'scripts/test-policy-runtime.py').read_text(encoding='utf-8')).strip())
            code = """import socket,sys
for host,port,allowed in [('postgres',5432,sys.argv[1]=='litellm'),('1.1.1.1',443,False)]:
    try:
        with socket.create_connection((host,port),timeout=3): connected=True
    except OSError: connected=False
    assert connected==allowed, 'Network isolation mismatch'
print('PASS: database/external TCP isolation for '+sys.argv[1])
"""
            for service in ('litellm', 'open-webui'):
                print(compose(ROOT, values, 'exec', '-T', service, 'python', '-', service, payload=code).strip())
        else:
            print(compose(ROOT, values, 'ps', '--format', 'table {{.Service}}\t{{.State}}\t{{.Health}}').strip())


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not expose subprocess arguments, environment, HTTP payload or config.
        sys.exit('Linux core operation failed (' + type(error).__name__ + '); credentials and existing data retained.')

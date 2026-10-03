#!/usr/bin/env python3
"""Mac-side preparation and foreground SSH transport for a GatewayAI test.

No gateway credential, host shell, cloud inference, or LAN Ollama listener.
The separately supplied connection.json contains public connection information.
"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import urllib.request

BASE_MODEL = 'qwen3.5:9b'
MODEL = 'mac-coder-9b:latest'
CONTEXT = 16384  # Compact gateway chat test; not a Codex tool-session setting.
GIB = 1024 ** 3
STATE = Path.home() / 'Library/Application Support/GatewayAI/mac-test'


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def output(args):
    return subprocess.check_output(args, text=True).strip()


def private_dir(path):
    if path.is_symlink():
        raise ValueError('Refusing symlink state directory')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def write_new(path, data):
    if path.exists() or path.is_symlink():
        if path.is_symlink() or path.read_text() != data:
            raise ValueError('Existing file differs: ' + path.name)
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(data)


def load_connection(path):
    cfg = json.loads(path.read_text())
    required = {'host', 'port', 'user', 'host_key', 'vpn_address'}
    if set(cfg) not in (required, required | {'vpn_type'}):
        raise ValueError('Unexpected connection fields')
    if cfg.get('vpn_type', 'WireGuard') not in ('WireGuard', 'OpenVPN'):
        raise ValueError('Unsupported VPN type')
    ip = ipaddress.ip_address(cfg['host'])
    if ip.version != 4 or not any(ip in ipaddress.ip_network(n) for n in
            ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('Gateway must have an approved private IPv4 address')
    if cfg['port'] != 22 or cfg['user'] != 'gatewayai-mac-test':
        raise ValueError('Only the restricted gateway test account is supported')
    auto = cfg.get('vpn_type') == 'OpenVPN' and cfg['vpn_address'] == 'auto'
    vpn = None if auto else ipaddress.ip_address(cfg['vpn_address'])
    if not auto and (vpn.version != 4 or not any(vpn in ipaddress.ip_network(n) for n in
            ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))):
        raise ValueError('Expected the assigned private VPN IPv4 address')
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', cfg['host_key']):
        raise ValueError('Expected a verified ED25519 host key')
    return cfg


def vpn_preflight(cfg):
    label = cfg.get('vpn_type', 'WireGuard')
    route = output(['/sbin/route', '-n', 'get', cfg['host']])
    match = re.search(r'^\s*interface:\s*((?:utun|tun)[0-9]+)\s*$', route, re.MULTILINE)
    if not match:
        raise ValueError('Gateway route must use ' + label + '; activate the tunnel and its target-subnet route')
    interface = match.group(1)
    details = output(['/sbin/ifconfig', interface])
    if cfg.get('vpn_type') == 'OpenVPN' and cfg['vpn_address'] == 'auto':
        addresses = re.findall(r'\binet\s+([0-9.]+)\s', details)
        if len(addresses) != 1 or not any(ipaddress.ip_address(addresses[0]) in ipaddress.ip_network(n)
                for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
            raise ValueError('VPN interface must have one unambiguous private IPv4 address')
        cfg['vpn_address'] = addresses[0]
    if not re.search(r'\binet\s+' + re.escape(cfg['vpn_address']) + r'\s', details):
        raise ValueError('Gateway route uses a different VPN interface/address; inspect VPN routes')
    print(label + ' route interface/address verified:', interface, cfg['vpn_address'], '->', cfg['host'])
    return interface


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected local API redirect')


def api(path):
    # Ignore proxy environment settings for local-only traffic.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open('http://127.0.0.1:11434' + path, timeout=5) as response:
        if response.geturl() != 'http://127.0.0.1:11434' + path:
            raise ValueError('Unexpected local API redirect')
        return json.load(response)


def ollama_preflight(min_free_gib=15):
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('Run this script on the Apple Silicon Mac, not a cloud VM')
    ram = int(output(['sysctl', '-n', 'hw.memsize']))
    if ram < 16 * GIB:
        raise ValueError('This 9B test requires at least 16 GiB unified memory')
    if not shutil.which('ollama'):
        raise ValueError('The existing Ollama CLI is not on PATH')
    settings = json.loads((Path.home() / '.ollama/server.json').read_text())
    if settings.get('disable_ollama_cloud') is not True:
        raise ValueError('First enable persistent Ollama cloud disable and restart it')
    pids = output(['lsof', '-nP', '-iTCP:11434', '-sTCP:LISTEN', '-t']).splitlines()
    if len(set(pids)) != 1:
        raise ValueError('Expected exactly one native Ollama listener')
    listeners = output(['lsof', '-nP', '-a', '-p', pids[0], '-iTCP:11434', '-sTCP:LISTEN'])
    if '127.0.0.1:11434' not in listeners or '*:11434' in listeners:
        raise ValueError('Ollama must listen on IPv4 loopback only')
    env_text = output(['ps', 'eww', '-p', pids[0], '-o', 'command='])
    expected = {'OLLAMA_NO_CLOUD': '1', 'OLLAMA_MAX_LOADED_MODELS': '1',
                'OLLAMA_NUM_PARALLEL': '1', 'OLLAMA_HOST': '127.0.0.1:11434'}
    for key, value in expected.items():
        if not re.search(r'(?:^|\s)' + key + '=' + re.escape(value) + r'(?:\s|$)', env_text):
            raise ValueError('Restart Ollama with the verified setting ' + key + '=' + value)
    store_env = subprocess.run(['launchctl', 'getenv', 'OLLAMA_MODELS'],
                               text=True, capture_output=True).stdout.strip()
    store = Path(store_env or str(Path.home() / '.ollama/models'))
    store = store.expanduser().resolve()
    if any(part.lower() in ('cloudstorage', 'mobile documents') or 'onedrive' in part.lower()
           for part in store.parts):
        raise ValueError('Model storage must remain outside cloud-synced folders')
    if not store.is_dir():
        raise ValueError('Model storage not found; inspect OLLAMA_MODELS before continuing')
    free = shutil.disk_usage(store).free
    if free < min_free_gib * GIB:
        raise ValueError('Need at least ' + str(min_free_gib) + ' GiB free for this action')
    version = api('/api/version')['version']
    print('Preflight:', json.dumps({'ram_gib': ram / GIB, 'free_gib': round(free / GIB, 2),
                                    'ollama': version, 'cloud_disabled': True}))
    return store


def prepare(cfg):
    private_dir(STATE)
    key = STATE / 'id_ed25519'
    if key.is_symlink() or key.with_suffix('.pub').is_symlink():
        raise ValueError('Refusing symlink key files')
    if not key.exists():
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C',
             'gatewayai-mac-test-forwarding-only', '-f', str(key)])
    if stat.S_IMODE(key.stat().st_mode) & 0o077:
        raise ValueError('Private key permissions must be 0600')
    public = output(['ssh-keygen', '-y', '-f', str(key)])
    write_new(STATE / 'known_hosts', cfg['host'] + ' ' + cfg['host_key'] + '\n')
    print('PUBLIC KEY FOR GATEWAY ENROLLMENT (safe to share):\n' + public)
    print('Private key remains in macOS Application Support; do not upload it.')
    vpn_preflight(cfg)
    store = ollama_preflight(min_free_gib=25)
    names = {m['name'] for m in api('/api/tags')['models']}
    if BASE_MODEL not in names:
        run(['ollama', 'pull', BASE_MODEL])
    if shutil.disk_usage(store).free < 15 * GIB:
        raise ValueError('Storage below 15 GiB floor; stop without loading the model')
    modelfile = STATE / 'Modelfile.9b'
    write_new(modelfile, 'FROM ' + BASE_MODEL + '\nPARAMETER num_ctx ' + str(CONTEXT) + '\n')
    if MODEL not in names:
        run(['ollama', 'create', MODEL, '-f', str(modelfile)])
    # No inference here: free disk does not establish 9B runtime suitability.
    tags = api('/api/tags')['models']
    model = next(m for m in tags if m['name'] == MODEL)
    manifest = {'model': MODEL, 'digest': model['digest'], 'context_requested': CONTEXT,
                'inference_tested': False}
    report = STATE / ('prepared-' + hashlib.sha256(model['digest'].encode()).hexdigest()[:12] + '.json')
    write_new(report, json.dumps(manifest, indent=2) + '\n')
    print('Model prepared. Gateway enrollment and end-to-end testing remain pending.')


def ssh_args(cfg):
    key, pins = STATE / 'id_ed25519', STATE / 'known_hosts'
    if not key.is_file() or not pins.is_file() or key.is_symlink() or pins.is_symlink():
        raise ValueError('Run prepare first')
    if pins.read_text() != cfg['host'] + ' ' + cfg['host_key'] + '\n':
        raise ValueError('Host pin does not match the supplied connection record')
    return ['ssh', '-F', '/dev/null', '-i', str(key), '-o', 'IdentitiesOnly=yes',
            '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile="' + str(pins).replace('\\', '\\\\').replace('"', '\\"') + '"',
            '-o', 'GlobalKnownHostsFile=/dev/null',
            '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=15',
            '-o', 'ServerAliveCountMax=3', '-o', 'ExitOnForwardFailure=yes',
            '-o', 'ForwardAgent=no', '-T', cfg['user'] + '@' + cfg['host']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'link', 'test', 'public-key'))
    parser.add_argument('--connection', type=Path, default=Path(__file__).with_name('connection.json'))
    args = parser.parse_args()
    if platform.system() != 'Darwin':
        raise ValueError('This must execute on the Mac, not in Codex Cloud')
    cfg = load_connection(args.connection)
    if args.action == 'prepare':
        prepare(cfg)
    elif args.action == 'public-key':
        print(output(['ssh-keygen', '-y', '-f', str(STATE / 'id_ed25519')]))
    elif args.action == 'link':
        vpn_preflight(cfg)
        ollama_preflight()
        with socket.create_connection((cfg['host'], cfg['port']), timeout=5):
            pass
        base = ssh_args(cfg)
        print('Keep this process running. Ctrl+C closes only this Mac tunnel.')
        # Separate from the existing Windows model tunnel on 11435.
        os.execvp('ssh', base[:-1] + ['-b', cfg['vpn_address'], '-N', '-R',
                  '127.0.0.1:11436:127.0.0.1:11434', base[-1]])
    else:
        vpn_preflight(cfg)
        # Forced gateway command performs only a fixed synthetic inference/test.
        base = ssh_args(cfg)
        run(base[:-1] + ['-b', cfg['vpn_address'], base[-1], 'mac-gateway-test'])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print('STOP:', str(exc), file=sys.stderr)
        sys.exit(1)

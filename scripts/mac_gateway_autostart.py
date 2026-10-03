#!/usr/bin/env python3
"""Install a per-user Mac gateway tunnel service; no root or model downloads."""
import argparse
import importlib.util
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import plistlib
import shutil
import signal
import subprocess
import sys
import time

LABEL = 'org.gatewayai.mac-tunnel'
STATE = Path.home() / 'Library/Application Support/GatewayAI/mac-test'
RUNTIME = STATE / 'startup'
PLIST = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
SETTINGS = {'OLLAMA_HOST': '127.0.0.1:11434', 'OLLAMA_NO_CLOUD': '1',
            'OLLAMA_CONTEXT_LENGTH': '8192', 'OLLAMA_MAX_LOADED_MODELS': '1',
            'OLLAMA_NUM_PARALLEL': '1'}


def job(runtime, python, search_path):
    return {'Label': LABEL, 'ProgramArguments': [str(python), '-u',
            str(runtime / 'mac_gateway_autostart.py'), 'run'],
            'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 30,
            'ProcessType': 'Background', 'WorkingDirectory': str(runtime),
            'EnvironmentVariables': {'PATH': search_path, 'PYTHONUNBUFFERED': '1'}}


def helper(path):
    spec = importlib.util.spec_from_file_location('mac_gateway_setup', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_owned(path, data):
    if path.is_symlink():
        raise ValueError('Refusing symlink: ' + str(path))
    if path.exists() and path.stat().st_uid != os.getuid():
        raise ValueError('File is not owned by this user: ' + str(path))
    temp = path.with_name(path.name + '.new')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    os.replace(temp, path)


def target():
    return 'gui/' + str(os.getuid()) + '/' + LABEL


def stop():
    found = subprocess.run(['launchctl', 'print', target()], capture_output=True)
    if found.returncode == 0:
        subprocess.run(['launchctl', 'bootout', target()], check=True)


def configure_openvpn(binary, backup):
    def settings():
        return json.loads(subprocess.check_output([str(binary), '--list-settings'], text=True))
    before = settings()
    names = ('launch-at-startup', 'connect-on-launch')
    if not isinstance(before, dict) or any(name not in before for name in names):
        return False  # Different client/version: use its supported native settings.
    if not backup.exists():
        write_owned(backup, json.dumps({name: before[name] for name in names}).encode())
    for name in names:
        if str(before[name]).lower() != 'true':
            subprocess.run([str(binary), '--set-setting=' + name, '--value=true'],
                           check=True, capture_output=True)
    after = settings()
    if not all(str(after.get(name)).lower() == 'true' for name in names):
        raise ValueError('OpenVPN startup settings did not persist; inspect the native client')
    return True


def install(connection):
    source = Path(__file__).resolve().parent
    mod = helper(source / 'mac_gateway_setup.py')
    cfg = mod.load_connection(connection)
    if cfg.get('vpn_type') != 'OpenVPN' or cfg['vpn_address'] != 'auto':
        raise ValueError('Use the OpenVPN connection record with vpn_address=auto')
    mod.ssh_args(cfg)  # Existing enrolled key and pinned host only; no new key.
    mod.ollama_preflight()
    python = Path(sys.executable).resolve()
    ollama = shutil.which('ollama')
    if not ollama:
        raise ValueError('Existing Ollama is missing from PATH')
    for directory in (STATE, RUNTIME):
        mod.private_dir(directory)
    vpn_ready = False
    for app in (Path('/Applications/OpenVPN Connect/OpenVPN Connect.app'),
                Path('/Applications/OpenVPN Connect.app')):
        binary = app / 'Contents/MacOS/OpenVPN Connect'
        if binary.is_file():
            vpn_ready = configure_openvpn(binary, RUNTIME / 'openvpn-settings-before.json')
            break
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    if PLIST.is_symlink():
        raise ValueError('Refusing symlink LaunchAgent')
    if PLIST.exists():
        old = plistlib.loads(PLIST.read_bytes())
        if old.get('Label') != LABEL or old.get('ProgramArguments', [])[2:3] != [str(RUNTIME / 'mac_gateway_autostart.py')]:
            raise ValueError('Existing LaunchAgent is not ours; inspect it first')
        backup = RUNTIME / ('previous-' + str(time.time_ns()) + '.plist')
        write_owned(backup, PLIST.read_bytes())
    stop()
    for name in ('mac_gateway_setup.py', 'mac_gateway_autostart.py'):
        write_owned(RUNTIME / name, (source / name).read_bytes())
    write_owned(RUNTIME / 'connection.json', json.dumps(cfg, indent=2).encode())
    search_path = ':'.join(dict.fromkeys([str(python.parent), str(Path(ollama).parent),
                                        '/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin']))
    write_owned(PLIST, plistlib.dumps(job(RUNTIME, python, search_path)))
    subprocess.run(['plutil', '-lint', str(PLIST)], check=True)
    subprocess.run(['launchctl', 'enable', target()], check=True)
    subprocess.run(['launchctl', 'bootstrap', 'gui/' + str(os.getuid()), str(PLIST)], check=True)
    subprocess.run(['launchctl', 'print', target()], check=True)
    print('OpenVPN native startup settings verified:', vpn_ready)
    if not vpn_ready:
        print('Use the installed VPN client settings to enable launch and reconnect after login.')
    print('Installed at login; connection and actual restart acceptance still require verification.')
    print('Log:', RUNTIME / 'tunnel.log')


def run():
    logger = logging.getLogger('gatewayai-tunnel')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(RUNTIME / 'tunnel.log', maxBytes=1024 * 1024, backupCount=2)
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(handler)
    child = None
    ending = False

    def terminate(signum, frame):
        nonlocal ending
        ending = True
        if child and child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    mod = helper(RUNTIME / 'mac_gateway_setup.py')
    for key, value in SETTINGS.items():
        subprocess.run(['launchctl', 'setenv', key, value], check=True)
    logger.info('Login service running; VPN and strict Ollama checks are required.')
    while not ending:
        try:
            try:
                mod.api('/api/version')
            except (OSError, ValueError):
                subprocess.run(['open', '-g', '-a', 'Ollama'], check=True, capture_output=True)
            child = subprocess.Popen([sys.executable, '-u', str(RUNTIME / 'mac_gateway_setup.py'),
                                      'link', '--connection', str(RUNTIME / 'connection.json')],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output, _ = child.communicate()
            logger.info('Tunnel process exited (%s): %s', child.returncode, output[-3000:].strip())
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            logger.info('Waiting for dependencies: %s', str(exc)[:500])
        child = None
        for _ in range(30):
            if ending:
                break
            time.sleep(1)
    logger.info('Login service stopped.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'run', 'status', 'remove'))
    parser.add_argument('--connection', type=Path, default=Path(__file__).with_name('connection.json'))
    args = parser.parse_args()
    if platform.system() != 'Darwin' or os.getuid() == 0:
        raise ValueError('Run as the signed-in Mac user, without sudo')
    if args.action == 'install':
        install(args.connection)
    elif args.action == 'run':
        run()
    elif args.action == 'status':
        subprocess.run(['launchctl', 'print', target()], check=True)
    else:
        if PLIST.is_symlink():
            raise ValueError('Refusing symlink LaunchAgent')
        if PLIST.exists() and plistlib.loads(PLIST.read_bytes()).get('Label') != LABEL:
            raise ValueError('LaunchAgent owner mismatch')
        stop()
        PLIST.unlink(missing_ok=True)
        print('Removed login job; SSH key, models, runtime and evidence preserved.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit('STOP: ' + str(exc)) from None

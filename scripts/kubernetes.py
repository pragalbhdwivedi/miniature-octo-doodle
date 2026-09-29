"""Scoped, zero-spend local Kubernetes validation deployment. Never reads .env."""
import argparse
import json
import secrets
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
NAMESPACE = 'gatewayai'


def run(args, payload=None):
    result = subprocess.run(args, input=payload, text=True, capture_output=True, encoding='utf-8', timeout=600)
    if result.returncode:
        # kubectl errors can include submitted Secrets and credentials.
        raise RuntimeError('Command failed; output withheld to protect local credentials: ' + args[0])
    return result.stdout


def configuration():
    """Advertise configured template routes, with no usable provider credentials."""
    values = dict(line.split('=', 1) for line in (REPO / '.env.example').read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith('#'))
    policy = json.loads((REPO / 'config/policy/policy.json').read_text(encoding="utf-8"))
    if policy['decision_plane'].get('mode') != 'deterministic' or policy['decision_plane'].get('jev_enabled') is not False:
        raise ValueError('Jev must remain disabled')
    providers = {p: {'alias': values[p + '_ALIAS'], 'model': values[p + '_MODEL']}
                 for p in ('OPENAI', 'GEMINI')}
    resolved = {v['alias']: [v] for v in providers.values()}
    resolved.update({name: [providers[p] for p in order] for name, order in policy['routes'].items()})
    policy['resolved_routes'] = resolved
    config = {
        'general_settings': {'master_key': 'os.environ/LITELLM_MASTER_KEY', 'database_url': 'os.environ/DATABASE_URL', 'disable_spend_logs': True},
        'litellm_settings': {'telemetry': False, 'set_verbose': False, 'turn_off_message_logging': True, 'callbacks': ['gateway.callbacks.proxy_handler_instance']},
        'router_settings': {'num_retries': 0, 'max_fallbacks': 1, 'timeout': 60, 'disable_cooldowns': True, 'fallbacks': [], 'context_window_fallbacks': [], 'content_policy_fallbacks': []}}
    config['model_list'] = [{'model_name': name, 'litellm_params': {'model': candidates[0]['model'],
                            'api_key': 'os.environ/' + candidates[0]['model'].split('/')[0].upper() + '_API_KEY'}}
                            for name, candidates in resolved.items()]
    return config, policy


def resource(kind, name, data):
    return {'apiVersion': 'v1', 'kind': kind, 'metadata': {'name': name, 'namespace': NAMESPACE},
            'stringData' if kind == 'Secret' else 'data': data}


def render(credentials):
    items = yaml.safe_load((REPO / 'deploy/k8s/base/core.yaml').read_text(encoding="utf-8"))['items']
    config, policy = configuration()
    items += [resource('ConfigMap', 'gateway-config', {'config.yaml': json.dumps(config), 'policy.json': json.dumps(policy)}),
              resource('ConfigMap', 'gateway-code', {p.name: p.read_text(encoding="utf-8") for p in sorted((REPO / 'gateway').glob('*.py'))})]
    for name, data in credentials.items():
        items.append(resource('Secret', name, data))
    items.append(yaml.safe_load((REPO / 'deploy/k8s/overlays/local/ingress.yaml').read_text(encoding="utf-8")))
    for item in items:
        if item['kind'] == 'PersistentVolumeClaim':
            item['spec']['storageClassName'] = 'local-path'
    return {'apiVersion': 'v1', 'kind': 'List', 'items': items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['deploy', 'test'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    kubeconfig = root / 'kubeconfig.yaml'
    cfg = yaml.safe_load(kubeconfig.read_text(encoding="utf-8"))
    if cfg['current-context'] != 'k3d-gatewayai' or len(cfg['clusters']) != 1 or cfg['clusters'][0]['cluster']['server'] != 'https://127.0.0.1:6550':
        raise ValueError('Refusing a kubeconfig outside the dedicated local cluster')
    base = ['kubectl', '--kubeconfig', str(kubeconfig), '--context', 'k3d-gatewayai', '--namespace', NAMESPACE]

    def kubectl(*cmd, payload=None):
        return run(base + list(cmd), payload)

    def apply(document):
        kubectl('apply', '-f', '-', payload=json.dumps(document))

    def execute(deployment, code, *argv):
        return kubectl('exec', '-i', 'deployment/' + deployment, '--', 'python', '-', *argv, payload=code)

    credentials_path = root / 'credentials.json'
    if args.action == 'deploy':
        existing = json.loads(kubectl('get', 'namespace', NAMESPACE, '--ignore-not-found', '-o', 'json') or '{}')
        if not credentials_path.exists():
            if existing:
                raise ValueError('Existing namespace without local credentials; refusing to replace secrets')
            pg = secrets.token_hex(32)
            credentials = {
                'postgres-credentials': {'POSTGRES_USER': 'litellm', 'POSTGRES_DB': 'litellm', 'POSTGRES_PASSWORD': pg},
                'litellm-credentials': {'DATABASE_URL': 'postgresql://litellm:' + pg + '@postgres:5432/litellm', 'LITELLM_MASTER_KEY': 'sk-' + secrets.token_hex(32), 'LITELLM_SALT_KEY': secrets.token_hex(32)},
                'open-webui-credentials': {'OPENAI_API_KEY': 'unprovisioned', 'WEBUI_SECRET_KEY': secrets.token_hex(32), 'WEBUI_ADMIN_EMAIL': 'admin@gatewayai.local', 'WEBUI_ADMIN_PASSWORD': secrets.token_hex(32)}}
            credentials_path.write_text(json.dumps(credentials), encoding='utf-8')
        credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
        document = render(credentials)
        apply(document['items'][0])  # Namespace must exist for server-side validation.
        kubectl('apply', '--dry-run=server', '-f', '-', payload=json.dumps(document))
        apply(document)
        for name in ('postgres', 'litellm'):
            kubectl('rollout', 'status', 'deployment/' + name, '--timeout=300s')
            print('Ready: ' + name, flush=True)
        if credentials['open-webui-credentials']['OPENAI_API_KEY'] == 'unprovisioned':
            code = """import json,os,urllib.request
body=json.dumps({'key_alias':'open-webui-kubernetes','models':['all-proxy-models'],'allowed_routes':['/v1/models','/models','/v1/chat/completions','/chat/completions']}).encode()
req=urllib.request.Request('http://127.0.0.1:4000/key/generate',body,{'Content-Type':'application/json','Authorization':'Bearer '+os.environ['LITELLM_MASTER_KEY']})
with urllib.request.urlopen(req,timeout=30) as response: print(json.load(response)['key'])
"""
            key = execute('litellm', code).strip()
            if not key.startswith('sk-') or any(c.isspace() for c in key):
                raise ValueError('Invalid scoped key')
            credentials['open-webui-credentials']['OPENAI_API_KEY'] = key
            credentials_path.write_text(json.dumps(credentials), encoding='utf-8')
            apply(resource('Secret', 'open-webui-credentials', credentials['open-webui-credentials']))
        # Restart on explicit deployment so updated ConfigMap/Secret data takes effect.
        for name in ('litellm', 'open-webui'):
            kubectl('rollout', 'restart', 'deployment/' + name)
            kubectl('rollout', 'status', 'deployment/' + name, '--timeout=300s')
        print('Core deployed with fresh data, zero budget, blank provider keys and Jev disabled.', flush=True)
    else:
        expected = list(configuration()[1]['resolved_routes'])
        print(execute('open-webui', (REPO / 'scripts/test-recovery-runtime.py').read_text(encoding="utf-8"), json.dumps(expected)).strip())
        credentials = json.loads(credentials_path.read_text(encoding="utf-8"))['open-webui-credentials']
        for host in ('127.0.0.1', 'localhost'):
            url = 'http://' + host + ':3080'
            with urllib.request.urlopen(url + '/health', timeout=15) as response:
                assert response.status == 200
            body = json.dumps({'email': credentials['WEBUI_ADMIN_EMAIL'], 'password': credentials['WEBUI_ADMIN_PASSWORD']}).encode()
            req = urllib.request.Request(url + '/api/v1/auths/signin', body, {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as response:
                login = json.load(response)
            assert login['role'] == 'admin'
            req = urllib.request.Request(url + '/api/models', headers={'Authorization': 'Bearer ' + login['token']})
            with urllib.request.urlopen(req, timeout=30) as response:
                assert sorted(x['id'] for x in json.load(response)['data']) == sorted(expected)
            print('Ingress HTTP, admin login and model discovery passed: ' + host, flush=True)
        network_probe = """import socket,sys
for host,port,allowed in [('postgres',5432,sys.argv[1]=='litellm'),('1.1.1.1',443,False)]:
    try:
        with socket.create_connection((host,port),timeout=3): connected=True
    except (TimeoutError,OSError): connected=False
    assert connected == allowed, 'NetworkPolicy connection mismatch'
print('PASS: PostgreSQL isolation and external TCP egress denial for '+sys.argv[1])
"""
        for name in ('litellm', 'open-webui'):
            print(execute(name, network_probe, name).strip(), flush=True)
        print(execute('litellm', (REPO / 'scripts/test-policy-runtime.py').read_text(encoding="utf-8")).strip())
        print('Kubernetes internal HTTP and synthetic policy suite passed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not print subprocess output, manifests or credential-bearing requests.
        sys.exit('Kubernetes operation failed (' + type(exc).__name__ + '); credentials and existing data preserved.')

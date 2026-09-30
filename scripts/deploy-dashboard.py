"""Deploy the static directory into an existing local NPM instance (administrator run).

No package/image installation. Requires the existing admin.json, wildcard
certificate and /data bind. Run on the ingress VM, never inside an application.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--services', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path('/etc/gatewayai-ingress'))
    parser.add_argument('--state', type=Path, default=Path('/var/lib/gatewayai-ingress'))
    parser.add_argument('--container', default='gatewayai-ingress-npm-1')
    args = parser.parse_args()
    os.umask(0o077)
    if shutil.disk_usage(args.state).free < 15 * 1024**3:
        raise SystemExit('Critical storage reserve reached; no change made.')
    services = json.loads(args.services.read_text())
    from urllib.parse import urlsplit
    assert isinstance(services.get('services'), list)
    for service in services['services']:
        assert isinstance(service.get('name'), str) and service['name']
        if service.get('url'):
            url = urlsplit(service['url'])
            assert url.scheme in ('https', 'http') and url.hostname and not url.username and not url.password
    credentials = json.loads((args.config / 'admin.json').read_text())
    token = None

    def api(path, payload=None, method=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request('http://127.0.0.1:81/api' + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    token = api('/tokens', {'identity': credentials['email'], 'secret': credentials['password']})['token']
    certificate = next(c for c in api('/nginx/certificates') if c['nice_name'] == 'AADI internal wildcard')
    hosts = api('/nginx/proxy-hosts')
    existing = next((h for h in hosts if h['domain_names'] == ['dash.aadi.dgoi.local']), None)
    target = args.state / 'data/dashboard'
    backup = args.config / ('dashboard-before-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(mode=0o700)
    (backup / 'proxy-host.json').write_text(json.dumps(existing, indent=2))
    if target.exists():
        shutil.copytree(target, backup / 'dashboard')
    target.mkdir(exist_ok=True, mode=0o755)
    for filename in ('index.html', 'style.css', 'app.js'):
        shutil.copyfile(args.source / filename, target / filename)
        (target / filename).chmod(0o644)
    (target / 'services.json').write_text(json.dumps(services, indent=2) + '\n')
    (target / 'services.json').chmod(0o644)
    advanced = '''location / {
  root /data/dashboard;
  index index.html;
  try_files $uri $uri/ =404;
  limit_except GET { deny all; }
  add_header X-Content-Type-Options nosniff always;
  add_header Referrer-Policy no-referrer always;
  add_header X-Frame-Options DENY always;
  add_header Cache-Control "no-store" always;
  add_header Content-Security-Policy "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'" always;
}
location ~ /\\. { deny all; }
'''
    payload = {'domain_names': ['dash.aadi.dgoi.local'], 'forward_scheme': 'http',
        'forward_host': '127.0.0.1', 'forward_port': 80, 'certificate_id': certificate['id'],
        'ssl_forced': False, 'hsts_enabled': False, 'hsts_subdomains': False,
        'http2_support': True, 'block_exploits': True, 'caching_enabled': False,
        'allow_websocket_upgrade': False, 'access_list_id': 0, 'advanced_config': advanced, 'locations': []}
    result = api('/nginx/proxy-hosts' + ('/' + str(existing['id']) if existing else ''), payload,
                 'PUT' if existing else 'POST')
    subprocess.run(['docker', 'exec', args.container, 'nginx', '-t'], check=True)
    probe = subprocess.check_output(['docker', 'exec', args.container, 'curl', '-fsS',
        '-H', 'Host: dash.aadi.dgoi.local', 'http://127.0.0.1/'])
    assert probe == (target / 'index.html').read_bytes(), 'Dashboard response differs from deployed source'
    print(json.dumps({'hostname': payload['domain_names'][0], 'proxy_host_id': result['id'],
                      'backup': str(backup), 'services': len(services['services']),
                      'free_gib': round(shutil.disk_usage(args.state).free / 1024**3, 2)}))


if __name__ == '__main__':
    main()

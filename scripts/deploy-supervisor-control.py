"""Administrator deployment into existing ingress/controller; no image downloads."""
import argparse
from datetime import datetime,timezone
import json
import ipaddress
from pathlib import Path
import os
import shutil
import subprocess
import urllib.request


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--hostname',default='control.aadi.dgoi.local')
    parser.add_argument('--networks',type=Path,required=True,help='Protected JSON list of admitted management, development and VPN CIDRs')
    args=parser.parse_args()
    if args.hostname!='control.aadi.dgoi.local':raise ValueError('Only the approved control hostname is deployable')
    networks=[str(ipaddress.ip_network(x)) for x in json.loads(args.networks.read_text())]
    if not networks or any(not ipaddress.ip_network(x).is_private or ipaddress.ip_network(x).prefixlen < 16 for x in networks):
        raise ValueError('Explicit narrow private network allowlist required')
    os.umask(0o077)
    root=Path('/opt/gatewayai-pilot');config=Path('/etc/gatewayai-controller')
    backup=config/('supervision-before-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));backup.mkdir()
    for path in (root/'scripts',root/'workflows'):
        if path.exists():shutil.copytree(path,backup/path.name)
    if (config/'supervision.json').exists():shutil.copy2(config/'supervision.json',backup/'supervision.json')
    for unit in ('gatewayai-supervisor-control.service','gatewayai-supervisor-edge.socket','gatewayai-supervisor-edge.service'):
        path=Path('/etc/systemd/system')/unit
        if path.exists():shutil.copy2(path,backup/unit)
    for path in (args.source/'scripts').glob('*.py'):shutil.copy2(path,root/'scripts'/path.name)
    shutil.copytree(args.source/'workflows',root/'workflows',dirs_exist_ok=True)
    inventory={'hostname':args.hostname,'port':8769,'assets':str(root/'workflows'),
        'dispatch_config':str(config/'dispatch.json'),
        'allowed_networks':networks}
    (config/'supervision.json').write_text(json.dumps(inventory,indent=2));(config/'supervision.json').chmod(0o600)
    edge=json.loads(subprocess.check_output(['docker','network','inspect','gatewayai-ingress_edge']))[0]['IPAM']['Config'][0]['Gateway']
    units={
      'gatewayai-supervisor-control.service':f'''[Unit]
Description=AADI internal supervisor task controls
After=docker.service network-online.target
[Service]
ExecStart=/usr/bin/python3 {root}/scripts/supervisor_http.py --config {config}/supervision.json
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
UMask=0077
[Install]
WantedBy=multi-user.target
''',
      'gatewayai-supervisor-edge.socket':f'''[Unit]
Description=Internal ingress socket for supervisor controls
After=docker.service
Requires=docker.service
[Socket]
ListenStream={edge}:18769
FreeBind=true
NoDelay=true
[Install]
WantedBy=sockets.target
''',
      'gatewayai-supervisor-edge.service':'''[Unit]
Description=Supervisor loopback proxy
[Service]
ExecStart=/usr/lib/systemd/systemd-socket-proxyd 127.0.0.1:8769
DynamicUser=yes
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
'''}
    for name,body in units.items():
        p=Path('/etc/systemd/system')/name;p.write_text(body);p.chmod(0o644)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','gatewayai-supervisor-control','gatewayai-supervisor-edge.socket'],check=True)
    subprocess.run(['systemctl','restart','gatewayai-supervisor-control'],check=True)
    creds=json.loads(Path('/etc/gatewayai-ingress/admin.json').read_text());token=None
    def api(path,data=None,method=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=urllib.request.Request('http://127.0.0.1:81/api'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
    token=api('/tokens',{'identity':creds['email'],'secret':creds['password']})['token']
    hosts=api('/nginx/proxy-hosts');existing=next((h for h in hosts if h['domain_names']==[args.hostname]),None)
    (backup/'proxy-host.json').write_text(json.dumps(existing))
    cert=next(c for c in api('/nginx/certificates') if c['nice_name']=='AADI internal wildcard')
    allow='\n'.join('allow '+network+';' for network in networks)
    advanced=f'''location / {{
{allow}
deny all;
proxy_pass http://{edge}:18769;
proxy_set_header Host {args.hostname};
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto https;
proxy_read_timeout 30s;
client_max_body_size 10k;
}}
'''
    payload={'domain_names':[args.hostname],'forward_scheme':'http','forward_host':edge,'forward_port':18769,
        'certificate_id':cert['id'],'ssl_forced':True,'hsts_enabled':False,'hsts_subdomains':False,
        'http2_support':True,'block_exploits':True,'caching_enabled':False,'allow_websocket_upgrade':False,
        'access_list_id':0,'advanced_config':advanced,'locations':[]}
    saved=api('/nginx/proxy-hosts'+('/'+str(existing['id']) if existing else ''),payload,'PUT' if existing else 'POST')
    subprocess.run(['docker','exec','gatewayai-ingress-npm-1','nginx','-t'],check=True)
    # Preserve all existing services, add/update only the new control card.
    catalog=Path('/var/lib/gatewayai-ingress/data/dashboard/services.json')
    shutil.copy2(catalog,backup/'services.json');services=json.loads(catalog.read_text())
    entry={'id':'supervisor-control','name':'Task control','description':'AADI and GatewayAI tasks, coders, PR reviews and corrections.',
           'url':'https://'+args.hostname,'group':'Development','status':'Open controls','symbol':'TASK'}
    old=next((x for x in services['services'] if x.get('id')=='supervisor-control' or x.get('url')==entry['url']),None)
    if old:old.update(entry)
    else:services['services'].append(entry)
    catalog.write_text(json.dumps(services,indent=2));catalog.chmod(0o644)
    print(json.dumps({'hostname':args.hostname,'proxy_id':saved['id'],'backup':str(backup),'dns':'separate verification required'}))


if __name__=='__main__':main()

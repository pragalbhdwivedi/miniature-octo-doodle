"""Apply approved private service routes to the existing NPM ingress VM.

Run as the VM administrator; accepts only a private JSON route inventory.
Preserves application state and makes no image pulls or container changes.
"""
from pathlib import Path
import json,urllib.request,subprocess,shutil,os,datetime,argparse,re
parser=argparse.ArgumentParser()
parser.add_argument('--routes',type=Path,required=True)
args=parser.parse_args()
routes=json.loads(args.routes.read_text())
assert isinstance(routes,list) and routes
for route in routes:
 assert re.fullmatch('[a-z][a-z0-9-]{0,30}',route['name'])
 assert isinstance(route['port'],int) and 1024 <= route['port'] <= 65535
 assert route['scheme'] in ('https','http')
 assert re.fullmatch(r'https://[a-zA-Z0-9.:-]+',route['original_origin'])
 for old,new in route.get('link_replacements',[]):
  assert re.fullmatch(r'https://[a-zA-Z0-9.:-]+',old)
  assert re.fullmatch(r'https://[a-z0-9.-]+',new)
 if route['scheme']=='https':
  assert Path(route['ca_file']).is_file()
  assert re.fullmatch(r'[a-zA-Z0-9.-]+',route['tls_name'])
os.umask(0o077)
r=Path('/etc/gatewayai-ingress'); state=Path('/var/lib/gatewayai-ingress/data')
if shutil.disk_usage(state).free < 15*1024**3: raise SystemExit('Critical storage reserve reached.')
creds=json.loads((r/'admin.json').read_text()); token=None
def api(path,data=None,method=None):
 headers={'Content-Type':'application/json'}
 if token: headers['Authorization']='Bearer '+token
 req=urllib.request.Request('http://127.0.0.1:81/api'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
 with urllib.request.urlopen(req,timeout=45) as res:return json.load(res)
token=api('/tokens',{'identity':creds['email'],'secret':creds['password']})['token']
hosts=api('/nginx/proxy-hosts'); cert=next(x for x in api('/nginx/certificates') if x['nice_name']=='AADI internal wildcard')
backup=r/('services-before-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir()
(backup/'proxy-hosts.json').write_text(json.dumps(hosts))
edge=json.loads(subprocess.check_output(['docker','network','inspect','gatewayai-ingress_edge']))[0]['IPAM']['Config'][0]['Gateway']
for route in routes:
 name,port,scheme,original=(route[k] for k in ('name','port','scheme','original_origin'))
 if scheme=='https':
  ca_target=state/(name+'-upstream.crt')
  shutil.copyfile(route['ca_file'],ca_target);ca_target.chmod(0o644)
 unit='gatewayai-'+name+'-tunnel'
 socket=f'''[Unit]
Description=GatewayAI {name} ingress to protected SSH reverse tunnel
After=docker.service
Requires=docker.service
[Socket]
ListenStream={edge}:{port}
FreeBind=true
NoDelay=true
[Install]
WantedBy=sockets.target
'''
 service=f'''[Unit]
Description=Unprivileged {name} tunnel proxy
[Service]
ExecStart=/usr/lib/systemd/systemd-socket-proxyd 127.0.0.1:{port}
DynamicUser=yes
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
'''
 for ext,body in [('socket',socket),('service',service)]:
  p=Path('/etc/systemd/system')/(unit+'.'+ext)
  if p.exists():shutil.copy2(p,backup/p.name)
  p.write_text(body);p.chmod(0o644)
 subprocess.run(['systemctl','daemon-reload'],check=True)
 subprocess.run(['systemctl','enable','--now',unit+'.socket'],check=True)
 hostname=name+'.aadi.dgoi.local'
 # Translate only this exact public origin. Foreign origins are left unchanged
 # so the application continues to deny them. CSRF tokens are never synthesized.
 config=f'''set $aadi_origin $http_origin;
if ($http_origin = "https://{hostname}") {{ set $aadi_origin "{original}"; }}
location / {{
  proxy_pass {scheme}://{edge}:{port};
  proxy_http_version 1.1;
  proxy_set_header Host "{original.split('://')[1]}";
  proxy_set_header Origin $aadi_origin;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $remote_addr;
  proxy_set_header X-Forwarded-Proto https;
  proxy_set_header Connection "";
  proxy_read_timeout 120s;
  proxy_connect_timeout 10s;
  proxy_redirect {original}/ https://{hostname}/;
  client_max_body_size 32m;
'''
 if scheme=='https':
  config+=f"  proxy_ssl_verify on;\n  proxy_ssl_trusted_certificate /data/{name}-upstream.crt;\n  proxy_ssl_server_name on;\n  proxy_ssl_name {route['tls_name']};\n"
 if route.get('link_replacements'):
  config+='  proxy_set_header Accept-Encoding "";\n  sub_filter_once off;\n'
  for old,new in route['link_replacements']:
   config+=f'  sub_filter "{old}" "{new}";\n'
 config+='}\n'
 payload={'domain_names':[hostname],'forward_scheme':scheme,'forward_host':edge,'forward_port':port,'certificate_id':cert['id'],'ssl_forced':True,'hsts_enabled':False,'hsts_subdomains':False,'http2_support':True,'block_exploits':False,'caching_enabled':False,'allow_websocket_upgrade':False,'access_list_id':0,'advanced_config':config,'locations':[]}
 old=next((h for h in hosts if h['domain_names']==[hostname]),None)
 result=api('/nginx/proxy-hosts'+('/'+str(old['id']) if old else ''),payload,'PUT' if old else 'POST')
 print(json.dumps({'hostname':hostname,'proxy_id':result['id']}))
subprocess.run(['docker','exec','gatewayai-ingress-npm-1','nginx','-t'],check=True)
print('Backup:',backup)

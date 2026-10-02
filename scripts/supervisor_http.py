"""Internal task control HTTP server. Network authority, no login or host shell."""
import argparse
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit

import pilot_server
import supervisor_board as board


class Application:
    def __init__(self,store,config):
        self.store,self.config=store,config
        self.secret=secrets.token_bytes(32)
        self.host=config['hostname'];self.origin='https://'+self.host
        self.networks=[ipaddress.ip_network(x) for x in config['allowed_networks']]
        self.assets=Path(config['assets']).resolve()

    def allowed(self,host,client):
        try:return host==self.host and any(ipaddress.ip_address(client) in n for n in self.networks)
        except ValueError:return False

    def sign(self,value):return hmac.new(self.secret,value.encode(),hashlib.sha256).hexdigest()

    def session(self,cookie):
        c=SimpleCookie()
        try:c.load(cookie or '');value=c['__Host-supervisor'].value
        except (KeyError,ValueError):value=''
        parts=value.split('.')
        if (len(parts)!=3 or not parts[0].isdigit() or not 0<=time.time()-int(parts[0])<3600
                or not hmac.compare_digest(parts[-1],self.sign('.'.join(parts[:2])))):
            raw=str(int(time.time()))+'.'+secrets.token_hex(16);value=raw+'.'+self.sign(raw)
        return value,self.sign('csrf:'+value)

    def authorize_write(self,headers):
        if headers.get('Origin')!=self.origin:raise ValueError('This action must come from the control page.')
        if headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required')
        if headers.get('Sec-Fetch-Site','same-origin')!='same-origin':raise ValueError('Cross-site action denied')
        cookie=headers.get('Cookie','');value,token=self.session(cookie)
        if value not in cookie or not hmac.compare_digest(headers.get('X-CSRF-Token',''),token):
            raise ValueError('Page session expired. Refresh before trying again.')

    def state(self):
        def current(s):
            board.ensure(s)
            return board.snapshot(s)
        return self.store.mutate(current)


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version='AADI-Control'
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def log_message(self,*args):pass
        def response(self,code,body,kind='application/json',cookie=None):
            if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode()
            self.send_response(code)
            for k,v in {'Content-Type':kind,'Content-Length':str(len(body)),
                'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
                'Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"}.items():self.send_header(k,v)
            if cookie:self.send_header('Set-Cookie','__Host-supervisor='+cookie+'; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=3600')
            self.end_headers();self.wfile.write(body)

        def admitted(self):
            # Only the loopback socket proxy may forward verified ingress identity.
            client=self.headers.get('X-Real-IP','')
            if self.client_address[0]!='127.0.0.1' or not app.allowed(self.headers.get('Host',''),client):
                self.response(403,{'error':'Control is available only through the approved internal address.'});return False
            return True

        def do_GET(self):
            if not self.admitted():return
            path=urlsplit(self.path).path
            try:
                if path=='/api/state':
                    cookie,token=app.session(self.headers.get('Cookie'))
                    value=app.state();value['csrf_token']=token
                    return self.response(200,value,cookie=cookie)
                if path.startswith('/api/documents/'):
                    name=path.removeprefix('/api/documents/')
                    docs=app.store.mutate(lambda s:board.documents(s))
                    if name not in docs:return self.response(404,{'error':'Unknown document'})
                    return self.response(200,docs[name].encode(),'text/markdown; charset=utf-8')
                name={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(path)
                if not name:return self.response(404,{'error':'Not found'})
                kind={'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[name]
                self.response(200,(app.assets/name).read_bytes(),kind+'; charset=utf-8')
            except Exception:self.response(503,{'error':'The controller is unavailable. Saved work is retained.'})

        def do_POST(self):
            if not self.admitted():return
            if self.path!='/api/control':return self.response(404,{'error':'Not found'})
            try:
                app.authorize_write(self.headers)
                if self.headers.get('Transfer-Encoding'):raise ValueError('Unsupported transfer encoding')
                size=int(self.headers.get('Content-Length','0'))
                if not 1<=size<=10000:raise ValueError('Action size limit exceeded')
                request=json.loads(self.rfile.read(size));request['actor']='Internal network operator (no individual login)'
                result=app.store.mutate(lambda s:board.action(s,request))
                self.response(200,result)
            except (ValueError,KeyError,TypeError) as exc:self.response(409,{'ok':False,'error':str(exc)[:200]})
            except Exception:self.response(503,{'ok':False,'error':'Action acknowledgement unavailable. Refresh to check before retrying.'})
    return Handler


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True)
    config=json.loads(parser.parse_args().config.read_text())
    dispatch=json.loads(Path(config['dispatch_config']).read_text())
    app=Application(pilot_server.Store(dispatch['container'],dispatch['database']),config)
    server=ThreadingHTTPServer(('127.0.0.1',config['port']),handler(app));server.serve_forever()


if __name__=='__main__':main()

"""HTTP security tests against an ephemeral loopback-only fake-store server."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import supervisor_http as web
import test_supervisor_board as fixture


class FakeStore:
    def __init__(self,value):
        self.value=copy.deepcopy(value);self.lock=threading.RLock()
    def read(self):
        with self.lock:return {'value':copy.deepcopy(self.value)}
    def mutate(self,operation):
        with self.lock:
            candidate=copy.deepcopy(self.value)
            result=operation(candidate)
            self.value=candidate
            return copy.deepcopy(result)


class SupervisorHttpTests(unittest.TestCase):
    def test_large_future_snapshot_disables_disk_buffering(self):
        from test_supervisor_future_integration import entry
        import supervisor_future
        supervisor_future.seed(self.store.value,[entry(i) for i in range(1,111)],'2026-10-02T13:00:00+00:00')
        code,headers,body=self.request('/api/state')
        self.assertEqual(code,200)
        self.assertEqual(headers['X-Accel-Buffering'],'no')
        self.assertEqual(int(headers['Content-Length']),len(body))
        self.assertEqual(len(json.loads(body)['future']['tasks']),110)

    def setUp(self):
        base=fixture.SupervisorBoardTests();base.setUp()
        self.store=FakeStore(base.s)
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.app=web.Application(self.store,{'hostname':'control.aadi.dgoi.local',
            'allowed_networks':['10.176.46.0/24','10.176.50.0/24'],'assets':self.directory.name})
        self.server=web.ThreadingHTTPServer(('127.0.0.1',0),web.handler(self.app))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close_server)

    def test_archive_history_is_readonly_bounded_and_no_full_snapshot_export(self):
        self.store.value['supervision']['archived_tasks']={'SUP-000099':{
            'id':'SUP-000099','key':'saved','title':'Completed work','state':'merged'}}
        before=copy.deepcopy(self.store.value)
        code,_,raw=self.request('/api/archive-history?offset=0&limit=1')
        self.assertEqual(code,200)
        value=json.loads(raw)
        self.assertEqual(value['total'],1)
        self.assertEqual(value['tasks'][0]['id'],'SUP-000099')
        self.assertEqual(before,self.store.value)
        for query in ('limit=201','offset=-1','file=secret','limit=1&limit=2'):
            self.assertEqual(self.request('/api/archive-history?'+query)[0],400)
        self.assertEqual(self.request('/api/archive-history',headers={'X-Real-IP':'8.8.8.8'})[0],403)
        self.assertEqual(self.request('/api/archive-history',method='POST')[0],404)

    def close_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def request(self,path='/api/state',method='GET',body=None,headers=None):
        values={'Host':self.app.host,'X-Real-IP':'10.176.46.20',**(headers or {})}
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            connection.request(method,path,body=body,headers=values)
            response=connection.getresponse()
            return response.status,dict(response.getheaders()),response.read()
        finally:connection.close()

    def session(self):
        code,headers,body=self.request()
        self.assertEqual(code,200)
        data=json.loads(body)
        return data,{'Cookie':headers['Set-Cookie'].split(';',1)[0],
            'X-CSRF-Token':data['csrf_token'],'Origin':self.app.origin,
            'Sec-Fetch-Site':'same-origin','Content-Type':'application/json'}

    def command(self,data,headers,**kw):
        action={'action':'pause','request_id':'browser-click','revision':data['revision'],**kw}
        return self.request('/api/control','POST',json.dumps(action),headers)

    def test_host_network_and_proxy_headers_cannot_bypass_allowlist(self):
        for headers in ({'Host':'evil.invalid'},{'Host':self.app.host+'.evil.invalid'},
                        {'X-Real-IP':'192.0.2.1'},{'X-Real-IP':'invalid'},
                        {'X-Real-IP':'10.176.46.1, 192.0.2.1'},
                        {'X-Real-IP':'192.0.2.1','X-Forwarded-For':'10.176.46.20'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers)[0],403)
        self.assertFalse(self.app.allowed(self.app.host,'::1'))
        self.assertTrue(self.app.allowed(self.app.host,'10.176.50.1'))

    def test_nonproxy_socket_peer_cannot_supply_trusted_forwarded_identity(self):
        Handler=web.handler(self.app)
        handler=Handler.__new__(Handler)
        handler.client_address=('10.176.46.20',12345)
        handler.headers={'Host':self.app.host,'X-Real-IP':'10.176.46.20'}
        handler.response=Mock()
        self.assertFalse(handler.admitted())
        self.assertEqual(handler.response.call_args.args[0],403)

    def test_foreign_origin_missing_cookie_csrf_and_cross_site_are_rejected_without_effect(self):
        data,headers=self.session()
        before=copy.deepcopy(self.store.value)
        for bad in ({'Origin':'https://evil.invalid'}, {'Origin':self.app.origin+'.evil.invalid'},
                    {'Cookie':''},{'X-CSRF-Token':'wrong'}, {'Sec-Fetch-Site':'cross-site'},
                    {'Content-Type':'text/plain'}):
            with self.subTest(bad=bad):
                self.assertEqual(self.command(data,{**headers,**bad})[0],409)
                self.assertEqual(self.store.value,before)

    def test_expired_and_tampered_cookie_cannot_write(self):
        with patch.object(web.time,'time',return_value=1000):data,headers=self.session()
        with patch.object(web.time,'time',return_value=4600):
            self.assertEqual(self.command(data,headers)[0],409)
        value=headers['Cookie']
        headers['Cookie']=value[:-1]+('0' if value[-1]!='0' else '1')
        with patch.object(web.time,'time',return_value=1001):
            self.assertEqual(self.command(data,headers)[0],409)
        self.assertTrue(self.store.value['ongoing']['enabled'])

    def test_button_command_is_idempotent_and_stale_revision_conflicts(self):
        data,headers=self.session()
        first=self.command(data,headers)
        self.assertEqual(first[0],200)
        self.assertFalse(self.store.value['ongoing']['enabled'])
        before=copy.deepcopy(self.store.value)
        again=self.command(data,headers)
        self.assertEqual(json.loads(again[2]),json.loads(first[2]))
        self.assertEqual(self.store.value,before)
        self.assertEqual(self.command(data,headers,request_id='new-click',action='resume')[0],409)
        self.assertEqual(self.store.value,before)

    def test_security_headers_cookie_flags_and_static_path_allowlist(self):
        code,headers,_=self.request()
        self.assertEqual(code,200)
        for expected in ('Secure','HttpOnly','SameSite=Strict','Path=/','Max-Age=3600'):
            self.assertIn(expected,headers['Set-Cookie'])
        self.assertEqual(headers['X-Frame-Options'],'DENY')
        self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        for path in ('/../../private','/api/documents/../../private','/api/documents/unknown.md'):
            self.assertEqual(self.request(path)[0],404)

    def test_body_limit_transfer_encoding_and_nonobject_json_do_not_mutate(self):
        data,headers=self.session();before=copy.deepcopy(self.store.value)
        self.assertEqual(self.request('/api/control','POST','x'*10001,headers)[0],409)
        self.assertEqual(self.request('/api/control','POST','[]',headers)[0],409)
        self.assertEqual(self.command(data,{**headers,'Transfer-Encoding':'chunked'})[0],409)
        self.assertEqual(self.store.value,before)


if __name__=='__main__':unittest.main()

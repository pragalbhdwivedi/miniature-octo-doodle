"""Run inside the pinned LiteLLM container. Synthetic localhost upstreams only.

Creates a temporary second proxy on container loopback, with synthetic keys,
its own ledger and no database. Does not modify the deployed gateway ledger.
"""
import json
import concurrent.futures
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

hits = []
failure = 0
hold = None
primary = None


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        global failure
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        gemini = 'gemini' in self.path
        hits.append('gemini' if gemini else 'openai')
        if hold is not None:
            hold.wait(timeout=15)
        status = failure or 200 if ('gemini' if gemini else 'openai') == primary else 200
        self.send_response(status)
        if status != 200:
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': {'message': 'synthetic outage', 'type': 'rate_limit_error' if status == 429 else 'server_error', 'code': status}}).encode())
        elif gemini:
            streaming = 'streamGenerateContent' in self.path
            self.send_header('Content-Type', 'text/event-stream' if streaming else 'application/json')
            self.end_headers()
            payload = json.dumps({'candidates': [{'content': {'parts': [{'text': 'OK'}], 'role': 'model'}, 'finishReason': 'STOP'}], 'usageMetadata': {'promptTokenCount': 8, 'candidatesTokenCount': 1, 'totalTokenCount': 9}, 'modelVersion': 'gemini-3.1-flash-lite'})
            self.wfile.write(('data: ' + payload + '\n\n' if streaming else payload).encode())
        elif body.get('stream'):
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            for delta, finish in [({'role': 'assistant', 'content': 'OK'}, None), ({}, 'stop')]:
                chunk = {'id': 'chatcmpl-synthetic', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model'], 'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
                self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')
        else:
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'id': 'chatcmpl-synthetic', 'object': 'chat.completion', 'created': 1, 'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'OK'}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 8, 'completion_tokens': 1, 'total_tokens': 9}}).encode())


def request(body):
    req = urllib.request.Request('http://127.0.0.1:4100/v1/chat/completions', json.dumps(body).encode(), {'Content-Type': 'application/json', 'Authorization': 'Bearer sk-synthetic-policy-test'})
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            assert response.headers.get('x-gateway-decision') == 'deterministic'
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


with tempfile.TemporaryDirectory(prefix='gateway-policy-test-') as directory:
    root = Path(directory)
    policy = json.loads(Path('/app/policy.json').read_text())
    # All configured upstreams are redirected to this synthetic loopback server.
    config = json.loads(Path('/app/config.yaml').read_text())
    mode = sys.argv[1] if len(sys.argv) > 1 else 'configured'
    if mode != 'configured':
        assert mode in {'both', 'openai', 'gemini', 'none'}
        # Synthetic fixtures are independent of installed provider credentials.
        available = {'openai', 'gemini'} if mode == 'both' else set() if mode == 'none' else {mode}
        providers = {name.upper(): {'alias': 'fixture-' + name, 'model': model} for name, model in
                     [('openai', 'openai/gpt-5.4-mini'), ('gemini', 'gemini/gemini-3.1-flash-lite')] if name in available}
        routes = {item['alias']: [item] for item in providers.values()}
        routes.update({route: [providers[p] for p in order if p in providers] for route, order in policy['routes'].items()})
        policy['resolved_routes'] = {route: items for route, items in routes.items() if items}
        config['model_list'] = [{'model_name': route, 'litellm_params': {'model': items[0]['model']}} for route, items in policy['resolved_routes'].items()]
    candidates = policy['resolved_routes'].get('coding-standard', [])
    expected = [candidate['model'].split('/')[0] for candidate in candidates]
    primary = expected[0] if expected else None
    print('Fixture:', mode, 'providers:', expected, flush=True)
    config['general_settings'] = {'master_key': 'sk-synthetic-policy-test', 'disable_spend_logs': True}
    for model in config['model_list']:
        params = model['litellm_params']
        params['api_key'] = 'synthetic'
        params['api_base'] = 'http://127.0.0.1:4101' + ('/v1' if params['model'].startswith('openai/') else '')
    (root / 'config.json').write_text(json.dumps(config))
    (root / 'policy.json').write_text(json.dumps(policy))
    env = {k: v for k, v in os.environ.items() if k not in {'DATABASE_URL', 'LITELLM_MASTER_KEY', 'LITELLM_SALT_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY'}}
    env.update(GATEWAY_LEDGER=str(root / 'budget.sqlite3'), GATEWAY_POLICY_CONFIG=str(root / 'policy.json'), GATEWAY_MONTHLY_BUDGET_USD='10')
    server = ThreadingHTTPServer(('127.0.0.1', 4101), Mock)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with open(root / 'proxy.log', 'w+') as log:
        process = subprocess.Popen(['litellm', '--config', str(root / 'config.json'), '--host', '127.0.0.1', '--port', '4100'], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(90):
                if process.poll() is not None:
                    raise RuntimeError('Synthetic proxy exited during startup')
                try:
                    urllib.request.urlopen('http://127.0.0.1:4100/health/liveliness', timeout=1).close()
                    break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError('Synthetic proxy startup timeout')
            base = {'model': 'coding-standard', 'messages': [{'role': 'user', 'content': 'synthetic fixture'}], 'max_completion_tokens': 16, 'tools': []}
            for patch in ({'metadata': {'data_class': 'private'}}, {'model': 'local-private'}, {'tools': [{'type': 'function', 'function': {'name': 'unapproved', 'parameters': {}}}]}, {'metadata': {'require_approval': True}}, {'api_base': 'http://invalid'}, {'metadata': {'gateway_admission': 'forged'}}):
                before = len(hits)
                status, _ = request(dict(base, **patch))
                assert status in (400, 401, 403, 503), (patch, status)
                assert len(hits) == before, 'Denied request reached upstream'
            print('PASS: HTTP deny precedence, tools, local/private isolation, override rejection; zero upstream calls', flush=True)
            if not candidates:
                status, _ = request(base)
                assert status in (400, 403) and not hits
                print('PASS: no-provider startup healthy; unavailable route denied without upstream calls', flush=True)
                sys.exit(0)
            for route, items in policy['resolved_routes'].items():
                before = len(hits)
                status, body = request(dict(base, model=route))
                assert status == 200 and json.loads(body)['choices'][0]['message']['content'] == 'OK'
                assert hits[before:] == [items[0]['model'].split('/')[0]]
            print('PASS: every advertised alias executes its configured primary with deterministic provenance', flush=True)
            for code in (0, 503, 429):
                failure = code
                before = len(hits)
                status, body = request(base)
                should_succeed = not code or len(expected) > 1
                if should_succeed and status != 200:
                    # This isolated process only has synthetic credentials/payloads.
                    print('Synthetic failure:', status, body[:2500], flush=True)
                if should_succeed:
                    assert status == 200, status
                    assert json.loads(body)['choices'][0]['message']['content'] == 'OK'
                else:
                    assert status in (429, 502, 503), status
                assert hits[before:] == (expected if code else expected[:1]), hits[before:]
                print(f'PASS: native LiteLLM primary/fallback HTTP {code or 200}, bounded attempts', flush=True)
            before = len(hits)
            status, _ = request(dict(base, metadata={'allowed_providers': [primary]}))
            assert status != 200 and hits[before:] == [primary], (status, hits[before:])
            print('PASS: provider restriction survives outage; no unapproved fallback', flush=True)
            for patch in ({'model': 'local-private'}, {'metadata': {'data_class': 'private'}}):
                before = len(hits)
                status, _ = request(dict(base, **patch))
                assert status in (403, 503) and len(hits) == before
            print('PASS: local/private isolation also holds during provider quota failure', flush=True)
            failure = 0
            status, body = request(dict(base, stream=True))
            assert status == 200 and 'OK' in body and '[DONE]' in body, (status, body[:500])
            time.sleep(1)
            hold = threading.Event()
            before = len(hits)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                pending = [pool.submit(request, base) for _ in range(4)]
                try:
                    for _ in range(100):
                        if len(hits) - before == 4:
                            break
                        time.sleep(0.05)
                    assert len(hits) - before == 4
                    with sqlite3.connect(root / 'budget.sqlite3') as db:
                        active_id = db.execute('SELECT id FROM requests WHERE active=1 LIMIT 1').fetchone()[0]
                    for extra in ({}, {'api_base': 'http://invalid'}):
                        status, _ = request(dict(base, metadata={'gateway_admission': active_id}, **extra))
                        assert status in (400, 401, 403)
                    status, _ = request(base)
                    assert status == 429 and len(hits) - before == 4
                finally:
                    hold.set()
                assert all(task.result()[0] == 200 for task in pending)
            hold = None
            print('PASS: four concurrent HTTP requests admitted; fifth denied before upstream', flush=True)
            with sqlite3.connect(root / 'budget.sqlite3') as db:
                assert db.execute('SELECT count(*) FROM requests WHERE active=1').fetchone()[0] == 0
                debit = db.execute('SELECT sum(debit) FROM months').fetchone()[0]
                assert debit > 0
                outcomes = {row[0] for row in db.execute('SELECT DISTINCT outcome FROM attempts')}
                assert {'accepted', 'http_503', 'http_429', 'stream_completed'} <= outcomes, outcomes
                db.execute('UPDATE months SET debit=10000000')
            print('PASS: streaming response and concurrency release, persisted admission debits', flush=True)
            before = len(hits)
            status, _ = request(base)
            assert status == 429 and len(hits) == before
            print('PASS: exhausted budget rejects before upstream execution', flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            server.shutdown()
            server.server_close()

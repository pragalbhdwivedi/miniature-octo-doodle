#!/usr/bin/env python3
"""One fixed synthetic code-generation test via the authenticated local gateway.

The model writes arithmetic function bodies, not shell commands. A strict AST
grammar precedes execution; no imports, calls, attributes, loops, or arbitrary
files are permitted. This is not an autonomous-agent acceptance test.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import urllib.error
import urllib.request
import uuid

ALIAS = 'mac-coding-test'
PROMPT = '''Return only Python source, no Markdown or explanation. Define exactly
four functions: add(a,b), subtract(a,b), multiply(a,b), divide(a,b).
Each function must contain exactly one return statement using its two arguments
and the appropriate arithmetic operator. For divide, Python / should raise
ZeroDivisionError naturally. No imports, annotations, calls, comments, docstrings,
decorators, assignments, tests or additional definitions.'''


def validate_source(source):
    if not isinstance(source, str) or len(source.encode()) > 8192:
        raise ValueError('Generated source missing or oversized')
    tree = ast.parse(source)
    expected = {'add', 'subtract', 'multiply', 'divide'}
    if len(tree.body) != 4 or {getattr(n, 'name', None) for n in tree.body} != expected:
        raise ValueError('Expected exactly four calculator functions')
    for fn in tree.body:
        if (not isinstance(fn, ast.FunctionDef) or fn.decorator_list or fn.returns
                or getattr(fn, 'type_params', []) or fn.type_comment):
            raise ValueError('Invalid function declaration')
        args = fn.args
        if (args.posonlyargs or args.vararg or args.kwarg or args.kwonlyargs
                or args.defaults or args.kw_defaults
                or [a.arg for a in args.args] != ['a', 'b']
                or any(a.annotation or a.type_comment for a in args.args)
                or len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return)):
            raise ValueError('Only two-argument single-return functions are allowed')
        expr = fn.body[0].value
        if (not isinstance(expr, ast.BinOp)
                or type(expr.op) not in (ast.Add, ast.Sub, ast.Mult, ast.Div)
                or not isinstance(expr.left, ast.Name) or expr.left.id not in ('a', 'b')
                or not isinstance(expr.right, ast.Name) or expr.right.id not in ('a', 'b')):
            raise ValueError('Only a single arithmetic operation on a/b is allowed')
    return tree


def check_source(source):
    tree = validate_source(source)
    scope = {'__builtins__': {}}
    exec(compile(tree, '<validated-local-calculator>', 'exec'), scope)
    cases = [('add', 2, 3, 5), ('add', -2, -3, -5), ('add', .1, .2, .3),
             ('subtract', 5, 2, 3), ('subtract', -2, 3, -5), ('subtract', 2.5, .5, 2),
             ('multiply', 3, 4, 12), ('multiply', -3, 4, -12), ('multiply', 2.5, .4, 1),
             ('divide', 8, 2, 4), ('divide', -9, 3, -3), ('divide', 1, 4, .25)]
    for name, a, b, expected in cases:
        actual = scope[name](a, b)
        if not isinstance(actual, (int, float)) or not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError('Independent test failed: ' + name)
    for zero in (0, 0.0):
        try:
            scope['divide'](1, zero)
        except ZeroDivisionError:
            continue
        raise ValueError('Division by zero did not raise')
    return 14


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Gateway redirects are forbidden')


def request(key):
    body = {'model': ALIAS, 'messages': [{'role': 'user', 'content': PROMPT}],
            'max_tokens': 768, 'temperature': 0, 'stream': False,
            'metadata': {'data_class': 'synthetic', 'allowed_providers': ['ollama']}}
    req = urllib.request.Request('http://127.0.0.1:4000/v1/chat/completions',
                                 json.dumps(body).encode(), headers={
                                     'Content-Type': 'application/json',
                                     'Authorization': 'Bearer ' + key})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=180) as response:
        data = response.read(65537)
        if len(data) > 65536:
            raise ValueError('Gateway response too large')
        admission = response.headers.get('x-gateway-request-id')
        if not admission or response.headers.get('x-gateway-decision') != 'deterministic':
            raise ValueError('Missing gateway policy provenance')
        return json.loads(data), admission


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    info = args.key_file.stat()
    if args.key_file.is_symlink() or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o007:
        raise ValueError('Key must be an ordinary protected file')
    key = args.key_file.read_text().strip()
    if not key or '\n' in key:
        raise ValueError('Invalid key file')
    run_dir = args.evidence_dir / uuid.uuid4().hex
    run_dir.mkdir(parents=True, mode=0o700)
    started = time.monotonic()
    response, admission = request(key)
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Model output was incomplete')
    source = choice['message']['content']
    count = check_source(source)
    result = {'status': 'synthetic_gateway_code_test_pass', 'tests_passed': count,
              'gateway_request_id': admission, 'route': ALIAS,
              'response_model': response.get('model'), 'elapsed_seconds': round(time.monotonic() - started, 2),
              'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
              'provider_ledger_verified': False,
              'boundary': 'Strict arithmetic grammar only; not Codex tool or real-project acceptance'}
    for name, value in [('calculator.py', source), ('result.json', json.dumps(result, indent=2) + '\n')]:
        fd = os.open(run_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(value)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as exc:
        raise SystemExit('Gateway test failed: HTTP ' + str(exc.code)) from None
    except (ValueError, SyntaxError, OSError, KeyError, IndexError, TypeError) as exc:
        raise SystemExit('Gateway test failed: ' + str(exc)) from None

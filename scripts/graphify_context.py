"""Read-only, public-source Graphify retrieval with a fresh-Git gate.

The graph is advisory context. It never supplies controller authority or source
content. Build and provenance stamp are one operation, bound to the same Git SHA.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


REPOSITORY = 'https://github.com/pragalbhdwivedi/miniature-octo-doodle'
MAX_RESULT_BYTES = 16384
MAX_GRAPH_BYTES = 64 * 1024 * 1024


class ContextError(ValueError):
    pass


def command(*args, timeout=30, cwd=None):
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=False, cwd=cwd)
    if result.returncode:
        detail = (result.stderr or result.stdout).decode('utf-8', errors='replace')[-300:]
        raise ContextError('Source refresh or graph query failed: '+detail.strip())
    return result.stdout


def git(repo, *args):
    return command('git', '-C', str(repo), *args).decode('utf-8').strip()


def source_sha(repo):
    repo = Path(repo).resolve(strict=True)
    if Path(git(repo, 'rev-parse', '--show-toplevel')).resolve() != repo:
        raise ContextError('Use an exact repository root')
    if git(repo, 'remote', 'get-url', 'origin').removesuffix('.git') != REPOSITORY:
        raise ContextError('Only the approved public repository is allowed')
    if git(repo, 'status', '--porcelain'):
        raise ContextError('Source checkout is not clean')
    sha = git(repo, 'rev-parse', 'HEAD')
    remote_line = git(repo, 'ls-remote', 'origin', 'refs/heads/main')
    remote_sha = remote_line.split('\t', 1)[0]
    if not re.fullmatch(r'[a-f0-9]{40}', sha) or sha != remote_sha:
        raise ContextError('Graph source is stale against GitHub main')
    return sha


def build(repo, index, graphify, runner=command):
    """Extract a new graph and stamp only the exact revision just extracted."""
    repo = Path(repo).resolve(strict=True)
    index = Path(index).resolve()
    if index.is_relative_to(repo) or index.is_symlink():
        raise ContextError('Graph index must be outside source and not a symlink')
    before = source_sha(repo)
    with tempfile.TemporaryDirectory(prefix='graph-build-', dir=index.parent) as temporary:
        work = Path(temporary)
        runner(str(graphify), 'extract', str(repo), '--code-only', '--max-workers',
               '2', '--out', str(work), timeout=300, cwd=index.parent)
        runner(str(graphify), 'cluster-only', str(work), '--no-label', '--no-viz',
               timeout=120, cwd=index.parent)
        graph = work/'graphify-out'/'graph.json'
        if not graph.is_file() or graph.stat().st_size > MAX_GRAPH_BYTES:
            raise ContextError('Graph extraction missing or oversized')
        graph_bytes = graph.read_bytes()
        if source_sha(repo) != before:
            raise ContextError('Source advanced during graph extraction')
    index.mkdir(mode=0o700, exist_ok=True)
    output = index/'graphify-out'
    output.mkdir(mode=0o700, exist_ok=True)
    graph_tmp = output/'graph.json.next'
    graph_tmp.write_bytes(graph_bytes)
    os.replace(graph_tmp, output/'graph.json')
    manifest = {'schema': 'gatewayai.graph-context.v1', 'repository': REPOSITORY,
                'source_sha': before, 'graph_sha256': hashlib.sha256(graph_bytes).hexdigest(),
                'classification': 'public'}
    target = index/'source.json'
    next_manifest = index/'source.json.next'
    next_manifest.write_text(json.dumps(manifest, sort_keys=True)+'\n', encoding='utf-8')
    os.replace(next_manifest, target)
    return target


def query(repo, index, graphify, question, role='public-worker', token_budget=500):
    if role not in ('public-worker', 'operator'):
        raise ContextError('Context role is not allowed')
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 200:
        raise ContextError('A bounded query is required')
    if not 100 <= token_budget <= 1000:
        raise ContextError('Token budget is outside the public context limit')
    sha = source_sha(repo)
    index = Path(index).resolve(strict=True)
    manifest = json.loads((index/'source.json').read_text(encoding='utf-8'))
    graph = index/'graphify-out'/'graph.json'
    if (graph.stat().st_size > MAX_GRAPH_BYTES
            or manifest.get('schema') != 'gatewayai.graph-context.v1'
            or manifest.get('repository') != REPOSITORY
            or manifest.get('classification') != 'public'
            or manifest.get('source_sha') != sha
            or manifest.get('graph_sha256') != hashlib.sha256(graph.read_bytes()).hexdigest()):
        raise ContextError('Graph provenance is stale or altered')
    output = command(str(graphify), 'query', question, '--graph', str(graph),
                     '--budget', str(token_budget), timeout=45, cwd=index.parent)
    if len(output) > MAX_RESULT_BYTES:
        raise ContextError('Graph query exceeded output limit')
    return {'schema': 'gatewayai.graph-result.v1', 'repository': REPOSITORY,
            'source_sha': sha, 'classification': 'public', 'role': role,
            'advisory_only': True, 'query': question,
            'result': output.decode('utf-8')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--graphify', type=Path)
    parser.add_argument('--query')
    parser.add_argument('--role', default='public-worker')
    parser.add_argument('--budget', type=int, default=500)
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    try:
        if args.build and args.graphify and not args.query:
            print(build(args.repo, args.index, args.graphify))
        elif args.query and args.graphify and not args.build:
            print(json.dumps(query(args.repo, args.index, args.graphify, args.query,
                                   args.role, args.budget), ensure_ascii=False))
        else:
            raise ContextError('Choose --build or --query with --graphify')
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise SystemExit('Graph context stopped: '+str(exc)) from None


if __name__ == '__main__':
    main()

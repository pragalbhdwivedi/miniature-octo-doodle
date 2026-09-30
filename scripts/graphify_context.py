"""Read-only, public-source Graphify retrieval with a fresh-Git gate.

The graph is advisory context. It never supplies controller authority or source
content, and this command is not wired into production dispatch.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


REPOSITORY = 'https://github.com/pragalbhdwivedi/miniature-octo-doodle'
MAX_RESULT_BYTES = 16384


class ContextError(ValueError):
    pass


def command(*args, timeout=30):
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        raise ContextError('Source refresh or graph query failed')
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


def make_manifest(repo, index):
    """Record provenance only after a completed extraction from current main."""
    sha = source_sha(repo)
    graph = Path(index).resolve()/'graphify-out'/'graph.json'
    digest = hashlib.sha256(graph.read_bytes()).hexdigest()
    manifest = {'schema': 'gatewayai.graph-context.v1', 'repository': REPOSITORY,
                'source_sha': sha, 'graph_sha256': digest, 'classification': 'public'}
    target = Path(index).resolve()/'source.json'
    target.write_text(json.dumps(manifest, sort_keys=True)+'\n', encoding='utf-8')
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
    if (manifest.get('schema') != 'gatewayai.graph-context.v1'
            or manifest.get('repository') != REPOSITORY
            or manifest.get('classification') != 'public'
            or manifest.get('source_sha') != sha
            or manifest.get('graph_sha256') != hashlib.sha256(graph.read_bytes()).hexdigest()):
        raise ContextError('Graph provenance is stale or altered')
    output = command(str(graphify), 'query', question, '--graph', str(graph),
                     '--budget', str(token_budget), timeout=45)
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
    parser.add_argument('--stamp', action='store_true')
    args = parser.parse_args()
    try:
        if args.stamp and not args.query:
            print(make_manifest(args.repo, args.index))
        elif args.query and args.graphify and not args.stamp:
            print(json.dumps(query(args.repo, args.index, args.graphify, args.query,
                                   args.role, args.budget), ensure_ascii=False))
        else:
            raise ContextError('Choose --stamp or --query with --graphify')
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise SystemExit('Graph context stopped: '+str(exc)) from None


if __name__ == '__main__':
    main()

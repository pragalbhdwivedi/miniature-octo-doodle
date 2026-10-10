"""One-shot paid synthetic reviewer probe with exact-main OpenViking excerpts.

Operator-only; a durable root-only reservation is written before gateway HTTP.
This does not claim a full worker/pipeline execution or publication authority.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location('pipeline', ROOT/'scripts/controller_pipeline.py')
pipeline = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(pipeline)


class ProbeStore:
    def __init__(self, folder):
        self.folder = folder

    def reserve_pipeline(self, run_id, stage, debit, body_hash):
        if stage != 'review0' or not 0 < debit <= 1_000_000:
            raise ValueError('One reviewer stage, at most 1 USD')
        target = self.folder/'reservation.json'
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'run_id': run_id, 'stage': stage, 'debit_micro_usd': debit,
                       'request_sha256': body_hash, 'status': 'reserved_before_http'}, stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--dispatch-config', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('Linux operator only')
    os.umask(0o077)
    source = args.source.resolve(strict=True)
    sha = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != pipeline.memory.main_sha():
        raise ValueError('Source is not current public main')
    config = pipeline.d.private_json(args.dispatch_config)
    folder = args.receipt.resolve()
    folder.mkdir(mode=0o700, exist_ok=False)
    run_id = uuid.uuid4().hex
    spec = {'run_id': run_id, 'source_sha': sha, 'artifact_sha256': '0'*64,
            'requirements': 'Review a synthetic clamp(value, lower, upper) function for inclusive bounds and inverted-bound rejection. Return only the specified JSON verdict and findings.',
            'read_paths': ['docs/OPENVIKING.md'],
            'test_commands': [['python3', '-c', 'print("synthetic")']],
            'budget_micro_usd': 1_000_000, 'max_repairs': 0}
    root = {'project': 'gatewayai', 'request': {'plan': {
        'repository': 'pragalbhdwivedi/miniature-octo-doodle', 'ref': 'refs/heads/main',
        'source_sha': sha}}}
    context = pipeline.advisory_context(root, spec, config)
    if not context or not context['hits'] or not all(hit['abstract'] for hit in context['hits']):
        raise ValueError('Current OpenViking excerpts required for this probe')
    original = {name: ((source/name).read_bytes(), 0o644)
                for name in ('PROJECT.md', 'AGENTS.md', 'docs/OPENVIKING.md')}
    candidate = b'def clamp(value, lower, upper):\n    if lower > upper:\n        raise ValueError("inverted bounds")\n    return max(lower, min(upper, value))\n'
    proposal = {'changes': [{'path': 'docs/examples/controller_acceptance.py',
                             'content_base64': base64.b64encode(candidate).decode()}]}
    prompt = pipeline.messages(spec, original, proposal, 'review',
                               {'tests_passed': True}, context)
    store = ProbeStore(folder)
    response = pipeline.model_call(store, spec, 'review0', prompt,
                                   Path(config['coding_config']))
    verdict = pipeline.review_result(response)
    receipt = {'source_sha': sha, 'run_id': run_id,
               'advisory_hit_count': len(context['hits']),
               'advisory_sha256': pipeline.d.digest(context),
               'verdict': verdict['verdict'], 'finding_count': len(verdict['findings']),
               'usage': response.get('usage', {}), 'synthetic_only': True,
               'full_pipeline_executed': False}
    target = folder/'result.json'
    with target.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    target.chmod(0o600)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()

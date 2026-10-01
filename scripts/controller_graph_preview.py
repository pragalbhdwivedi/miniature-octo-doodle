"""Attach a fresh public Graphify advisory to an exact controller plan for review.

This sidecar never changes a plan, dispatches work, calls a model, or grants
publication authority. It is for an operator's read-only planning review.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

import graphify_context as graph


def preview(plan_path, repo, index, graphify, question):
    plan_path = Path(plan_path).resolve(strict=True)
    if plan_path.stat().st_size > 262144:
        raise ValueError('Controller plan exceeds input limit')
    raw = plan_path.read_bytes()
    plan = json.loads(raw)
    if (not isinstance(plan, dict) or plan.get('project') != 'gatewayai'
            or plan.get('repository') != 'pragalbhdwivedi/miniature-octo-doodle'
            or plan.get('ref') != 'refs/heads/main'
            or not re.fullmatch(r'[a-f0-9]{40}', plan.get('source_sha', ''))):
        raise ValueError('Only an exact public GatewayAI main plan is supported')
    result = graph.query(repo, index, graphify, question, role='operator', token_budget=300)
    if result['source_sha'] != plan['source_sha']:
        raise ValueError('Plan and graph source revisions differ')
    return {'schema': 'gatewayai.controller-graph-preview.v1',
            'plan_sha256': hashlib.sha256(raw).hexdigest(),
            'plan_run_id': plan.get('run_id'), 'source_sha': result['source_sha'],
            'authority': 'advisory_only', 'model_calls': 0, 'actions_executed': [],
            'graph': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--graphify', type=Path, required=True)
    parser.add_argument('--query', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(preview(args.plan, args.repo, args.index,
                                 args.graphify, args.query), ensure_ascii=False))
    except (OSError, ValueError) as exc:
        raise SystemExit('Graph preview stopped: '+str(exc)) from None

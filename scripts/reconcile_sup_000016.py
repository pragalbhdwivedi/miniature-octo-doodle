#!/usr/bin/env python3
"""One-time operator reconciliation of SUP-000016; never runs a coder or publisher.

Run on the control VM as the operator after reviewing the original failed receipt.
Preview is read-only. Apply requires the just-observed board revision.
"""
import argparse
import copy
import json
from pathlib import Path
import urllib.request

import controller_telegram as telegram
from pilot_server import Store
import supervisor_board as board


REPO = 'pragalbhdwivedi/miniature-octo-doodle'
TASK = 'SUP-000016'
JOB = 'intake-sup-000016'
SOURCE = '19cc2032e8264a8f04980db10a280304013ebf5a'
PR = 59
HEAD = 'c3956cbd335ec73f7da5789aa07b7333cf22316e'
MERGE = 'c6a4f24226c49751f8ab12e9f9f7429e5aacb057'
FAILED_DIGEST = '772eb7e23a8436ffdba137204610d8f2a308b57c52607abc38a1277684f663b9'
FAILED_RECEIPT = 'd385cf056607575cc552cd85a16b032dbf38655f79f9036705bf2275a763f7eb'
URL = f'https://github.com/{REPO}/pull/{PR}'
NOTE = ('Operator recovery merged PR #59 after the Gemini candidate failed source validation. '
        'The original attempt was not retested or reviewed; its blocked state and receipts remain in the ledger.')


def github(path):
    request = urllib.request.Request('https://api.github.com/repos/'+REPO+path,
        headers={'Accept':'application/vnd.github+json','User-Agent':'GatewayAI-operator-reconciliation'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def verify_github():
    pr = github('/pulls/'+str(PR))
    issue = github('/issues/53')
    if (pr['html_url'] != URL or pr['head']['sha'] != HEAD
            or pr['merge_commit_sha'] != MERGE or pr['merged_at'] is None
            or pr['base']['ref'] != 'main' or issue['state'] != 'closed'):
        raise ValueError('GitHub merged PR or issue identity changed')


def current(state):
    job = next(j for j in state['ongoing']['jobs'] if j['id'] == JOB)
    meta = state['supervision']['tasks'][TASK]
    if (job['state'] != 'blocked' or job['attempt'] != 0 or job['source_sha'] != SOURCE
            or job.get('publication') or meta['history'][-1]['state'] != 'blocked'
            or meta['history'][-1]['evidence_digest'] != FAILED_DIGEST
            or FAILED_DIGEST not in state['supervision']['evidence']):
        raise ValueError('Original failed attempt or evidence changed')
    return job, meta


def run(store, *, apply=False, expected_revision=None):
    verify_github()
    before = store.read()['value']
    job, meta = current(before)
    if meta.get('external_resolution'):
        resolution = meta['external_resolution']
        if resolution.get('url') == URL and resolution.get('merge_sha') == MERGE:
            return {'state':'already_reconciled','revision':before['supervision']['revision']}
        raise ValueError('A different external resolution is present')
    revision = before['supervision']['revision']
    fields=dict(expected_revision=revision, task_id=TASK, job_id=JOB, source_sha=SOURCE,
        failed_evidence_digest=FAILED_DIGEST, failed_receipt_sha256=FAILED_RECEIPT,
        pr_url=URL, head_sha=HEAD, merge_sha=MERGE, note=NOTE)
    if not apply:
        simulated=copy.deepcopy(before)
        board.record_operator_merge(simulated, **fields)
        simulated_task=next(t for t in board.snapshot(simulated)['tasks'] if t['id']==TASK)
        if (simulated_task['state']!='completed' or simulated_task['original_state']!='blocked'
                or current(simulated)[0]!=job):
            raise RuntimeError('Preview did not preserve the original failed attempt')
        return {'state':'preview','revision':revision,'task_id':TASK,'original_state':job['state'],
                'failed_evidence_digest':FAILED_DIGEST,'failed_receipt_sha256':FAILED_RECEIPT,
                'pr_url':URL,'merge_sha':MERGE}
    if expected_revision != revision:
        raise board.ConflictError('Board revision changed; preview again')
    old_job = copy.deepcopy(job)
    old_history = copy.deepcopy(meta['history'])
    old_evidence = copy.deepcopy(before['supervision']['evidence'][FAILED_DIGEST])
    result = store.mutate(lambda state: board.record_operator_merge(state,**fields))
    after = store.read()['value']
    final_job, final_meta = current(after)
    task = next(t for t in board.snapshot(after)['tasks'] if t['id'] == TASK)
    if (final_job != old_job or final_meta['history'] != old_history
            or after['supervision']['evidence'][FAILED_DIGEST] != old_evidence
            or task['state'] != 'completed' or task['original_state'] != 'blocked'
            or task['pr_url'] != URL or task['review_state'] != 'merged_external'
            or task['progress']['tests_passed'] or task['progress']['review_passed']):
        raise RuntimeError('Post-write verification failed; inspect the operator audit')
    return {**result,'original_attempt_preserved':True,'failed_evidence_preserved':True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-revision', type=int)
    args = parser.parse_args()
    if args.apply and args.expected_revision is None:
        parser.error('--apply requires --expected-revision from a fresh preview')
    config = telegram.d.private_json(args.config)
    dispatch = telegram.d.private_json(Path(config['dispatch_config']))
    store = Store(dispatch['container'], dispatch['database'])
    print(json.dumps(run(store, apply=args.apply, expected_revision=args.expected_revision)))


if __name__ == '__main__':
    main()

"""Operator-only release of the local SUP-000016 claim after external merge.

Retains the original packet, result, error and receipt files; never runs a model.
Preview is read-only. Apply requires the preview revision and takes both worker locks.
"""
import argparse
import copy
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pilot_worker as pilot
import ongoing_worker
import reconcile_sup_000016 as original
from supervisor_board import externally_resolved


CHILD='ongoing-'+original.JOB+'-a0'


def identity(snapshot):
    job=next(j for j in snapshot['jobs'] if j['id']==original.JOB)
    meta=snapshot['supervision']['tasks'][original.TASK]
    if (snapshot['ongoing'].get('lease_active',True) or job.get('child_id')!=CHILD
            or job.get('attempt')!=0 or job.get('source_sha')!=original.SOURCE
            or not externally_resolved(job,snapshot['supervision'])
            or meta['external_resolution'].get('url')!=original.URL
            or meta['external_resolution'].get('merge_sha')!=original.MERGE
            or meta['external_resolution'].get('failed_evidence_digest')!=original.FAILED_DIGEST
            or meta['external_resolution'].get('failed_receipt_sha256')!=original.FAILED_RECEIPT):
        raise ValueError('External resolution or original failed attempt changed')
    return job,meta


def release(coordinator,snapshot,*,apply=False,expected_revision=None):
    job,meta=identity(snapshot)
    revision=snapshot['supervision']['revision']
    with coordinator.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM tasks WHERE id=?',(CHILD,)).fetchone()
        if not row:raise ValueError('Original local claim is missing')
        before=dict(row)
        packet=json.loads(row['packet'])
        if (packet.get('repository') not in (original.REPO,'https://github.com/'+original.REPO)
                or packet.get('branch')!='main' or packet.get('owner')!='gemini'
                or packet.get('source',{}).get('sha')!=original.SOURCE
                or set(packet.get('write_paths',[]))!=set(job.get('write_paths',[]))):
            raise ValueError('Local packet differs from original failed claim')
        if row['state']=='closed':
            table=db.execute("SELECT name FROM sqlite_master WHERE name='external_claim_releases'").fetchone()
            receipt=db.execute('SELECT record FROM external_claim_releases WHERE id=?',(CHILD,)).fetchone() if table else None
            if not receipt or json.loads(receipt['record'])['resolution']!=meta['external_resolution']:
                raise ValueError('Closed claim has no matching release audit')
            return {'state':'already_released','task_id':original.TASK,'revision':revision}
        if row['state'] not in ('blocked','human_review_required'):
            raise ValueError('Unfinished or running local claim stays held')
        if not apply:return {'state':'preview','task_id':original.TASK,'child_state':row['state'],'revision':revision}
        if expected_revision!=revision:raise ValueError('Board changed; preview again')
        record={'task_id':original.TASK,'revision':revision,'original_row':before,
                'released_at':datetime.now(timezone.utc).isoformat(),'actor':'Operator external-merge reconciliation',
                'resolution':copy.deepcopy(meta['external_resolution'])}
        db.execute('CREATE TABLE IF NOT EXISTS external_claim_releases (id TEXT PRIMARY KEY,record TEXT NOT NULL)')
        db.execute('INSERT INTO external_claim_releases VALUES(?,?)',
                   (CHILD,json.dumps(record,allow_nan=False,separators=(',',':'))))
        db.execute('UPDATE tasks SET state="closed" WHERE id=?',(CHILD,))
        after=dict(db.execute('SELECT * FROM tasks WHERE id=?',(CHILD,)).fetchone())
        if after!={**before,'state':'closed'}:raise RuntimeError('Original claim evidence changed')
    return {'state':'released','task_id':original.TASK,'revision':revision,'original_evidence_preserved':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--expected-revision',type=int)
    args=parser.parse_args()
    if args.apply and args.expected_revision is None:parser.error('Apply requires preview revision')
    config=pilot.read_json(args.config);pilot.configure_tool_path(config)
    worker=ongoing_worker.Worker(config)
    with pilot.local_lock(worker.base.root) as outer:
        if not outer:raise ValueError('Pilot worker is active')
        with pilot.local_lock(worker.root) as inner:
            if not inner:raise ValueError('Ongoing worker is active')
            original.verify_github()
            snapshot=worker.remote({'action':'ongoing_board_data'});job,_=identity(snapshot)
            receipt=worker.root/original.JOB/'0'/'test'/'failure.json'
            if hashlib.sha256(receipt.read_bytes()).hexdigest()!=original.FAILED_RECEIPT:
                raise ValueError('Original failure receipt changed')
            coordinator=worker.for_job(job).coordinator
            if args.apply:
                import sqlite3
                backup=coordinator.db.with_name('coordination.pre-sup16-claim-release.sqlite3')
                if backup.exists():raise ValueError('Release backup already exists; inspect before applying again')
                with coordinator.connect() as db,closing(sqlite3.connect(backup)) as target:db.backup(target)
            print(json.dumps(release(coordinator,snapshot,apply=args.apply,expected_revision=args.expected_revision)))


if __name__=='__main__':main()

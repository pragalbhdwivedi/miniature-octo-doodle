"""Operator-only fresh-source admission after SUP-000023 failed before inference."""
import argparse
import copy
import json
from pathlib import Path
import re

import supervisor_board as board

JOB='intake-sup-000023'
TASK='SUP-000023'


def rebind(state,*,expected_revision,old_sha,new_sha,paths_sha256):
    def change(candidate):
        ledger=candidate['supervision'];ongoing=candidate['ongoing']
        job=next(j for j in ongoing['jobs'] if j['id']==JOB)
        if (ledger['revision']!=expected_revision or ongoing.get('lease')
                or job.get('supervisor_id')!=TASK or job.get('source_sha')!=old_sha
                or job.get('state')!='blocked' or job.get('blocked_stage')!='admit'
                or job.get('attempt') not in (0,1) or job.get('child_id')
                or (job.get('attempt')==1 and job.get('recovery')!='Operator fresh-source admission; original pre-inference failure retained')
                or any(job.get(k) for k in ('coding','tests','review','publication'))
                or any(re.fullmatch('[a-f0-9]{40}',s or '') is None for s in (old_sha,new_sha))
                or old_sha==new_sha or re.fullmatch('[a-f0-9]{64}',paths_sha256 or '') is None):
            raise ValueError('Only the exact unstarted SUP-000023 admission can be rebound')
        meta=ledger['tasks'][TASK]
        meta.setdefault('source_rebindings',[]).append({'original_job':copy.deepcopy(job),
            'new_source_sha':new_sha,'unchanged_paths_sha256':paths_sha256,
            'actor':'Operator pre-inference source reconciliation','at':board._instant(None).isoformat()})
        job.update(source_sha=new_sha,state='queued',attempt=1,
                   recovery='Operator fresh-source admission; original pre-inference failure retained')
        job.pop('blocked_stage',None);job.pop('error',None)
        board._event(ledger,board._instant(None).isoformat(),'Operator pre-inference source reconciliation',
                     TASK,'source_rebinding','Unstarted admission rebound from '+old_sha+' to '+new_sha+'; no model replay.')
        return {'state':'queued','task_id':TASK,'attempt':1,'source_sha':new_sha,'revision':ledger['revision']}
    return board._transaction(state,change)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--expected-revision',type=int,required=True)
    parser.add_argument('--old-sha',required=True)
    parser.add_argument('--new-sha',required=True)
    parser.add_argument('--paths-sha256',required=True)
    args=parser.parse_args()
    # Operator has verified equal admitted files at both commits and absence of
    # the coordinator child under the Windows worker locks before this CAS.
    import controller_telegram as telegram
    from pilot_server import Store
    config=telegram.d.private_json(args.config)
    dispatch=telegram.d.private_json(Path(config['dispatch_config']))
    store=Store(dispatch['container'],dispatch['database'])
    print(json.dumps(store.mutate(lambda state:rebind(state,expected_revision=args.expected_revision,
        old_sha=args.old_sha,new_sha=args.new_sha,paths_sha256=args.paths_sha256))))


if __name__=='__main__':main()

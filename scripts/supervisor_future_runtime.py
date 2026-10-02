"""Operator RPC bridge for future planning; browser controls only queue requests.

The operator supplies registered scopes. Model output never supplies executable
paths, commands, credentials, or catalog entries. Intake admission stays separate.
"""
import copy
from datetime import datetime, timezone
import supervisor_board as board
import supervisor_future as future


def reconcile(s, now):
    b=s['supervision']
    for task in b.get('future',{}).get('tasks',[]):
        intake=next((x for x in b['intake'] if x['id']==task.get('intake_id')),None)
        if not intake:continue
        job=next((x for x in s['ongoing']['jobs'] if x.get('intake_id')==intake['id']),None)
        if job:
            if task['state']=='queued':future.mark_admitted(s,task['id'],intake['id'],now)
            if job.get('state') in ('blocked','needs_owner'):
                future.mark_blocked(s,task['id'],'Coder evidence is held for technical recovery; independent tasks may continue.',now)
                continue
            if task['state']=='blocked':future.mark_admitted(s,task['id'],intake['id'],now)
            # Dependencies require integration, not just an independently reviewed draft.
            if job.get('pr_observation',{}).get('state')=='merged' and task['state'] in ('admitted','review_ready'):
                future.mark_completed(s,task['id'],now)
            elif job.get('state')=='draft_ready' and task['state']=='admitted':
                future.mark_review_ready(s,task['id'],now)
        elif intake['state']=='needs_scope':
            task.update(state='needs_scope',reason=intake.get('error','Scope admission required'),updated_at=now)


def rpc(s,r):
    now=datetime.now(timezone.utc).isoformat()
    def change(candidate):
        b=board._ensure(candidate,now)
        before=copy.deepcopy(b.get('future'))
        action=r['action']
        if action=='ongoing_future_seed':
            result=future.seed(candidate,r['entries'],now)
        elif action=='ongoing_future_prepare':
            reconcile(candidate,now)
            result=future.promote(candidate,r['scope_ids'],now)
            if candidate['ongoing']['enabled']:
                for task in list(b.get('future',{}).get('tasks',[])):
                    if task['state']!='ready':continue
                    # Stable future identity prevents duplicate intake after a lost receipt.
                    intake=next((i for i in b['intake'] if i.get('future_id')==task['id']),None)
                    if intake is None:
                        sid=board._allocate(b)
                        intake={'id':sid,'future_id':task['id'],'scope_hint':task['scope_id'],
                            'project':task['project'],'title':task['title'],'prompt':task['prompt'],
                            'state':'planned','created_at':now,'updated_at':now,'priority':task['priority'],
                            'paused':False,'owner':'unassigned'}
                        b['intake'].append(intake)
                    future.mark_intake(candidate,task['id'],intake['id'],now)
            result={'ok':True,'future':future.public(candidate,now)}
        elif action=='ongoing_future_request':
            result=future.request_generation(candidate,r['request_id'],now)
        elif action=='ongoing_future_begin':
            o=candidate['ongoing'];today=now[:10]
            if not o['enabled'] or o.get('lease'):return {'execute':False,'reason':'paused_or_busy'}
            if o.get('day')!=today:o.update(day=today,calls=0)
            if o['calls']>=o['policy']['max_calls_per_day']:return {'execute':False,'reason':'daily_model_limit'}
            result=future.begin_generation(candidate,r['request_id'],now)
            if result.get('execute'):o['calls']+=1
        elif action=='ongoing_future_finish':
            result=future.finish_generation(candidate,r['request_id'],r['proposals'],r['model'],now)
            if before!=b.get('future'):
                import pilot_state
                pilot_state.message(candidate,'Supervisor · Windows worker\n'+str(len(result.get('added',[])))+
                    ' new future tasks are ready for scope checks. Planned by '+r['model']+
                    '. I will refill the next ten as eligible work completes. Coding and PR checks follow separately.',
                    {'inline_keyboard':[[{'text':'View future tasks','url':'https://control.aadi.dgoi.local/#future'}]]})
        elif action=='ongoing_future_fail':
            result=future.fail_generation(candidate,r['request_id'],r['error'],now)
        else:raise ValueError('Unknown future operator action')
        if before!=b.get('future'):
            board._event(b,now,'Supervisor planner',None,action,'Future backlog updated; execution scope is independently admitted.')
        return result
    return board._transaction(s,change)

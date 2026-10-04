"""Deterministic offline contracts for metadata, commands and audit retention."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import supervisor_board as board


class SupervisorBoardTests(unittest.TestCase):
    at='2026-10-02T00:00:00+00:00'

    def setUp(self):
        self.s={'ongoing':{'enabled':True,'lease':None,'jobs':[
            {'id':'identity-one','repo':'aadi','title':'Identity regression','state':'queued',
             'owner':'codex','attempt':0,'operation':'test_addition','write_paths':['tests/test_identity.py'],
             'prompt':'Add one synthetic test.','source_sha':'a'*40},
            {'id':'gateway-one','repo':'gatewayai','title':'Controller regression','state':'queued',
             'owner':'gemini','attempt':0,'operation':'test_addition','write_paths':['tests/test_queue.py'],
             'prompt':'Test a bounded queue.','source_sha':'b'*40}],
            'policy':{'max_calls_per_day':12,'publication':'draft_pr','secret_config':'must-not-render'}},
            'questions':[],'private_credential':'must-not-render'}
        board.ensure(self.s,now=self.at)

    def command(self,action,task='SUP-000001',**kw):
        request={'action':action,'task_id':task,'request_id':'req-'+str(len(self.s['supervision']['requests'])+1),
                 'revision':self.s['supervision']['revision'],**kw}
        return board.action(self.s,request,now=self.at)

    def test_ids_stable_monotonic_across_reorder_restart_intake_and_missing_job(self):
        original={j['id']:j['supervisor_id'] for j in self.s['ongoing']['jobs']}
        self.s['ongoing']['jobs'].reverse()
        board.ensure(self.s,now=self.at)
        self.assertEqual({j['id']:j['supervisor_id'] for j in self.s['ongoing']['jobs']},original)
        planned=self.command('add_task',task=None,project='GatewayAI',title='Next task',text='Review only')
        self.assertEqual(planned['task_id'],'SUP-000003')
        self.s['ongoing']['jobs'].append({'id':'new-job','title':'New admitted task','state':'queued','owner':'local'})
        board.ensure(self.s,now=self.at)
        self.assertEqual(self.s['ongoing']['jobs'][-1]['supervisor_id'],'SUP-000004')
        self.s=json.loads(json.dumps(self.s))
        removed=self.s['ongoing']['jobs'].pop(0)
        retained=next(t for t in board.snapshot(self.s)['tasks'] if t['id']==removed['supervisor_id'])
        self.assertEqual(retained['state'],'retained_missing')
        self.s['ongoing']['jobs'].append(removed)
        board.ensure(self.s,now=self.at)
        self.assertEqual(removed['supervisor_id'],original[removed['id']])

    def test_request_replay_returns_same_result_and_conflicts_are_atomic(self):
        req={'action':'pause','task_id':'SUP-000001','request_id':'same','revision':self.s['supervision']['revision']}
        result=board.action(self.s,req,now=self.at)
        before=copy.deepcopy(self.s)
        self.assertEqual(board.action(self.s,req,now=self.at),result)
        self.assertEqual(self.s,before)
        with self.assertRaises(board.ConflictError):
            board.action(self.s,{**req,'action':'resume'},now=self.at)
        with self.assertRaises(board.ConflictError):
            board.action(self.s,{**req,'request_id':'different'},now=self.at)
        self.assertEqual(self.s,before)

    def test_pause_resume_and_priority_preserve_execution_state_and_lease(self):
        lease={'stage':'codex','job_id':'identity-one','token':'private-token'}
        self.s['ongoing']['lease']=copy.deepcopy(lease)
        self.s['ongoing']['jobs'][0]['state']='coding'
        self.command('pause')
        self.assertTrue(self.s['ongoing']['jobs'][0]['supervision_paused'])
        self.command('priority',priority=5)
        self.assertEqual(self.s['ongoing']['jobs'][0]['supervision_priority'],5)
        self.command('pause',task=None)
        self.assertFalse(self.s['ongoing']['enabled'])
        self.command('resume',task=None)
        self.assertTrue(self.s['ongoing']['enabled'])
        self.assertTrue(self.s['ongoing']['jobs'][0]['supervision_paused'])
        self.command('resume')
        self.assertFalse(self.s['ongoing']['jobs'][0]['supervision_paused'])
        self.assertEqual(self.s['ongoing']['lease'],lease)
        self.assertEqual(self.s['ongoing']['jobs'][0]['state'],'coding')

    def test_safe_correction_preserves_scope_attempt_and_prior_evidence(self):
        job=self.s['ongoing']['jobs'][0]
        job.update(state='draft_ready',coding={'route':{'model':'observed-coder'},'proposal':'old'},
                   tests={'passed':True},review={'verdict':'pass'})
        board.record(self.s,now=self.at)
        before=copy.deepcopy(self.s['ongoing']['jobs'][0])
        result=self.command('request_changes',text='Add the missing boundary assertion.')
        correction=self.s['supervision']['corrections'][0]
        self.assertEqual(result['state'],'rerun_waiting')
        self.assertEqual(board.snapshot(self.s)['tasks'][0]['review_state'],'changes_requested')
        self.assertEqual(correction['requested_attempt'],1)
        self.assertEqual(self.s['ongoing']['jobs'][0],before)
        evidence=self.s['supervision']['evidence'][correction['evidence_digest']]
        self.assertEqual(evidence['coding']['proposal'],'old')
        self.s['ongoing']['jobs'][0]['coding']['proposal']='new'
        board.record(self.s,now='2026-10-02T00:01:00+00:00')
        self.assertEqual(self.s['supervision']['evidence'][correction['evidence_digest']]['coding']['proposal'],'old')
        self.assertEqual(len(self.s['supervision']['corrections']),1)

    def test_ambiguous_blocked_or_leased_correction_never_prepares_retry(self):
        for state,lease in [('blocked',None),('coding',None),('queued',{'job_id':'identity-one'}),
                            ('draft_ready',{'job_ids':['identity-one','gateway-one']}),
                            ('queued',{'stage':'plan','job_id':None})]:
            with self.subTest(state=state,lease=lease):
                self.s['ongoing']['jobs'][0]['state']=state
                self.s['ongoing']['lease']=lease
                result=self.command('request_changes',text='Please inspect the saved result.')
                self.assertEqual(result['state'],'reconciliation_required')
                self.assertIsNone(self.s['supervision']['corrections'][-1]['requested_attempt'])
                self.assertEqual(self.s['ongoing']['jobs'][0]['attempt'],0)
                self.assertEqual(self.s['ongoing']['lease'],lease)

    def test_add_task_is_planned_and_ask_is_linked_without_admission(self):
        count=len(self.s['ongoing']['jobs'])
        added=self.command('add_task',task=None,project='AADI',title='Proposed extension',text='Investigate test coverage.')
        self.assertEqual(len(self.s['ongoing']['jobs']),count)
        self.assertEqual(added['state'],'planned')
        self.command('ask',task=added['task_id'],text='What evidence is needed?')
        self.assertEqual(self.s['questions'][0]['task_id'],added['task_id'])
        self.assertEqual(self.s['questions'][0]['kind'],'ask')
        self.assertEqual(self.s['questions'][0]['state'],'pending')
        planned=next(t for t in board.snapshot(self.s)['tasks'] if t['id']==added['task_id'])
        self.assertEqual(planned['owner'],'unassigned')
        self.assertEqual(planned['state'],'planned')

    def test_mark_reviewed_is_not_merge_or_execution_authority(self):
        job_before=copy.deepcopy(self.s['ongoing']['jobs'][0])
        self.command('mark_reviewed',text='Reviewed the saved proposal; retain as a draft.')
        self.assertEqual(self.s['ongoing']['jobs'][0],job_before)
        self.assertEqual(board.snapshot(self.s)['tasks'][0]['review_state'],'reviewed')

    def test_progress_record_is_deterministic_and_hourly_digest_fires_once(self):
        initial=self.s['supervision']['revision']
        self.assertEqual(board.record(self.s,now=self.at)['changed'],[])
        self.assertEqual(self.s['supervision']['revision'],initial)
        self.s['ongoing']['jobs'][0]['state']='ready_test'
        result=board.record(self.s,now='2026-10-02T00:30:00+00:00')
        self.assertEqual(result['changed'],['SUP-000001'])
        self.assertFalse(result['digest_due'])
        self.assertTrue(board.record(self.s,now='2026-10-02T01:00:00+00:00')['digest_due'])
        revision=self.s['supervision']['revision']
        self.assertFalse(board.record(self.s,now='2026-10-02T01:00:00+00:00')['digest_due'])
        self.assertEqual(self.s['supervision']['revision'],revision)
        self.s['ongoing']['enabled']=False
        self.assertFalse(board.record(self.s,now='2026-10-02T03:00:00+00:00')['digest_due'])
        self.assertEqual(sum(e['action']=='digest_due' for e in self.s['supervision']['events']),1)

    def test_confidence_unknown_without_observation_and_explicitly_uncalibrated(self):
        snap=board.snapshot(self.s)
        self.assertEqual(snap['tasks'][0]['coder_model'],'unknown')
        self.assertIsNone(snap['tasks'][0]['coder_confidence'])
        self.s['ongoing']['jobs'][0]['coding']={'route':{'model':'actual-model'},'confidence':8,
                                               'confidence_reason':'Observed bounded test evidence.'}
        self.s['ongoing']['jobs'][0]['review']={'route':{'model':'independent-model'},'confidence':105,'verdict':'pass'}
        snap=board.snapshot(self.s)
        self.assertEqual(snap['tasks'][0]['coder_model'],'actual-model')
        self.assertEqual(snap['tasks'][0]['coder_confidence'],8)
        self.assertIsNone(snap['tasks'][0]['reviewer_confidence'])
        self.assertIn('uncalibrated',snap['tasks'][0]['confidence_reason'])
        self.assertIn('Observed bounded test evidence.',snap['tasks'][0]['confidence_reason'])
        self.assertFalse(snap['tasks'][0]['progress']['tests_passed'])

    def test_full_repository_names_map_to_projects(self):
        self.s['ongoing']['jobs'][0]['repo']='pragalbhdwivedi/aadi'
        self.s['ongoing']['jobs'][1]['repo']='pragalbhdwivedi/miniature-octo-doodle'
        self.assertEqual([t['project'] for t in board.snapshot(self.s)['tasks']],['AADI','GatewayAI'])

    def test_snapshot_allowlist_redaction_pr_scope_and_detachment(self):
        job=self.s['ongoing']['jobs'][0]
        job['prompt']='password=hidden-123 safe request'
        job['coding']={'raw_private_source':'must-not-render','route':{'model':'model-x','api_key':'must-not-render'}}
        job['publication']={'pull_request':{'url':'https://evil.invalid/leak?token=secret'}}
        snap=board.snapshot(self.s,now=self.at)
        encoded=json.dumps(snap)
        self.assertNotIn('must-not-render',encoded)
        self.assertNotIn('hidden-123',encoded)
        self.assertNotIn('evil.invalid',encoded)
        self.assertEqual(snap['tasks'][0]['pr_url'],'')
        job['publication']['pull_request']['url']='https://github.com/pragalbhdwivedi/aadi/pull/17'
        self.assertEqual(board.snapshot(self.s)['tasks'][0]['pr_number'],17)
        snap['tasks'][0]['title']='Changed display'
        self.assertEqual(self.s['ongoing']['jobs'][0]['title'],'Identity regression')

    def test_documents_have_five_views_and_full_audit_without_silent_loss(self):
        self.s['ongoing']['jobs'][0]['state']='draft_ready'
        board.record(self.s,now=self.at)
        self.command('request_changes',text='Check one assertion.')
        for index in range(105):
            self.command('mark_reviewed',text='Review note '+str(index))
        snap=board.snapshot(self.s)
        self.assertEqual(len(snap['events']),100)
        self.assertGreater(snap['events_omitted'],0)
        docs=board.documents(self.s)
        self.assertEqual(set(docs),{'future_supervisor_tasks.md','active_supervisor_tasks.md',
            'completed_supervisor_tasks.md','rerun_supervision_tasks.md','supervisor_audit.md'})
        self.assertIn('SUP\\-000001',docs['completed_supervisor_tasks.md'])
        self.assertIn('SUP\\-000002',docs['future_supervisor_tasks.md'])
        self.assertIn('rerun\\_waiting',docs['rerun_supervision_tasks.md'])
        for event in self.s['supervision']['events']:
            self.assertIn('- '+str(event['sequence'])+' |',docs['supervisor_audit.md'])
        self.assertIn('Review note 0',docs['supervisor_audit.md'])
        self.assertIn('Review note 104',docs['supervisor_audit.md'])

    def test_storage_limit_rejects_atomically_without_audit_eviction(self):
        before=copy.deepcopy(self.s)
        with patch.object(board,'MAX_BYTES',len(json.dumps(self.s).encode())):
            with self.assertRaises(board.StorageLimitError):
                self.command('ask',text='x'*2000)
        self.assertEqual(self.s,before)

    def test_successful_board_mutations_preserve_surrounding_reducer_references(self):
        ongoing=self.s['ongoing'];jobs=ongoing['jobs'];job=jobs[0]
        metadata=self.s['supervision'];meta=metadata['tasks']['SUP-000001']
        events=metadata['events']
        self.command('priority',priority=4)
        board.ensure(self.s,now=self.at)
        job['state']='draft_ready'
        board.record(self.s,now=self.at)
        self.command('request_changes',text='Revise this assertion')
        corrections=metadata['corrections'];correction=corrections[0]
        board.record(self.s,now=self.at)
        self.assertIs(self.s['ongoing'],ongoing)
        self.assertIs(self.s['ongoing']['jobs'],jobs)
        self.assertIs(self.s['ongoing']['jobs'][0],job)
        self.assertIs(self.s['supervision'],metadata)
        self.assertIs(metadata['tasks']['SUP-000001'],meta)
        self.assertIs(metadata['events'],events)
        self.assertIs(metadata['corrections'][0],correction)
        correction['state']='running';job['attempt']=1
        self.assertEqual(self.s['supervision']['corrections'][0]['state'],'running')
        self.assertEqual(self.s['ongoing']['jobs'][0]['attempt'],1)

    def test_invalid_commands_rejected_without_mutation(self):
        for fields in ({'action':'merge'}, {'action':'priority','priority':True},
                       {'action':'priority','priority':6}, {'action':'priority','priority':0}, {'action':'request_changes','text':''},
                       {'action':'add_task','project':'Production','title':'No','text':'No'},
                       {'action':'pause','task_id':'SUP-999999'}):
            before=copy.deepcopy(self.s)
            request={'request_id':'invalid','revision':self.s['supervision']['revision'],
                     'task_id':'SUP-000001',**fields}
            with self.assertRaises(ValueError):board.action(self.s,request,now=self.at)
            self.assertEqual(self.s,before)

    def test_operator_merge_resolves_display_without_rewriting_failed_attempt(self):
        job=self.s['ongoing']['jobs'][1]
        job.update(state='blocked',error='Source validation failed; no replay.',
                   coding={'proposal':'invalid original candidate'},tests={'passed':False})
        board.record(self.s,now=self.at)
        meta=self.s['supervision']['tasks']['SUP-000002']
        digest=meta['history'][-1]['evidence_digest']
        original_job=copy.deepcopy(job)
        original_history=copy.deepcopy(meta['history'])
        original_evidence=copy.deepcopy(self.s['supervision']['evidence'][digest])
        revision=self.s['supervision']['revision']
        fields={'expected_revision':revision,'task_id':'SUP-000002','job_id':'gateway-one',
                'source_sha':'b'*40,'failed_evidence_digest':digest,'failed_receipt_sha256':'f'*64,
                'pr_url':'https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/59',
                'head_sha':'c'*40,'merge_sha':'d'*40,
                'note':'Operator fix merged after the original candidate failed validation.'}
        result=board.record_operator_merge(self.s,now=self.at,**fields)
        self.assertEqual(result['state'],'completed')
        self.assertEqual(job,original_job)
        self.assertEqual(meta['history'],original_history)
        self.assertEqual(self.s['supervision']['evidence'][digest],original_evidence)
        task=next(t for t in board.snapshot(self.s)['tasks'] if t['id']=='SUP-000002')
        self.assertEqual((task['state'],task['display_state'],task['original_state']),
                         ('completed','completed','blocked'))
        self.assertEqual(task['review_state'],'merged_external')
        self.assertEqual(task['pr_url'],fields['pr_url'])
        self.assertFalse(task['progress']['tests_passed'])
        self.assertFalse(task['progress']['review_passed'])
        self.assertIn('Source validation failed',task['error'])
        docs=board.documents(self.s)
        self.assertIn('SUP\\-000002',docs['completed_supervisor_tasks.md'])
        self.assertNotIn('SUP\\-000002',docs['active_supervisor_tasks.md'])
        self.assertEqual(self.s['supervision']['events'][-1]['action'],'external_resolution')
        after=copy.deepcopy(self.s)
        with self.assertRaises(board.ConflictError):
            board.record_operator_merge(self.s,now=self.at,**fields)
        self.assertEqual(self.s,after)

    def test_operator_merge_rejects_wrong_failed_evidence_atomically(self):
        job=self.s['ongoing']['jobs'][1]
        job.update(state='blocked',tests={'passed':False})
        board.record(self.s,now=self.at)
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):
            board.record_operator_merge(self.s,expected_revision=self.s['supervision']['revision'],
                task_id='SUP-000002',job_id='gateway-one',source_sha='b'*40,
                failed_evidence_digest='0'*64,failed_receipt_sha256='f'*64,
                pr_url='https://github.com/pragalbhdwivedi/miniature-octo-doodle/pull/59',
                head_sha='c'*40,merge_sha='d'*40,note='Original candidate was invalid.',now=self.at)
        self.assertEqual(self.s,before)


if __name__=='__main__':
    unittest.main()

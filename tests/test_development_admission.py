"""Intake lineage and exact replay across uncertain controller delivery."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import development_admission as admission
import ongoing_state
import pilot_state
import supervisor_board as board
import supervisor_runtime


class DevelopmentAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.now=datetime(2026,10,2,12,tzinfo=timezone.utc)
        self.state=pilot_state.make_state('a'*40);self.state['batch']['state']='completed'
        ongoing_state.install(self.state,[]);board.ensure(self.state)
        result=board.action(self.state,{'action':'add_task','request_id':'new-feature','revision':self.state['supervision']['revision'],
            'project':'AADI','title':'Implement a useful feature','text':'Implement the approved validation behavior with regression coverage.'})
        self.task_id=result['task_id'];self.catalog=self.root/'catalog.json';self.catalog.write_text('[]')
        scope={'repository':'pragalbhdwivedi/aadi','owner':'gemini','complexity':'complex',
            'description':'Public application validation logic','parent_issue':8,
            'paths':['src/app.py','tests/test_existing.py','tests/test_new.py'],
            'write_paths':['src/app.py','tests/test_new.py'],
            'test_files':['src/app.py','tests/test_existing.py','tests/test_new.py']}
        profile={'image':'sha256:'+'b'*64,'commands':[['python','-m','unittest','discover','-s','tests']],
            'acceptance_tests':['tests/test_existing.py'],'timeout_seconds':90,'minimum_tests':1}
        self.config={'development_enabled':True,'development_scopes':{'validation':scope},
            'development_profiles':{'validation':profile},'ongoing_catalog':str(self.catalog)}
        self.chat=Mock(return_value={'profile':'validation','reason':'The registered module implements this behavior.'})
        self.project=SimpleNamespace(repository='pragalbhdwivedi/aadi',coordinator=SimpleNamespace(
            source=Mock(return_value={'sha':'a'*40,'files':{'src/app.py':'source'}})))
        self.worker=SimpleNamespace(base=SimpleNamespace(chat=self.chat),for_job=Mock(return_value=self.project))
        self.observer=SimpleNamespace(config=self.config,root=self.root,worker=self.worker,remote=self.remote)
        self.calls=[];self.uncertain=False
        self.refresh=patch.object(admission,'refresh_source',return_value=True).start();self.addCleanup(patch.stopall)

    def remote(self,request):
        self.calls.append(copy.deepcopy(request))
        if request['action']=='ongoing_sync':
            if self.uncertain:raise TimeoutError('Delivery is unknown')
            result=ongoing_state.rpc(self.state,request);board.ensure(self.state);return result
        return supervisor_runtime.rpc(self.state,request)

    def data(self):return supervisor_runtime.rpc(self.state,{'action':'ongoing_board_data'})
    def admit(self):return admission.admit_intake(self.observer,self.data(),{},self.now)

    def test_free_text_admits_one_scoped_job_preserving_sup_id(self):
        result=self.admit();self.assertEqual(result['state'],'admitted')
        job=self.state['ongoing']['jobs'][0]
        self.assertEqual(job['supervisor_id'],self.task_id)
        self.assertEqual(job['intake_id'],self.task_id)
        self.assertEqual(job['source_sha'],'a'*40)
        self.assertEqual(job['operation'],'development_change')
        self.assertEqual(job['write_paths'],self.config['development_scopes']['validation']['write_paths'])
        self.assertEqual(self.state['supervision']['intake'][0]['state'],'admitted')
        self.assertEqual(self.state['supervision']['next_id'],2)
        self.assertEqual(self.admit()['state'],'no_intake');self.chat.assert_called_once()
        self.assertEqual(len(json.loads(self.catalog.read_text())),1)

    def test_uncertain_model_is_not_repeated_on_poll(self):
        self.chat.side_effect=TimeoutError('Unknown inference')
        with self.assertRaises(TimeoutError):self.admit()
        self.chat.side_effect=None
        self.assertEqual(self.admit()['state'],'no_intake');self.chat.assert_called_once()
        self.assertEqual(json.loads(self.catalog.read_text()),[])

    def test_uncertain_delivery_replays_persisted_exact_job_after_base_advance(self):
        self.uncertain=True
        with self.assertRaises(TimeoutError):self.admit()
        persisted=json.loads(self.catalog.read_text())
        self.assertEqual(persisted[0]['source_sha'],'a'*40)
        self.project.coordinator.source.return_value={'sha':'c'*40,'files':{}}
        self.uncertain=False
        result=self.admit()
        self.assertEqual(result['state'],'admitted')
        self.assertEqual(json.loads(self.catalog.read_text()),persisted)
        self.assertEqual(self.state['ongoing']['jobs'][0]['source_sha'],'a'*40)
        self.chat.assert_called_once()

    def test_outside_scope_becomes_explicit_hold_without_catalog_change(self):
        self.chat.return_value={'profile':'none','reason':'This requests production credentials.'}
        self.assertEqual(self.admit()['state'],'needs_scope')
        self.assertEqual(self.state['supervision']['intake'][0]['state'],'needs_scope')
        self.assertEqual(self.admit()['state'],'no_intake');self.chat.assert_called_once()
        self.assertEqual(json.loads(self.catalog.read_text()),[])

    def test_suggested_scope_requires_independent_writable_scope_match(self):
        self.state['supervision']['intake'][0]['scope_hint']='validation'
        self.chat.return_value={'profile':'none','reason':'The suggested profile cannot edit the required source.'}
        self.assertEqual(self.admit()['state'],'needs_scope')
        prompt=self.chat.call_args.args[1][0]['content']
        self.assertIn('"suggested_profile": "validation"',prompt)
        self.assertIn('write_paths; paths alone may be read-only context',prompt)
        self.assertEqual(json.loads(self.catalog.read_text()),[])

    def test_held_gemini_attempt_does_not_reserve_coder_across_projects(self):
        snapshot=self.data()
        snapshot['jobs'].append({'id':'held-gateway','state':'blocked','child_id':'claim',
            'repository':'pragalbhdwivedi/miniature-octo-doodle','owner':'gemini',
            'write_paths':['gateway/jev.py']})
        result=admission.admit_intake(self.observer,snapshot,{},self.now)
        self.assertEqual(result['state'],'admitted')
        self.assertEqual(self.state['ongoing']['jobs'][0]['intake_id'],self.task_id)

    def test_held_write_paths_still_prevent_conflicting_admission(self):
        snapshot=self.data()
        snapshot['jobs'].append({'id':'held-aadi','state':'blocked','child_id':'claim',
            'repository':'pragalbhdwivedi/aadi','owner':'gemini',
            'write_paths':['src/app.py']})
        self.assertEqual(admission.admit_intake(self.observer,snapshot,{},self.now)['state'],'no_intake')
        self.assertEqual(json.loads(self.catalog.read_text()),[])

    def test_pause_skips_classification_and_priority_survives_admission(self):
        item=self.state['supervision']['intake'][0];item.update(paused=True,priority=5)
        self.assertEqual(self.admit()['state'],'no_intake');self.chat.assert_not_called()
        item['paused']=False;self.admit()
        self.assertEqual(self.state['ongoing']['jobs'][0]['supervision_priority'],5)

    def test_second_job_cannot_rebind_existing_intake_identity(self):
        self.admit();second=copy.deepcopy(self.state['ongoing']['jobs'][0]);second['id']='another-job'
        second.pop('supervisor_id');self.state['ongoing']['jobs'].append(second)
        before=copy.deepcopy(self.state['supervision'])
        with self.assertRaises(ValueError):board.ensure(self.state)
        self.assertEqual(self.state['supervision'],before)

    def test_changed_intake_cannot_reuse_saved_classification(self):
        self.uncertain=True
        with self.assertRaises(TimeoutError):self.admit()
        self.state['supervision']['intake'][0]['prompt']='A different scope request'
        with self.assertRaisesRegex(ValueError,'Intake changed'):self.admit()
        self.chat.assert_called_once()

    def test_full_owner_request_is_preserved_past_old_prompt_ceiling(self):
        prompt='Implement the approved behavior. '+('Retain compatibility. '*70)+'Final requirement: include the failure recovery path.'
        self.assertGreater(len(prompt),1000)
        self.state['supervision']['intake'][0]['prompt']=prompt
        self.admit()
        self.assertEqual(self.state['ongoing']['jobs'][0]['prompt'],prompt)
        self.assertEqual(json.loads(self.catalog.read_text())[0]['prompt'],prompt)


if __name__=='__main__':unittest.main()

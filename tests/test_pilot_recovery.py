import json
import unittest
import test_coder_coordination as fixture
import coder_coordination as coordination
import pilot_state as state


class RecoveryTests(unittest.TestCase):
    setUp=fixture.CoordinationTests.setUp
    command=fixture.CoordinationTests.command
    admit=fixture.CoordinationTests.admit
    claimed=fixture.CoordinationTests.claimed

    def saved_failure(self):
        original=self.coordinator.coder
        def coder(executable,prompt,directory):
            value=original(executable,prompt,directory)
            (directory/'codex-answer.json').write_text(json.dumps(value))
            (directory/'codex-events.jsonl').write_text('{"type":"turn.completed"}\n')
            return value
        self.coordinator.coder=coder
        self.coordinator.chat=lambda *args:{'invalid':'response'}
        task,token=self.claimed();self.coordinator.submit(task,token,self.value)
        with self.assertRaises(coordination.agent.AgentError):self.coordinator.advance(task,token)
        return task

    def test_recover_saved_candidates_without_inference_or_claim_replay(self):
        task=self.saved_failure();calls=list(self.calls)
        result=self.coordinator.recover_saved(task,'Owner approved saved-proposal-only recovery')
        self.assertEqual(self.calls,calls)
        self.assertEqual(result['advisory_status'],'unavailable')
        self.assertEqual(result['state'],'human_review_required')
        self.assertFalse(result['publication'])
        with self.assertRaises(coordination.agent.AgentError):self.coordinator.recover_saved(task,'Duplicate recovery denied')

    def test_recovery_denies_tampered_original_output(self):
        task=self.saved_failure()
        (self.coordinator.root/task/'codex-answer.json').write_text(json.dumps({**self.value,'summary':'Changed'}))
        with self.assertRaises(coordination.agent.AgentError):self.coordinator.recover_saved(task,'Owner approved saved-proposal-only recovery')
        self.assertEqual(self.coordinator.status()['tasks'][0]['state'],'blocked')


class RecoveryBudgetTests(unittest.TestCase):
    def test_recovery_is_exact_once_and_cannot_dispatch_new_coders(self):
        value=state.make_state('a'*40);value['batch'].update(state='blocked',gpt_calls=6)
        for task in value['tasks'][:2]:task['state']='verified'
        value['tasks'][2].update(state='blocked',coordination_task_id='saved-third')
        evidence={'task_id':'saved-third','source_sha':'a'*40,'state':'human_review_required','advisory_status':'unavailable'}
        state.begin_recovery(value,evidence)
        self.assertEqual(value['batch']['max_gpt_calls'],8)
        self.assertEqual(value['tasks'][2]['state'],'ready_test')
        with self.assertRaises(ValueError):state.begin_recovery(value,evidence)
        self.assertEqual(state.reserve(value,'dispatch',value['tasks'][2]),{'action':'idle'})
        self.assertEqual(value['batch']['gpt_calls'],6)


if __name__=='__main__':unittest.main()

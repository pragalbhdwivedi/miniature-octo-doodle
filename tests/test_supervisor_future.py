"""Offline planning, scheduling and generation replay contracts."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import supervisor_future as future


class FutureTests(unittest.TestCase):
    at = '2026-10-02T12:00:00+00:00'
    later = '2026-10-02T12:05:00+00:00'

    def setUp(self):
        self.s = {'ongoing': {'enabled': True}, 'supervision': {'revision': 7}}

    def entry(self, n, **updates):
        return {'id': 'FUT-'+str(n).zfill(6), 'project': 'AADI',
                'title': 'Future change '+str(n), 'prompt': 'Implement bounded change '+str(n),
                'scope_id': 'erp_manifest', 'priority': 3, 'evidence': ['tools/check_erp.py'],
                'acceptance': ['Validate the existing behavior and new boundary'],
                'dependencies': [], 'risk': 'routine', **updates}

    def seed(self, count=20):
        return future.seed(self.s, [self.entry(i) for i in range(1, count+1)], self.at)

    def proposals(self, n=1):
        return [{k: v for k, v in self.entry(i).items() if k != 'id'} for i in range(1, n+1)]

    def start(self, request_id='generate-one'):
        future.request_generation(self.s, request_id, self.at)
        return future.begin_generation(self.s, request_id, self.at)

    def promote(self, at=None):
        return future.promote(self.s, ['erp_manifest'], at or self.at)

    def admit(self, n):
        fid, sid = 'FUT-'+str(n).zfill(6), 'SUP-'+str(n).zfill(6)
        future.mark_intake(self.s, fid, sid, self.at)
        future.mark_admitted(self.s, fid, sid, self.at)
        return fid

    def test_seed_100_replay_and_public_isolation(self):
        self.assertEqual(len(self.seed(100)['added']), 100)
        before = copy.deepcopy(self.s)
        self.assertEqual(self.seed(100)['added'], [])
        self.assertEqual(self.s, before)
        result = future.public(self.s, self.at)
        self.assertEqual(result['total'], 100)
        self.assertEqual(result['counts'], {'planned': 100})
        result['tasks'][0]['prompt'] = 'changed'
        self.assertEqual(self.s, before)
        self.assertEqual(self.s['supervision']['future']['next_id'], 101)

    def test_missing_public_never_initializes_state(self):
        self.assertEqual(future.public({}, self.at)['tasks'], [])
        self.assertEqual(self.s['supervision'], {'revision': 7})

    def test_mutation_preserves_board_and_task_references(self):
        self.seed()
        board = self.s['supervision']
        task = board['future']['tasks'][0]
        self.promote()
        self.assertIs(board, self.s['supervision'])
        self.assertIs(task, board['future']['tasks'][0])
        self.assertEqual(task['state'], 'ready')

    def test_seed_conflict_duplicate_and_validation_are_atomic(self):
        self.seed(1)
        before = copy.deepcopy(self.s)
        bad_entries = [self.entry(1, prompt='Different'), self.entry(2, prompt=self.entry(1)['prompt']),
                       self.entry(2, prompt='x'*1001), self.entry(2, commands=['shell']),
                       self.entry(2, priority=True), self.entry(2, evidence=['../secret']),
                       self.entry(2, evidence=['C:/secrets']), self.entry(2, evidence=[]),
                       self.entry(2, acceptance=[])]
        for entry in bad_entries:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                future.seed(self.s, [self.entry(3), entry], self.at)
            self.assertEqual(self.s, before)

    def test_unknown_or_cyclic_dependencies_reject_whole_batch(self):
        for entries in ([self.entry(1, dependencies=['FUT-000009'])],
                        [self.entry(1, dependencies=['FUT-000002']), self.entry(2, dependencies=['FUT-000001'])]):
            before = copy.deepcopy(self.s)
            with self.assertRaises(ValueError):
                future.seed(self.s, entries, self.at)
            self.assertEqual(self.s, before)

    def test_retained_500_limit_rejects_without_deletion(self):
        self.seed(500)
        before = copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError, 'full'):
            future.seed(self.s, [self.entry(501)], self.at)
        self.assertEqual(self.s, before)

    def test_generation_requires_full_ten_slots_before_reserving_inference(self):
        self.seed(491)
        before = copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError, 'full'):
            future.request_generation(self.s, 'no-capacity', self.at)
        self.assertEqual(self.s, before)

    def test_seed_cannot_consume_pending_or_running_generation_reservation(self):
        self.seed(489)
        future.request_generation(self.s, 'reserved', self.at)
        future.seed(self.s, [self.entry(490)], self.at)
        before = copy.deepcopy(self.s)
        with self.assertRaisesRegex(ValueError, 'reserved'):
            future.seed(self.s, [self.entry(491)], self.at)
        self.assertEqual(self.s, before)
        future.begin_generation(self.s, 'reserved', self.at)
        with self.assertRaisesRegex(ValueError, 'reserved'):
            future.seed(self.s, [self.entry(491)], self.at)
        proposals = [{k: v for k, v in self.entry(i).items() if k != 'id'} for i in range(491, 501)]
        result = future.finish_generation(self.s, 'reserved', proposals, 'model', self.at)
        self.assertEqual(len(result['added']), 10)
        self.assertEqual(len(self.s['supervision']['future']['tasks']), 500)

    def test_promotes_ten_and_repeated_ticks_do_not_overfill(self):
        self.seed(100)
        first = self.promote()
        self.assertEqual(len(first['ready']), 10)
        self.assertEqual(first['next_batch_at'], self.later)
        self.assertEqual(self.promote(self.later)['ready'], [])
        self.assertEqual(future.public(self.s, self.at)['counts']['ready'], 10)

    def test_priority_is_deterministic(self):
        self.seed(12)
        self.s['supervision']['future']['tasks'][11]['priority'] = 5
        result = self.promote()
        self.assertIn('FUT-000012', result['ready_ids'])
        self.assertNotIn('FUT-000010', result['ready_ids'])

    def test_review_ready_refills_but_does_not_complete_dependencies(self):
        entries = [self.entry(i) for i in range(1, 13)]
        entries[10]['dependencies'] = ['FUT-000001']
        future.seed(self.s, entries, self.at)
        self.promote()
        fid = self.admit(1)
        future.mark_review_ready(self.s, fid, self.at)
        self.assertEqual(self.promote()['ready'], [])
        self.assertEqual(self.promote(self.later)['ready_ids'], ['FUT-000012'])
        future.mark_completed(self.s, fid, self.later)
        future.mark_review_ready(self.s, self.admit(2), self.later)
        self.assertEqual(self.promote('2026-10-02T12:10:00+00:00')['ready_ids'], ['FUT-000011'])

    def test_override_only_bypasses_refill_delay(self):
        entries = [self.entry(i) for i in range(1, 15)]
        entries[10]['risk'] = 'needs_owner'
        entries[11]['scope_id'] = 'unregistered'
        entries[12]['not_before'] = '2026-10-03T00:00:00Z'
        future.seed(self.s, entries, self.at)
        self.promote()
        future.mark_review_ready(self.s, self.admit(1), self.at)
        future.request_override(self.s, self.at)
        self.s['ongoing']['enabled'] = False
        self.assertEqual(self.promote()['state'], 'paused')
        self.assertTrue(future.public(self.s, self.at)['override_pending'])
        self.s['ongoing']['enabled'] = True
        self.assertEqual(self.promote()['ready_ids'], ['FUT-000014'])
        by_id = {t['id']: t for t in future.public(self.s, self.at)['tasks']}
        self.assertEqual(by_id['FUT-000011']['state'], 'needs_owner')
        self.assertEqual(by_id['FUT-000012']['state'], 'needs_scope')
        self.assertEqual(by_id['FUT-000013']['state'], 'scheduled')
        self.assertFalse(future.public(self.s, self.at)['override_pending'])

    def test_task_time_normalized_and_dependencies_must_be_completed(self):
        future.seed(self.s, [self.entry(1, not_before='2026-10-02T17:35:00+05:30'),
                             self.entry(2, dependencies=['FUT-000001'])], self.at)
        self.assertEqual(self.promote()['ready'], [])
        self.assertEqual(self.promote(self.later)['ready_ids'], ['FUT-000001'])

    def test_blocked_work_releases_slot_preserves_link_and_holds_dependencies(self):
        entries = [self.entry(i) for i in range(1, 13)]
        entries[10]['dependencies'] = ['FUT-000001']
        future.seed(self.s, entries, self.at)
        self.promote()
        fid = self.admit(1)
        future.mark_blocked(self.s, fid, 'Independent review needs correction', self.at)
        before = copy.deepcopy(self.s)
        future.mark_blocked(self.s, fid, 'Independent review needs correction', self.later)
        self.assertEqual(self.s, before)
        self.assertEqual(self.promote(self.later)['ready_ids'], ['FUT-000012'])
        blocked = future.public(self.s, self.at)['tasks'][0]
        self.assertEqual(blocked['intake_id'], 'SUP-000001')
        self.assertEqual(blocked['state'], 'blocked')
        with self.assertRaises(ValueError):
            future.mark_admitted(self.s, fid, 'SUP-000099', self.later)
        future.mark_admitted(self.s, fid, 'SUP-000001', self.later)
        self.assertEqual(future.public(self.s, self.at)['tasks'][0]['state'], 'admitted')

    def test_intake_links_and_transition_audit_are_idempotent(self):
        self.seed(2)
        self.promote()
        future.mark_intake(self.s, 'FUT-000001', 'SUP-000099', self.at)
        before = copy.deepcopy(self.s)
        future.mark_intake(self.s, 'FUT-000001', 'SUP-000099', self.later)
        self.assertEqual(self.s, before)
        with self.assertRaises(ValueError):
            future.mark_intake(self.s, 'FUT-000002', 'SUP-000099', self.at)
        with self.assertRaises(ValueError):
            future.mark_admitted(self.s, 'FUT-000001', 'SUP-000100', self.at)
        with self.assertRaises(ValueError):
            future.mark_completed(self.s, 'FUT-000001', self.at)
        future.mark_admitted(self.s, 'FUT-000001', 'SUP-000099', self.at)
        future.mark_completed(self.s, 'FUT-000001', self.later)
        self.assertEqual(future.public(self.s, self.at)['counts']['completed'], 1)

    def test_generation_request_and_running_replay_never_execute_again(self):
        request = future.request_generation(self.s, 'one', self.at)
        self.assertEqual(future.request_generation(self.s, 'one', self.later), request)
        with self.assertRaises(ValueError):
            future.request_generation(self.s, 'two', self.at)
        self.assertTrue(future.begin_generation(self.s, 'one', self.at)['execute'])
        restored = copy.deepcopy(self.s)
        self.assertFalse(future.begin_generation(restored, 'one', self.later)['execute'])
        self.assertEqual(self.s, restored)
        with self.assertRaises(ValueError):
            future.begin_generation(self.s, 'unknown', self.at)

    def test_paused_generation_stays_pending(self):
        future.request_generation(self.s, 'one', self.at)
        self.s['ongoing']['enabled'] = False
        self.assertFalse(future.begin_generation(self.s, 'one', self.at)['execute'])
        self.assertEqual(future.public(self.s, self.at)['generation']['state'], 'pending')

    def test_finish_dedupes_assigns_ids_and_exact_replay(self):
        self.seed(1)
        self.start()
        proposals = self.proposals(3)
        proposals.append(copy.deepcopy(proposals[2]))
        result = future.finish_generation(self.s, 'generate-one', proposals, 'configured-model', self.at)
        self.assertEqual(result['added'], ['FUT-000002', 'FUT-000003'])
        self.assertEqual(len(result['duplicates']), 2)
        before = copy.deepcopy(self.s)
        self.assertEqual(future.finish_generation(self.s, 'generate-one', proposals, 'configured-model', self.later), result)
        self.assertEqual(self.s, before)
        with self.assertRaises(ValueError):
            future.finish_generation(self.s, 'generate-one', proposals, 'other-model', self.later)
        future.request_generation(self.s, 'next', self.later)
        self.assertEqual(future.request_generation(self.s, 'generate-one', self.later), result)
        self.assertEqual(future.public(self.s, self.at)['generation']['request_id'], 'next')

    def test_model_cannot_supply_execution_authority_or_timestamp(self):
        self.start()
        before = copy.deepcopy(self.s)
        for key, value in [('id', 'FUT-123456'), ('commands', ['execute']), ('write_paths', ['src/x.py']),
                           ('state', 'admitted'), ('not_before', self.at), ('owner', 'codex')]:
            proposals = self.proposals()
            proposals[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                future.finish_generation(self.s, 'generate-one', proposals, 'model', self.at)
            self.assertEqual(self.s, before)

    def test_model_unknown_scope_stays_unadmitted(self):
        self.start()
        proposals = self.proposals()
        proposals[0]['scope_id'] = 'unknown-but-valid-name'
        future.finish_generation(self.s, 'generate-one', proposals, 'model', self.at)
        self.assertEqual(self.promote()['ready'], [])
        self.assertEqual(future.public(self.s, self.at)['tasks'][0]['state'], 'needs_scope')

    def test_explicit_empty_scope_never_becomes_ready(self):
        future.seed(self.s, [self.entry(1, scope_id='')], self.at)
        self.assertEqual(self.promote()['ready'], [])
        self.assertEqual(future.public(self.s, self.at)['tasks'][0]['state'], 'needs_scope')
        with self.assertRaises(ValueError):
            future.promote(self.s, [''], self.at)

    def test_large_or_invalid_generation_is_atomic_and_never_restarts(self):
        self.start()
        before = copy.deepcopy(self.s)
        for proposals in (self.proposals(11), [None], {'tasks': []},
                          [{**self.proposals()[0], 'dependencies': ['FUT-999999']}]):
            with self.assertRaises(ValueError):
                future.finish_generation(self.s, 'generate-one', proposals, 'model', self.at)
            self.assertEqual(self.s, before)
        self.assertFalse(future.begin_generation(self.s, 'generate-one', self.later)['execute'])

    def test_failure_receipt_is_terminal_and_deduplicated(self):
        self.start()
        result = future.fail_generation(self.s, 'generate-one', 'Provider unavailable', self.at)
        self.assertEqual(future.fail_generation(self.s, 'generate-one', 'Provider unavailable', self.later), result)
        self.assertFalse(future.begin_generation(self.s, 'generate-one', self.later)['execute'])
        with self.assertRaises(ValueError):
            future.finish_generation(self.s, 'generate-one', self.proposals(), 'model', self.later)
        self.assertEqual(future.request_generation(self.s, 'generate-one', self.later), result)
        self.assertEqual(future.request_generation(self.s, 'new-request', self.later)['state'], 'pending')

    def test_audit_limit_fails_closed_without_losing_tasks(self):
        self.seed(1)
        before = copy.deepcopy(self.s)
        with patch.object(future, 'MAX_EVENTS', 1), self.assertRaisesRegex(ValueError, 'audit is full'):
            self.promote()
        self.assertEqual(self.s, before)

    def test_naive_timestamp_rejected_without_mutation(self):
        before = copy.deepcopy(self.s)
        with self.assertRaises(ValueError):
            future.seed(self.s, [self.entry(1)], '2026-10-02T12:00:00')
        self.assertEqual(self.s, before)

    def test_cancelled_proposal_is_never_repromoted_or_a_completed_dependency(self):
        future.seed(self.s, [self.entry(1), self.entry(2, dependencies=['FUT-000001'])], self.at)
        self.promote()
        future.cancel_task(self.s, 'FUT-000001', 'Factual premise was wrong', self.at)
        before = copy.deepcopy(self.s)
        future.cancel_task(self.s, 'FUT-000001', 'Factual premise was wrong', self.later)
        self.assertEqual(self.s, before)
        future.request_override(self.s, self.at)
        self.assertEqual(self.promote(self.later)['ready'], [])
        self.assertEqual(future.public(self.s, self.at)['tasks'][0]['state'], 'cancelled')
        self.assertEqual(future.public(self.s, self.at)['tasks'][1]['state'], 'planned')

    def test_cancel_does_not_touch_linked_or_held_work(self):
        self.seed(2)
        self.promote()
        self.admit(1)
        with self.assertRaises(ValueError):
            future.cancel_task(self.s, 'FUT-000001', 'Cannot silently cancel live work', self.at)
        self.s['supervision']['future']['tasks'][1]['state'] = 'needs_owner'
        with self.assertRaises(ValueError):
            future.cancel_task(self.s, 'FUT-000002', 'Must not bypass hold', self.at)


if __name__ == '__main__':
    unittest.main()

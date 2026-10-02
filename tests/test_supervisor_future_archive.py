"""Durable future archival, immutable evidence, and capacity recovery contracts."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import supervisor_archive as task_archive
import supervisor_future as future
import supervisor_future_archive as archive
from test_supervisor_archive import fixture as job_fixture, NOW
import test_supervisor_future as future_tests


def fixture(count=25):
    state = job_fixture(count)
    entries = [future_tests.FutureTests().entry(n, prompt=f'Implement real task {n}: '+('bounded acceptance; '*30)) for n in range(1, count+1)]
    future.seed(state, entries, NOW)
    for n, task in enumerate(state['supervision']['future']['tasks'], 1):
        task.update(state='completed', intake_id=f'SUP-{n:06d}', completed_at=NOW.isoformat())
        state['ongoing']['jobs'][n-1]['intake_id'] = task['intake_id']
        state['supervision']['tasks'][task['intake_id']]['observed']['pr_number'] = n
    return state


class Store:
    def __init__(self, state):
        self.state = copy.deepcopy(state)

    def mutate(self, operation):
        candidate = copy.deepcopy(self.state)
        result = operation(candidate)
        self.state = candidate
        return result


class FutureArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)/'private'
        self.state = fixture()

    def test_lossless_backup_retains_twenty_and_indexes_dependencies(self):
        before = copy.deepcopy(self.state)
        candidate, receipt = archive.archive_state(self.state, self.directory, now=NOW)
        self.assertEqual(self.state, before)
        self.assertEqual(archive.ArchiveStore(self.directory).read(receipt['archive_id'])['state'], before)
        f = candidate['supervision']['future']
        self.assertEqual(len(f['tasks']), 20)
        self.assertEqual(len(f['archived_tasks']), 5)
        self.assertEqual(f['next_id'], 26)
        self.assertEqual(candidate['ongoing'], before['ongoing'])
        self.assertEqual(f['archived_tasks']['FUT-000001']['pr_number'], 1)
        self.assertNotIn('prompt', f['archived_tasks']['FUT-000001'])
        future.seed(candidate, [future_tests.FutureTests().entry(26, dependencies=['FUT-000001'])], NOW)
        result = future.promote(candidate, ['erp_manifest'], NOW)
        self.assertEqual(result['ready_ids'], ['FUT-000026'])
        self.assertEqual(future.public(candidate, NOW)['archived_total'], 5)

    def test_archived_seed_replay_and_semantic_deduplication_remain_effective(self):
        original = self.state['supervision']['future']['tasks'][0]
        spec = {k: original[k] for k in future.FIELDS | {'id'}}
        candidate, receipt = archive.archive_state(self.state, self.directory, now=NOW)
        self.assertEqual(future.seed(candidate, [spec], NOW)['added'], [])
        for changed in ({**spec, 'prompt': 'Changed'}, {**spec, 'id': 'FUT-000030'}):
            with self.assertRaises(ValueError):
                future.seed(candidate, [changed], NOW)
        future.request_generation(candidate, 'dedupe-archived', NOW)
        future.begin_generation(candidate, 'dedupe-archived', NOW)
        result = future.finish_generation(candidate, 'dedupe-archived',
                    [{k: v for k, v in spec.items() if k != 'id'}], 'model', NOW)
        self.assertEqual(result['added'], [])
        self.assertEqual(result['duplicates'][0]['existing_id'], 'FUT-000001')

    def test_verified_archive_reclaims_capacity_without_reusing_ids(self):
        state = fixture(50)
        future.seed(state, [future_tests.FutureTests().entry(i) for i in range(51, 501)], NOW)
        with self.assertRaises(ValueError):
            future.request_generation(state, 'capacity-full', NOW)
        candidate, receipt = archive.archive_state(state, self.directory, now=NOW)
        self.assertEqual(receipt['task_count'], 30)
        future.request_generation(candidate, 'after-archive', NOW)
        future.begin_generation(candidate, 'after-archive', NOW)
        proposals = [{k: v for k, v in future_tests.FutureTests().entry(i).items() if k != 'id'} for i in range(501, 511)]
        result = future.finish_generation(candidate, 'after-archive', proposals, 'model', NOW)
        self.assertEqual(result['added'], [f'FUT-{i:06d}' for i in range(501, 511)])

    def test_terminal_receipts_and_full_audit_survive_verified_compaction(self):
        future.request_generation(self.state, 'done', NOW)
        future.begin_generation(self.state, 'done', NOW)
        result = future.finish_generation(self.state, 'done', [], 'model', NOW)
        future.request_generation(self.state, 'still-running', NOW)
        future.begin_generation(self.state, 'still-running', NOW)
        before = copy.deepcopy(self.state)
        candidate, receipt = archive.archive_state(self.state, self.directory, now=NOW)
        f = candidate['supervision']['future']
        self.assertEqual([r['request_id'] for r in f['requests']], ['still-running'])
        self.assertEqual(future.request_generation(candidate, 'done', NOW), result)
        self.assertEqual(future.finish_generation(candidate, 'done', [], 'model', NOW), result)
        self.assertFalse(future.begin_generation(candidate, 'still-running', NOW)['execute'])
        self.assertEqual(f['events'][0]['kind'], 'archive_verified')
        saved = archive.ArchiveStore(self.directory).read(receipt['archive_id'])
        self.assertEqual(saved['state']['supervision']['future']['events'], before['supervision']['future']['events'])

    def test_unmerged_live_held_and_pending_corrections_cannot_be_archived(self):
        for mutate in (lambda s: s['supervision']['future']['tasks'][0].update(state='blocked'),
                       lambda s: s['ongoing']['jobs'][0]['pr_observation'].update(state='open', merged=False),
                       lambda s: s['ongoing']['jobs'][0].update(state='local_ready'),
                       lambda s: s['ongoing']['jobs'][0].update(supervision_paused=True),
                       lambda s: s['supervision']['corrections'].append({'task_id': 'SUP-000001', 'state': 'pending'})):
            with self.subTest(mutate=mutate):
                state = copy.deepcopy(self.state)
                mutate(state)
                self.assertNotIn('FUT-000001', archive.plan(state, now=NOW)['task_ids'])

    def test_prior_job_archive_is_read_and_verified_before_future_compaction(self):
        cold, job_receipt = task_archive.archive_state(self.state, self.directory, now=NOW)
        candidate, receipt = archive.archive_state(cold, self.directory, now=NOW)
        self.assertEqual(receipt['task_count'], 5)
        self.assertEqual(candidate['supervision']['future']['archived_tasks']['FUT-000001']['source_archive_id'], job_receipt['archive_id'])
        target = self.directory/(job_receipt['archive_id']+'.json')
        target.write_bytes(b'corrupt')
        with self.assertRaises(archive.ArchiveError):
            archive.archive_state(cold, self.directory, now=NOW)

    def test_corrupt_readback_and_changed_cas_source_never_compact(self):
        store = archive.ArchiveStore(self.directory)
        proposal = archive.plan(self.state, now=NOW)
        receipt = store.persist(self.state, proposal)
        changed = copy.deepcopy(self.state)
        changed['supervision']['revision'] += 1
        with self.assertRaises(archive.ArchiveError):
            archive.compact(changed, receipt, store)
        target = self.directory/(receipt['archive_id']+'.json')
        target.write_bytes(b'corrupt')
        with self.assertRaises(archive.ArchiveError):
            archive.compact(self.state, receipt, store)

    def test_repeated_persist_is_immutable_and_receipt_tampering_is_rejected(self):
        store = archive.ArchiveStore(self.directory)
        proposal = archive.plan(self.state, now=NOW)
        receipt = store.persist(self.state, proposal)
        self.assertEqual(store.persist(self.state, proposal), receipt)
        self.assertEqual(len(list(self.directory.glob('*.json'))), 1)
        with self.assertRaises(archive.ArchiveError):
            archive.compact(self.state, {**receipt, 'task_count': 999}, store)

    def test_malformed_or_cross_repository_pr_identity_never_proves_completion(self):
        for change in ({'number': True}, {'head_sha': None},
                       {'repository': 'pragalbhdwivedi/miniature-octo-doodle'}):
            state = copy.deepcopy(self.state)
            state['ongoing']['jobs'][0]['pr_observation'].update(change)
            self.assertNotIn('FUT-000001', archive.plan(state, now=NOW)['task_ids'])

    def test_failed_write_and_failed_cas_keep_hot_state_and_allow_retry(self):
        store = Store(self.state)
        request = {'action': 'ongoing_future_archive', 'revision': 25}
        config = {'enabled': True, 'directory': str(self.directory)}
        with patch.object(archive.os, 'fsync', side_effect=OSError('simulated')):
            with self.assertRaises(OSError):
                archive.run(store, request, config)
        self.assertEqual(store.state, self.state)
        self.assertFalse(list(self.directory.glob('*.json')))
        self.assertFalse(list(self.directory.glob('*.tmp')))
        class FailedCAS(Store):
            def mutate(self, operation):
                operation(copy.deepcopy(self.state))
                raise RuntimeError('CAS conflict')
        conflict = FailedCAS(self.state)
        with self.assertRaises(RuntimeError):
            archive.run(conflict, request, config)
        self.assertEqual(conflict.state, self.state)
        self.assertTrue(list(self.directory.glob('*.json')))
        self.assertEqual(archive.run(store, request, config)['archived'], 5)

    def test_operator_revision_configuration_and_path_authority(self):
        store = Store(self.state)
        request = {'action': 'ongoing_future_archive', 'revision': 25}
        config = {'enabled': True, 'directory': str(self.directory)}
        for req, cfg in ((request, {}), ({**request, 'directory': '/other'}, config),
                         ({**request, 'revision': 24}, config), ({**request, 'revision': True}, config)):
            with self.assertRaises(archive.ArchiveError):
                archive.run(store, req, cfg)
        self.assertEqual(store.state, self.state)
        result = archive.run(store, request, config)
        self.assertEqual((result['archived'], result['revision']), (5, 26))
        with self.assertRaises(archive.ArchiveError):
            archive.run(store, request, config)

    def test_small_backlog_noop_does_not_create_archive_directory(self):
        candidate, receipt = archive.archive_state(fixture(20), self.directory, now=NOW)
        self.assertIsNone(receipt)
        self.assertFalse(self.directory.exists())

    def test_archive_index_limit_fails_closed_and_preserves_snapshot(self):
        before = copy.deepcopy(self.state)
        with patch.object(future, 'MAX_ARCHIVED', 4), self.assertRaisesRegex(archive.ArchiveError, 'index is full'):
            archive.archive_state(self.state, self.directory, now=NOW)
        self.assertEqual(self.state, before)
        self.assertTrue(list(self.directory.glob('*.json')))


if __name__ == '__main__':
    unittest.main()

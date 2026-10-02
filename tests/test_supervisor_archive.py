import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import supervisor_archive as archive

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


def fixture(count=25):
    board = {'version': 1, 'revision': count, 'next_id': count+1, 'tasks': {}, 'by_key': {},
             'events': [], 'requests': {'request-1': {'fingerprint': 'saved', 'result': {'ok': True}}},
             'evidence': {}, 'corrections': [], 'intake': []}
    jobs = []
    for n in range(1, count+1):
        sid, key = f'SUP-{n:06d}', f'task-{n}'
        url = f'https://github.com/pragalbhdwivedi/aadi/pull/{n}'
        evidence = {'coding': {'candidate': 'retained evidence '+str(n)+'x'*2000}}
        h = archive.digest(evidence)
        board['evidence'][h] = evidence
        board['by_key'][key] = sid
        meta = {'id': sid, 'key': key, 'created_at': (NOW-timedelta(days=count-n)).isoformat(),
                'updated_at': NOW.isoformat(), 'review_state': 'merged',
                'history': [{'evidence_digest': h, 'state': 'draft_ready'}],
                'observed': {'id': sid, 'key': key, 'title': f'Task {n}', 'project': 'AADI', 'pr_url': url}}
        board['tasks'][sid] = meta
        board['events'].append({'sequence': n, 'task_id': sid, 'detail': 'Evidence retained',
                                'timestamp': NOW.isoformat(), 'actor': 'test', 'action': 'registered'})
        jobs.append({'id': key, 'supervisor_id': sid, 'state': 'draft_ready', 'title': f'Task {n}',
                     'coding': evidence['coding'], 'publication': {'pull_request': {'url': url}},
                     'pr_observed_at': NOW.isoformat(),
                     'pr_observation': {'url': url, 'repository': 'pragalbhdwivedi/aadi', 'number': n,
                         'state': 'merged', 'draft': False, 'open': False, 'merged': True, 'head_sha': 'a'*40}})
    return {'ongoing': {'jobs': jobs, 'lease': None, 'enabled': True}, 'supervision': board,
            'questions': [], 'leases': {}, 'outbox': [], 'unrelated': {'keep': ['unchanged']}}


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'private'
        self.store = archive.ArchiveStore(self.root)
        self.state = fixture()

    def prepare(self):
        proposal = archive.plan(self.state, now=NOW)
        return self.store.persist(self.state, proposal)

    def test_lossless_snapshot_readback_and_compaction_keep_twenty(self):
        before = copy.deepcopy(self.state)
        candidate, receipt = archive.archive_state(self.state, self.root, now=NOW)
        self.assertEqual(self.state, before)
        self.assertEqual(self.store.read(receipt['archive_id'])['state'], before)
        self.assertEqual(len(candidate['ongoing']['jobs']), 20)
        self.assertEqual(candidate['supervision']['next_id'], 26)
        self.assertEqual(candidate['supervision']['by_key'], before['supervision']['by_key'])
        self.assertEqual(candidate['supervision']['requests'], before['supervision']['requests'])
        self.assertEqual(candidate['supervision']['events'][:-1], before['supervision']['events'])
        self.assertEqual(candidate['unrelated'], before['unrelated'])
        self.assertEqual(candidate['supervision']['events'][-1]['sequence'], 26)
        self.assertEqual(len(candidate['supervision']['archived_tasks']), 5)
        recovered = self.store.task(candidate, 'SUP-000001')
        self.assertEqual(recovered['task'], before['ongoing']['jobs'][0])
        self.assertEqual(recovered['metadata'], before['supervision']['tasks']['SUP-000001'])
        self.assertTrue(recovered['evidence'])
        self.assertTrue(recovered['events'])
        self.assertLess(len(archive.encoded(candidate)), len(archive.encoded(before)))

    def test_archive_write_is_idempotent_and_does_not_overwrite(self):
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(first, second)
        self.assertEqual(len(list(self.root.glob('*.json'))), 1)
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_interrupted_write_leaves_hot_state_untouched(self):
        before = copy.deepcopy(self.state)
        with patch.object(archive.os, 'fsync', side_effect=OSError('simulated failure')):
            with self.assertRaises(OSError):
                archive.archive_state(self.state, self.root, now=NOW)
        self.assertEqual(before, self.state)
        self.assertFalse(list(self.root.glob('*.json')))
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_corrupt_archive_prevents_compaction_and_retrieval(self):
        receipt = self.prepare()
        path = self.root / (receipt['archive_id']+'.json')
        path.write_text('{}', encoding='utf-8')
        with self.assertRaises(archive.ArchiveError):
            archive.compact(self.state, receipt, self.store, now=NOW)
        self.assertEqual(len(self.state['ongoing']['jobs']), 25)

    def test_changed_state_rejects_stale_cas_candidate(self):
        receipt = self.prepare()
        self.state['questions'].append({'task_id': 'SUP-000001', 'state': 'pending'})
        with self.assertRaises(archive.ArchiveError):
            archive.compact(self.state, receipt, self.store, now=NOW)
        self.assertEqual(len(self.state['ongoing']['jobs']), 25)

    def test_missing_archive_and_stale_evidence_fail_closed(self):
        receipt = self.prepare()
        with self.assertRaises(archive.ArchiveError):
            archive.compact(self.state, receipt, self.store, now=NOW+timedelta(seconds=901))
        (self.root/(receipt['archive_id']+'.json')).unlink()
        with self.assertRaises(archive.ArchiveError):
            archive.compact(self.state, receipt, self.store, now=NOW)

    def test_pending_interactions_and_dependencies_remain_hot(self):
        self.state['questions'] = [{'task_id': 'SUP-000001', 'state': 'pending'}]
        self.state['supervision']['corrections'] = [{'task_id': 'SUP-000002', 'state': 'running'}]
        self.state['supervision']['pending_reply'] = {'task_id': 'SUP-000003'}
        self.state['outbox'] = [{'task_id': 'SUP-000004', 'state': 'uncertain'}]
        self.state['ongoing']['jobs'][-1]['depends_on'] = ['task-5']
        self.assertIsNone(archive.plan(self.state, now=NOW))

    def test_completed_questions_and_corrections_are_retained(self):
        self.state['questions'] = [{'task_id': 'SUP-000001', 'state': 'answered', 'answer': 'retained'}]
        self.state['supervision']['corrections'] = [{'task_id': 'SUP-000001', 'state': 'completed'}]
        result, _ = archive.archive_state(self.state, self.root, now=NOW)
        self.assertEqual(result['questions'], self.state['questions'])
        self.assertEqual(result['supervision']['corrections'], self.state['supervision']['corrections'])
        self.assertIn('SUP-000001', result['supervision']['archived_tasks'])

    def test_active_lease_blocks_all_archival(self):
        self.state['ongoing']['lease'] = {'job_id': 'task-25'}
        self.assertIsNone(archive.plan(self.state, now=NOW))
        self.state['ongoing']['lease'] = None
        self.state['leases'] = {'q': {'state': 'running'}}
        self.assertIsNone(archive.plan(self.state, now=NOW))

    def test_draft_open_active_future_stale_and_wrong_pr_are_not_archived(self):
        changes = [lambda j: j['pr_observation'].update(state='draft'),
                   lambda j: j['pr_observation'].update(state='open'),
                   lambda j: j.update(state='coding'),
                   lambda j: j.update(pr_observed_at=(NOW+timedelta(seconds=1)).isoformat()),
                   lambda j: j.update(pr_observed_at=(NOW-timedelta(seconds=901)).isoformat()),
                   lambda j: j['pr_observation'].update(url='https://example.test'),
                   lambda j: j['pr_observation'].update(draft=True)]
        for change in changes:
            with self.subTest(change=change):
                candidate = copy.deepcopy(self.state)
                change(candidate['ongoing']['jobs'][0])
                proposal = archive.plan(candidate, now=NOW)
                self.assertNotIn('task-1', proposal['job_ids'])

    def test_shared_evidence_retained_for_hot_tasks(self):
        first = self.state['supervision']['tasks']['SUP-000001']['history'][0]['evidence_digest']
        self.state['supervision']['tasks']['SUP-000025']['history'].append({'evidence_digest': first})
        result, _ = archive.archive_state(self.state, self.root, now=NOW)
        self.assertIn(first, result['supervision']['evidence'])

    def test_noop_at_twenty_and_second_compaction(self):
        state = fixture(20)
        self.assertIsNone(archive.plan(state, now=NOW))
        result, receipt = archive.archive_state(self.state, self.root, now=NOW)
        self.assertIsNotNone(receipt)
        same, second = archive.archive_state(result, self.root, now=NOW)
        self.assertEqual(same, result)
        self.assertIsNone(second)

    def test_archive_index_is_bounded_and_full_evidence_is_not_in_summary(self):
        result, _ = archive.archive_state(self.state, self.root, now=NOW)
        page = archive.history_index(result, offset=1, limit=2)
        self.assertEqual(page['total'], 5)
        self.assertEqual(page['omitted'], 2)
        self.assertEqual(len(page['tasks']), 2)
        self.assertNotIn('retained evidence', json.dumps(page))
        for offset, limit in [(-1, 10), (0, 201), (True, 1)]:
            with self.assertRaises(archive.ArchiveError):
                archive.history_index(result, offset=offset, limit=limit)

    def test_traversal_and_retention_bypass_rejected(self):
        for value in ('../secrets', 'A'*64, '/tmp/file'):
            with self.assertRaises(archive.ArchiveError):
                self.store.read(value)
        with self.assertRaises(archive.ArchiveError):
            archive.plan(self.state, now=NOW, retain=0)
        with self.assertRaises(archive.ArchiveError):
            archive.plan(self.state, now=NOW, fresh_seconds=99999)

    def test_insufficient_compaction_retains_entire_hot_state(self):
        before = copy.deepcopy(self.state)
        with patch.object(archive, 'MAX_HOT_BYTES', 10):
            with self.assertRaises(archive.ArchiveError):
                archive.archive_state(self.state, self.root, now=NOW)
        self.assertEqual(self.state, before)
        self.assertEqual(len(list(self.root.glob('*.json'))), 1)

    def test_receipt_tampering_rejected(self):
        receipt = self.prepare()
        receipt['bytes'] += 1
        with self.assertRaises(archive.ArchiveError):
            archive.compact(self.state, receipt, self.store, now=NOW)

    def test_second_archive_preserves_prior_index_ids_and_readback(self):
        first, receipt1 = archive.archive_state(self.state, self.root, now=NOW)
        expanded = fixture(30)
        for job in expanded['ongoing']['jobs'][-5:]:
            first['ongoing']['jobs'].append(job)
            sid = job['supervisor_id']
            meta = expanded['supervision']['tasks'][sid]
            first['supervision']['tasks'][sid] = meta
            first['supervision']['by_key'][job['id']] = sid
            for row in meta['history']:
                h = row['evidence_digest']
                first['supervision']['evidence'][h] = expanded['supervision']['evidence'][h]
        first['supervision']['next_id'] = 31
        second, receipt2 = archive.archive_state(first, self.root, now=NOW)
        self.assertNotEqual(receipt1['archive_id'], receipt2['archive_id'])
        self.assertEqual(len(second['supervision']['archived_tasks']), 10)
        self.assertEqual(len(second['ongoing']['jobs']), 20)
        self.assertEqual(second['supervision']['next_id'], 31)
        self.assertEqual(self.store.task(second, 'SUP-000001')['task']['id'], 'task-1')
        self.assertEqual(self.store.task(second, 'SUP-000006')['task']['id'], 'task-6')

    def test_readback_failure_prevents_any_hot_mutation(self):
        before = copy.deepcopy(self.state)
        with patch.object(archive.ArchiveStore, 'read', side_effect=archive.ArchiveError('readback failed')):
            with self.assertRaises(archive.ArchiveError):
                archive.archive_state(self.state, self.root, now=NOW)
        self.assertEqual(self.state, before)
        self.assertEqual(len(list(self.root.glob('*.json'))), 1)

    @unittest.skipUnless(archive.os.name == 'posix', 'POSIX archive permissions require Linux')
    def test_linux_private_directory_and_file_permissions_required(self):
        unsafe = self.root / 'unsafe'
        unsafe.mkdir(mode=0o755)
        unsafe.chmod(0o755)  # A previous worker test can leave a restrictive umask.
        with self.assertRaises(archive.ArchiveError):
            archive.ArchiveStore(unsafe)
        receipt = self.prepare()
        (self.root/(receipt['archive_id']+'.json')).chmod(0o644)
        with self.assertRaises(archive.ArchiveError):
            self.store.read(receipt['archive_id'])

    def test_newly_closed_old_task_is_retained_by_closure_time(self):
        for j in self.state['ongoing']['jobs']:
            j['pr_observation']['updated_at'] = (NOW-timedelta(days=1)).isoformat()
        self.state['ongoing']['jobs'][0]['pr_observation']['updated_at'] = NOW.isoformat()
        proposal = archive.plan(self.state, now=NOW)
        self.assertNotIn('task-1', proposal['job_ids'])


if __name__ == '__main__':
    unittest.main()

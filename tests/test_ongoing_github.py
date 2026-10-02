"""Publication authority, ambiguous-write reconciliation and real Git boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ongoing_github as g


class FakeAPI:
    def __init__(self):
        self.rows = {'issues': [], 'pulls': []}
        self.calls = []
        self.lose_response = False
        self.fail_before_write = False

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        bits = path.split('?', 1)[0].strip('/').split('/')
        kind = bits[0]
        if method == 'GET':
            if len(bits) == 2:
                return copy.deepcopy(next(x for x in self.rows[kind] if x['number'] == int(bits[1])))
            return copy.deepcopy(self.rows[kind])
        if self.fail_before_write:
            raise OSError('offline')
        if method == 'POST':
            row = dict(body, number=len(self.rows[kind]) + 1,
                       html_url='https://github.com/' + g.REPOSITORY + '/' + kind + '/1', state='open')
            if kind == 'pulls':
                row['head'] = {'ref': body['head'], 'repo': {'full_name': g.REPOSITORY}}
                row['base'] = {'ref': body['base']}
            self.rows[kind].append(row)
        elif method == 'PATCH':
            row = next(x for x in self.rows[kind] if x['number'] == int(bits[1]))
            row.update(body)
        else:
            raise AssertionError(method)
        if self.lose_response:
            self.lose_response = False
            raise OSError('response lost')
        return copy.deepcopy(row)


class GithubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.api = FakeAPI()
        self.config = {'ledger_path': str(self.root / 'ledger.json')}
        self.client = g.Github(self.config, self.api)

    def test_issue_create_update_and_replay_are_exactly_once(self):
        one = self.client.ensure_issue('job-1', 'Improve tests', 'In progress')
        two = self.client.ensure_issue('job-1', 'Improve tests', 'In progress')
        self.assertEqual(one, two)
        self.client.ensure_issue('job-1', 'Improve tests', 'Blocked: repair needed')
        self.assertEqual([m for m, _, _ in self.api.calls if m != 'GET'], ['POST', 'PATCH'])
        self.assertIn('Blocked: repair needed', self.api.rows['issues'][0]['body'])

    def test_ambiguous_creation_reconciles_without_duplicate(self):
        self.api.lose_response = True
        with self.assertRaises(OSError):
            self.client.ensure_issue('job-1', 'Title', 'Body')
        receipt = self.client.ensure_issue('job-1', 'Title', 'Body')
        self.assertEqual(receipt['number'], 1)
        self.assertEqual(sum(m == 'POST' for m, _, _ in self.api.calls), 1)

    def test_creation_readback_does_not_depend_on_list_freshness(self):
        def lagging(method, path, body=None):
            if method == 'GET' and '?' in path:
                return []
            return self.api(method, path, body)
        client = g.Github(self.config, lagging)
        receipt = client.ensure_issue('job-1', 'Title', 'Body')
        self.assertEqual(receipt['state'], 'confirmed')
        self.assertEqual(sum(m == 'POST' for m, _, _ in self.api.calls), 1)
        self.assertIn(('GET', '/issues/1', None), self.api.calls)

    def test_unobserved_creation_is_not_retried(self):
        self.api.fail_before_write = True
        with self.assertRaises(OSError):
            self.client.ensure_issue('job-1', 'Title', 'Body')
        self.api.fail_before_write = False
        with self.assertRaisesRegex(g.PublishError, 'not replayed'):
            self.client.ensure_issue('job-1', 'Title', 'Body')
        self.assertEqual(sum(m == 'POST' for m, _, _ in self.api.calls), 1)

    def test_ambiguous_update_does_not_overwrite_or_repeat(self):
        self.client.ensure_issue('job-1', 'Title', 'Body')
        self.api.lose_response = True
        with self.assertRaises(OSError):
            self.client.ensure_issue('job-1', 'Title', 'New body')
        self.client.ensure_issue('job-1', 'Title', 'New body')
        self.assertEqual(sum(m == 'PATCH' for m, _, _ in self.api.calls), 1)

    def test_only_owned_open_drafts_can_be_updated(self):
        branch = g.branch_for('job-1')
        receipt = self.client.ensure_draft('job-1', branch, 'Title', 'Body', 2)
        self.assertTrue(receipt['draft'])
        self.assertEqual(receipt['base'], 'Dev')
        self.api.rows['pulls'][0]['draft'] = False
        with self.assertRaisesRegex(g.PublishError, 'draft scope'):
            self.client.ensure_draft('job-1', branch, 'Title', 'New body', 2)
        with self.assertRaises(g.PublishError):
            self.client.ensure_draft('job-1', 'Dev', 'Title', 'Body')
        self.assertEqual(sum(m != 'GET' for m, _, _ in self.api.calls), 1)

    def test_closed_duplicate_and_foreign_scope_refused(self):
        self.client.ensure_issue('job-1', 'Title', 'Body')
        self.api.rows['issues'][0]['state'] = 'closed'
        with self.assertRaisesRegex(g.PublishError, 'closed'):
            self.client.ensure_issue('job-1', 'Title', 'Body')
        self.api.rows['issues'].append(copy.deepcopy(self.api.rows['issues'][0]))
        with self.assertRaisesRegex(g.PublishError, 'Duplicate'):
            self.client.ensure_issue('job-1', 'Title', 'Body')
        with self.assertRaises(g.PublishError):
            g.Github(dict(self.config, repository='owner/other'))


class RealGitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.remote = self.root / 'remote.git'
        self.repo.mkdir()
        self.run_git(self.repo, 'init', '-b', 'Dev')
        self.run_git(self.repo, 'config', 'user.name', 'Test')
        self.run_git(self.repo, 'config', 'user.email', 'test@example.invalid')
        (self.repo / 'tests').mkdir()
        (self.repo / 'tests' / 'sample.py').write_text('before\n')
        self.run_git(self.repo, 'add', '.')
        self.run_git(self.repo, 'commit', '-m', 'base')
        self.sha = self.run_git(self.repo, 'rev-parse', 'HEAD')
        self.run_git(self.repo, 'branch', 'main')
        self.run_git(self.root, 'init', '--bare', str(self.remote))
        self.run_git(self.repo, 'push', str(self.remote), 'Dev', 'main')
        self.remote_patch = patch.object(g, 'REMOTE', str(self.remote))
        self.remote_patch.start()
        self.addCleanup(self.remote_patch.stop)
        self.config = {'repo': str(self.repo), 'worktree_root': str(self.root / 'drafts'),
                       'admitted_paths': ['tests/sample.py'], 'ledger_path': str(self.root / 'ledger.json')}
        self.api = FakeAPI()
        self.client = g.Github(self.config, self.api)
        self.task = {'id': 'sample-task', 'title': 'Improve synthetic coverage', 'body': 'Test only.',
                     'source_sha': self.sha, 'files': {'tests/sample.py': 'after\n'}}

    def run_git(self, cwd, *args):
        r = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(r.stderr)
        return r.stdout.strip()

    def evidence(self):
        return {'source_sha': self.sha, 'artifact_sha256': g.artifact_digest(self.task),
                'tests_passed': True, 'review_passed': True}

    def publish(self):
        return g.publish_candidate(self.config, self.task, self.evidence(), self.client)

    def test_real_publish_update_retains_base_and_disables_hooks(self):
        hooks = self.repo / '.git' / 'hooks'
        hook = hooks / 'pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        first = self.publish()
        self.assertEqual(self.run_git(self.remote, 'rev-parse', 'Dev'), self.sha)
        self.assertEqual(self.run_git(self.remote, 'rev-parse', 'main'), self.sha)
        self.assertEqual((self.repo / 'tests/sample.py').read_text(), 'before\n')
        self.assertEqual(self.run_git(self.remote, 'show', first['branch'] + ':tests/sample.py'), 'after')
        self.assertEqual(self.publish(), first)
        self.task['files']['tests/sample.py'] = 'repaired\n'
        second = self.publish()
        self.assertEqual(self.run_git(self.remote, 'rev-parse', second['commit'] + '^'), first['commit'])
        self.assertEqual(len(self.api.rows['pulls']), 1)
        self.assertEqual(len(self.api.rows['issues']), 1)
        self.assertEqual(self.run_git(self.remote, 'rev-parse', 'Dev'), self.sha)
        self.assertFalse(second['merged'])

    def test_failed_or_changed_evidence_prevents_all_writes(self):
        evidence = self.evidence()
        self.task['files']['tests/sample.py'] = 'changed after review\n'
        with self.assertRaisesRegex(g.PublishError, 'evidence'):
            g.publish_candidate(self.config, self.task, evidence, self.client)
        self.assertEqual(self.api.calls, [])
        self.assertFalse((self.root / 'drafts').exists())

    def test_path_escape_and_unadmitted_file_prevent_writes(self):
        for name in ('../escape', 'tests/../../escape', '.git/config', 'tests\\sample.py', 'other.py'):
            self.task['files'] = {name: 'evil'}
            with self.assertRaises(g.PublishError):
                self.publish()
        self.assertEqual(self.api.calls, [])

    def test_stale_base_refused_before_draft_creation(self):
        (self.repo / 'tests/sample.py').write_text('new base\n')
        self.run_git(self.repo, 'commit', '-am', 'advance Dev')
        self.run_git(self.repo, 'push', str(self.remote), 'Dev')
        with self.assertRaisesRegex(g.PublishError, 'Dev advanced'):
            self.publish()
        self.assertTrue(all(method == 'GET' for method, _, _ in self.api.calls))

    def test_ready_pr_stops_branch_updates_before_push(self):
        first = self.publish()
        self.api.rows['pulls'][0]['draft'] = False
        self.task['files']['tests/sample.py'] = 'repair\n'
        with self.assertRaisesRegex(g.PublishError, 'draft scope'):
            self.publish()
        self.assertEqual(self.run_git(self.remote, 'rev-parse', first['branch']), first['commit'])

    def test_task_repairs_cannot_change_admitted_path_set(self):
        first = self.publish()
        self.config['admitted_paths'].append('tests/new.py')
        self.task['files']['tests/new.py'] = 'extra\n'
        with self.assertRaisesRegex(g.PublishError, 'file scope changed'):
            self.publish()
        self.assertEqual(self.run_git(self.remote, 'rev-parse', first['branch']), first['commit'])

    def test_uncertain_unapplied_push_is_never_retried(self):
        original = g.git
        pushes = []

        def no_push(repo, *args, **kwargs):
            if args[0] == 'push':
                pushes.append(args)
                raise g.PublishError('offline')
            return original(repo, *args, **kwargs)

        with patch.object(g, 'git', no_push):
            with self.assertRaisesRegex(g.PublishError, 'offline'):
                self.publish()
            with self.assertRaisesRegex(g.PublishError, 'Uncertain push'):
                self.publish()
        self.assertEqual(len(pushes), 1)

    def test_lost_push_response_reconciles_without_repeated_push(self):
        original = g.git
        pushes = []

        def ambiguous(repo, *args, **kwargs):
            result = original(repo, *args, **kwargs)
            if args[0] == 'push':
                pushes.append(args)
                raise g.PublishError('Response lost')
            return result

        with patch.object(g, 'git', ambiguous):
            with self.assertRaisesRegex(g.PublishError, 'Response lost'):
                self.publish()
            result = self.publish()
        self.assertEqual(len(pushes), 1)
        self.assertEqual(result['commit'], self.run_git(self.remote, 'rev-parse', result['branch']))


if __name__ == '__main__':
    unittest.main()

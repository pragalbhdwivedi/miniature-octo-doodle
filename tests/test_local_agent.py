import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    'local_agent', Path(__file__).resolve().parents[1]/'scripts/local_agent.py')
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class LocalAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)/'source'
        self.repo.mkdir()
        self.remote = Path(self.temp.name)/'remote.git'
        subprocess.run(['git', 'init', '-q', '--bare', str(self.remote)], check=True)
        self.command('init', '-q', '-b', 'main')
        self.command('remote', 'add', 'origin', str(self.remote))
        original = agent.REPOSITORY
        agent.REPOSITORY = str(self.remote).removesuffix('.git')
        self.addCleanup(setattr, agent, 'REPOSITORY', original)
        (self.repo/'example.py').write_text('def answer():\n    return 41\n', encoding='utf-8')
        self.command('add', 'example.py')
        self.command('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                     'commit', '-q', '-m', 'fixture')
        self.command('push', '-q', 'origin', 'main')

    def command(self, *args):
        subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def chat(model, messages, schema, predict):
        if model == 'coder-fixture':
            return {'summary': 'Increment the result',
                    'proposal': 'Change return 41 to return 42.',
                    'changes': [{'path': 'example.py',
                                 'content': 'def answer():\n    return 42'}]}
        if model == 'supervisor-fixture':
            return {'verdict': 'review', 'findings': ['Check the assertion.']}
        raise AssertionError('Unexpected model')

    def test_two_models_produce_advice_without_edit_or_authority(self):
        original = (self.repo/'example.py').read_bytes()
        record = agent.proposal(self.repo, 'Return 42 from answer', ['example.py'],
                                'coder-fixture', 'supervisor-fixture', self.chat)
        self.assertEqual(record['state'], 'human_review_required')
        self.assertEqual(record['actions_executed'], [])
        self.assertEqual(record['critique']['verdict'], 'review')
        self.assertIn('+    return 42', record['patch'])
        patch_file = self.repo.parent/'candidate.patch'
        patch_file.write_text(record['patch'], encoding='utf-8')
        self.command('apply', '--check', str(patch_file))
        self.assertEqual((self.repo/'example.py').read_bytes(), original)

    def test_dirty_repo_and_sensitive_or_untracked_files_fail_closed(self):
        (self.repo/'example.py').write_text('modified', encoding='utf-8')
        with self.assertRaisesRegex(agent.AgentError, 'uncommitted'):
            agent.proposal(self.repo, 'Task', ['example.py'], 'coder', 'supervisor', self.chat)
        self.command('checkout', '--', 'example.py')
        with self.assertRaisesRegex(agent.AgentError, 'allowlist'):
            agent.source_files(self.repo, ['creds/key.json'])
        with self.assertRaises(agent.AgentError):
            agent.source_files(self.repo, ['untracked.py'])

    def test_model_cannot_authorize_action_or_rewrite_source(self):
        def unsafe_chat(model, messages, schema, predict):
            if model == 'coder':
                return {'summary': 'x', 'proposal': 'proposal', 'changes': []}
            return {'verdict': 'publish', 'findings': []}
        with self.assertRaisesRegex(agent.AgentError, 'Supervisor'):
            agent.proposal(self.repo, 'Task', ['example.py'], 'coder', 'supervisor',
                           unsafe_chat)
        self.assertEqual((self.repo/'example.py').read_text(),
                         'def answer():\n    return 41\n')

    def test_stale_or_mutated_source_fails_closed(self):
        def mutating_chat(model, messages, schema, predict):
            if model == 'coder':
                return {'summary': 'x', 'proposal': 'candidate', 'changes': []}
            (self.repo/'example.py').write_text('changed', encoding='utf-8')
            return {'verdict': 'review', 'findings': []}
        with self.assertRaisesRegex(agent.AgentError, 'uncommitted'):
            agent.proposal(self.repo, 'Task', ['example.py'], 'coder', 'supervisor',
                           mutating_chat)

    def test_origin_must_be_exact_public_allowlist(self):
        self.command('remote', 'set-url', 'origin',
                     'https://github.com/pragalbhdwivedi/aadi.git')
        with self.assertRaisesRegex(agent.AgentError, 'approved public'):
            agent.source_state(self.repo)

    def test_unpublished_or_stale_main_is_denied_before_model_call(self):
        (self.repo/'example.py').write_text('def answer():\n    return 42\n', encoding='utf-8')
        self.command('add', 'example.py')
        self.command('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                     'commit', '-q', '-m', 'unpublished')
        with self.assertRaisesRegex(agent.AgentError, 'current public main'):
            agent.source_state(self.repo)
        self.command('push', '-q', 'origin', 'main')
        self.assertEqual(agent.source_state(self.repo)[1],
                         subprocess.check_output(['git', '-C', str(self.repo),
                                                  'rev-parse', 'HEAD']).decode().strip())


if __name__ == '__main__':
    unittest.main()

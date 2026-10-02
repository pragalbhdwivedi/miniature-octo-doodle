from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import desktop_review as desktop
import test_local_agent as fixture


class DesktopReviewTests(unittest.TestCase):
    command = fixture.LocalAgentTests.command
    chat = staticmethod(fixture.LocalAgentTests.chat)

    def setUp(self):
        fixture.LocalAgentTests.setUp(self)
        original = desktop.agent.REPOSITORY
        desktop.agent.REPOSITORY = str(self.remote).removesuffix('.git')
        self.addCleanup(setattr, desktop.agent, 'REPOSITORY', original)

    def packet(self, owner='gemini-pro'):
        return desktop.prepare(self.repo, 'Return 42', ['example.py'], owner)

    def test_both_desktop_owners_share_local_review_without_edits(self):
        for owner in desktop.OWNERS:
            packet, prompt = self.packet(owner)
            self.assertIn('return 41', prompt)
            candidate = self.chat('coder-fixture', [], {}, 0)
            record = desktop.review(packet, candidate, 'supervisor-fixture', self.chat)
            self.assertEqual(record['desktop_owner'], owner)
            self.assertEqual(record['submitted_candidate_sha256'], desktop.digest(candidate))
            self.assertEqual(record['actions_executed'], [])
            self.assertEqual(record['tests_executed'], [])
            self.assertIn('return 41', (self.repo/'example.py').read_text())

    def test_changed_packet_denied_before_local_model(self):
        packet, _ = self.packet()
        packet['source_digest'] = '0'*64
        def no_call(*args):
            self.fail('Model should not be called')
        with self.assertRaisesRegex(desktop.agent.AgentError, 'source changed'):
            desktop.review(packet, {}, chat=no_call)

    def test_candidate_cannot_expand_paths_or_authority(self):
        packet, _ = self.packet()
        bad = {'summary': 'bad', 'proposal': 'edit private file',
               'changes': [{'path': 'creds/key.json', 'content': 'bad'}]}
        with self.assertRaises(desktop.agent.AgentError):
            desktop.review(packet, bad, chat=lambda *args: self.fail('Unexpected model'))
        with self.assertRaises(desktop.agent.AgentError):
            desktop.review(packet, [], chat=lambda *args: self.fail('Unexpected model'))

    def test_wrong_owner_and_oversized_inputs_denied(self):
        with self.assertRaises(desktop.agent.AgentError):
            self.packet('unknown')
        large = self.repo.parent/'large.json'
        large.write_text('x'*(desktop.agent.MAX_RESPONSE_BYTES+1))
        with self.assertRaisesRegex(desktop.agent.AgentError, 'byte ceiling'):
            desktop.read_json(large)

    def test_rendered_markdown_is_not_silently_repaired(self):
        raw = self.repo.parent/'candidate.json'
        raw.write_text('{"summary":"broken", "content":"""bad escaping"""}')
        with self.assertRaisesRegex(desktop.agent.AgentError, 'plain UTF-8 JSON'):
            desktop.read_json(raw)


if __name__ == '__main__':
    unittest.main()

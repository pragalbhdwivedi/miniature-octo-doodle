import concurrent.futures
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import coder_schedule as s
import test_coder_coordination as fixture


class ScheduleTests(unittest.TestCase):
    setUp = fixture.CoordinationTests.setUp
    command = fixture.CoordinationTests.command
    admit = fixture.CoordinationTests.admit
    claimed = fixture.CoordinationTests.claimed
    conversation = '11111111-2222-3333-4444-555555555555'

    def run_tick(self, sender=None):
        return s.tick(self.coordinator, self.conversation, 'agentapi',
                      sender or (lambda *args: self.calls.append(args)))

    def test_idle_tick_never_sends_or_calls_models(self):
        self.assertEqual(self.run_tick()['state'], 'idle')
        self.assertEqual(self.calls, [])

    def test_concurrent_ticks_and_restart_send_only_once(self):
        self.admit()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.run_tick(), range(2)))
        self.assertCountEqual([r['state'] for r in results], ['notified', 'already_dispatched'])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], self.conversation)
        self.assertIn('test-1', self.calls[0][2])
        self.coordinator = s.Coordinator(self.config)
        self.assertEqual(self.run_tick()['state'], 'already_dispatched')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.coordinator.status()['tasks'][0]['state'], 'queued')

    def test_unknown_delivery_is_not_retried(self):
        self.admit()
        def sender(*args):
            self.calls.append('send')
            raise TimeoutError('ambiguous result')
        self.assertEqual(self.run_tick(sender)['state'], 'delivery_uncertain')
        self.assertEqual(self.run_tick(sender)['state'], 'already_dispatched')
        self.assertEqual(self.run_tick(sender)['dispatch_state'], 'delivery_uncertain')
        self.assertEqual(self.calls, ['send'])

    def test_crash_after_reservation_does_not_repeat(self):
        self.admit()
        def crash(*args):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_tick(crash)
        self.assertEqual(self.run_tick()['state'], 'already_dispatched')
        self.assertEqual(self.run_tick()['dispatch_state'], 'delivery_started')
        self.assertEqual(self.calls, [])

    def test_claimed_task_is_not_interrupted(self):
        self.claimed()
        self.assertEqual(self.run_tick()['state'], 'held')
        self.assertEqual(self.calls, [])

    def test_dirty_source_stops_before_delivery_and_stays_blocked(self):
        self.admit()
        (self.repo/'example.py').write_text('dirty')
        self.assertEqual(self.run_tick()['state'], 'blocked_source')
        self.command('checkout', '--', 'example.py')
        self.assertEqual(self.run_tick()['state'], 'already_dispatched')
        self.assertEqual(self.run_tick()['dispatch_state'], 'blocked_source')
        self.assertEqual(self.calls, [])

    def test_closed_task_allows_new_admission_without_replaying_old(self):
        self.admit()
        self.run_tick()
        self.coordinator.close('test-1', 'Reconciled scheduled delivery; no inference.')
        self.coordinator.admit('test-2', 'Next bounded task', ['example.py'])
        self.assertEqual(self.run_tick()['task_id'], 'test-2')
        self.assertEqual(len(self.calls), 2)

    def test_invalid_conversation_rejected_before_dispatch(self):
        self.admit()
        with self.assertRaises(ValueError):
            s.tick(self.coordinator, 'bad; command', 'agentapi')
        self.assertEqual(self.calls, [])

    def test_heartbeat_and_transport_have_bounded_scope(self):
        result = s.heartbeat(self.coordinator.root, {'state': 'idle'})
        self.assertEqual(json.loads((self.coordinator.root/'schedule-status.json').read_text()), result)
        with patch.object(s.subprocess, 'run') as run:
            run.return_value.returncode = 0
            s.notify('agentapi', self.conversation, 'fixed prompt')
            self.assertEqual(run.call_args.args[0], ['agentapi', 'send-message', self.conversation, 'fixed prompt'])
            self.assertEqual(run.call_args.kwargs['timeout'], 30)
            self.assertNotIn('shell', run.call_args.kwargs)

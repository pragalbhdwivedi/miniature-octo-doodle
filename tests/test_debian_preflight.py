"""Admission guard regressions; fixtures do not prove a Debian deployment."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('debian_preflight', Path(__file__).resolve().parents[1] / 'scripts/debian-preflight.py')
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class DebianPreflightTests(unittest.TestCase):
    def setUp(self):
        self.facts = dict(system='Linux', os_id='debian', os_version='13',
                          virtual_machine=True, container=False, wsl=False,
                          cpu_count=4, memory_gib=7.8, runtime_parent_valid=True,
                          runtime_free_gib=40, docker_free_gib=40,
                          engine_linux=True, engine_desktop=False, docker_enabled=True,
                          docker_active=True, compose_version='5.5.1', running_containers=0,
                          available_ports=[3000, 4000])

    def test_supported_os_and_missing_facts(self):
        for version in ('12', '13'):
            self.assertEqual(preflight.evaluate({**self.facts, 'os_version': version})['status'], 'PASS')
        for facts in ({}, {**self.facts, 'os_id': 'ubuntu'}, {**self.facts, 'system': 'Windows'},
                      {**self.facts, 'os_version': '11'}):
            self.assertEqual(preflight.evaluate(facts)['status'], 'BLOCKED')

    def test_storage_thresholds_apply_to_both_filesystems(self):
        for name in ('runtime', 'docker'):
            self.assertEqual(preflight.evaluate({**self.facts, f'{name}_free_gib': 26.99})['status'], 'BLOCKED')
            report = preflight.evaluate({**self.facts, f'{name}_free_gib': 27})
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(len(report['warnings']), 1)

    def test_wrong_target_or_occupied_target_is_blocked(self):
        for key, value in [('virtual_machine', False), ('container', True), ('wsl', True),
                           ('running_containers', 1), ('available_ports', [3000]),
                           ('engine_desktop', True), ('engine_linux', False),
                           ('docker_enabled', False), ('docker_active', False),
                           ('cpu_count', 2), ('memory_gib', 6.9), ('runtime_parent_valid', False),
                           ('compose_version', None), ('engine_error', 'inspection failed')]:
            with self.subTest(key=key):
                self.assertEqual(preflight.evaluate({**self.facts, key: value})['status'], 'BLOCKED')

    def test_endpoint_overrides_never_contact_daemon(self):
        for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
            with patch.dict(os.environ, {key: 'forbidden'}, clear=True), patch.object(preflight, 'command') as cmd:
                self.assertIn('engine_error', preflight.inspect_local_engine())
                cmd.assert_not_called()

    def test_remote_context_never_contacts_daemon(self):
        for endpoint in ('ssh://server', 'tcp://127.0.0.1:2375', 'npipe:////./pipe/docker_engine'):
            with patch.dict(os.environ, {}, clear=True), patch.object(preflight, 'command', return_value='[{"Endpoints":{"docker":{"Host":"' + endpoint + '"}}}]') as cmd:
                self.assertIn('engine_error', preflight.inspect_local_engine())
                self.assertEqual(cmd.call_args_list[0].args[0], ['docker', 'context', 'inspect'])
                self.assertEqual(cmd.call_count, 1)

    def test_non_debian_stops_before_engine_probe(self):
        with patch.object(preflight.platform, 'system', return_value='Linux'), \
             patch.object(preflight.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}), \
             patch.object(preflight, 'inspect_local_engine') as engine:
            self.assertEqual(preflight.evaluate(preflight.collect('/srv'))['status'], 'BLOCKED')
            engine.assert_not_called()

    def test_failed_command_does_not_disclose_stderr(self):
        with patch.object(preflight.subprocess, 'run') as run:
            run.return_value.returncode = 1
            run.return_value.stderr = 'potentially sensitive diagnostic'
            self.assertIsNone(preflight.command(['docker', 'info']))

    def test_unreadable_or_malformed_context_fails_closed(self):
        for value in (None, 'invalid', '[]', '[{}]', '[{"Endpoints":{"docker":{"Host":0}}}]'):
            with patch.dict(os.environ, {}, clear=True), patch.object(preflight, 'command', return_value=value) as cmd:
                self.assertIn('engine_error', preflight.inspect_local_engine())
                self.assertEqual(cmd.call_count, 1)

    def test_engine_collection_and_unreadable_engine(self):
        context = '[{"Endpoints":{"docker":{"Host":"unix:///var/run/docker.sock"}}}]'
        with tempfile.TemporaryDirectory() as directory:
            engine = json.dumps({'DockerRootDir': directory, 'ContainersRunning': 0,
                                 'OSType': 'linux', 'OperatingSystem': 'Debian GNU/Linux 13', 'ServerVersion': '29.8.0'})
            with patch.dict(os.environ, {}, clear=True), patch.object(preflight, 'command', side_effect=[context, engine, '5.5.1', 'enabled', 'active']):
                facts = preflight.inspect_local_engine()
                self.assertTrue(facts['engine_linux'] and facts['docker_active'] and facts['docker_enabled'])
                self.assertFalse(facts['engine_desktop'])
                self.assertEqual(facts['running_containers'], 0)
            for value in (None, '{}', 'invalid'):
                with patch.dict(os.environ, {}, clear=True), patch.object(preflight, 'command', side_effect=[context, value]):
                    self.assertIn('engine_error', preflight.inspect_local_engine())


if __name__ == '__main__':
    unittest.main()

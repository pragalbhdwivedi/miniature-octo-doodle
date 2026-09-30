"""Cutover ownership, allowance and isolation guards; no Docker/provider calls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_recovery

spec=importlib.util.spec_from_file_location('cutover',Path(__file__).parents[1]/'scripts/linux-cutover.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CutoverTests(unittest.TestCase):
    def source(self):
        original=test_recovery.RecoveryTests().config()
        original['services']['litellm']['environment'].pop('TYPESAFE_API_KEY')
        for service in original['services'].values(): service['networks']=['core']
        return original

    def test_egress_only_gateway_credentials_preserved_and_source_unchanged(self):
        original=self.source()
        before=copy.deepcopy(original)
        staged=module.recovery.restore_config(original,Path('/safe'),'gatewayai-recovery-test')
        live=module.live_document(staged,original)
        self.assertEqual(original,before)
        self.assertEqual(live['services']['litellm']['environment'],original['services']['litellm']['environment'])
        self.assertEqual(live['volumes'],staged['volumes'])
        self.assertTrue(live['networks']['core']['internal'])
        for name,s in live['services'].items():
            self.assertNotIn('ports',s)
            self.assertEqual('provider-egress' in s['networks'],name=='litellm')

    def test_budget_reset_and_jev_activation_rejected(self):
        for change in ({'GATEWAY_MONTHLY_BUDGET_USD':'200'}, {'TYPESAFE_API_KEY':'secret'}):
            original=self.source()
            original['services']['litellm']['environment'].update(change)
            staged=module.recovery.restore_config(original,Path('/safe'),'gatewayai-recovery-test')
            with self.assertRaises(ValueError): module.live_document(staged,original)

    def test_handoff_must_match_snapshot_and_frozen_source(self):
        good={'backup_manifest_sha256':'abc','source_project':module.recovery.PROJECT,
              'containers_stopped':True,'restart_disabled':True}
        with patch.object(module.core,'read_private',return_value=json.dumps(good)), patch.object(module.recovery,'sha',return_value='abc'):
            module.verify_handoff(Path('/safe'),'abc')
            with self.assertRaises(ValueError): module.verify_handoff(Path('/safe'),'other')
        for key in ('containers_stopped','restart_disabled'):
            bad={**good,key:False}
            with patch.object(module.core,'read_private',return_value=json.dumps(bad)), patch.object(module.recovery,'sha',return_value='abc'):
                with self.assertRaises(ValueError): module.verify_handoff(Path('/safe'),'abc')


if __name__=='__main__': unittest.main()


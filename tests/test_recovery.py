"""Recovery rejection and isolation tests; no Docker or credentials required."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).parents[1]/'scripts/recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def config(self):
        return {'name':recovery.PROJECT,
                'services':{
                    'postgres':{'image':'postgres@sha256:fixture','environment':{'POSTGRES_PASSWORD':'preserve'},'volumes':[]},
                    'litellm':{'image':'gateway@sha256:fixture','environment':{'OPENAI_API_KEY':'remove','GEMINI_API_KEY':'remove','TYPESAFE_API_KEY':'remove','GATEWAY_MONTHLY_BUDGET_USD':'100'},
                               'volumes':[{'type':'bind','target':'/app/policy-code/gateway','source':'original'}]},
                    'open-webui':{'image':'ui@sha256:fixture','environment':{},'volumes':[]}},
                'volumes':{name:{'name':'original_'+name} for name in recovery.VOLUMES},
                'networks':{'core':{'name':'original_core'},'database':{'name':'original_database','internal':True}}}

    def test_restore_isolation_without_mutating_source(self):
        original=self.config()
        before=copy.deepcopy(original)
        result=recovery.restore_config(original,Path('sandbox'),'gatewayai-recovery-test',4400,4300)
        self.assertEqual(original,before)
        self.assertTrue(all(n['internal'] for n in result['networks'].values()))
        self.assertTrue(all(v['name'].startswith('gatewayai-recovery-test_') for v in result['volumes'].values()))
        env=result['services']['litellm']['environment']
        self.assertEqual((env['OPENAI_API_KEY'],env['GEMINI_API_KEY'],env['GATEWAY_MONTHLY_BUDGET_USD']),('','','0'))
        self.assertNotIn('TYPESAFE_API_KEY',env)
        self.assertEqual(result['services']['postgres']['environment']['POSTGRES_PASSWORD'],'preserve')
        for name,service in result['services'].items():
            self.assertEqual(service['restart'],'no')
            self.assertTrue(all(p['host_ip']=='127.0.0.1' for p in service.get('ports',[])))

    def test_source_names_ports_and_unsafe_mounts_rejected(self):
        for name in ('miniature-octo-doodle','../gatewayai-recovery-test','gatewayai-recovery-'):
            with self.assertRaises(RuntimeError):
                recovery.restore_config(self.config(),Path('sandbox'),name,4400,4300)
        for ports in ((3000,4300),(4400,4000),(4400,4400),(80,4300)):
            with self.assertRaises(RuntimeError):
                recovery.restore_config(self.config(),Path('sandbox'),'gatewayai-recovery-test',*ports)
        config=self.config()
        config['services']['litellm']['volumes'][0]['target']='/var/run/docker.sock'
        with self.assertRaises(RuntimeError):
            recovery.restore_config(config,Path('sandbox'),'gatewayai-recovery-test',4400,4300)

    def make_tar(self,path,name='safe',kind=tarfile.REGTYPE,duplicate=False):
        with tarfile.open(path,'w') as archive:
            member=tarfile.TarInfo(name)
            member.type=kind
            member.size=4 if kind==tarfile.REGTYPE else 0
            member.linkname='/outside' if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE) else ''
            archive.addfile(member,io.BytesIO(b'test') if member.size else None)
            if duplicate:
                archive.addfile(member,io.BytesIO(b'test'))

    def test_archive_safety_and_content_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'test.tar'
            self.make_tar(path)
            self.assertEqual(recovery.archive_index(path)['safe'][3],4)
            for name in ('../outside','/absolute','a/../../outside','C:/outside','a\\outside'):
                self.make_tar(path,name)
                with self.assertRaises(RuntimeError): recovery.archive_index(path)
            for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.CHRTYPE,tarfile.FIFOTYPE):
                self.make_tar(path,kind=kind)
                with self.assertRaises(RuntimeError): recovery.archive_index(path)
            self.make_tar(path,duplicate=True)
            with self.assertRaises(RuntimeError): recovery.archive_index(path)

    def test_corruption_and_inventory_rejected_before_restore_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            for filename in recovery.FILES:
                (folder/filename).write_bytes(b'original')
            manifest={'format':1,'files':{name:recovery.sha(folder/name) for name in recovery.FILES}}
            (folder/'manifest.json').write_text(json.dumps(manifest))
            (folder/'policy-data.tar').write_bytes(b'corrupt')
            with patch.object(recovery,'docker') as docker:
                with self.assertRaisesRegex(RuntimeError,'integrity'):
                    recovery.restore(folder,folder,'gatewayai-recovery-test',4400,4300)
                docker.assert_not_called()
            manifest['files']['../outside']='fake'
            (folder/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'inventory'): recovery.validate_bundle(folder)

    def test_disk_reserve(self):
        with patch.object(recovery.shutil,'disk_usage') as usage:
            usage.return_value.free=16*1024**3
            with self.assertRaises(RuntimeError): recovery.disk_guard(Path('.'),2*1024**3)
            recovery.disk_guard(Path('.'),1024**3)


if __name__=='__main__':
    unittest.main()

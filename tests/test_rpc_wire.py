"""Wire size, exact audit retention and bounded decompression contracts."""
import base64
import copy
import json
from pathlib import Path
import sys
import unittest
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import rpc_wire as wire
import pilot_worker


class WireTests(unittest.TestCase):
    def test_large_board_roundtrip_retains_every_field_and_event(self):
        value={'events':[{'sequence':i,'detail':'Preserved failure · '+'x'*70} for i in range(10000)],'attempt':0}
        encoded=wire.encode(value).encode()+b'\n'
        self.assertLessEqual(len(encoded),wire.WIRE_LIMIT)
        self.assertEqual(json.loads(encoded)['rpc_encoding'],wire.ENCODING)
        self.assertEqual(wire.decode(encoded),value)
        self.assertEqual(wire.decode(wire.encode({'state':'idle'}).encode()),{'state':'idle'})
        limits=[]
        def runner(command,**kwargs):
            limits.append(kwargs['limit']);return 0,encoded,b''
        remote=pilot_worker.Remote({'ssh_host':'controller','remote_script':'/opt/pilot.py',
                                  'remote_config':'/etc/pilot.json'},runner=runner)
        self.assertEqual(remote({'action':'ongoing_board_data'}),value)
        self.assertEqual(limits,[wire.WIRE_LIMIT])

    def test_hash_truncation_trailing_data_and_zip_bomb_fail_closed(self):
        envelope=json.loads(wire.encode({'evidence':'x'*1100000}))
        variants=[]
        for key,value in (('sha256','0'*64),('raw_bytes',1),('raw_bytes',wire.DECODED_LIMIT+1),('payload','invalid')):
            variants.append({**envelope,key:value})
        packed=base64.b64decode(envelope['payload'])
        variants.append({**envelope,'payload':base64.b64encode(packed[:-1]).decode()})
        variants.append({**envelope,'payload':base64.b64encode(packed+b'trailing').decode()})
        variants.append({**envelope,'raw_bytes':10,'payload':base64.b64encode(zlib.compress(b'x'*2000000)).decode()})
        for value in variants:
            with self.subTest(raw_bytes=value['raw_bytes']):
                with self.assertRaises((ValueError,zlib.error)):wire.decode(json.dumps(value).encode())

    def test_storage_and_wire_caps_are_not_removed(self):
        with self.assertRaises(ValueError):wire.encode({'history':'x'*wire.DECODED_LIMIT})
        with self.assertRaises(ValueError):wire.decode(b' '* (wire.WIRE_LIMIT+1))


if __name__=='__main__':unittest.main()

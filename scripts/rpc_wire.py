"""Lossless bounded operator RPC replies, including growing audit snapshots."""
import base64
import hashlib
import json
import re
import zlib

WIRE_LIMIT=1048576
DECODED_LIMIT=1900000
ENCODING='zlib-json-v1'


def encode(value):
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
    if len(raw)>DECODED_LIMIT:raise ValueError('RPC decoded storage limit exceeded')
    if len(raw)+1<=WIRE_LIMIT:return raw.decode('utf-8')
    envelope={'rpc_encoding':ENCODING,'raw_bytes':len(raw),
        'sha256':hashlib.sha256(raw).hexdigest(),
        'payload':base64.b64encode(zlib.compress(raw)).decode('ascii')}
    wire=json.dumps(envelope,separators=(',',':'))
    if len(wire.encode())+1>WIRE_LIMIT:raise ValueError('RPC wire limit exceeded')
    return wire


def decode(wire):
    if len(wire)>WIRE_LIMIT:raise ValueError('RPC wire limit exceeded')
    value=json.loads(wire)
    if not isinstance(value,dict) or 'rpc_encoding' not in value:return value
    if (set(value)!={'rpc_encoding','raw_bytes','sha256','payload'} or value['rpc_encoding']!=ENCODING
            or type(value['raw_bytes']) is not int or not 0<value['raw_bytes']<=DECODED_LIMIT
            or not isinstance(value['payload'],str)
            or re.fullmatch('[0-9a-f]{64}',str(value['sha256'])) is None):
        raise ValueError('Invalid compressed RPC envelope')
    packed=base64.b64decode(value['payload'],validate=True)
    inflater=zlib.decompressobj()
    raw=inflater.decompress(packed,value['raw_bytes']+1)
    if (len(raw)!=value['raw_bytes'] or not inflater.eof or inflater.unconsumed_tail or inflater.unused_data
            or hashlib.sha256(raw).hexdigest()!=value['sha256']):
        raise ValueError('Compressed RPC integrity or size differs')
    return json.loads(raw)

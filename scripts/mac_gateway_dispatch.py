#!/usr/bin/env python3
"""Forced SSH command for the Mac test account; never a general shell."""
import os
from pathlib import Path
import sys

if os.environ.get('SSH_ORIGINAL_COMMAND') != 'mac-gateway-test':
    raise SystemExit('Only the fixed mac-gateway-test command is allowed')

key = Path('/etc/gatewayai-mac-test/inference.key')
if not key.is_file():
    raise SystemExit('PENDING: operator must verify the tunnel and activate the dedicated gateway route/key')

os.execv('/usr/bin/python3', ['/usr/bin/python3',
         '/opt/gatewayai/mac-test/mac_gateway_acceptance.py',
         '--key-file', str(key), '--evidence-dir', '/var/lib/gatewayai-mac-test/evidence'])

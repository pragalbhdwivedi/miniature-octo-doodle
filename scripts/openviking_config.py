"""Create a one-time, local-only OpenViking configuration on VM9125.

Run as root after verifying the live provider-egress bridge. Never print keys.
"""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets


def configuration(gateway, key):
    address = ipaddress.ip_address(gateway)
    if not isinstance(address, ipaddress.IPv4Address) or address not in ipaddress.ip_network('172.16.0.0/12'):
        raise ValueError('Expected a private Docker bridge gateway')
    if not isinstance(key, str) or len(key) < 48:
        raise ValueError('Root key is too short')
    return {
        'server': {'host': '0.0.0.0', 'port': 1933, 'root_api_key': key,
                   'cors_origins': []},
        'storage': {'workspace': '/app/.openviking/workspace',
                    'agfs': {'backend': 'local'},
                    'vectordb': {'backend': 'local'}},
        'embedding': {'max_concurrent': 1, 'max_retries': 0,
                      'dense': {'provider': 'litellm', 'api_key': 'ollama',
                                'model': 'ollama/nomic-embed-text',
                                'api_base': 'http://embedding:11434',
                                'dimension': 768, 'input': 'text'}},
        'vlm': {'provider': 'litellm', 'api_key': 'ollama',
                'model': 'ollama/qwen3:4b-thinking',
                'api_base': f'http://{address}:11435',
                'extra_request_body': {'think': False},
                'max_concurrent': 1, 'max_retries': 0, 'timeout': 300},
        'retrieval': {'enable_intent': False},
    }


def create(root, gateway, network):
    if not re.fullmatch(r'gatewayai-[A-Za-z0-9_-]+_provider-egress', network):
        raise ValueError('Expected the live gateway provider-egress network')
    root = Path(root).resolve()
    if root.is_symlink() or root.exists():
        raise ValueError('Refusing to replace an existing OpenViking installation')
    os.umask(0o077)
    root.mkdir(mode=0o700)
    (root/'openviking').mkdir(mode=0o700)
    (root/'ollama').mkdir(mode=0o700)
    key = 'ov_root_' + secrets.token_urlsafe(48)
    config = configuration(gateway, key)
    (root/'openviking'/'ov.conf').write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    (root/'admin.json').write_text(json.dumps({'url': 'http://127.0.0.1:1933',
                                               'root_api_key': key}, indent=2)+'\n',
                                   encoding='utf-8')
    (root/'compose.env').write_text('GATEWAY_PROVIDER_EGRESS='+network+'\n', encoding='utf-8')
    for path in (root/'openviking'/'ov.conf', root/'admin.json', root/'compose.env'):
        path.chmod(0o600)
    print('OpenViking private config created; no key printed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--provider-gateway', required=True)
    parser.add_argument('--provider-network', required=True)
    args = parser.parse_args()
    create(args.root, args.provider_gateway, args.provider_network)


if __name__ == '__main__':
    main()

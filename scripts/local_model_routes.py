"""Render the explicitly requested laptop-only LiteLLM aliases for VM9125.

This writes staged JSON only. An operator checks the tunnel, backs up the live
files, and replaces them during a controlled gateway restart.
"""

import argparse
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlparse


MODELS = {
    'local-coding': 'ollama/devstral-small-2:24b',
    'local-supervisor': 'ollama/qwen3:4b-thinking',
}


def render(config, policy, api_base):
    address = urlparse(api_base)
    try:
        ip = ipaddress.ip_address(address.hostname)
        private = (isinstance(ip, ipaddress.IPv4Address)
                   and ip in ipaddress.ip_network('172.16.0.0/12'))
    except ValueError as exc:
        raise ValueError('Local base must be a private IPv4 Docker bridge') from exc
    if (address.scheme != 'http' or not private or address.port != 11435
            or address.path not in ('', '/') or address.query or address.fragment
            or address.username or address.password):
        raise ValueError('Local base must be a private Docker bridge on port 11435')
    if policy.get('decision_plane') != {'mode': 'deterministic', 'jev_enabled': False}:
        raise ValueError('Jev must remain disabled')
    if policy.get('local_models_enabled') is not None:
        raise ValueError('Local route already configured; inspect it before changing')
    configured = {item['model_name'] for item in config['model_list']}
    if (configured & MODELS.keys() or MODELS.keys() & policy['resolved_routes'].keys()
            or any(name in policy['prices'] for name in MODELS.values())):
        raise ValueError('A local alias or model price already exists')
    config = json.loads(json.dumps(config))
    policy = json.loads(json.dumps(policy))
    for alias, model in MODELS.items():
        config['model_list'].append({'model_name': alias,
                                     'litellm_params': {'model': model,
                                                        'api_base': api_base}})
        policy['resolved_routes'][alias] = [{'alias': alias, 'model': model}]
        policy['prices'][model] = {'input_micro_usd': 0,
                                   'output_micro_usd': 0}
    policy['local_models_enabled'] = True
    return config, policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-in', type=Path, required=True)
    parser.add_argument('--policy-in', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--api-base', required=True)
    args = parser.parse_args()
    config, policy = render(json.loads(args.config_in.read_text(encoding='utf-8')),
                            json.loads(args.policy_in.read_text(encoding='utf-8')),
                            args.api_base)
    args.out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, value in (('gateway-config.json', config), ('policy.json', policy)):
        target = args.out_dir/name
        with target.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        target.chmod(0o600)
    print('Staged two local-only aliases with zero vendor-cost debit; no live file changed')


if __name__ == '__main__':
    main()

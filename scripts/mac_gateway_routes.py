"""Stage a separate Mac test alias without changing existing routes or policy."""
import copy
import ipaddress
from urllib.parse import urlsplit

ALIAS = 'mac-coding-test'
MODEL = 'ollama/mac-coder-9b:latest'


def render(config, policy, api_base):
    address = urlsplit(api_base)
    ip = ipaddress.ip_address(address.hostname or '')
    if (address.scheme != 'http' or ip.version != 4
            or ip not in ipaddress.ip_network('172.16.0.0/12')
            or address.port != 11436 or address.path not in ('', '/')
            or address.query or address.fragment or address.username or address.password):
        raise ValueError('Expected approved Docker bridge IPv4 and Mac-only port 11436')
    if policy.get('decision_plane') != {'mode': 'deterministic', 'jev_enabled': False}:
        raise ValueError('Deterministic policy must be preserved')
    if any(m.get('model_name') == ALIAS for m in config['model_list']) or ALIAS in policy['resolved_routes']:
        raise ValueError('Mac alias already exists; inspect rather than overwrite')
    if MODEL in policy['prices']:
        raise ValueError('Existing model price requires review')
    result, guard = copy.deepcopy(config), copy.deepcopy(policy)
    result['model_list'].append({'model_name': ALIAS, 'litellm_params': {
        'model': MODEL, 'api_base': api_base, 'reasoning_effort': 'none',
        'num_ctx': 16384}})
    guard['resolved_routes'][ALIAS] = [{'alias': ALIAS, 'model': MODEL}]
    guard['prices'][MODEL] = {'input_micro_usd': 0, 'output_micro_usd': 0}
    guard['local_models_enabled'] = True
    return result, guard

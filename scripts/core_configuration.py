"""Shared zero-spend validation configuration; never reads live credentials."""
import json


def configuration(repo):
    values = dict(line.split('=', 1) for line in (repo / '.env.example').read_text(encoding='utf-8').splitlines()
                  if line and not line.startswith('#'))
    policy = json.loads((repo / 'config/policy/policy.json').read_text(encoding='utf-8'))
    if policy['decision_plane'].get('mode') != 'deterministic' or policy['decision_plane'].get('jev_enabled') is not False:
        raise ValueError('Jev must remain disabled')
    providers = {p: {'alias': values[p + '_ALIAS'], 'model': values[p + '_MODEL']}
                 for p in ('OPENAI', 'GEMINI')}
    resolved = {v['alias']: [v] for v in providers.values()}
    resolved.update({name: [providers[p] for p in order] for name, order in policy['routes'].items()})
    policy['resolved_routes'] = resolved
    config = {
        'general_settings': {'master_key': 'os.environ/LITELLM_MASTER_KEY', 'database_url': 'os.environ/DATABASE_URL', 'disable_spend_logs': True},
        'litellm_settings': {'telemetry': False, 'set_verbose': False, 'turn_off_message_logging': True, 'callbacks': ['gateway.callbacks.proxy_handler_instance']},
        'router_settings': {'num_retries': 0, 'max_fallbacks': 1, 'timeout': 60, 'disable_cooldowns': True, 'fallbacks': [], 'context_window_fallbacks': [], 'content_policy_fallbacks': []}}
    config['model_list'] = [{'model_name': name, 'litellm_params': {'model': candidates[0]['model'],
                            'api_key': 'os.environ/' + candidates[0]['model'].split('/')[0].upper() + '_API_KEY'}}
                            for name, candidates in resolved.items()]
    return config, policy

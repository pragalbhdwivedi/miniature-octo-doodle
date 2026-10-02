"""Bounded subscription-model routing; no implicit retries or API fallback.

The caller owns the durable per-task attempt counter and admission budget.
This module selects one route and invokes it once. It does not inspect full chat
history or change user settings. Model availability is checked against the
installed client's cache, not inferred from a public model name.
"""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


MAX_PROMPT_BYTES = 64 * 1024
MAX_EVENT_BYTES = 1024 * 1024
STAGES = {'code', 'review', 'plan'}
COMPLEXITIES = {'routine', 'complex', 'hard', 'high_risk'}
# UI evidence establishes shared provider pools, not one allowance per model.
# These are configuration labels, not API IDs or an executable model switch.
ANTIGRAVITY_MODELS = (
    {'model': 'Gemini 3.8 Flash Medium', 'group': 'gemini', 'rank': 0},
    {'model': 'Gemini 3.7 Flash Medium', 'group': 'gemini', 'rank': 1},
    {'model': 'Gemini 3.6 Flash Medium', 'group': 'gemini', 'rank': 2},
    {'model': 'Gemini 3.1 Pro Low', 'group': 'gemini', 'rank': 3},
    {'model': 'GPT-OSS 120B Medium', 'group': 'claude_gpt', 'rank': 4},
    {'model': 'Claude Sonnet 4.6 Thinking', 'group': 'claude_gpt', 'rank': 5},
    {'model': 'Claude Opus 4.6 Thinking', 'group': 'claude_gpt', 'rank': 6},
)


class RoutingError(ValueError):
    """A request cannot use the bounded configured model route."""


def confirmed_quota_denial(directory):
    """Only an explicit server quota denial before any generated output allows rerouting."""
    directory=Path(directory);path=directory/'codex-events.jsonl'
    try:
        if path.stat().st_size>MAX_EVENT_BYTES:return False
        events=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        if any(e.get('type')=='turn.completed' or e.get('item',{}).get('type') in ('agent_message','reasoning','command_execution') for e in events):return False
        answer=directory/'codex-answer.json'
        if answer.exists() and answer.stat().st_size:return False
        errors=[json.dumps(e,ensure_ascii=False).lower() for e in events if e.get('type') in ('error','turn.failed')]
        return any('usage_limit_reached' in e or 'you’ve hit your usage limit' in e or "you've hit your usage limit" in e for e in errors)
    except (OSError,ValueError,TypeError):return False


def route(complexity='routine', stage='code', attempt=0):
    if complexity not in COMPLEXITIES or stage not in STAGES:
        raise RoutingError('Unknown complexity or stage; classify explicitly')
    if type(attempt) is not int or attempt not in (0, 1):
        raise RoutingError('At most one explicit escalation is allowed')
    if complexity in {'hard', 'high_risk'}:
        if attempt:
            raise RoutingError('Hard-task route is already at the model ceiling')
        model, effort = 'gpt-6-astra', 'high'
    elif complexity == 'complex':
        model, effort = ('gpt-6-astra', 'high') if attempt else ('gpt-6-sol', 'medium')
    else:
        model, effort = ('gpt-6-sol', 'medium') if attempt else (
            'gpt-6-luna', 'low' if stage in {'review', 'plan'} else 'medium')
    return {'model': model, 'effort': effort, 'stage': stage,
            'complexity': complexity, 'attempt': attempt,
            'authentication': 'chatgpt', 'api_fallback': False}


def validate_route(selected, cache_path=None):
    """Read only model metadata; never execute cache instructions or print it."""
    path = Path(cache_path) if cache_path is not None else Path.home()/'.codex/models_cache.json'
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            raise RoutingError('Installed model cache exceeds the metadata limit')
        cache = json.loads(path.read_text(encoding='utf-8'))
        matches = [m for m in cache['models'] if m.get('slug') == selected['model']]
        supported = {v['effort'] for m in matches for v in m.get('supported_reasoning_levels', [])}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RoutingError('Cannot validate installed model metadata; no inference started') from exc
    if len(matches) != 1 or selected['effort'] not in supported:
        raise RoutingError('Configured model or effort is unavailable; no fallback permitted')
    return {'source': 'installed_models_cache', 'fetched_at': cache.get('fetched_at'),
            'supported': True, 'account_access_live_verified': False}


def usage_from_events(path):
    """Report only observed CLI totals; absent/malformed usage remains unknown."""
    unknown = {'status': 'unavailable', 'input_tokens': None,
               'cached_input_tokens': None, 'output_tokens': None}
    path = Path(path)
    try:
        if path.stat().st_size > MAX_EVENT_BYTES:
            return unknown
        events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        completed = [event for event in events if event.get('type') == 'turn.completed']
        # A proposal run is one turn. Summing unknown event semantics risks
        # double-counting cumulative usage, so ambiguous logs are unavailable.
        if len(completed) != 1:
            return unknown
        usage = completed[0].get('usage', {})
        values = {key: usage.get(key) for key in ('input_tokens', 'cached_input_tokens', 'output_tokens')}
        if any(type(value) is not int or value < 0 for value in values.values()):
            return unknown
        if values['cached_input_tokens'] > values['input_tokens']:
            return unknown
        return {'status': 'observed', **values}
    except (OSError, ValueError, TypeError, AttributeError):
        return unknown


def run(executable, prompt, directory, schema=None, complexity='routine',
        stage='code', attempt=0, *, coder=None, cache_path=None):
    selected = route(complexity, stage, attempt)
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode('utf-8')) > MAX_PROMPT_BYTES:
        raise RoutingError('Provide a focused task prompt of at most 64 KiB, not a full transcript')
    available = validate_route(selected, cache_path)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    report_path = directory/'model-report.json'
    # Separate attempt folders also prevent overwriting prior inference evidence.
    if any((directory/name).exists() for name in ('model-report.json', 'codex-input.txt', 'codex-events.jsonl', 'codex-answer.json')):
        raise RoutingError('Inference evidence exists; use a separately admitted attempt directory')
    report = {'route': selected, 'availability': available,
              'prompt_bytes': len(prompt.encode('utf-8')), 'state': 'reserved'}
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    if coder is None:
        from coder_coordination import codex_candidate
        coder = codex_candidate
    try:
        candidate = coder(executable, prompt, directory, schema=schema,
                          model=selected['model'], effort=selected['effort'])
    except Exception:
        report.update(state='failed_no_retry', usage=usage_from_events(directory/'codex-events.jsonl'))
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        raise
    report.update(state='completed', usage=usage_from_events(directory/'codex-events.jsonl'))
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return {'candidate': candidate, 'route': selected, 'usage': report['usage']}


def gemini_status(configured_model=None):
    """Managed sidecar has no documented per-message model selection control."""
    if configured_model is not None and (not isinstance(configured_model, str) or len(configured_model) > 120):
        raise RoutingError('Invalid configured Gemini model label')
    return {'provider': 'antigravity', 'configured_conversation_model': configured_model,
            'selection': 'conversation_configuration', 'per_message_override': False,
            'actual_model_verified': False, 'automatic_switching': False,
            'usage': {'status': 'unavailable'}, 'api_fallback': False}


def _instant(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError) as exc:
        raise RoutingError('Quota reset must be an explicit timestamp with timezone') from exc
    if parsed.tzinfo is None:
        raise RoutingError('Quota reset must include a timezone')
    return parsed.astimezone(timezone.utc)


def mark_quota_exhausted(quotas, group, reset_at=None):
    """Return JSON-safe quota state for the caller's durable state transaction.

    A reset is recorded only if observed; never guess a reset five hours from an
    error. Unknown reset stays blocked until fresh provider evidence clears it.
    """
    if not isinstance(group, str) or not group or len(group) > 80:
        raise RoutingError('Quota group is required')
    if reset_at is not None:
        _instant(reset_at)
    updated = deepcopy(quotas)
    updated[group] = {'exhausted': True, 'reset_at': reset_at}
    return updated


def select_available_model(candidates, quotas, now=None, fallback_count=0):
    """Choose a pre-execution recommendation, never replay an ambiguous run.

    Callers persist quota state and the fallback counter before attempting an
    authorized, documented model switch. This is not an Antigravity switch API.
    Rank expresses operator preference, not fabricated monetary prices.
    """
    if type(fallback_count) is not int or fallback_count not in (0, 1):
        raise RoutingError('At most one pre-execution fallback selection is allowed')
    when = datetime.now(timezone.utc) if now is None else _instant(now)
    ordered = list(candidates)
    for value in ordered:
        if (not isinstance(value, dict) or not isinstance(value.get('model'), str)
                or not value['model'] or not isinstance(value.get('group'), str)
                or not value['group'] or type(value.get('rank')) is not int):
            raise RoutingError('Candidate requires model, quota group and integer preference rank')
    blocked = []
    for candidate in sorted(ordered, key=lambda value: value['rank']):
        quota = quotas.get(candidate['group'], {})
        reset = quota.get('reset_at')
        exhausted = quota.get('exhausted', False)
        if type(exhausted) is not bool:
            raise RoutingError('Quota exhausted state must be boolean')
        if exhausted and (reset is None or _instant(reset) > when):
            blocked.append({'group': candidate['group'], 'reset_at': reset})
            continue
        return {'status': 'recommended', 'model': candidate['model'],
                'group': candidate['group'], 'fallback_count': fallback_count,
                'selection_enforced': False, 'requires_documented_switch': True,
                'execution_retry': False}
    known = sorted({_instant(v['reset_at']).isoformat() for v in blocked if v['reset_at'] is not None})
    return {'status': 'wait', 'model': None, 'blocked_groups': sorted({v['group'] for v in blocked}),
            'next_known_reset': known[0] if known else None, 'execution_retry': False}

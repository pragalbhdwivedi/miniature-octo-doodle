"""Operator RPC adapter; archives remain disabled until private configuration opts in."""
import copy
import supervisor_archive as archive


def filter_catalog(state, catalog):
    """Prune only identity-checked archived entries; preserve every other spec."""
    if not isinstance(catalog, list) or len(catalog) > 10000:
        raise archive.ArchiveError('Catalog input bound exceeded')
    board = state.get('supervision', {})
    archived = {row['key']: row for row in board.get('archived_tasks', {}).values()}
    result, seen = [], set()
    for item in catalog:
        key = item.get('id')
        if not isinstance(key, str) or key in seen:
            raise archive.ArchiveError('Invalid or duplicate catalog identity')
        seen.add(key)
        row = archived.get(key)
        if row is None:
            result.append(copy.deepcopy(item))
            continue
        receipt = board.get('archive_index', {}).get(row.get('archive_id'))
        if (not receipt or receipt.get('archive_id') != row['archive_id']
                or board.get('by_key', {}).get(key) != row['id']
                or row.get('scope_digest') != archive.task_scope_digest(item)):
            raise archive.ArchiveError('Archived catalog identity changed or receipt is missing')
    return result


def run(store, request, config):
    """Existing privileged RPC only; no caller-selected directory or file path."""
    action = request.get('action')
    if action == 'ongoing_archive_history':
        if set(request) - {'action', 'offset', 'limit'}:
            raise archive.ArchiveError('Unexpected archive history parameter')
        return archive.history_index(store.read()['value'], offset=request.get('offset', 0),
                                     limit=request.get('limit', 100))
    if action != 'ongoing_archive' or set(request) != {'action', 'revision'}:
        raise archive.ArchiveError('Invalid operator archive request')
    if (not isinstance(config, dict) or config.get('enabled') is not True
            or not isinstance(config.get('directory'), str)):
        raise archive.ArchiveError('Operator archive writing is disabled')
    if type(request['revision']) is not int:
        raise archive.ArchiveError('Expected board revision is required')
    def apply(state):
        if state['supervision']['revision'] != request['revision']:
            raise archive.ArchiveError('Board changed; refresh before archive preparation')
        candidate, receipt = archive.archive_state(state, config['directory'], retain=20)
        if receipt:
            state.clear()
            state.update(candidate)
        return {'archived': receipt['task_count'] if receipt else 0, 'receipt': receipt,
                'revision': state['supervision']['revision']}
    return store.mutate(apply)

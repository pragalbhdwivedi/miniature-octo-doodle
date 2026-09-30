"""Operator-only publication of an exact reviewed artifact to a new draft PR."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tarfile

spec = importlib.util.spec_from_file_location('worker', Path(__file__).with_name('worker.py'))
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def plan(folder, digest):
    if not re.fullmatch('[a-f0-9]{64}', digest):
        raise ValueError('Exact reviewed artifact digest required')
    result = json.loads((folder/'result.json').read_text())
    job_bytes = (folder/'input/job.json').read_bytes()
    source_bytes = (folder/'input/source.tar').read_bytes()
    if (result['status'] != 'review_required' or not result['container_removed']
            or result['run_id'] != folder.name or not re.fullmatch('[a-f0-9]{32}', folder.name)
            or result.get('artifact_sha256') != digest
            or hashlib.sha256(job_bytes).hexdigest() != result['job_sha256']
            or hashlib.sha256(source_bytes).hexdigest() != result['source_archive_sha256']):
        raise ValueError('Run not eligible or immutable inputs changed')
    job = json.loads(job_bytes)
    job.pop('branch')
    registry = json.loads((worker.REPO/'config/worker/projects.json').read_text())
    project = worker.validate_job(job, registry)
    branch = 'worker/'+result['run_id']
    if result['branch'] != branch or result['project'] != job['project'] or result['ref'] != job['ref']:
        raise ValueError('Run identity mismatch')
    base = job['ref'].removeprefix('refs/heads/')
    if base != project['default_branch'] or branch == base:
        raise ValueError('Only approved default-base review branches')
    raw = (folder/'changes.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Artifact changed after review')
    payload = json.loads(raw)
    with tarfile.open(folder/'input/source.tar') as archive:
        original = worker.sandbox.source_files(archive)
    worker.artifacts(payload, original, job['write_paths'])
    if not payload['changes']:
        raise ValueError('No changes to publish')
    # No workflow changes or credential-looking paths through this first adapter.
    for c in payload['changes']:
        if any(p.startswith('.') for p in c['path'].split('/')) or c['path'].split('/')[0] in {'secrets', 'creds', 'VM_NOTES', 'LOCAL_CERTIFICATES'}:
            raise ValueError('Sensitive publication path denied')
    if not re.fullmatch('[a-f0-9]{40}', result['source_sha']):
        raise ValueError('Invalid source revision')
    return {'repository': project['url'].removeprefix('https://github.com/').removesuffix('.git'),
            'base': base, 'head': branch, 'source_sha': result['source_sha'], 'artifact_sha256': digest,
            'run_id': result['run_id'], 'changes': payload['changes']}


def publish(value, config, transport=worker.coding.request_json):
    if (not re.fullmatch('[a-f0-9]{32}', value['run_id'])
            or value['head'] != 'worker/'+value['run_id'] or value['head'] == value['base']
            or not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value['repository'])
            or not re.fullmatch('[A-Za-z0-9_/-]+', value['base']) or '..' in value['base']):
        raise ValueError('Invalid publication scope')
    if (set(config) != {'repository', 'github_token'} or config['repository'] != value['repository']
            or not isinstance(config['github_token'], str) or not config['github_token'].strip()):
        raise ValueError('Publisher credential repository mismatch')
    url = 'https://api.github.com/repos/'+value['repository']
    def api(path, body=None):
        return transport(url+path, config['github_token'], body)
    repo = api('')
    if repo['private'] or repo['default_branch'] != value['base']:
        raise ValueError('Repository visibility/default branch changed')
    current = api('/git/ref/heads/'+value['base'])
    if current['object']['sha'] != value['source_sha']:
        raise ValueError('Base advanced; rerun and review a fresh snapshot')
    # Ref creation (never update/force/delete) fails if the run branch already exists.
    parent = api('/git/commits/'+value['source_sha'])
    tree = []
    for change in value['changes']:
        entry = {'path': change['path'], 'type': 'blob', 'mode': '100755' if change['mode'] == 0o755 else '100644'}
        if change['content_base64'] is None:
            entry['sha'] = None
        else:
            blob = api('/git/blobs', {'content': change['content_base64'], 'encoding': 'base64'})
            entry['sha'] = blob['sha']
        tree.append(entry)
    new_tree = api('/git/trees', {'base_tree': parent['tree']['sha'], 'tree': tree})
    commit = api('/git/commits', {'message': 'Worker review '+value['run_id'], 'tree': new_tree['sha'],
                                 'parents': [value['source_sha']]})
    # Recheck after uploads; if base races after this read, commit still retains exact reviewed parent.
    if api('/git/ref/heads/'+value['base'])['object']['sha'] != value['source_sha']:
        raise ValueError('Base changed during publication')
    api('/git/refs', {'ref': 'refs/heads/'+value['head'], 'sha': commit['sha']})
    pr = api('/pulls', {'title': 'Worker review '+value['run_id'][:12], 'head': value['head'],
        'base': value['base'], 'draft': True, 'maintainer_can_modify': False,
        'body': 'Operator-reviewed bounded worker artifact.\n\nRun: `'+value['run_id']+'`\n\n'
                'Artifact SHA-256: `'+value['artifact_sha256']+'`\n\n'
                'Source: `'+value['source_sha']+'`\n\n'
                'Sandbox commands passed. This is execution evidence, not independent code acceptance. '
                'Human review and merge approval remain required.'+
                ('\n\nTracked task: #'+str(value['issue']) if type(value.get('issue')) is int and value['issue']>0 else '')})
    if not pr.get('draft') or pr['head']['ref'] != value['head'] or pr['base']['ref'] != value['base']:
        raise ValueError('Unexpected publication response; inspect GitHub manually')
    return {'url': pr['html_url'], 'number': pr['number'], 'commit': commit['sha'], 'draft': True}


def publish_reviewed(folder, digest, config_path, issue=None):
    worker.private_root(folder.parent)
    worker.private_root(folder)
    value = plan(folder, digest)
    if issue is not None:
        if type(issue) is not int or issue < 1: raise ValueError('Invalid task issue')
        value['issue'] = issue
    if config_path.resolve().is_relative_to(worker.REPO):
        raise ValueError('Credentials must remain outside repository')
    config = worker.coding.private_config(config_path)
    if not config.get('github_token'):
        raise ValueError('Repository-scoped publisher credential is not configured')
    import fcntl
    with (folder/'publication.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = folder/'publication.json'
        if journal.exists():
            raise ValueError('Publication already attempted; inspect journal/GitHub before any retry')
        journal.write_text(json.dumps({'state': 'attempting', 'head': value['head']}))
        result = publish(value, config)
        journal.write_text(json.dumps({'state': 'published', **result}, indent=2))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--approve-sha256', required=True)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    worker.private_root(args.run.parent)
    worker.private_root(args.run)
    value = plan(args.run, args.approve_sha256)
    if args.config is None:
        print(json.dumps({k: v for k, v in value.items() if k != 'changes'}))
        return
    print(json.dumps(publish_reviewed(args.run,args.approve_sha256,args.config)))


if __name__ == '__main__':
    import os
    os.umask(0o077)
    try:
        main()
    except Exception as error:
        raise SystemExit('Publication rejected: '+type(error).__name__+'; credentials withheld')

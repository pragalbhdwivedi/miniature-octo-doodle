"""Boot-only operator service: refresh dynamic Docker IPs after core readiness."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import time

spec=importlib.util.spec_from_file_location('linux_core',Path(__file__).with_name('linux-core.py'))
core=importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def ready(containers, project):
    return (len(containers)==3 and
        {c['Config']['Labels'].get('com.docker.compose.service') for c in containers}==core.SERVICES and
        all(c['Config']['Labels'].get('com.docker.compose.project')==project and
            c['State'].get('Health',{}).get('Status')=='healthy' for c in containers))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    args=parser.parse_args()
    if os.geteuid()!=0 or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}',args.project):
        raise ValueError('Approved administrator and explicit project required')
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        ids=core.run(['docker','ps','-aq','--filter','label=com.docker.compose.project='+args.project]).split()
        containers=json.loads(core.run(['docker','inspect',*ids])) if ids else []
        if ready(containers,args.project):
            core.install_loopback(args.project,boot_refresh=False)
            print('Loopback targets refreshed for healthy selected core')
            return
        time.sleep(3)
    raise RuntimeError('Selected core did not become healthy; loopback refresh not applied')


if __name__=='__main__':
    try: main()
    except Exception as error: raise SystemExit('Loopback boot refresh failed ('+type(error).__name__+')')

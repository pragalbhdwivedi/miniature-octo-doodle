"""Apply additive schema 3 to a selected controller database, after a protected backup."""
import argparse
import os
from pathlib import Path
import re
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--container',required=True)
p.add_argument('--admin-role',required=True)
p.add_argument('--database',default='gatewayai_controller')
a=p.parse_args()
if os.name!='posix' or os.geteuid()!=0:raise SystemExit('Linux operator required')
if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',a.container) or not re.fullmatch('[a-z_][a-z0-9_]{0,62}',a.admin_role):
    raise SystemExit('Invalid selected database endpoint')
if not re.fullmatch('gatewayai_controller(?:_test_[a-f0-9]{8})?',a.database):raise SystemExit('Dedicated controller DB only')
sql=(Path(__file__).resolve().parents[1]/'deploy/controller/003-telegram-approvals.sql').read_text()
r=subprocess.run(['docker','--host','unix:///var/run/docker.sock','exec','-i','--user','postgres',a.container,
                  'psql','-XqAt','-v','ON_ERROR_STOP=1','-U',a.admin_role,'-d',a.database],
                 input=('SET ROLE gatewayai_controller_owner;\n'+sql).encode(),capture_output=True,timeout=30)
if r.returncode:raise SystemExit('Migration refused/rolled back; inspect selected DB; no retry')
print('Controller schema 3 applied; previous run, event and pipeline history preserved')

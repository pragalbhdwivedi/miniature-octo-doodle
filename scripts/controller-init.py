"""One-time additive controller database provisioning by an approved administrator."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--container',required=True)
parser.add_argument('--admin-role',required=True)
args=parser.parse_args()
if os.name!='posix' or os.geteuid()!=0:
    raise SystemExit('Linux operator required')
if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',args.container):
    raise SystemExit('Invalid selected container')
if not re.fullmatch('[a-z_][a-z0-9_]{0,62}',args.admin_role):
    raise SystemExit('Invalid administrator role')
base=['docker','--host','unix:///var/run/docker.sock','exec','-i','--user','postgres',
      args.container,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U',args.admin_role]
def sql(database,query):
    r=subprocess.run(base+['-d',database],input=query.encode(),capture_output=True,timeout=30)
    if r.returncode: raise SystemExit('Provisioning stopped; inspect selected database manually')
    return r.stdout.decode().strip()

# Refuse existing objects rather than silently adopting or modifying them.
count=sql('postgres',"SELECT (SELECT count(*) FROM pg_roles WHERE rolname IN "
          "('gatewayai_controller','gatewayai_controller_owner')) + "
          "(SELECT count(*) FROM pg_database WHERE datname='gatewayai_controller');")
if count!='0': raise SystemExit('Controller objects already exist; no migration or overwrite performed')
sql('postgres',"BEGIN; CREATE ROLE gatewayai_controller_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE; "
    "CREATE ROLE gatewayai_controller LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 4; COMMIT;")
sql('postgres','CREATE DATABASE gatewayai_controller OWNER gatewayai_controller_owner;')
sql('gatewayai_controller','REVOKE ALL ON DATABASE gatewayai_controller FROM PUBLIC; '
    'GRANT CONNECT ON DATABASE gatewayai_controller TO gatewayai_controller; '
    'REVOKE ALL ON SCHEMA public FROM PUBLIC;')
migration=(Path(__file__).resolve().parents[1]/'deploy/controller/001-run-state.sql').read_text()
sql('gatewayai_controller','SET ROLE gatewayai_controller_owner;\n'+migration)
print(json.dumps({'database':'gatewayai_controller','schema_version':1,'result':'created',
                  'new_passwords':0,'new_images':0,'existing_gateway_tables_modified':False}))

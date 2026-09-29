"""Static safety contract for the default core deployment (no runtime claim)."""
from pathlib import Path
import json
import subprocess
import yaml

root = Path(__file__).resolve().parent.parent
tracked = subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines()
for name in tracked:
    if Path(name).suffix in ('.yaml', '.yml'):
        yaml.safe_load((root / name).read_text(encoding='utf-8'))
    assert not (Path(name).name.startswith('.env') and Path(name).name != '.env.example'), name
    assert not name.startswith(('data/', 'backups/', 'models/', 'tmp/')), name

compose = yaml.safe_load((root / 'compose.yaml').read_text(encoding='utf-8'))
assert set(compose['services']) == {'postgres', 'litellm', 'open-webui'}
assert compose['name'] == 'miniature-octo-doodle'
for name, service in compose['services'].items():
    assert not service.get('privileged') and not service.get('env_file')
    assert service['healthcheck'] and service['logging']
    assert service.get('network_mode') != 'host'
    assert all(port.startswith('127.0.0.1:') for port in service.get('ports', []))
    assert all('docker.sock' not in volume for volume in service.get('volumes', []))
assert not compose['services']['postgres'].get('ports')
assert compose['networks']['database']['internal'] is True
gateway = compose['services']['litellm']
assert 'policy-data:/app/policy-data' in gateway['volumes']
assert 'GATEWAY_MONTHLY_BUDGET_USD' in gateway['environment']
assert 'TYPESAFE_API_KEY' not in gateway['environment']
ui = compose['services']['open-webui']['environment']
assert ui['OPENAI_API_BASE_URL'] == 'http://litellm:4000/v1'
assert 'WEBUI_GATEWAY_KEY' in ui['OPENAI_API_KEY']
assert not {'GEMINI_API_KEY', 'LITELLM_MASTER_KEY', 'POSTGRES_PASSWORD'} & ui.keys()
assert json.loads(ui['DEFAULT_MODEL_PARAMS']) == {'function_calling': 'legacy'}
assert all(ui[key] == 'False' for key in ('ENABLE_OLLAMA_API', 'ENABLE_DIRECT_CONNECTIONS', 'ENABLE_DIRECT_INTEGRATIONS', 'ENABLE_CODE_EXECUTION', 'ENABLE_CODE_INTERPRETER', 'ENABLE_EVALUATION_ARENA_MODELS', 'ENABLE_COMMUNITY_SHARING', 'ENABLE_SIGNUP'))
for line in (root / '.env.example').read_text().splitlines():
    if '_IMAGE=' in line and not line.startswith('#'):
        assert '@sha256:' in line, 'Images must have immutable digest pins'
print('Repository YAML and core security contract passed.')

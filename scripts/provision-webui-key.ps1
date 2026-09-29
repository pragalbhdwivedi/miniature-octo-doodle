param()
. "$PSScriptRoot/common.ps1"
$values = Read-LocalEnv
if ($values.WEBUI_GATEWAY_KEY) {
  Write-Host 'Preserving the existing WebUI gateway key.'
  return
}
$code = @'
import json, os, sys, urllib.request
body = json.dumps({'key_alias': 'open-webui', 'models': ['all-proxy-models'],
    'allowed_routes': ['/v1/models', '/models', '/v1/chat/completions', '/chat/completions']}).encode()
request = urllib.request.Request('http://127.0.0.1:4000/key/generate', data=body,
    headers={'Authorization': 'Bearer ' + os.environ['LITELLM_MASTER_KEY'], 'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        print(json.dumps({'key': json.load(response)['key']}))
except Exception:
    sys.exit('Gateway key provisioning failed; response omitted to protect credentials.')
'@
# Execute inside the gateway so no master key travels through shell arguments or logs.
$result = (Invoke-CoreCompose -Arguments @('exec','-T','litellm','python','-c',$code)) | ConvertFrom-Json
if (!$result.key -or $result.key -notmatch '^sk-[A-Za-z0-9_-]+$') { throw 'Gateway returned an invalid key.' }
$content = Get-Content $EnvPath -Raw
$content = [regex]::Replace($content, '(?m)^WEBUI_GATEWAY_KEY=.*$', "WEBUI_GATEWAY_KEY=$($result.key)")
[IO.File]::WriteAllText($EnvPath, $content, [Text.UTF8Encoding]::new($false))
Write-Host 'Provisioned a route-scoped inference key for Open WebUI; master key stays in the gateway.'

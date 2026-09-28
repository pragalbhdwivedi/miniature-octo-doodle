param([ValidateSet('gateway','all')][string]$Stage = 'all', [switch]$ContainerOnly)
. "$PSScriptRoot/common.ps1"
$values = Read-LocalEnv
function Assert-True($Condition, [string]$Message) {
  if (!$Condition) { throw $Message }
  Write-Host "PASS: $Message"
}
function Get-HttpStatus([string]$Uri, [hashtable]$Headers = @{}) {
  try { return [int](Invoke-WebRequest -Uri $Uri -Headers $Headers -UseBasicParsing -TimeoutSec 20).StatusCode }
  catch {
    if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
    throw 'HTTP probe could not reach its local target.'
  }
}
$services = if ($Stage -eq 'gateway') { @('postgres','litellm') } else { @('postgres','litellm','open-webui') }
foreach ($service in $services) {
  $id = Invoke-CoreCompose -Arguments @('ps','-q',$service)
  Assert-True (![string]::IsNullOrWhiteSpace($id)) "$service exists"
  $container = (docker inspect $id | ConvertFrom-Json)[0]
  Assert-True ($container.State.Health.Status -eq 'healthy') "$service healthy"
  Assert-True (!$container.HostConfig.Privileged) "$service not privileged"
  Assert-True (@($container.Mounts | Where-Object { $_.Destination -match 'docker.sock|/host' }).Count -eq 0) "$service has no Docker socket or host root mount"
  foreach ($property in $container.NetworkSettings.Ports.PSObject.Properties) {
    foreach ($binding in $property.Value) {
      Assert-True ($binding.HostIp -eq '127.0.0.1') "$service binding is localhost only"
    }
  }
  if ($service -eq 'postgres') {
    Assert-True (@($container.HostConfig.PortBindings.PSObject.Properties).Count -eq 0) 'PostgreSQL has no host port'
  }
  if ($service -eq 'open-webui') {
    $envMap = @{}
    foreach ($entry in $container.Config.Env) { $parts=$entry.Split('=',2); $envMap[$parts[0]]=$parts[1] }
    Assert-True ($envMap.OPENAI_API_BASE_URL -eq 'http://litellm:4000/v1') 'WebUI endpoint is LiteLLM only'
    Assert-True ($envMap.OPENAI_API_KEY -eq $values.WEBUI_GATEWAY_KEY -and $envMap.OPENAI_API_KEY -ne $values.LITELLM_MASTER_KEY) 'WebUI uses its own inference key'
    Assert-True (!$envMap.ContainsKey('GEMINI_API_KEY') -and !$envMap.ContainsKey('LITELLM_MASTER_KEY') -and !$envMap.ContainsKey('POSTGRES_PASSWORD')) 'WebUI does not receive provider/database/master secrets'
    foreach ($setting in @('ENABLE_OLLAMA_API','ENABLE_DIRECT_CONNECTIONS','ENABLE_DIRECT_INTEGRATIONS','ENABLE_CODE_EXECUTION','ENABLE_CODE_INTERPRETER','ENABLE_EVALUATION_ARENA_MODELS','ENABLE_COMMUNITY_SHARING','ENABLE_SIGNUP')) {
      Assert-True ($envMap[$setting] -eq 'False') "$setting disabled"
    }
  }
}
$sql = "select count(*) from information_schema.tables where table_schema='public' and table_name like 'LiteLLM%';"
$tables = Invoke-CoreCompose -Arguments @('exec','-T','postgres','psql','-U',$values.POSTGRES_USER,'-d',$values.POSTGRES_DB,'-Atc',$sql)
Assert-True ([int]($tables | Select-Object -Last 1) -gt 0) 'LiteLLM database schema exists'
$probe = Get-Content "$PSScriptRoot/test-runtime.py" -Raw
Invoke-CoreCompose -Arguments @('exec','-T','litellm','python','-c',$probe,'gateway')
if ($Stage -eq 'all') {
  Invoke-CoreCompose -Arguments @('exec','-T','open-webui','python','-c',$probe,'webui')
}
if ($ContainerOnly) {
  Write-Host 'Container checks passed. Host/browser reachability NOT validated. No cloud requests made.'
  return
}
$masterHeaders = @{Authorization="Bearer $($values.LITELLM_MASTER_KEY)"}
Assert-True ((Get-HttpStatus 'http://127.0.0.1:4000/health/liveliness') -eq 200) 'Gateway liveness returns 200'
Assert-True ((Get-HttpStatus 'http://localhost:4000/health/liveliness') -eq 200) 'Gateway localhost name returns 200'
Assert-True ((Get-HttpStatus 'http://127.0.0.1:4000/v1/models') -in @(401,403)) 'Unauthenticated model access denied'
try {
  $models = Invoke-RestMethod 'http://127.0.0.1:4000/v1/models' -Headers $masterHeaders -TimeoutSec 20
} catch { throw 'Authenticated model listing failed; response omitted.' }
$expected = @()
if ($values.OPENAI_API_KEY) { $expected += $values.OPENAI_ALIAS }
if ($values.GEMINI_API_KEY) { $expected += $values.GEMINI_ALIAS }
$actual = @($models.data | ForEach-Object { $_.id })
Assert-True ((($actual | Sort-Object) -join ',') -eq (($expected | Sort-Object) -join ',')) 'Model list matches configured providers'
Assert-True ('local-private' -notin $actual) 'No unimplemented local-private route is advertised'
if ($Stage -eq 'all') {
  $uiHeaders = @{Authorization="Bearer $($values.WEBUI_GATEWAY_KEY)"}
  Assert-True ((Get-HttpStatus 'http://127.0.0.1:4000/v1/models' $uiHeaders) -eq 200) 'WebUI inference key accepted'
  Assert-True ((Get-HttpStatus 'http://127.0.0.1:4000/key/list' $uiHeaders) -in @(401,403)) 'WebUI inference key denied key administration'
  Assert-True ((Get-HttpStatus 'http://127.0.0.1:3000/health') -eq 200) 'WebUI health returns 200'
  Assert-True ((Get-HttpStatus 'http://127.0.0.1:3000') -eq 200) 'WebUI HTML returns 200'
  Assert-True ((Get-HttpStatus 'http://localhost:3000') -eq 200) 'WebUI localhost name returns 200'
  try {
    $body = @{email=$values.WEBUI_ADMIN_EMAIL; password=$values.WEBUI_ADMIN_PASSWORD} | ConvertTo-Json
    $login = Invoke-RestMethod 'http://127.0.0.1:3000/api/v1/auths/signin' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 20
    $uiModels = Invoke-RestMethod 'http://127.0.0.1:3000/api/models' -Headers @{Authorization="Bearer $($login.token)"} -TimeoutSec 20
  } catch { throw 'WebUI sign-in/model discovery failed; response omitted to protect credentials.' }
  Assert-True ($login.role -eq 'admin') 'Local administrator sign-in works'
  $actualUi = @($uiModels.data | ForEach-Object { $_.id })
  Assert-True ((($actualUi | Sort-Object) -join ',') -eq (($expected | Sort-Object) -join ',')) 'WebUI model discovery matches the gateway'
}
Write-Host 'Core smoke tests passed. No cloud completion was requested; provider inference remains untested.'

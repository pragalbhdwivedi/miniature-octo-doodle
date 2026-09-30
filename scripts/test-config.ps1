param()
$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path $PSScriptRoot -Parent
$previousAlias = [Environment]::GetEnvironmentVariable('OPENAI_ALIAS', 'Process')
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('gatewayai-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path "$fixture/scripts","$fixture/config/litellm","$fixture/config/policy" -Force | Out-Null
Copy-Item "$sourceRoot/config/policy/policy.json" "$fixture/config/policy/policy.json"
Copy-Item "$PSScriptRoot/*.ps1" "$fixture/scripts/"
Copy-Item "$sourceRoot/.env.example" "$fixture/.env.example"
function Must-Fail([scriptblock]$Action, [string]$Name) {
  $failed = $false
  try { & $Action } catch { $failed = $true }
  if (!$failed) { throw "Expected rejection: $Name" }
  Write-Host "PASS: $Name rejected"
}
try {
  & "$fixture/scripts/init-env.ps1"
  $original = Get-Content "$fixture/.env" -Raw
  Must-Fail { & "$fixture/scripts/init-env.ps1" } 'secret replacement'
  if ((Get-Content "$fixture/.env" -Raw) -ne $original) { throw 'Init changed existing secrets.' }
  foreach ($providers in @('none','openai','gemini','both')) {
    $content = $original
    $count = 0
    if ($providers -in @('openai','both')) { $content = $content.Replace('OPENAI_API_KEY=', 'OPENAI_API_KEY=synthetic-openai-key'); $count++ }
    if ($providers -in @('gemini','both')) { $content = $content.Replace('GEMINI_API_KEY=', 'GEMINI_API_KEY=synthetic-gemini-key'); $count++ }
    Set-Content "$fixture/.env" $content
    & "$fixture/scripts/render-config.ps1"
    $rendered = Get-Content "$fixture/config/litellm/config.local.yaml" -Raw
    $config = $rendered | ConvertFrom-Json
    $expectedCount = if ($count) { $count + 6 } else { 0 }
    if (@($config.model_list).Count -ne $expectedCount -or $rendered -match 'synthetic-.+-key') { throw 'Provider omission/secret isolation failed.' }
    Write-Host "PASS: $providers provider rendering without secret values"
  }
  Set-Content "$fixture/.env" ($original.Replace('OPENAI_ALIAS=openai-chat','OPENAI_ALIAS=local-private'))
  Must-Fail { & "$fixture/scripts/render-config.ps1" } 'cloud local-private alias'
  Set-Content "$fixture/.env" ($original.Replace('GEMINI_ALIAS=gemini-chat','GEMINI_ALIAS=openai-chat'))
  Must-Fail { & "$fixture/scripts/render-config.ps1" } 'duplicate aliases'
  Set-Content "$fixture/.env" ($original.Replace('OPENAI_MODEL=openai/gpt-5.4-mini','OPENAI_MODEL=openai/*'))
  Must-Fail { & "$fixture/scripts/render-config.ps1" } 'wildcard model'
  Set-Content "$fixture/.env" ($original.Replace('OPENAI_ALIAS=openai-chat','OPENAI_ALIAS=coding-fast'))
  Must-Fail { & "$fixture/scripts/render-config.ps1" } 'capability alias collision'
  Set-Content "$fixture/.env" ($original.Replace('OPENAI_API_KEY=', 'OPENAI_API_KEY=synthetic-key').Replace('OPENAI_MODEL=openai/gpt-5.4-mini','OPENAI_MODEL=openai/unreviewed'))
  Must-Fail { & "$fixture/scripts/render-config.ps1" } 'unreviewed model price'
  Set-Content "$fixture/.env" $original
  $originalPolicy = Get-Content "$fixture/config/policy/policy.json" -Raw
  Set-Content "$fixture/config/policy/policy.json" ($originalPolicy.Replace('"jev_enabled": false','"jev_enabled": true'))
  Must-Fail { & "$fixture/scripts/render-config.ps1" } 'unvalidated Jev activation'
  Set-Content "$fixture/config/policy/policy.json" $originalPolicy
  . "$fixture/scripts/common.ps1"
  Assert-DiskReserve -FreeGiB 27 -AdditionalGiB 12
  Must-Fail { Assert-DiskReserve -FreeGiB 26.99 -AdditionalGiB 12 } 'projected reserve violation'
  Must-Fail { Assert-DiskReserve -FreeGiB 14.99 -AdditionalGiB 0 } 'critical threshold violation'
  Must-Fail { Assert-DiskReserve -FreeGiB 50 -AdditionalGiB 0 -CriticalGiB 1 } 'weakened disk policy'
  function Get-PSDrive { param($Name) [pscustomobject]@{ Free = $(if ($Name -eq 'C') { 50GB } else { 18GB }) } }
  try {
    Must-Fail { Assert-StorageReserves -DriveNames @('C','D') -AdditionalGiB 8 } 'Docker D drive cluster reserve'
    Must-Fail { Assert-StorageReserves -DriveNames @('C','D') -AdditionalGiB 4 } 'Docker D drive deployment reserve'
    Assert-StorageReserves -DriveNames @('C','D') -AdditionalGiB 0
  } finally { Remove-Item Function:Get-PSDrive }
  Set-Content "$fixture/.env" $original
  $env:OPENAI_ALIAS = 'unrelated-shell-value'
  function docker { $global:LASTEXITCODE = 42 }
  Must-Fail { Invoke-CoreCompose -Arguments @('config','--quiet') } 'native Docker failure'
  if ($env:OPENAI_ALIAS -ne 'unrelated-shell-value') { throw 'Shell environment was not restored.' }
  if (Test-Path Env:LITELLM_MASTER_KEY) { throw 'Generated secret leaked into caller environment.' }
  Write-Host 'PASS: Docker failure propagates and caller environment is restored'
} finally {
  Remove-Item Function:docker -ErrorAction SilentlyContinue
  if ($null -eq $previousAlias) { Remove-Item Env:OPENAI_ALIAS -ErrorAction SilentlyContinue }
  else { $env:OPENAI_ALIAS = $previousAlias }
  # Delete only the independently created, verified temporary fixture directory.
  $resolved = [IO.Path]::GetFullPath($fixture)
  $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
  if (!$resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolved -Leaf) -notlike 'gatewayai-test-*') { throw 'Unsafe fixture cleanup path.' }
  Remove-Item -LiteralPath $resolved -Recurse -Force
}
Write-Host 'Configuration regression checks passed; no network or provider calls made.'
# The deliberate Docker-failure mock must not become the CI runner's exit code.
$global:LASTEXITCODE = 0

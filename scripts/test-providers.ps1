param([switch]$RunLive)
. "$PSScriptRoot/common.ps1"
if (!$RunLive) { throw 'Live provider tests can incur charges. Invoke explicitly with -RunLive.' }
$configPath = Join-Path $RepoRoot 'config/litellm/config.local.yaml'
if (!(Test-Path -LiteralPath $configPath)) { throw 'Run manage.ps1 start first.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$aliases = @($config.model_list | ForEach-Object { $_.model_name })
if (!$aliases.Count -or $aliases.Count -gt 2) { throw 'Expected one or two configured core provider aliases.' }
foreach ($alias in $aliases) {
  if ($alias -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_-]*$' -or $alias -eq 'local-private') { throw 'Invalid cloud test alias.' }
}
$probe = Get-Content "$PSScriptRoot/test-providers.py" -Raw
# Uses the existing scoped inference key inside WebUI. No secret in arguments.
Invoke-CoreCompose -Arguments (@('exec','-T','open-webui','python','-c',$probe) + $aliases)

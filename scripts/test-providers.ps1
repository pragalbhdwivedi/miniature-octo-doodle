param([switch]$RunLive, [string[]]$Aliases)
. "$PSScriptRoot/common.ps1"
if (!$RunLive) { throw 'Live provider tests can incur charges. Invoke explicitly with -RunLive.' }
$configPath = Join-Path $RepoRoot 'config/litellm/config.local.yaml'
if (!(Test-Path -LiteralPath $configPath)) { throw 'Run manage.ps1 start first.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$values = Read-LocalEnv
$configured = @($config.model_list | ForEach-Object { $_.model_name })
if (!$Aliases) { $Aliases = @($configured | Where-Object { $_ -in @($values.OPENAI_ALIAS,$values.GEMINI_ALIAS) }) }
if (!$Aliases.Count -or $Aliases.Count -gt 2 -or @($Aliases | Where-Object { $_ -notin $configured }).Count) { throw 'Expected one or two configured core aliases.' }
foreach ($alias in $aliases) {
  if ($alias -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_-]*$' -or $alias -eq 'local-private') { throw 'Invalid cloud test alias.' }
}
$probe = Get-Content "$PSScriptRoot/test-providers.py" -Raw
# Uses the existing scoped inference key inside WebUI. No secret in arguments.
Invoke-CoreCompose -Arguments (@('exec','-T','open-webui','python','-c',$probe) + $aliases)

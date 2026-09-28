param([string]$EnvFile)
. "$PSScriptRoot/common.ps1"
if (!$EnvFile) { $EnvFile = $EnvPath }
$values = Read-LocalEnv -Path $EnvFile
$models = @()
$aliases = @()
foreach ($provider in @('OPENAI','GEMINI')) {
  $alias = $values["${provider}_ALIAS"]
  $model = $values["${provider}_MODEL"]
  if ($alias -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_-]*$' -or $alias -eq 'local-private' -or $alias -in $aliases) {
    throw 'Provider aliases must be unique, simple names; local-private is reserved.'
  }
  $aliases += $alias
  $prefix = $provider.ToLowerInvariant() + '/'
  if (!$model -or !$model.StartsWith($prefix) -or $model.Contains('*')) { throw "${provider}_MODEL must be a specific $prefix model." }
  if (![string]::IsNullOrWhiteSpace($values["${provider}_API_KEY"])) {
    $models += @{model_name=$alias; litellm_params=@{model=$model; api_key="os.environ/${provider}_API_KEY"}}
  }
}
$config = @{
  model_list = @($models)
  general_settings = @{master_key='os.environ/LITELLM_MASTER_KEY'; database_url='os.environ/DATABASE_URL'; disable_spend_logs=$true}
  litellm_settings = @{telemetry=$false; set_verbose=$false; turn_off_message_logging=$true}
}
# JSON is a YAML subset; serialization avoids unsafe interpolation into YAML.
[IO.File]::WriteAllText("$RepoRoot/config/litellm/config.local.yaml", ($config | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
Write-Host "Rendered gateway config with $($models.Count) configured provider route(s)."

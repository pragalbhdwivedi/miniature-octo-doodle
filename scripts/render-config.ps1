param([string]$EnvFile)
. "$PSScriptRoot/common.ps1"
if (!$EnvFile) { $EnvFile = $EnvPath }
$values = Read-LocalEnv -Path $EnvFile
$models = @()
$aliases = @()
$policy = Get-Content "$RepoRoot/config/policy/policy.json" -Raw | ConvertFrom-Json -AsHashtable
$providers = @{}
foreach ($provider in @('OPENAI','GEMINI')) {
  $alias = $values["${provider}_ALIAS"]
  $model = $values["${provider}_MODEL"]
  if ($alias -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_-]*$' -or $alias -eq 'local-private' -or $alias -in $aliases -or $policy.routes.ContainsKey($alias)) {
    throw 'Provider aliases must be unique, simple names; local-private is reserved.'
  }
  $aliases += $alias
  $prefix = $provider.ToLowerInvariant() + '/'
  if (!$model -or !$model.StartsWith($prefix) -or $model.Contains('*')) { throw "${provider}_MODEL must be a specific $prefix model." }
  if (![string]::IsNullOrWhiteSpace($values["${provider}_API_KEY"])) {
    if (!$policy.prices.ContainsKey($model)) { throw 'Model requires reviewed policy pricing before activation.' }
    $models += @{model_name=$alias; litellm_params=@{model=$model; api_key="os.environ/${provider}_API_KEY"}}
    $providers[$provider] = @{alias=$alias; model=$model}
  }
}
$resolved = @{}
foreach ($provider in $providers.Keys) { $resolved[$providers[$provider].alias] = @($providers[$provider]) }
foreach ($route in $policy.routes.Keys) {
  $candidates = @($policy.routes[$route] | Where-Object { $providers.ContainsKey($_) } | ForEach-Object { $providers[$_] })
  if ($candidates.Count) {
    $resolved[$route] = $candidates
    $primary = $policy.routes[$route] | Where-Object { $providers.ContainsKey($_) } | Select-Object -First 1
    $models += @{model_name=$route; litellm_params=@{model=$providers[$primary].model; api_key="os.environ/${primary}_API_KEY"}}
  }
}
$policy.resolved_routes = $resolved
[IO.File]::WriteAllText("$RepoRoot/config/policy/policy.local.json", ($policy | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
$config = @{
  model_list = @($models)
  general_settings = @{master_key='os.environ/LITELLM_MASTER_KEY'; database_url='os.environ/DATABASE_URL'; disable_spend_logs=$true}
  litellm_settings = @{telemetry=$false; set_verbose=$false; turn_off_message_logging=$true; callbacks=@('gateway.callbacks.proxy_handler_instance')}
  router_settings = @{num_retries=0; max_fallbacks=1; timeout=60; disable_cooldowns=$true; fallbacks=@(); context_window_fallbacks=@(); content_policy_fallbacks=@()}
}
# JSON is a YAML subset; serialization avoids unsafe interpolation into YAML.
[IO.File]::WriteAllText("$RepoRoot/config/litellm/config.local.yaml", ($config | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
Write-Host "Rendered gateway config with $($models.Count) configured provider route(s)."

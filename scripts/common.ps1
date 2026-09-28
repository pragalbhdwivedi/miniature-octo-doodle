$ErrorActionPreference = 'Stop'
$script:RepoRoot = Split-Path $PSScriptRoot -Parent
$script:EnvPath = Join-Path $RepoRoot '.env'

function Read-LocalEnv {
  param([string]$Path = $EnvPath)
  if (!(Test-Path -LiteralPath $Path)) { throw 'Run scripts/manage.ps1 init first.' }
  $values = @{}
  foreach ($line in Get-Content -LiteralPath $Path) {
    if ($line -match '^\s*(#|$)') { continue }
    if ($line -notmatch '^([A-Z][A-Z0-9_]*)=(.*)$') { throw 'Invalid .env line; use NAME=value.' }
    $name, $value = $Matches[1], $Matches[2].Trim()
    if ($value -match '[\s''"$`#]') { throw "Unsupported characters in $name; use an unquoted value without interpolation." }
    if ($values.ContainsKey($name)) { throw "Duplicate .env setting: $name" }
    $values[$name] = $value
  }
  return $values
}

function Invoke-CoreCompose {
  param([string[]]$Arguments)
  # Local configuration takes precedence over unrelated shell environment values.
  $values = Read-LocalEnv
  $saved = @{}
  try {
    foreach ($name in $values.Keys) {
      $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
      [Environment]::SetEnvironmentVariable($name, $values[$name], 'Process')
    }
    & docker compose --project-directory $RepoRoot --env-file $EnvPath -f "$RepoRoot/compose.yaml" @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed (exit $LASTEXITCODE)." }
  } finally {
    foreach ($name in $saved.Keys) {
      if ($null -eq $saved[$name]) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
      else { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
    }
  }
}

function Assert-CoreSecrets {
  param([hashtable]$Values)
  foreach ($name in @('POSTGRES_PASSWORD','LITELLM_MASTER_KEY','LITELLM_SALT_KEY','WEBUI_SECRET_KEY','WEBUI_ADMIN_PASSWORD')) {
    if (!$Values[$name] -or $Values[$name] -like '*replace-me*' -or $Values[$name].Length -lt 32) {
      throw "$name must contain a local secret of at least 32 characters."
    }
  }
  foreach ($name in @('POSTGRES_USER','POSTGRES_DB','POSTGRES_PASSWORD')) {
    if ($Values[$name] -notmatch '^[A-Za-z0-9_-]+$') { throw "$name must be URL-safe (letters, digits, underscore, hyphen)." }
  }
}

function Assert-DiskReserve {
  param([double]$FreeGiB, [double]$AdditionalGiB, [double]$CriticalGiB = 15, [double]$WarningGiB = 25)
  if ($CriticalGiB -lt 15 -or $WarningGiB -lt 25 -or $AdditionalGiB -lt 0) { throw 'Storage thresholds cannot weaken repository policy.' }
  if (($FreeGiB - $AdditionalGiB) -lt $CriticalGiB) { throw "Disk reserve failed: $FreeGiB GiB free minus $AdditionalGiB GiB estimated would leave less than $CriticalGiB GiB." }
  if (($FreeGiB - $AdditionalGiB) -lt $WarningGiB) { Write-Warning 'Projected free space is below the warning threshold.' }
}

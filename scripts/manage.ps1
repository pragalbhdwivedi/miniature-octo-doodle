param(
  [Parameter(Position=0)]
  [ValidateSet("status","components","disk","preflight","start","stop")]
  [string]$Command = "status"
)

switch ($Command) {
  "preflight" { & "$PSScriptRoot/preflight.ps1" }
  "disk"      { & "$PSScriptRoot/disk-report.ps1" }
  "start"     { docker compose up -d }
  "stop"      { docker compose down }
  "status"    { docker compose ps }
  "components" {
    Write-Host "Component registry: config/components.yaml"
    Get-Content "$PSScriptRoot/../config/components.yaml"
  }
}

# Install/uninstall commands are intentionally not implemented yet.
# They must first enforce dependency and disk-safety checks.

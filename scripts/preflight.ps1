param()

$ErrorActionPreference = "Continue"

Write-Host "miniature-octo-doodle preflight"
Write-Host "================================"

$drive = Get-PSDrive -Name C
$freeGB = [math]::Round($drive.Free / 1GB, 2)
Write-Host "C: free space: $freeGB GB"

$warning = 25
$critical = 15
if ($env:DISK_WARNING_GB) { $warning = [double]$env:DISK_WARNING_GB }
if ($env:DISK_CRITICAL_GB) { $critical = [double]$env:DISK_CRITICAL_GB }

if ($freeGB -lt $critical) {
  Write-Error "CRITICAL: free space is below $critical GB. Do not install optional components."
  exit 2
}
elseif ($freeGB -lt $warning) {
  Write-Warning "Free space is below the warning threshold of $warning GB."
}

Write-Host ""
Write-Host "Docker:"
docker --version
docker compose version

Write-Host ""
Write-Host "WSL:"
wsl --version

Write-Host ""
Write-Host "NVIDIA:"
nvidia-smi

Write-Host ""
Write-Host "Preflight finished. Review failures before installation."

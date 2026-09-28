param([switch]$ForInstall)
. "$PSScriptRoot/common.ps1"
$values = if (Test-Path $EnvPath) { Read-LocalEnv } else { Read-LocalEnv -Path "$RepoRoot/.env.example" }
$additional = if ($ForInstall) { [double]$values.CORE_ESTIMATED_GB } else { 0 }
if ($ForInstall -and $additional -lt 12) { throw 'The core pull reserve must be at least 12 GiB.' }
if ($env:OS -ne 'Windows_NT') { throw 'Target preflight requires Windows with Docker Desktop / WSL2.' }

$storagePaths = @($RepoRoot, "$env:LOCALAPPDATA/Docker/wsl")
$settingsPath = Join-Path $env:APPDATA 'Docker/settings-store.json'
if (!(Test-Path $settingsPath)) { throw 'Docker Desktop settings not found; verify storage/backend manually.' }
$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
if ($settings.WslEngineEnabled -ne $true) { throw 'Docker Desktop WSL2 backend is not enabled.' }
foreach ($name in @('DataFolder','DiskImageLocation')) {
  if ($settings.$name) { $storagePaths += [string]$settings.$name }
}
$drives = $storagePaths | ForEach-Object { [IO.Path]::GetPathRoot($_).TrimEnd('\').TrimEnd(':') } | Sort-Object -Unique
foreach ($driveName in $drives) {
  $drive = Get-PSDrive -Name $driveName
  $free = [math]::Round($drive.Free / 1GB, 2)
  Write-Host "${driveName}: $free GiB free; projected additional reserve $additional GiB"
  Assert-DiskReserve -FreeGiB $free -AdditionalGiB $additional -CriticalGiB ([double]$values.DISK_CRITICAL_GB) -WarningGiB ([double]$values.DISK_WARNING_GB)
}
& docker --version
if ($LASTEXITCODE -ne 0) { throw 'Docker CLI unavailable.' }
& docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Compose unavailable.' }
$infoText = & docker info --format '{{json .}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker daemon unavailable.' }
$info = $infoText | ConvertFrom-Json
if ($info.OSType -ne 'linux' -or $info.OperatingSystem -ne 'Docker Desktop' -or $info.KernelVersion -notmatch 'WSL2') { throw 'Expected local Docker Desktop Linux engine on WSL2.' }
$endpoint = (& docker context inspect --format '{{.Endpoints.docker.Host}}')
if ($LASTEXITCODE -ne 0 -or $endpoint -notlike 'npipe:*' -or $env:DOCKER_HOST) { throw 'Use a local Docker Desktop context without DOCKER_HOST override.' }
Write-Host "Docker server $($info.ServerVersion); $($info.KernelVersion); root $($info.DockerRootDir)"
& docker system df
if ($LASTEXITCODE -ne 0) { throw 'Docker usage report failed.' }
(& wsl --version) -replace "`0", ''
if ($LASTEXITCODE -ne 0) { throw 'WSL unavailable.' }
(& wsl --list --verbose) -replace "`0", ''
if ($LASTEXITCODE -ne 0) { throw 'WSL distribution discovery failed.' }
Get-ChildItem -LiteralPath "$env:LOCALAPPDATA/Docker/wsl" -Recurse -Filter '*.vhdx' -ErrorAction SilentlyContinue |
  Select-Object FullName, @{Name='AllocatedFileGiB';Expression={[math]::Round($_.Length/1GB,2)}} | Format-Table -AutoSize
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
  if ($LASTEXITCODE -ne 0) { Write-Warning 'Host GPU probe failed; cloud core does not require a GPU.' }
} else { Write-Warning 'nvidia-smi unavailable; cloud core does not require a GPU.' }
Write-Host 'Core preflight passed. GPU passthrough requires a separate no-download probe; no optional image was pulled.'

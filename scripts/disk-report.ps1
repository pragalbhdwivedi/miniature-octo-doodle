param()

$ErrorActionPreference = 'Stop'

Write-Host "Host disk"
Get-PSDrive -PSProvider FileSystem |
  Select-Object Name,
    @{Name='UsedGB';Expression={[math]::Round($_.Used/1GB,2)}},
    @{Name='FreeGB';Expression={[math]::Round($_.Free/1GB,2)}} |
  Format-Table -AutoSize

Write-Host ""
Write-Host "Docker disk usage"
docker system df
if ($LASTEXITCODE -ne 0) { throw "Docker usage report failed (exit $LASTEXITCODE)." }

Write-Host ""
Write-Host "This script reports usage only. It does not delete anything."

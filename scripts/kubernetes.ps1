param([Parameter(Mandatory)][ValidateSet('cluster','deploy','test','start','stop')][string]$Action)
. "$PSScriptRoot/common.ps1"
& "$PSScriptRoot/preflight.ps1"
$python = Join-Path $RepoRoot '.venv/Scripts/python.exe'
if (!(Test-Path $python)) { throw 'Create .venv and install requirements-ci.txt first.' }
$kubeRoot = Join-Path $env:LOCALAPPDATA 'GatewayAI/kubernetes'
New-Item -ItemType Directory -Force -Path $kubeRoot | Out-Null
if ((Get-Item $kubeRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Private storage cannot be a reparse point.' }
$kubeRoot = (& $python -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1])/".location"; p.write_text("GatewayAI Kubernetes"); print(p.resolve().parent)' $kubeRoot).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve physical private storage.' }
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true, $false)
foreach ($identity in @([Security.Principal.WindowsIdentity]::GetCurrent().User, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
}
[IO.FileSystemAclExtensions]::SetAccessControl([IO.DirectoryInfo]::new($kubeRoot), $acl)
$k3d = Join-Path $RepoRoot 'tmp/tools/k3d.exe'
if ($Action -eq 'cluster') {
  Assert-DiskReserve -FreeGiB ((Get-PSDrive C).Free / 1GB) -AdditionalGiB 8
  New-Item -ItemType Directory -Force (Split-Path $k3d) | Out-Null
  if (!(Test-Path $k3d)) {
    Invoke-WebRequest 'https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-windows-amd64.exe' -OutFile $k3d
  }
  if ((Get-FileHash $k3d -Algorithm SHA256).Hash.ToLowerInvariant() -ne '49d0b9c796f5b8ba6f58a1dd5469e8b7b34bf9b6ce9078633eedb2789680a034') { throw 'k3d checksum mismatch.' }
  # k3d 5.9.0 needs its standard image volume on this Docker Desktop target.
  & $k3d cluster create gatewayai --image rancher/k3s:v1.35.5-k3s1@sha256:2074403abe1bded11ef3dde09d457e13be8e0b64c218b1c4f8269b4565cfbc65 --servers 1 --agents 0 --servers-memory 6g --api-port 127.0.0.1:6550 --port '127.0.0.1:3080:80@loadbalancer' --kubeconfig-update-default=false --kubeconfig-switch-context=false --k3s-arg '--disable=metrics-server@server:0' --k3s-arg '--secrets-encryption@server:0' --no-rollback --timeout 180s
  if ($LASTEXITCODE -ne 0) { throw 'Cluster creation failed; inspect retained nodes before retrying.' }
}
if ($Action -in @('cluster','deploy')) {
  if ($Action -eq 'deploy') { Assert-DiskReserve -FreeGiB ((Get-PSDrive C).Free / 1GB) -AdditionalGiB 4 }
  if (!(Test-Path $k3d)) { throw 'Run the cluster action first.' }
  $config = & $k3d kubeconfig get gatewayai
  if ($LASTEXITCODE -ne 0) { throw 'Dedicated cluster kubeconfig unavailable.' }
  [IO.File]::WriteAllText((Join-Path $kubeRoot 'kubeconfig.yaml'), ($config -join "`n"), [Text.UTF8Encoding]::new($false))
}
if ($Action -in @('start','stop')) {
  & $k3d cluster $Action gatewayai
  if ($LASTEXITCODE -ne 0) { throw 'Cluster lifecycle operation failed.' }
} elseif ($Action -in @('deploy','test')) {
  & $python "$PSScriptRoot/kubernetes.py" $Action --root $kubeRoot
  if ($LASTEXITCODE -ne 0) { throw 'Kubernetes operation failed; existing data preserved.' }
}
Write-Host "Kubernetes $Action complete. Private configuration: $kubeRoot"

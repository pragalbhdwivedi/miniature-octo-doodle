param(
  [Parameter(Mandatory)][ValidateSet('backup','restore','verify')][string]$Action,
  [string]$Backup,
  [string]$Name,
  [int]$GatewayPort = 4400,
  [int]$WebUIPort = 4300
)
. "$PSScriptRoot/common.ps1"
& "$PSScriptRoot/preflight.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Preflight failed.' }
# Keep credentials and runtime data outside the repository and OneDrive.
$recoveryRoot = Join-Path $env:LOCALAPPDATA 'GatewayAI/recovery'
if (!(Test-Path -LiteralPath $recoveryRoot)) { New-Item -ItemType Directory -Path $recoveryRoot -Force | Out-Null }
if ((Get-Item -LiteralPath $recoveryRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Recovery root cannot be a reparse point.' }
# Packaged terminals can virtualize LocalAppData. Resolve a newly written file's
# physical path so Windows and Docker see the same private directory.
$recoveryRoot = (& python -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1])/".location"; p.write_text("GatewayAI recovery root"); print(p.resolve().parent)' $recoveryRoot).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve physical recovery storage.' }
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true, $false)
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
foreach ($identity in @($sid, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
  $rule = [Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
  $acl.AddAccessRule($rule)
}
# Write the DACL only; Set-Acl's provider can request SACL privileges on repeat runs.
[IO.FileSystemAclExtensions]::SetAccessControl([IO.DirectoryInfo]::new($recoveryRoot), $acl)
$arguments = @("$PSScriptRoot/recovery.py", $Action, '--root', $recoveryRoot)
if ($Backup) { $arguments += @('--backup', $Backup) }
if ($Name) { $arguments += @('--name', $Name) }
$arguments += @('--gateway-port', $GatewayPort, '--webui-port', $WebUIPort)
& python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Recovery operation failed; existing volumes are preserved. See the last safe progress message.' }

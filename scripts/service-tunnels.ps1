param(
    [Parameter(Mandatory=$true)][string]$PrivateDirectory,
    [string]$SshAlias = 'gatewayai-direct'
)
# Outbound-only transport for the existing laptop services. Does not change
# application configuration, credentials, data, firewall or Kubernetes resources.
$ErrorActionPreference = 'Stop'
$mutex = [Threading.Mutex]::new($false, 'Local\GatewayAI-ServiceTunnels')
if (-not $mutex.WaitOne(0)) { exit 0 }
$children = @{}
try {
    if (-not [IO.Path]::IsPathFullyQualified($PrivateDirectory) -or
        -not (Test-Path -LiteralPath $PrivateDirectory -PathType Container)) {
        throw 'Provision an absolute protected private directory first.'
    }
    if (Get-NetTCPConnection -LocalPort 18444 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Port 18444 is already owned; refusing to adopt or stop another process.'
    }
    $ssh = (Get-Command ssh.exe -ErrorAction Stop).Source
    $kubectl = (Get-Command kubectl.exe -ErrorAction Stop).Source
    while ($true) {
        if (-not $children.kubectl -or $children.kubectl.HasExited) {
            $children.kubectl = Start-Process -FilePath $kubectl -WindowStyle Hidden -PassThru `
                -ArgumentList @('--context','docker-desktop','-n','aadi-dev-synthetic','port-forward',
                    '--address','127.0.0.1','service/aadi-console','18444:80') `
                -RedirectStandardOutput (Join-Path $PrivateDirectory 'console-forward.out.log') `
                -RedirectStandardError (Join-Path $PrivateDirectory 'console-forward.err.log')
        }
        if (-not $children.ssh -or $children.ssh.HasExited) {
            $children.ssh = Start-Process -FilePath $ssh -WindowStyle Hidden -PassThru `
                -ArgumentList @('-N','-T','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes',
                    '-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
                    '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3',
                    '-R','127.0.0.1:18770:127.0.0.1:8770',
                    '-R','127.0.0.1:18444:127.0.0.1:18444',$SshAlias) `
                -RedirectStandardOutput (Join-Path $PrivateDirectory 'ssh.out.log') `
                -RedirectStandardError (Join-Path $PrivateDirectory 'ssh.err.log')
        }
        Start-Sleep -Seconds 10
    }
} finally {
    foreach ($child in $children.Values) {
        if ($child -and -not $child.HasExited) { $child.Kill() }
    }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}

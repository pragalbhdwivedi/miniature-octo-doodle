param(
    [Parameter(Mandatory=$true)][string]$PrivateDirectory,
    [string]$SshAlias = 'gatewayai-via-bastion'
)
# Reconnect the laptop's loopback-only Ollama to a VM loopback port after moves.
# This does not publish Ollama on the laptop LAN or hold a gateway credential.
$ErrorActionPreference = 'Stop'
$mutex = [Threading.Mutex]::new($false, 'Local\GatewayAI-LocalModelTunnel')
if (-not $mutex.WaitOne(0)) { exit 0 }
$child = $null
try {
    if (-not [IO.Path]::IsPathRooted($PrivateDirectory) -or
        -not (Test-Path -LiteralPath $PrivateDirectory -PathType Container)) {
        throw 'A protected absolute log directory is required.'
    }
    $ssh = (Get-Command ssh.exe -ErrorAction Stop).Source
    while ($true) {
        $localReady = $false
        try {
            $version = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 3
            $localReady = [bool]$version.version
        } catch { }
        if ($localReady -and (-not $child -or $child.HasExited)) {
            $child = Start-Process -FilePath $ssh -WindowStyle Hidden -PassThru `
                -ArgumentList @('-N','-T','-o','BatchMode=yes',
                    '-o','ExitOnForwardFailure=yes','-o','StrictHostKeyChecking=yes',
                    '-o','ConnectTimeout=10','-o','ServerAliveInterval=15',
                    '-o','ServerAliveCountMax=3',
                    '-R','127.0.0.1:11435:127.0.0.1:11434',$SshAlias) `
                -RedirectStandardOutput (Join-Path $PrivateDirectory 'ssh.out.log') `
                -RedirectStandardError (Join-Path $PrivateDirectory 'ssh.err.log')
        }
        Start-Sleep -Seconds 10
    }
} finally {
    if ($child -and -not $child.HasExited) { $child.Kill() }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}

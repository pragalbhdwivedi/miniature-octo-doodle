param(
    [Parameter(Mandatory = $true)][string]$CertificatePath,
    [Parameter(Mandatory = $true)][string]$ExpectedSha256
)
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script in an administrator PowerShell. No trust settings were changed.'
}
$resolved = (Resolve-Path -LiteralPath $CertificatePath).Path
$certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new($resolved)
$sha = [Security.Cryptography.SHA256]::Create()
try {
    $actual = [BitConverter]::ToString($sha.ComputeHash($certificate.RawData)).Replace('-', '').ToLowerInvariant()
} finally { $sha.Dispose() }
if ($actual -ne $ExpectedSha256.Replace(':', '').ToLowerInvariant()) {
    throw 'CA fingerprint mismatch. No trust settings were changed.'
}
if ($certificate.HasPrivateKey -or $certificate.Subject -ne $certificate.Issuer) {
    throw 'Expected a public, self-signed CA certificate.'
}
Import-Certificate -FilePath $resolved -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
$installed = Get-Item -LiteralPath "Cert:\LocalMachine\Root\$($certificate.Thumbprint)"
if ($installed.Thumbprint -ne $certificate.Thumbprint) { throw 'Certificate readback failed.' }
Write-Output "Installed public CA; SHA-256 $actual"

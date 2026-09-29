param()
. "$PSScriptRoot/common.ps1"
if (Test-Path -LiteralPath $EnvPath) { throw '.env already exists; refusing to replace secrets.' }
$content = Get-Content "$RepoRoot/.env.example" -Raw
foreach ($name in @('POSTGRES_PASSWORD','LITELLM_MASTER_KEY','LITELLM_SALT_KEY','WEBUI_SECRET_KEY','WEBUI_ADMIN_PASSWORD')) {
  $bytes = New-Object byte[] 32
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  $secret = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
  if ($name -eq 'LITELLM_MASTER_KEY') { $secret = "sk-$secret" }
  $content = $content.Replace("$name=replace-me-locally", "$name=$secret")
}
[IO.File]::WriteAllText($EnvPath, $content, [Text.UTF8Encoding]::new($false))
Write-Host 'Created local .env. Keep it private and preserve it with your protected backups.'

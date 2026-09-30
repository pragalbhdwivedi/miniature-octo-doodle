param(
  [Parameter(Position=0)]
  [ValidateSet('init','status','components','disk','preflight','configure','start','stop','test')]
  [string]$Command = 'status',
  [ValidateSet('gateway','all')][string]$Stage = 'all',
  [switch]$ContainerOnly
)
. "$PSScriptRoot/common.ps1"
switch ($Command) {
  'init' { & "$PSScriptRoot/init-env.ps1" }
  'preflight' { & "$PSScriptRoot/preflight.ps1" }
  'disk' { & "$PSScriptRoot/disk-report.ps1" }
  'configure' { & "$PSScriptRoot/render-config.ps1" }
  'start' {
    if (Test-Path -LiteralPath "$RepoRoot/.migration-handoff.json") {
      throw 'This source was frozen for VM migration. Reconcile the current VM ledger/data before an explicit rollback; do not start a duplicate live gateway.'
    }
    $values = Read-LocalEnv
    Assert-CoreSecrets -Values $values
    & "$PSScriptRoot/preflight.ps1" -ForInstall
    & "$PSScriptRoot/render-config.ps1"
    Invoke-CoreCompose -Arguments @('config','--quiet')
    # Only the three core services exist. No optional profile or model download.
    $services = if ($Stage -eq 'gateway') { @('postgres','litellm') } else { @('postgres','litellm','open-webui') }
    Invoke-CoreCompose -Arguments (@('pull') + $services)
    & "$PSScriptRoot/preflight.ps1"
    Invoke-CoreCompose -Arguments @('up','-d','--pull','never','--wait','--wait-timeout','300','postgres')
    # A bind-mounted config change alone does not trigger Compose recreation.
    Invoke-CoreCompose -Arguments @('up','-d','--no-deps','--force-recreate','--pull','never','--wait','--wait-timeout','300','litellm')
    if ($Stage -eq 'all') {
      & "$PSScriptRoot/provision-webui-key.ps1"
      Invoke-CoreCompose -Arguments @('up','-d','--pull','never','--wait','--wait-timeout','300','open-webui')
    }
  }
  'stop' { Invoke-CoreCompose -Arguments @('stop') }
  'status' { Invoke-CoreCompose -Arguments @('ps') }
  'test' { & "$PSScriptRoot/test-core.ps1" -Stage $Stage -ContainerOnly:$ContainerOnly }
  'components' { Get-Content "$RepoRoot/config/components.yaml" }
}

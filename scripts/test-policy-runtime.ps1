param()
. "$PSScriptRoot/common.ps1"
$probe = Get-Content "$PSScriptRoot/test-policy-runtime.py" -Raw
Invoke-CoreCompose -Arguments @('exec','-T','litellm','python','-u','-c',$probe)

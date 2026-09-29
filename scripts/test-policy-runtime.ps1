param([switch]$Matrix)
. "$PSScriptRoot/common.ps1"
$probe = Get-Content "$PSScriptRoot/test-policy-runtime.py" -Raw
$modes = if ($Matrix) { @('both','openai','gemini','none') } else { @('configured') }
foreach ($mode in $modes) {
  Invoke-CoreCompose -Arguments @('exec','-T','litellm','python','-u','-c',$probe,$mode)
}

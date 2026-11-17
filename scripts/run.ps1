param([Parameter(Mandatory=$true)][string]$Python,[Parameter(ValueFromRemainingArguments=$true)][string[]]$EngineArgs)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
& $Python (Join-Path $projectRoot 'src/main.py') @EngineArgs
exit $LASTEXITCODE

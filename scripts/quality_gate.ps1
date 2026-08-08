# Project Loot Raiders - Quality Gate PowerShell Executable Wrapper
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$env:PYTHONPATH = "."
python "$PSScriptRoot\quality_gate.py"
exit $LASTEXITCODE

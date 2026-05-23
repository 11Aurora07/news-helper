Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$logDir = Join-Path $projectRoot "data"
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$outLog = Join-Path $logDir "webui.out.log"
$errLog = Join-Path $logDir "webui.err.log"

& python -m webui.serve *>> $outLog

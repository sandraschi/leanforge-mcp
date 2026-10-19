#Requires -Version 5.1
<#
.SYNOPSIS
Pre-commit Biome gate for webapp/frontend (fleet template hook).
Runs `bun run biome:ci` when the frontend exists; passes silently otherwise.
#>
$ErrorActionPreference = "Stop"

$webapp = "$PSScriptRoot\..\webapp\frontend"
if (-not (Test-Path (Join-Path $webapp "package.json"))) { exit 0 }

$bun = Join-Path $env:USERPROFILE ".bun\bin\bun.exe"
if (-not (Test-Path $bun)) { $bun = "bun" }

Push-Location $webapp
try {
    & $bun run biome:ci
    if ($LASTEXITCODE -ne 0) { exit 1 }
} finally {
    Pop-Location
}

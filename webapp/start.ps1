# Start leanforge-mcp webapp (backend + frontend)
param([switch]$BackendOnly, [switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $PSCommandPath
$BackendPort = 10855
$FleetStartPath = Join-Path $ProjectRoot "scripts\FleetStartMode.ps1"
if (-not (Test-Path -LiteralPath $FleetStartPath)) {
    Write-Host "ERROR: Missing vendored launcher helper: $FleetStartPath" -ForegroundColor Red
    exit 1
}
. $FleetStartPath

$FrontendPort = 10856

Write-Host "leanforge-mcp webapp" -ForegroundColor Cyan

# Kill zombies
Get-NetTCPConnection -LocalPort $BackendPort -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Get-NetTCPConnection -LocalPort $FrontendPort -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

# Start backend
$BackendJob = Start-Job -Name "backend" -ScriptBlock {
    param($Root, $Port)
    Set-Location $Root
    uv run python -m webapp.backend.main
} -ArgumentList (Resolve-Path "$ScriptRoot/.."), $BackendPort

# Wait for backend
Write-Host "Waiting for backend on port $BackendPort..."
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) { Write-Host "Backend ready"; break }
    } catch {}
    Start-Sleep 1
}

if ($BackendOnly) {
    Write-Host "Backend running at http://127.0.0.1:$BackendPort"
    Write-Host "Press Ctrl+C to stop"
    while ($true) { Start-Sleep 60 }
    return
}

# Start frontend
$FrontRoot = Resolve-Path "$ScriptRoot/frontend"
Start-Process -NoNewWindow -FilePath "npx" -ArgumentList "vite --port $FrontendPort --host" -WorkingDirectory $FrontRoot

$Url = "http://127.0.0.1:$FrontendPort"
Write-Host "Frontend at $Url"

if (-not $NoBrowser) {
    Start-Sleep 3
    Start-Process $Url
}

# Keep-alive
while ($true) {
    if ($BackendJob.State -eq "Completed" -or $BackendJob.State -eq "Failed") {
        Receive-Job $BackendJob; break
    }
    Start-Sleep 2
}

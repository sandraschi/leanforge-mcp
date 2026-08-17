# Start leanforge-mcp webapp (backend + frontend)
# Naked-PC compliant: see mcd/standards/NAKED_PC_INSTALL_STANDARD.md
param([switch]$BackendOnly, [switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $PSCommandPath
$RepoRoot = Resolve-Path "$ScriptRoot/.."
$FrontRoot = Join-Path $ScriptRoot "frontend"
$BackendPort = 10867
$FrontendPort = 10868

function Require-Command {
    param([string]$Cmd, [string]$WingetId, [string]$Label)
    if (Get-Command $Cmd -ErrorAction SilentlyContinue) { return }
    Write-Host "  $Label not found - installing via winget ..." -ForegroundColor Yellow
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: winget unavailable. Install $Label manually ($WingetId)." -ForegroundColor Red
        exit 1
    }
    winget install --id $WingetId --silent --accept-source-agreements --accept-package-agreements
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
    if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) {
        Write-Host "Installed $Label but '$Cmd' still not in PATH. Reopen PowerShell and retry." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "leanforge-mcp webapp" -ForegroundColor Cyan

Require-Command "uv"  "Astral.uv"        "uv (Python package manager)"
Require-Command "node" "OpenJS.NodeJS.LTS" "Node.js LTS"
Require-Command "npm"  "OpenJS.NodeJS.LTS" "npm"

# npm install if node_modules is absent OR missing any declared dependency
# (NAKED_PC_INSTALL_STANDARD SS3). A bare "does node_modules exist" check
# misses the case where package.json gained a new dependency after the
# last install -- exactly what happened here: react-markdown/remark-gfm
# were declared but never actually installed, producing a confusing Vite
# import-resolution error instead of a clear install-time failure.
$nodeModulesPath = Join-Path $FrontRoot "node_modules"
$needsInstall = -not (Test-Path $nodeModulesPath)
if (-not $needsInstall) {
    $pkg = Get-Content (Join-Path $FrontRoot "package.json") -Raw | ConvertFrom-Json
    $allDeps = @()
    if ($pkg.dependencies) { $allDeps += $pkg.dependencies.PSObject.Properties.Name }
    if ($pkg.devDependencies) { $allDeps += $pkg.devDependencies.PSObject.Properties.Name }
    foreach ($dep in $allDeps) {
        if (-not (Test-Path (Join-Path $nodeModulesPath $dep))) {
            Write-Host "  Missing dependency: $dep" -ForegroundColor Yellow
            $needsInstall = $true
        }
    }
}
if ($needsInstall) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $FrontRoot
    & npm.cmd install --prefer-offline 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: npm install failed." -ForegroundColor Red
        Pop-Location; exit 1
    }
    Pop-Location
}

# Explicit vite guard (NAKED_PC_INSTALL_STANDARD SS4 -- vite is a
# devDependency and must be local, never assumed global). Target the
# .cmd shim specifically: the extensionless `vite` file npm also creates
# is a POSIX shell script for Git Bash/WSL, not a Win32 executable --
# Start-Process cannot launch it directly ("%1 is not a valid Win32
# application").
$viteLocal = Join-Path $FrontRoot "node_modules\.bin\vite.cmd"
if (-not (Test-Path $viteLocal)) {
    Write-Host "ERROR: vite.cmd missing from node_modules after npm install." -ForegroundColor Red
    Write-Host "Delete '$FrontRoot\node_modules' and re-run." -ForegroundColor Yellow
    exit 1
}

# Kill zombies
Get-NetTCPConnection -LocalPort $BackendPort -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Get-NetTCPConnection -LocalPort $FrontendPort -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

# Import smoke-test before the health-wait loop (NAKED_PC_INSTALL_STANDARD
# SS5 -- surfaces a startup crash immediately instead of a 60s health timeout)
$uvExe = (Get-Command uv).Source
Push-Location $RepoRoot
& $uvExe run --extra web python -c "import webapp.backend.main; print('  [ok] Import OK')"
$importOk = ($LASTEXITCODE -eq 0)
Pop-Location
if (-not $importOk) {
    Write-Host "ERROR: backend import check failed -- see output above." -ForegroundColor Red
    exit 1
}

# Start backend
$BackendJob = Start-Job -Name "backend" -ScriptBlock {
    param($Root, $Port)
    Set-Location $Root
    uv run --extra web python -m webapp.backend.main
} -ArgumentList $RepoRoot, $BackendPort

# Wait for backend
Write-Host "Waiting for backend on port $BackendPort..."
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) { Write-Host "Backend ready"; $ready = $true; break }
    } catch {}
    Start-Sleep 1
}
if (-not $ready) {
    Write-Host "ERROR: backend health timed out after 60s." -ForegroundColor Red
    Write-Host "Run this directly to see the error:" -ForegroundColor Yellow
    Write-Host "  cd $RepoRoot; $uvExe run python -m webapp.backend.main" -ForegroundColor Yellow
    Receive-Job $BackendJob
    exit 1
}

if ($BackendOnly) {
    Write-Host "Backend running at http://127.0.0.1:$BackendPort"
    Write-Host "Press Ctrl+C to stop"
    while ($true) { Start-Sleep 60 }
    return
}

# Start frontend
Start-Process -NoNewWindow -FilePath $viteLocal -ArgumentList "--port $FrontendPort --host" -WorkingDirectory $FrontRoot

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

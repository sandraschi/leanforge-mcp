# leanforge-mcp start.ps1
# Bootstrap and run the server on Windows (Goliath)
# Usage: .\start.ps1 [-Install] [-Check]

param(
    [switch]$Install,
    [switch]$Check
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name, [string]$InstallHint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "âœ- $Name not found. $InstallHint"
        exit 1
    }
    Write-Host "âœ… $Name found at $(where.exe $Name 2>$null | Select-Object -First 1)"
}

Write-Host "leanforge-mcp" -ForegroundColor Cyan
Write-Host "=============" -ForegroundColor Cyan

Require-Command "uv"   "Install: winget install astral-sh.uv"
Require-Command "lean" "Install: winget install leanprover.elan  then: elan install leanprover/lean4:stable"

if (-not (Test-Path "config.toml")) {
    Write-Warning "config.toml not found. Copying from config.example.toml..."
    Copy-Item "config.example.toml" "config.toml"
    Write-Warning "Edit config.toml before running (check Lean path, API keys)."
    exit 1
}

if ($Install -or -not (Test-Path ".venv")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    uv sync
}

if ($Check) {
    Write-Host "âœ… Dependency check passed" -ForegroundColor Green
    exit 0
}

New-Item -ItemType Directory -Force -Path "data"      | Out-Null
New-Item -ItemType Directory -Force -Path "logs"      | Out-Null
New-Item -ItemType Directory -Force -Path "workspace" | Out-Null

Write-Host "Starting leanforge-mcp..." -ForegroundColor Green
uv run python -m leanforge_mcp

set windows-shell := ["powershell.exe", "-NoProfile", "-Command"]

# leanforge-mcp justfile
import 'scripts/just/fleet.just'

REPO := justfile_directory()

# leanforge-mcp justfile
default:
    just --list

# Install all dependencies (core + dev + web)
install:
    uv sync --extra dev --extra web

# Run MCP server (stdio)
serve:
    uv run python -m leanforge_mcp

# Run web backend + frontend
web:
    Set-Location '{{justfile_directory()}}'; uv run python -m webapp.backend.main

# Bun resolution: CI puts bun on PATH (oven-sh/setup-bun); on dev machines it
# lives off-PATH at %USERPROFILE%\.bun\bin. Every frontend recipe resolves it
# the same way instead of assuming PATH.
BUN_RESOLVE := "$bunExe = if (Get-Command bun -ErrorAction SilentlyContinue) { 'bun' } else { \"$env:USERPROFILE\\.bun\\bin\\bun.exe\" }; if (-not (Get-Command $bunExe -ErrorAction SilentlyContinue) -and -not (Test-Path $bunExe)) { throw 'bun not found on PATH or at %USERPROFILE%/.bun/bin -- install from https://bun.sh' };"

# Run web frontend only (Vite dev)
web-frontend:
    {{BUN_RESOLVE}} Set-Location '{{justfile_directory()}}\webapp\frontend'; & $bunExe x vite --port 10868 --host

# Run both backend + frontend with auto-open
web-dev:
    Set-Location '{{justfile_directory()}}\webapp'; .\start.ps1

# Lint
lint:
    uv run ruff check src/ webapp/backend/

# Format
fmt:
    uv run ruff format src/ webapp/backend/

# Format check
format-check:
    uv run ruff format --check src/ webapp/backend/

# Typecheck (Python)
typecheck:
    uv run --with pyright pyright src/

# Run tests
test:
    uv run pytest tests/ -v

# Full local gate set (mirrors CI backend + frontend)
certify:
    uv run ruff check src/ webapp/backend/; uv run ruff format --check src/ webapp/backend/; uv run --with pyright pyright src/; uv run pytest tests/ -q; {{BUN_RESOLVE}} Set-Location '{{justfile_directory()}}\webapp\frontend'; & $bunExe install --frozen-lockfile; & $bunExe run check; & $bunExe run biome:ci; & $bunExe run build

# Alias for certify
gates-green:
    just certify

# Smoke test (requires Lean workspace)
smoke:
    uv run python scripts/smoke_test.py

# Build frontend for production
build-web:
    {{BUN_RESOLVE}} Set-Location '{{justfile_directory()}}\webapp\frontend'; & $bunExe install --frozen-lockfile; & $bunExe run build
# --- Playwright E2E ---

# Install Playwright browsers (one-time)
e2e-install:
    {{BUN_RESOLVE}} Set-Location '{{REPO}}\webapp\frontend'; & $bunExe x playwright install chromium

# Run Playwright E2E smoke tests (start backend first: just serve)
e2e:
    {{BUN_RESOLVE}} Set-Location '{{REPO}}\webapp\frontend'; & $bunExe x playwright test

# CUA + MCPB recipes come from the fleet import (scripts/just/fleet.just):
# just mcpb-pack | just cua-nsis-test | just cua-webapp-test


# Bootstrap: install dev deps + pre-commit hook
bootstrap:
    uv sync --group dev --extra dev --extra web
    uv run --with pre-commit pre-commit install
    Write-Host "Pre-commit hooks installed." -ForegroundColor Green

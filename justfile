set windows-shell := ["powershell.exe", "-NoProfile", "-Command"]

# leanforge-mcp justfile
import 'scripts/just/fleet.just'
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
    Set-Location '{{justfile_directory()}}' && uv run python -m webapp.backend.main

# Run web frontend only (Vite dev)
web-frontend:
    Set-Location '{{justfile_directory()}}\webapp\frontend' && npx vite --port 10856 --host

# Run both backend + frontend with auto-open
web-dev:
    cd webapp && .\start.ps1

# Lint
lint:
    uv run ruff check src/

# Format
fmt:
    uv run ruff format src/

# Format check
format-check:
    uv run ruff format --check src/

# Run tests
test:
    uv run pytest tests/ -v

# Smoke test (requires Lean workspace)
smoke:
    uv run python scripts/smoke_test.py

# Build frontend for production
build-web:
    Set-Location '{{justfile_directory()}}\webapp\frontend' && npm install && npm run build
# --- Playwright E2E ---

# Install Playwright browsers (one-time)
e2e-install:
    cd {{REPO}}\webapp/frontend
    npx playwright install chromium

# Run Playwright E2E smoke tests (start backend first: just serve)
e2e:
    cd {{REPO}}\webapp/frontend
    npx playwright test


# Bootstrap: install dev deps + pre-commit hook
bootstrap:
    uv sync --group dev
    uv run pre-commit install
    Write-Host "Pre-commit hooks installed." -ForegroundColor Green
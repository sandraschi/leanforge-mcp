# Development Setup

## Tools Required

```powershell
winget install astral-sh.uv
winget install Git.Git
winget install leanprover.elan
winget install Casey.Just
```

## Setup

```powershell
git clone https://github.com/sandraschi/leanforge-mcp
cd leanforge-mcp
uv sync --extra web --extra dev
```

The `web` extra adds FastAPI/uvicorn for the webapp backend. The `dev` extra adds
pytest and ruff.

## Common tasks

```powershell
just lint          # ruff check + ruff format --check
just format        # ruff format (auto-fix)
just test          # pytest tests/ -v  (pure Python, no Lean required)
just smoke         # scripts/smoke_test.py (needs Lean workspace)
just web-dev       # start webapp backend + frontend in dev mode
```

## Running the MCP server directly

```powershell
uv run python -m leanforge_mcp
```

Reads `config.toml` from the repo root. Starts in stdio mode by default.

## Project layout

```
src/leanforge_mcp/
  server.py           FastMCP entry point, lifespan, tool mounts
  core/
    agent.py          Proof loop, parallel subagent orchestration
    lean_client.py    lake env lean subprocess wrapper
    llm_client.py     Ollama / DeepSeek / Anthropic, tier escalation
    job_manager.py    SQLite CRUD for jobs and attempts
    runner.py         Runner class, get_runner(ctx), process fallback
    config.py         TOML loader and config dataclasses
  tools/
    submit.py         submit_theorem, submit_lean_file
    status.py         get_proof_status, list_attempts, list_jobs, validate_lean
    control.py        cancel_job
    mathlib.py        get_mathlib_search
webapp/
  backend/            FastAPI backend (port 10855)
  frontend/           Vite/React dashboard (port 10856)
scripts/
  smoke_test.py       Standalone validation script (run before Cursor tasks)
tests/
  test_pipeline.py    Pure-Python pytest (no Lean, no LLM)
```

## Critical rules

- Never call `lean` directly -- always `lake env lean <file>` via `LeanClient`
- Never hardcode paths -- always read from `Config`
- Never block the asyncio event loop -- all Lean and LLM calls are async
- Never modify theorem statements in agent edits -- the tamper guard will reject them
- Use `uv run` not bare `python`

## Code standards

- Formatter/linter: [Ruff](https://docs.astral.sh/ruff/)
- `just lint` must pass before committing
- No `asyncio.run()` inside async code
- Type annotations on all public functions

See [mcp-central-docs standards](https://github.com/sandraschi/mcp-central-docs) for fleet-wide standards.

## Phase B work (current priority)

See [docs/ASSESSMENT_2026-06-24.md](ASSESSMENT_2026-06-24.md) for the full issue list.
Quick summary of what needs doing before the first real benchmark run:

1. Fix helper-lemma tamper guard (P1-1) -- `agent.py`
2. Bracket-aware `extract_statement` regex (P1-2) -- `agent.py`
3. `owner_pid` safe interrupted-job recovery (P1-4) -- `job_manager.py`
4. `cancel_requested` column for cross-process cancel (P1-6) -- `job_manager.py`
5. Repeated-edit detection + error provenance (P2-4) -- `agent.py`
6. Smoke test gate passing

Phase C (REPL client, LLM timeout/retry, cost accounting) must be in place before
any tier-2/3 overnight batch run.

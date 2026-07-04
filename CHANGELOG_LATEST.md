# Changelog -- Latest Release

## v0.1.1 -- 2026-06-24

### Fixed

- **SQLite WAL mode** -- `_configure_db()` helper applies `journal_mode=WAL`,
  `busy_timeout=5000`, `synchronous=NORMAL` on every connection in `JobManager`.
  Two concurrent writers (stdio MCP server + webapp) no longer risk `database is
  locked` errors under load.

- **Agent parse-failure transparency** -- `PARSE_ERROR`, `EDIT_NOT_FOUND`, and
  `LLM_ERROR` branches in `run_subagent` now persist a labelled attempt record and
  call `maybe_escalate(turn)`. A tier-1 model that cannot format responses will
  escalate and leave an inspectable trajectory instead of burning its turn budget
  silently.

- **Lean error extraction false positives** -- `LeanClient._extract()` now anchors
  on the structured diagnostic prefix (`: error:` / `: warning:`) rather than bare
  substring match. Goal text containing the word "error" no longer produces phantom
  error records.

- **Field doc pseudo-Lean** -- `submit_theorem` statement field example corrected
  from English `'for all n : ℕ, ...'` to valid Lean 4 `'∀ n : ℕ, ...'`.

- **Stale server comment** -- Lifespan docstring updated to reference `get_runner(ctx)`
  rather than the removed `ctx.lifespan["runner"]` attribute.

### Removed

- `scripts/FleetStartMode.ps1` -- stray fleet artifact, not part of this repo.

---

## v0.1.0 -- 2026-06-10

Initial scaffold. See `docs/ASSESSMENT_2026-06-10.md` for full gap analysis.

- Repo structure, all docs, config schema
- `lean_client.py` -- async `lake env lean` wrapper with semaphore, timeout, sorry detection
- `agent.py` -- proof loop, parallel subagents, tier escalation, tamper guard
- `job_manager.py` -- SQLite job/attempt persistence
- `runner.py` -- `Runner` + `get_runner(ctx)` with `lifespan_context` + process fallback
- MCP tools: `submit_theorem`, `submit_lean_file`, `get_proof_status`, `list_attempts`,
  `list_jobs`, `validate_lean`, `cancel_job`, `get_mathlib_search`
- Webapp skeleton: FastAPI backend + Vite/React frontend (Dashboard, Job Inspector,
  Problem Library, New Theorem)
- P0 bugs resolved: `ctx.lifespan_context` fix, Ollama `/v1` base URL

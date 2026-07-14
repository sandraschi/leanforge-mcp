# CHANGELOG -- leanforge-mcp

All notable changes to this project will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed (2026-07-08 to 2026-07-09 -- Phase B correctness, see docs/ASSESSMENT_2026-06-24.md)

Every P1 correctness item plus P2-4 (stateless prompting) closed in one
sprint. Verified via 42 new tests, all executed for real -- first in
scratch Linux containers during development, then confirmed with
`uv run pytest tests/ -v` on Goliath itself (56/56 passed, 79.18s).

- **P1-1: helper-lemma tamper guard conflict.** The old guard hashed all
  signatures concatenated together, so a legitimate helper lemma (which
  the system prompt explicitly invites) got rejected as tampering.
  Replaced with a name-keyed check (`capture_original_signatures` /
  `check_tamper` in `agent.py`): every ORIGINAL declaration must keep its
  exact signature under its original name; new names are unrestricted.
  Keying on name (not just "is the text present anywhere") also closes a
  decoy-duplicate attack -- an agent could otherwise add a lemma
  reproducing the original text under a new name while quietly weakening
  the real theorem under its original name.
- **P1-2: `extract_statement` truncated at the first `:=`.** A default-arg
  binder's own `:=` (e.g. `(n : Nat := 0)`) was mistaken for the
  proof-start `:=`, leaving the actual return type unprotected. New
  module `core/lean_lexer.py`: a bracket/comment/string-aware scanner
  that finds the terminating `:=` at the correct nesting depth. Bonus:
  comment-stripping also eliminates a false-positive tamper class.
- **P1-4: webapp restart falsely interrupted live MCP-server jobs.**
  `JobManager.init()` unconditionally flipped every `running` job to
  `interrupted`. Added `owner_pid`/`owner_started_at` columns (the latter
  guards against OS PID reuse between crash and restart); the startup
  sweep now only interrupts jobs whose owning process is confirmed dead
  via `psutil`.
- **P1-6: cross-process cancel was a no-op.** `Runner.cancel()` only
  checked its own process's in-memory task dict. Added a
  `cancel_requested` DB column any process can set; the agent loop polls
  it once per turn via an injected callable (same pattern as the existing
  `on_attempt` hook, keeping `agent.py` DB-agnostic).
- **P2-4: stateless prompting.** Each turn was a fresh LLM call with only
  the current file + last error -- no memory of failed strategies. Added
  exact repeated-edit detection (`hash(old, new)`; skips a real Lean
  recompile, ~30-60s, when the model resends something already known to
  fail) and a rolling summary of (tactic, error-class) pairs injected into
  the prompt, capped at 8.
- (found during the P1-1 fix) tamper-rejected turns were not persisted --
  the tamper branch was the one rejection path not calling `on_attempt`.

### Fixed (2026-06-10, Phase A -- see docs/ASSESSMENT_2026-06-10.md)

- **P0: `ctx.lifespan` → proper Runner retrieval.** Installed fastmcp exposes
  `ctx.lifespan_context`, not `ctx.lifespan`; every tool call raised
  AttributeError. Additionally, the lifespan-context route through mounted
  child routers is broken in the installed fastmcp (a child's empty lifespan
  dict short-circuits the parent fallback -- verified by integration test).
  `get_runner()` now tries own lifespan dict → session request-context
  lifespan dict → process-level fallback anchored by the server lifespan
  (`set_runner_fallback`). All tools consolidated on `get_runner(ctx)`.
- **P0: Ollama tier-1 base_url missing `/v1`.** The OpenAI-compatible API is
  served at `http://localhost:11434/v1`; without the suffix every tier-1 call
  404s. Fixed in config.example.toml, config.toml, and the config.py default.
- TODO.md known-issue entries for the fastmcp lifespan import and mount()
  prefix resolved against installed fastmcp source (import valid; mount with
  no namespace keeps tool names unprefixed).
- `.gitignore`: added `*.bak`.

### Added

- `tests/test_server_integration.py` -- boots the real server in-process via
  the fastmcp in-memory Client: asserts unprefixed tool names after mount()
  and exercises the full get_runner path from a mounted child tool. This test
  caught the mounted-child lifespan short-circuit that code reading missed.
  11/11 tests passing.

### Planned

- **Phase C (next):** REPL worker pool for compile-time (P2-1 -- every turn
  currently pays a full `import Mathlib` compile, ~30-60s), LLM client
  timeout/retry hardening (P2-2), token/cost accounting -- hard gate before
  any batch run (P2-3). See TODO.md.
- EVOLVE-BLOCK marker support (Phase D+)
- Attempt Elo ranking for partial proof sketches (Phase D+)
- AlphaProof Nexus unsolved batch runner (Phase D+, blocked on P2-3 cost gate)
- Overnight job scheduler with budget cap (Phase D+, blocked on P2-3 cost gate)
- `meta_mcp` and `advanced-memory-mcp` fleet integration (Phase D+)
- Population-based agent (Agent D from AlphaProof Nexus) (Phase D+)

---

## [0.1.0] -- 2026-06-10

Initial scaffold. Architecture complete, compile pipeline correct, all
components wired. Not yet validated against a live Lean + Mathlib installation.

### Added

**Core pipeline**
- `src/leanforge_mcp/core/lean_client.py` -- async `LeanClient` wrapping
  `lake env lean <file>` inside a Mathlib Lake project workspace.
  Concurrent compile semaphore (default 4). Workspace health check on startup.
- `src/leanforge_mcp/core/agent.py` -- Agent A from AlphaProof Nexus.
  Independent subagents, LLM-propose → Lean-compile → error-feedback loop.
  Full multi-line statement tamper detection via `extract_statement()`.
  `AttemptHook` callback for SQLite persistence. Proper `asyncio.CancelledError`
  propagation.
- `src/leanforge_mcp/core/llm_client.py` -- Multi-tier async LLM client.
  Supports Ollama, OpenAI-compatible (DeepSeek), Anthropic. Per-subagent tier
  escalation via `__post_init__` + `maybe_escalate()`. Proper dataclass field
  hygiene (`field(init=False)`).
- `src/leanforge_mcp/core/job_manager.py` -- SQLite-backed job and attempt
  persistence via `aiosqlite`. Full job lifecycle (queued/running/complete/
  failed/cancelled/interrupted). Interrupted job recovery on startup.
- `src/leanforge_mcp/core/runner.py` -- `Runner` orchestrator. Fire-and-forget
  `asyncio.Task` registry with `cancel()` support. Runner stored in FastMCP
  lifespan context (`ctx.lifespan["runner"]`); no module-level globals.
- `src/leanforge_mcp/core/config.py` -- TOML config loader. Typed dataclasses
  for `LeanConfig` (lake_path, workspace_dir, compile_timeout,
  max_concurrent_compiles), `LLMConfig` (tier1/2/3), `AgentConfig`,
  `ServerConfig`, `LoggingConfig`.

**MCP tools**
- `submit_theorem` -- submit a theorem statement for proof search, returns
  job_id immediately.
- `submit_lean_file` -- submit a pre-formalized `.lean` stub with `sorry`
  placeholders.
- `get_proof_status` -- poll job; returns proven Lean file if complete.
- `list_attempts` -- inspect per-turn proof search trajectory with compiler
  feedback.
- `list_jobs` -- list all jobs with status filter.
- `cancel_job` -- cancel a live proof search task.
- `validate_lean` -- raw `lake env lean` compile, no job tracking.
- `get_mathlib_search` -- natural language → Mathlib theorem names via
  LeanSearch API.

**Server infrastructure**
- `src/leanforge_mcp/server.py` -- FastMCP 3.2 server with `@fastmcp_lifespan`
  context manager. Single event loop for all async components. Clean shutdown
  cancels live jobs. `mount()` composition with no prefix.
- `src/leanforge_mcp/__main__.py` -- enables `python -m leanforge_mcp`.

**Tooling**
- `scripts/smoke_test.py` -- standalone validation of config, Lake workspace,
  compile pipeline, sorry detection, error detection, and agent logic.
  Structured pass/fail output with recovery hints.
- `tests/test_pipeline.py` -- pure-Python pytest (no Lean required). Tests
  `_apply_edit`, `_statement_hash`, `extract_statement`, multi-line theorem
  handling.
- `config.example.toml` -- fully annotated configuration template.
- `start.ps1` -- Windows bootstrap with `Require-Command` guards.
- `glama.json`, `llms.txt` -- fleet discovery artifacts.

**Documentation**
- `README.md` -- architecture overview, GitHub LaTeX math rendering, quickstart,
  training wheels progression (MiniF2F → PutnamBench → AlphaProof Nexus
  unsolved → erdosproblems.com).
- `AGENTS.md` -- agent protocols for Cursor/Windsurf.
- `CLAUDE.md` -- Claude Desktop / Claude Code context.
- `docs/ARCHITECTURE.md` -- detailed architecture including correct one-time
  Lake workspace setup, compile invocation, SQLite schema, performance table.
- `docs/LEAN_PRIMER.md` -- Lean 4 intro for engineers.
- `docs/BENCHMARK_RESULTS.md` -- tracking template for MiniF2F, PutnamBench,
  Erdős unsolved set.
- `TODO.md` -- phased task list for Cursor continuation.

### Fixed (during scaffold session)

- **Critical: `lean --stdin` replaced with `lake env lean <file>`.**
  Bare `lean` invocation cannot resolve `import Mathlib`; must run inside a Lake
  project environment. This was a foundational compile failure.
- **Critical: package layout `src/` → `src/leanforge_mcp/`.**
  `python -m leanforge_mcp` would fail to import; flat `src/` layout not a
  valid Python package name.
- **Critical: `include_router()` → `mount()`.**
  `include_router` does not exist in FastMCP. Composition is via `mount()`.
- **Critical: dual `asyncio.run()` + `mcp.run()` event loop split.**
  `_startup()` called via `asyncio.run()` before `mcp.run()` would orphan
  JobManager connections and task registry in a dead loop. Fixed by using
  FastMCP `lifespan=` context manager.
- **`LeanConfig` field name mismatch.**
  `server.py` referenced `config.lean.lake_path` but `LeanConfig` only had
  `lean_path`. Renamed throughout and added `max_concurrent_compiles`.
- **Statement hash only caught single-line signatures.**
  Multi-line theorem statements (common in real Mathlib) had continuation lines
  unhashed. Replaced with `extract_statement()` regex capturing full signature
  up to `:=`.
- **`has_sorry` false positives from source regex.**
  `SORRY_PATTERN.search(source)` matched "sorry" in comments and strings.
  Replaced with compiler warning detection only.
- **`LLMClient._current_tier` dataclass field.**
  `_current_tier` as a plain dataclass field appeared in `__init__` and
  external mutation (`client._current_tier = tier`) was fragile. Fixed with
  `field(init=False)` + `__post_init__` + `start_tier` init parameter.
- **Unused `httpx` import in `llm_client.py`.** Removed.
- **Global runner singleton replaced with lifespan context.**
  Module-level `_runner` global replaced by `ctx.lifespan["runner"]` pattern,
  consistent with FastMCP 3.x idioms.

### Architecture decisions

- Agent A (independent subagents, no shared state) chosen over Agent D
  (population-based) for initial implementation. Simpler to reason about,
  still sufficient for research-level problems per AlphaProof Nexus results.
- `lake env lean <file>` over `lake build` for single-theorem compile speed.
  Lake project is persistent (one-time setup), temp files are per-job.
- Tier escalation is per-subagent and irreversible within a job. Cheap model
  handles mechanical fill-in; expensive model reserved for genuinely stuck
  sessions.
- SQLite over PostgreSQL. Single-user workload on Goliath; no concurrency
  pressure; no external service dependency for a research tool.

---

[Unreleased]: https://github.com/sandraschi/leanforge-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandraschi/leanforge-mcp/releases/tag/v0.1.0

# leanforge-mcp — Assessment & Gap Analysis

**Date:** 2026-06-24
**Scope:** Follow-up to 2026-06-10 assessment. All P0 items resolved; P1 correctness
fixes applied in this session. Remaining open items documented below.

---

## Status vs 2026-06-10 assessment

### Resolved (pre-session — already fixed before 2026-06-24)

| Item | Fix |
|------|-----|
| P0-1: `ctx.lifespan` AttributeError | `get_runner()` in `runner.py` uses `ctx.lifespan_context` with process-level `_runner_fallback` fallback |
| P0-2: Ollama `/v1` missing | `base_url = "http://localhost:11434/v1"` in `config.py` defaults and `config.example.toml` |
| P3-9: stale mount() comment | Resolved and TODO note removed |

### Fixed in this session (2026-06-24)

| Item | Fix | File |
|------|-----|------|
| P1-3: parse-failure branches silent | `PARSE_ERROR` / `EDIT_NOT_FOUND` / `LLM_ERROR` attempts persisted; `maybe_escalate(turn)` called on all non-compile branches | `agent.py` |
| P1-5: SQLite lock contention | `_configure_db()` helper applies WAL + `busy_timeout=5000` + `synchronous=NORMAL` on every connection | `job_manager.py` |
| P3-5: `_extract` false positives | Anchored on `: error:` / `: warning:` diagnostic prefix regex; no longer matches goal text | `lean_client.py` |
| P3-6: pseudo-Lean field doc | `'for all n : ℕ'` → `'∀ n : ℕ'` | `tools/submit.py` |
| P3-8: stray fleet file | `scripts/FleetStartMode.ps1` deleted | — |

---

## Still open

### P1 — Correctness (fix before sustained proof runs)

**P1-1: Helper-lemma tamper guard conflict**
The system prompt invites `lemma` or `have` helpers. `extract_statement()` hashes
all `theorem|lemma|example` signatures — a top-level helper lemma added by the
agent changes the signature set and gets rejected as tampering.

Fix: capture the *original* signature set at job start; require original signatures
to remain present and unmodified while permitting *additional* ones. ~15 lines in
`agent.py`.

**P1-2: `extract_statement` regex truncates at first `:=`**
Pattern `\b(theorem|lemma|example)\b.*?:=` stops at the first `:=`, which may be
inside a default-arg binder (`(n : ℕ := 0)`), leaving the actual proposition
unprotected. Fix: anchor on `:=` followed by proof-start tokens
(`:=\s*(by\b|sorry\b|calc\b|fun\b|⟨)`) or scan at bracket-depth zero.

**P1-4: Webapp startup marks live MCP-server jobs as interrupted**
`JobManager.init()` unconditionally flips `running` → `interrupted`. If the webapp
is restarted while the stdio MCP server has live jobs, those jobs are falsely
interrupted. Fix: add `owner_pid` column; `init()` only marks jobs interrupted
whose PID is no longer alive.

**P1-6: Cross-process cancel is a no-op**
`Runner.cancel()` only checks the in-process `_tasks` dict. A job started in the
MCP server cannot be cancelled from the webapp and vice versa. Fix: add
`cancel_requested INTEGER` column; agent loop polls it between turns.

### P2 — Performance and safety (gate before any batch run)

**P2-1: Cold compile per attempt — dominant bottleneck**
`import Mathlib` costs 30–60s per `lake env lean` call even with cached oleans.
At 4 agents × 100 turns, one job could take ~67 min just in compile time.
Fix: integrate [leanprover-community/repl](https://github.com/leanprover-community/repl)
— a persistent `lake env .../repl` subprocess that pays the Mathlib import once per
worker. Keep `lake env lean` as final verification of any winning proof.
Interim: make the stub template's `import Mathlib` line configurable so targeted
imports can replace it.

**P2-2: LLM client — per-call construction, no timeout, no retry**
`AsyncOpenAI`/`AsyncAnthropic` built fresh per call; no `asyncio.wait_for`
anywhere in the loop. One hung HTTP call stalls a subagent indefinitely.
Fix: cache one client per tier in `LLMClient`; wrap `complete()` in
`asyncio.wait_for(timeout=120)`; 2–3 retries with backoff.

**P2-3: No token/cost accounting — HARD GATE before overnight batches**
Tier 3 is Fable at $50/M output, `max_tokens=8192`, up to 40 tier-3 turns × 4
agents. An overnight batch without a spend meter is a budget risk.
Fix: accumulate `input_tokens`/`output_tokens` per attempt; enforce
`max_cost_per_job` from config; global cap in the batch runner.

**P2-4: Stateless prompting — model has no memory of failed strategies**
Each turn sends only the current file + last error. The model will retry the same
tactic. Fix: detect repeated identical edits (hash `old→new`) and inject explicit
feedback; maintain a rolling summary of failed (tactic, error-class) pairs.

### P3 — Hygiene

| # | Item | File |
|---|------|------|
| P3-1 | `leanforge-web` console script broken on install | `pyproject.toml` |
| P3-2 | `_from_dict()` dead code; `DatabaseConfig(**raw)` TypeError on unknown keys | `config.py` |
| P3-3 | Blocking `tmp_path.write_text` in async hot path | `lean_client.py` |
| P3-4 | `retain_workspace` config read but never honored in cleanup | `lean_client.py` |
| P3-7 | DeepSeek model id `deepseek/deepseek-v4-flash` is OpenRouter convention, not DeepSeek native API | `config.example.toml` |

---

## Process topology note (deferred)

Two processes (stdio MCP server + webapp FastAPI backend) share one SQLite DB and
each instantiate their own `Runner`. WAL mitigates lock contention but the split
task registry and doubled Mathlib RAM remain. Recommended direction: invert so the
FastAPI process owns the Runner; the stdio MCP server becomes a thin HTTP client.
This makes Claude Desktop restarts free and kills the cross-process cancel and
interrupted-job class of bugs. Effort ~1 day.

---

## Next milestone

Phase A is complete (server can serve tool calls; `validate_lean` and `list_jobs`
work; escalation and attempt persistence work correctly).

Phase B target: fix P1-1 and P1-2 (tamper guard), P1-4/P1-6 (cross-process safety),
P2-4 (stateless prompting). Then run the pure-Python pytest suite and the smoke test.

Phase C gate: P2-1 (REPL client) + P2-2 (timeout/retry) + P2-3 (cost accounting)
must all be in place before any tier-2/3 batch run.

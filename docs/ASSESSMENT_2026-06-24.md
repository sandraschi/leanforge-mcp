# leanforge-mcp -- Assessment & Gap Analysis

**Date:** 2026-06-24
**Scope:** Follow-up to 2026-06-10 assessment. All P0 items resolved; P1 correctness
fixes applied in this session. Remaining open items documented below.

> **REAL-HARDWARE VERIFICATION (2026-07-09):** `uv run pytest tests/ -v` on Goliath (Windows, Python 3.13.5): **56/56 passed in 79.18s.** Confirms every P1/P2-4 fix below holds on the actual target platform, not just the Linux scratch-container mirrors used during development. (A `PermissionError` in an unrelated pytest `atexit` temp-cleanup callback appears after the run completes -- cosmetic Windows temp-lock race, not a test failure.)

---

## Status vs 2026-06-10 assessment

### Resolved (pre-session -- already fixed before 2026-06-24)

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
| P3-8: stray fleet file | `scripts/FleetStartMode.ps1` deleted | -- |

### Fixed in this session (2026-07-09)

| Item | Fix | File |
|------|-----|------|
| P1-1: Helper-lemma tamper guard conflict | Name-keyed comparison (`capture_original_signatures`/`check_tamper`) replaces the single concatenated-hash check: every original declaration must keep its exact signature under its original NAME; new names (helper lemmas) are unrestricted. Keying on name (not just text presence) closes a decoy-duplicate attack a naive fix would miss. New module `core/lean_lexer.py`. 21 new tests, all passing (verified by actual pytest run); 7 pre-existing hash/extract tests unchanged and still passing. | `agent.py`, `lean_lexer.py` (new) |
| P1-2: `extract_statement` truncates at first `:=` | `lean_lexer.py` tracks bracket nesting depth and skips comments/strings, so a default-arg binder's own `:=` is no longer mistaken for the proof-start `:=`. Bonus: comment-stripping also eliminates a false-positive tamper class. | `lean_lexer.py` |
| (found during fix) Tamper-rejected turns not persisted | The tamper-guard branch in `run_subagent` was the one rejection path not calling `on_attempt`. Now calls it with a `TAMPER_REJECTED:` marker like the other branches. | `agent.py` |

---

## Still open

### P1 -- Correctness (fix before sustained proof runs)

~~**P1-1: Helper-lemma tamper guard conflict**~~ -- Fixed 2026-07-09 (see "Fixed in this session" above).

~~**P1-2: `extract_statement` regex truncates at first `:=`**~~ -- Fixed 2026-07-09 (see "Fixed in this session" above).

~~**P1-4: Webapp startup marks live MCP-server jobs as interrupted**~~ -- Fixed 2026-07-09. Added `owner_pid`/`owner_started_at` columns (creation-timestamp double-check guards against OS PID reuse, not just PID-alone matching); `init()`'s startup sweep now only interrupts jobs whose owning process is confirmed gone via `psutil`, leaving jobs owned by a still-live other process alone. Migration is safe against pre-existing DBs (`PRAGMA table_info` + `ALTER TABLE ADD COLUMN` for any missing column). 7 tests in `tests/test_job_manager_cross_process.py`, all passing (verified by actual pytest run, including a real spawn-and-kill subprocess for a guaranteed-dead PID case).

~~**P1-6: Cross-process cancel is a no-op**~~ -- Fixed 2026-07-09, same session. Added `cancel_requested` column + `JobManager.request_cancel`/`is_cancel_requested`; `Runner.cancel()` now always records the flag for any queued/running job regardless of whether a local `asyncio.Task` exists, so a job started in one process can be cancelled from the other. `agent.py` gained an injected `CancelPoll` callable (same pattern as the existing `on_attempt` hook, keeping agent.py DB-agnostic) checked once per turn, before any LLM or Lean call. 3 additional tests in `tests/test_cancel_poll.py` confirm the check fires before touching `llm`/`lean` at all (via stub objects that raise if called).

### P2 -- Performance and safety (gate before any batch run)

**P2-1: Cold compile per attempt -- dominant bottleneck**
`import Mathlib` costs 30-60s per `lake env lean` call even with cached oleans.
At 4 agents × 100 turns, one job could take ~67 min just in compile time.
Fix: integrate [leanprover-community/repl](https://github.com/leanprover-community/repl)
-- a persistent `lake env .../repl` subprocess that pays the Mathlib import once per
worker. Keep `lake env lean` as final verification of any winning proof.
Interim: make the stub template's `import Mathlib` line configurable so targeted
imports can replace it.

**P2-2: LLM client -- per-call construction, no timeout, no retry**
`AsyncOpenAI`/`AsyncAnthropic` built fresh per call; no `asyncio.wait_for`
anywhere in the loop. One hung HTTP call stalls a subagent indefinitely.
Fix: cache one client per tier in `LLMClient`; wrap `complete()` in
`asyncio.wait_for(timeout=120)`; 2-3 retries with backoff.

**P2-3: No token/cost accounting -- HARD GATE before overnight batches**
Tier 3 is Fable at $50/M output, `max_tokens=8192`, up to 40 tier-3 turns × 4
agents. An overnight batch without a spend meter is a budget risk.
Fix: accumulate `input_tokens`/`output_tokens` per attempt; enforce
`max_cost_per_job` from config; global cap in the batch runner.

~~**P2-4: Stateless prompting -- model has no memory of failed strategies**~~ -- Fixed 2026-07-09, same session (completes Phase B -- every P1/P2-4 item in this assessment is now closed). Two mechanisms: (1) exact repeated-edit detection via `hash(old, new)` -- a resent identical edit is caught BEFORE a real Lean recompile (saves ~30-60s), with a pointed pushback quoting the prior failure instead of a generic retry message; (2) a rolling summary of (tactic snippet, error class) pairs, deduped and capped at 8, injected into each turn's prompt. Error classification (`_classify_error`) is substring-based against Lean 4's well-documented core error headers (unsolved goals, type mismatch, unknown identifier/constant); tactic-specific messages (simp/linarith/ring/omega) are matched more loosely and flagged in the code as unverified against live compiler output -- worth tightening once real proof runs produce a sample corpus. 11 tests in `tests/test_p2_4_stateless_prompting.py`, all passing (verified via actual pytest run with a scripted stub LLM and a call-counting stub Lean client, proving the compile-skip is real and the prompt injection contains the right content, not just that the code runs).

### P3 -- Hygiene

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

# leanforge-mcp -- Deep Assessment & Gap Analysis

**Date:** 2026-06-10-1430
**Assessor:** Claude (Fable 5), full source review against installed fastmcp in `.venv`
**Scope:** All core modules, MCP tools, webapp backend, config, tests, smoke test, environment state
**Verdict:** Architecture is sound and the scaffold is genuinely good -- but the server **cannot currently serve a single successful tool call**. Three P0 defects, several P1 correctness bugs that would surface within the first real proof job, and one P2 architecture gap (cold compile per attempt) that dominates everything else for research-scale use.

---

## 1. What is right (credit where due)

- Async semantics are correct throughout: single event loop via lifespan, no `asyncio.run()` inside async code, proper `CancelledError` propagation in `run_parallel_agents`, first-winner-cancels-rest logic is clean.
- Compiler-warning-based sorry detection (not source regex) is the correct call.
- `lake env lean <file>` inside a persistent Lake workspace is the correct compile invocation.
- Semaphore-gated concurrent compiles, timeout + kill handling, temp-file cleanup in `finally`.
- Interrupted-job recovery concept, full attempt persistence, honest failure surfaces.
- Smoke test is well designed: ordered gates, recovery hints, pure-Python tests separated from Lean-dependent ones.
- CHANGELOG honestly documents what was fixed during scaffold -- rare and valuable.

The skeleton deserves the ambition. The gaps below are fixable in days, not weeks.

---

## 2. P0 -- Blocks everything (fix first, ~1 hour total)

### P0-1: `ctx.lifespan` does not exist -- every tool call will AttributeError

**Verified against installed fastmcp** (`.venv/.../fastmcp/server/context.py` line 354): the Context class exposes a property **`lifespan_context`**, not `lifespan`. There is no `lifespan` attribute or alias.

Affected (all of them):
- `src/leanforge_mcp/core/runner.py` → `get_runner()`: `ctx.lifespan["runner"]`
- `src/leanforge_mcp/tools/submit.py` → `_runner()`
- `src/leanforge_mcp/tools/status.py` → `_runner()`
- `src/leanforge_mcp/tools/control.py` → inline `ctx.lifespan["runner"]`

**Fix:** `ctx.lifespan["runner"]` → `ctx.lifespan_context["runner"]` in all four files. Also have the tools actually use `get_runner()` instead of three duplicated `_runner()` helpers.

**Mounted-child nuance (verified in context.py source):** the tools live on child routers (`FastMCP("submit")` etc.) that have no lifespan of their own. `lifespan_context` first checks the *child's* `_lifespan_result` (None), then falls back to the request context's lifespan -- which is the parent's, containing `"runner"`. So the one-line fix works, but this fallback behavior is an implementation detail; add an integration test that boots the server in-process and calls `list_jobs` to lock it in.

### P0-2: Ollama tier-1 base_url missing `/v1` -- tier 1 dead on arrival

`config.example.toml` and the `LLMTierConfig` default both say `base_url = "http://localhost:11434"`. The `AsyncOpenAI` client appends `/chat/completions`; Ollama serves the OpenAI-compatible API at **`/v1/chat/completions`**. Every tier-1 call will 404.

**Fix:** `base_url = "http://localhost:11434/v1"` in `config.example.toml`, `config.toml`, and the dataclass default in `config.py`.

### P0-3: Lean workspace not set up -- `workspace/` is empty

Nothing can compile. This is the manual gate from TODO.md step 3 (`lake new leanforge_workspace math` → `lake exe cache get` → `lake build`, ~4GB, 20-40 min). Verify `C:\Users\sandr\.elan\bin\lake.exe` exists first (`winget install leanprover.elan` if not). No code change -- but P1 work that needs the smoke test is blocked behind it.

---

## 3. P1 -- Correctness bugs that surface in the first real job

### P1-1: The system prompt invites edits the tamper guard rejects

System prompt rule 2: *"You may introduce helper lemmas (using `lemma` or `have`)"*. But `extract_statement()` hashes **all** `theorem|lemma|example` signatures in the file. An agent that adds a top-level `lemma helper : ... := by ...` changes the extracted signature set → hash mismatch → rejected as statement tampering. The prompt explicitly encourages a move the guard punishes; a model following instructions wastes turns in a loop it cannot understand.

**Fix (choose one):**
- (a) Capture the *original* signature set at job start; the guard requires the original signatures to remain present and unmodified, while permitting *additional* signatures. Cleanest, preserves the AlphaProof-style helper-lemma capability.
- (b) Change the prompt to allow only `have`/`suffices` inside proof bodies. Simpler, weaker.

Option (a) recommended; it is ~15 lines in `agent.py` plus tests.

### P1-2: `extract_statement` regex truncates at the first `:=` -- default args break the guard

Pattern `\b(theorem|lemma|example)\b.*?:=` stops at the **first** `:=`. Lean signatures legally contain `:=` inside binders: `theorem foo (n : ℕ := 0) : n + 0 = n := by`. The protected region then ends at the default-arg `:=`, leaving the actual proposition **unprotected** -- the agent could rewrite the conclusion without tripping the hash.

**Fix:** match up to `:=` followed by proof-start (`:=\s*(by\b|sorry\b|calc\b|fun\b|⟨)`) or, more robustly, scan for the first `:=` at bracket-depth zero. Add test cases: default-arg binder, instance-implicit `[inst : ...]`, multi-line with `:=` in a `let` inside the statement.

### P1-3: Parse-failure turns are invisible and never escalate

In `run_subagent`, three branches `continue` without recording an attempt **and without calling `maybe_escalate`**: LLM exception, unparseable response, edit-not-found. A tier-1 model that cannot reliably emit the `<<<REPLACE` format -- the *most likely* failure mode for a 7B model -- burns all 100 turns producing zero persisted attempts, never escalates (escalation is exactly what it needs), and `get_proof_status` shows a running job with no trajectory.

**Fix:**
- Move `await llm.maybe_escalate(turn)` to the top of the loop body so it runs every turn unconditionally.
- Record a lightweight attempt (`compiler_output="PARSE_ERROR"` / `"EDIT_NOT_FOUND"` / `"LLM_ERROR: ..."`) on those branches so the trajectory is inspectable.
- Track consecutive parse failures; after ~5, force-escalate regardless of turn count.

### P1-4: Web backend startup corrupts live MCP-server jobs

`JobManager.init()` unconditionally flips `status='running'` → `'interrupted'`. Two processes share this DB (stdio MCP server + FastAPI backend). Start or restart the webapp while the MCP server has live proof jobs → their status is falsely marked interrupted while the tasks are still running and will later overwrite it (or worse, complete a job marked interrupted).

**Fix:** add an `owner_pid` column on jobs; `init()` only marks jobs interrupted whose owner PID is no longer alive (`psutil.pid_exists` or `OpenProcess` check). Cheap and correct for the single-machine case.

### P1-5: SQLite -- no WAL, no busy_timeout, two writer processes

Per-operation `aiosqlite.connect()` with default rollback journal, two concurrent writer processes (MCP server with 4 agents persisting attempts + web backend). This is the exact `database is locked` pattern already fought in advanced-memory-mcp.

**Fix:** in `JobManager.init()` and ideally on every connection: `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL;`. Better: hold one `aiosqlite` connection per JobManager instance (single-user workload; per-op connect is pure overhead).

### P1-6: Cross-process cancel is silently a no-op

`Runner.cancel()` only checks the in-process `_tasks` dict. A job started from the webapp cannot be cancelled from Claude Desktop and vice versa -- the tool returns "already <status>" which is misleading for a job that is actually running in the other process.

**Fix (minimal):** add `cancel_requested INTEGER` column; `Runner._run`/`run_subagent` check it between turns and abort cooperatively. Both processes can then cancel anything. (Long-term: single runner process owning all jobs, webapp + MCP as thin clients -- see §5.)

---

## 4. P2 -- The architecture gap that dominates: cold compile per attempt

Every attempt invokes `lake env lean <file>` on a file beginning `import Mathlib`. Even with cached oleans, importing all of Mathlib costs **~30-60s per invocation** on Goliath. Concretely:

| Scenario | Compiles | Wall-clock compile time (sem=4, ~40s each) |
|---|---|---|
| 1 job, 4 agents × 100 turns (worst case) | 400 | **~67 min** |
| Overnight Erdős batch, 20 jobs | 8 000 | **~22 h** -- does not fit the night |

The LLM is not the bottleneck; the compiler invocation strategy is. AlphaProof-style loops keep a **persistent Lean environment** and check tactics incrementally.

**Fix -- `LeanReplClient` (P2-1, the highest-leverage change in the repo):**
- Integrate [leanprover-community/repl](https://github.com/leanprover-community/repl): a long-lived `lake env .../repl` subprocess speaking JSON over stdin/stdout. `import Mathlib` is paid **once per worker process**; each subsequent command/tactic check is sub-second to a few seconds.
- Pool of N REPL workers (one per concurrent compile slot, reuse the existing semaphore concept). Recycle a worker on crash or after K commands (REPL memory growth is a known issue).
- Keep `lake env lean` as fallback path and as the **final verification** of any claimed proof (full clean compile of the winning file -- defense in depth, and later `lean4checker` for novel results, already planned as P3-2 in TODO.md).
- Interim mitigation even before REPL lands: stop importing all of Mathlib in the stub. `import Mathlib` → targeted imports (`import Mathlib.Tactic`, plus problem-specific modules) cuts cold compile substantially. Make the stub template's import line configurable.

Realistic effort with AI-assisted dev: 1-2 days including the worker pool and tests.

### P2-2: LLM client -- per-call client construction, no timeout, no retry

`_complete_openai_compat` and `_complete_anthropic` build a fresh `AsyncOpenAI`/`AsyncAnthropic` per call (connection-pool churn, TLS handshakes ×100s of turns) and apply **no timeout and no retry**. One hung HTTP call stalls a subagent forever -- there is no outer `asyncio.wait_for` anywhere in the loop.

**Fix:** cache one client per tier in `LLMClient` (or module-level per provider); wrap `complete()` in `asyncio.wait_for(..., llm_timeout)` (config, default ~120s); 2-3 retries with backoff on transient errors. ~40 lines.

### P2-3: No token/cost accounting -- the PRD's own risk mitigation is unimplemented

PRD §8 lists budget cap as the mitigation for runaway overnight spend; nothing in the code counts tokens. Tier 3 is Fable at $50/M output, `max_tokens=8192`, up to 40 tier-3 turns × 4 agents per job. An overnight batch without a meter is how a €100/month budget dies in one night.

**Fix:** both providers return usage in the response object -- accumulate `input_tokens`/`output_tokens` per attempt (add columns), compute cost from per-tier config prices, enforce `max_cost_per_job` (config) in the agent loop and a global cap in the future batch runner. **Gate: do not run any tier-2/3 batch before this exists.**

### P2-4: Stateless prompting -- the model has no memory of failed strategies

Each turn sends only the current file + last error. The model will happily retry `simp` five times. Cheap, high-value fixes:
- Detect a repeated identical edit (hash of `old→new`) and inject "you already tried exactly this; it failed with the same error -- use a different tactic family".
- Maintain a rolling summary of the last N failed (tactic, error-class) pairs in the user message. Keeps token cost bounded while killing the dominant failure loop.
- Mislabeled feedback: an LLM exception sets `last_error`, which next turn is presented as "Lean compiler error" -- label error provenance correctly.

---

## 5. P2 -- Process topology: two Runners, one DB

The webapp backend instantiates its **own** Runner/LeanClient against the shared DB. Consequences beyond P1-4/P1-6: doubled Mathlib RAM if both compile, split task registries, two sources of truth for "running".

**Recommended direction (after P0/P1):** invert the topology -- one long-lived **leanforge daemon** (the FastAPI process is the natural host) owns the Runner and all compilation; the stdio MCP server becomes a thin client calling the daemon's REST API (localhost:10867). This matches the federation-hub direction, makes Claude Desktop restarts free (jobs survive), and kills the entire class of cross-process bugs. Effort: ~1 day. Until then, P1-4 + P1-6 mitigations make coexistence safe.

---

## 6. P3 -- Hygiene and smaller defects

| # | Item | File | Note |
|---|---|---|---|
| P3-1 | `leanforge-web` console script broken on install | `pyproject.toml` | Wheel only packages `src/leanforge_mcp`; `webapp.backend.main` not in the wheel and `webapp/__init__.py` is missing. Drop the script entry or package webapp properly. |
| P3-2 | `_from_dict()` dead code; `DatabaseConfig(**raw)` etc. TypeError on unknown keys | `config.py` | Apply the LeanConfig-style field filtering to all sections, delete `_from_dict`. |
| P3-3 | Blocking `tmp_path.write_text` in async path | `lean_client.py` | `aiofiles` is a declared dependency, unused. Minor, but it's in the hot loop. |
| P3-4 | `retain_workspace` config read but never honored | `lean_client.py` | Wire it into the `finally` cleanup or remove from config. |
| P3-5 | `_extract` substring match | `lean_client.py` | `"error:" in line.lower()` can false-positive on goal text containing the word. Anchor on the `file:line:col: error:` shape. |
| P3-6 | `submit_theorem` field doc shows English pseudo-Lean | `tools/submit.py` | `'for all n : ℕ, ...'` is not valid Lean; the stub will fail to compile. Use `∀ n : ℕ, ...` in the example. |
| P3-7 | DeepSeek model id `deepseek/deepseek-v4-flash` | config | The `vendor/model` prefix is OpenRouter convention; DeepSeek's native API expects a bare model name. Verify with one curl before tier-2 testing. |
| P3-8 | `FleetStartMode.ps1` + 3 `.bak` files | `scripts/` | Stray fleet artifacts; remove, and add `*.bak` to `.gitignore`. |
| P3-9 | TODO.md open question #2 (mount prefix) is now answered | `TODO.md` | Verified in installed fastmcp: `mount(server, namespace=None)` -- no namespace → tool names unprefixed. Remove the open question; the `import_server` fallback note is obsolete. |
| P3-10 | GitHub push status unverified | repo | `.git` exists; confirm `origin` is set and pushed (GIT_REPOSITORY_SAFETY). |

---

## 7. Prioritized improvement TODO

**Phase A -- make it run (≈ half a day + the 4GB download)**
1. [P0-1] `ctx.lifespan` → `ctx.lifespan_context` (4 files); consolidate on `get_runner()`.
2. [P0-2] Ollama `/v1` base_url (3 places).
3. [P0-3] One-time Lean workspace setup (manual); verify lake.exe path.
4. Run `pytest` + `smoke_test.py`; resolve PRD open questions #1/#3 (exit-code semantics, sorry string) from raw output; tune `lean_client.py` if needed (P1-1 in old TODO).
5. [P3-9] Update TODO.md -- mount question resolved.
6. In-process integration test: boot server, call `list_jobs` + `validate_lean`, assert lifespan plumbing.

**Phase B -- make it correct (≈ 1 day)**
7. [P1-3] Escalation every turn + persist parse-failure attempts + force-escalate after consecutive parse failures.
8. [P1-1] Original-signature-superset tamper guard (helper lemmas allowed).
9. [P1-2] Bracket-aware / proof-start-anchored `extract_statement` + adversarial tests.
10. [P1-5] WAL + busy_timeout + persistent connection in JobManager.
11. [P1-4] `owner_pid` + liveness-checked interrupted recovery.
12. [P1-6] `cancel_requested` column, cooperative cross-process cancel.
13. [P2-4] Repeated-edit detection + error-provenance labels.

**Phase C -- make it fast and affordable (≈ 2-3 days) -- gate for any real benchmark run**
14. [P2-1] `LeanReplClient` with worker pool; `lake env lean` kept as final verification. Interim: configurable targeted imports in the stub template.
15. [P2-2] Cached LLM clients + timeout + retry.
16. [P2-3] Token/cost accounting, per-job and global budget caps. **Hard gate before any overnight batch.**

**Phase D -- make it a research instrument (existing Phase 2/3 plan, now unblocked)**
17. MiniF2F validation script (P1-2 old TODO) → 5-problem sanity → full MiniF2F run with the REPL client.
18. Topology inversion: daemon owns Runner, MCP as thin client (§5).
19. EVOLVE-BLOCK, Elo ranking, Erdős batch runner, overnight scheduler -- per existing TODO.md, all dependent on Phase C cost controls.

---

## 8. Realistic timeline (AI-assisted)

| Phase | Effort | Outcome |
|---|---|---|
| A | half a day | First `proven: true` from Claude Desktop |
| B | 1 day | Survives a real multi-agent job without corrupting state |
| C | 2-3 days | 10-50× compile throughput, spend is bounded |
| D | ongoing | MiniF2F numbers, then Erdős nights |

Total to a benchmark-capable research tool: **≈ one week of sessions.**

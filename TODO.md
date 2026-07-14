# leanforge-mcp -- TODO

**Updated:** 2026-07-09. Supersedes the 2026-06-10 version (archived at the
bottom of this file for history -- most of it is now DONE or obsolete).

**Numbering note:** this file's task IDs (C1, C2, ...) are independent of
`docs/ASSESSMENT_2026-06-24.md`'s P1-x/P2-x IDs -- those numbered a *different*
set of correctness bugs (all now fixed) and reusing the same numbers here
would be confusing. Cross-references are spelled out where relevant.

---

## Current state (read this first)

- **Mathlib workspace: DONE and verified.** `D:\Dev\repos\leanforge-mcp\workspace\leanforge_workspace`
  is live with a real cached `.olean` tree (confirmed 1200+ files under
  `mathlib\.lake\build\lib`, not just the cache tool's own bootstrap set --
  that was the signature of an earlier failed attempt). `lake new ... math`
  auto-runs `cache get` via Mathlib's post-clone hook; no separate manual
  `lake exe cache get` step is needed the way the old Manual Steps section
  below describes.
- **Phase A + Phase B: DONE.** Core proof loop works; every P1 correctness
  bug and P2-4 (stateless prompting) from `docs/ASSESSMENT_2026-06-24.md`
  is fixed and verified -- 56/56 tests passing via `uv run pytest tests/ -v`
  on Goliath (Windows, Python 3.13.5, 79.18s). See CHANGELOG.md Unreleased
  section for the full list.
- **Not yet done:** the repo has never been run against a *live* LLM +
  Lean compile end-to-end (no `scripts/smoke_test.py` or e2e run has been
  executed this cycle) -- Phase B's fixes were verified with stub
  llm/lean objects in pytest, which proves the CONTROL FLOW is correct but
  not that a real DeepSeek/Ollama call plus a real Lean compile produces a
  proof. That's the natural first task below.

---

## PHASE C -- Performance and safety (current focus)

Maps to `docs/ASSESSMENT_2026-06-24.md` P2-1/P2-2/P2-3. This phase gates
any batch/overnight run.

### C1: Live end-to-end smoke run (do this first)

Nothing in Phase C matters if the basic loop doesn't work against real
services. Before touching REPL pooling or cost accounting, confirm the
whole pipeline end to end:

```powershell
cd D:\Dev\repos\leanforge-mcp
uv run python scripts\smoke_test.py
```

Tests 1-2 and 6 don't need Lean; tests 3-5 need the workspace (now ready).
If Ollama's `deepseek-prover-v2:7b` isn't pulled yet: `ollama pull deepseek-prover-v2:7b`.
Then try one real submission through the MCP tools (via Claude Desktop or
a direct Python call to `run_subagent`) on a trivial theorem like
`theorem foo : 1 + 1 = 2 := by sorry` and confirm it actually proves.

**This is the real verification gate Phase B's pytest suite couldn't
provide** -- stub llm/lean objects proved the control flow (tamper guard,
cancel poll, repeated-edit skip) is correct, but only a live run confirms
the compile pipeline, LLM response parsing, and tier escalation work
against the real Lean toolchain and a real model.

### C2: REPL worker pool (P2-1 -- the actual performance bottleneck)

File: `src/leanforge_mcp/core/lean_client.py`

Every turn currently shells out `lake env lean <file>`, which pays a full
`import Mathlib` elaboration cost (~30-60s) EVERY compile, even though
Mathlib's environment doesn't change between turns. Fix: a persistent
worker pool talking to `leanprover-community/repl` over stdin/stdout,
keeping Mathlib's environment loaded and only re-elaborating the changed
theorem. This is the single biggest lever on wall-clock time and API
cost (fewer turns needed within the same time budget, or more turns
possible within the same budget).

Design sketch:
- `LeanReplClient`: spawns `lake env lean --server` (or the community REPL
  binary) once per worker, keeps N workers in a pool sized to
  `max_concurrent_compiles`.
- Pickled/named environments so a worker can be handed a specific job's
  accumulated state rather than re-importing Mathlib from scratch.
- Fallback to the current subprocess-per-compile path if the REPL
  protocol proves too fragile for a first pass -- don't let this become a
  blocker for C1.

### C3: LLM client hardening (P2-2)

File: `src/leanforge_mcp/core/llm_client.py`

`AsyncOpenAI`/`AsyncAnthropic` are built fresh per call; there's no
`asyncio.wait_for` anywhere in the loop, so one hung HTTP call stalls a
subagent indefinitely (and, in a parallel batch, ties up that agent's
turn budget for nothing).

- Cache one client per tier in `LLMClient.__post_init__`.
- Wrap `complete()` in `asyncio.wait_for(timeout=120)`.
- 2-3 retries with exponential backoff on timeout/transient errors.

### C4: Token/cost accounting -- HARD GATE before any batch run (P2-3)

File: `src/leanforge_mcp/core/llm_client.py`, `job_manager.py`

Tier 3 is Fable at ~$50/M output tokens, `max_tokens=8192`, up to 40
tier-3 turns x 4 parallel agents per job. **An overnight batch without a
spend meter is a real budget risk against the ~€100/month AI tools
budget.** Do not build the overnight scheduler (Phase D+) before this
lands.

- Accumulate `input_tokens`/`output_tokens` per attempt (most SDKs return
  usage on the response; capture it in `on_attempt`).
- Add a `total_cost_usd` column to the `jobs` table (or compute on read
  from accumulated tokens x per-model rate table).
- Enforce `max_cost_per_job` from config -- when a job crosses the
  threshold mid-run, cancel it via the same `cancel_requested` mechanism
  P1-6 built (no new plumbing needed).
- A global cap belongs in the batch runner (Phase D+), not here, but the
  per-job accounting this task adds is the prerequisite for it.

---

## PHASE D+ -- After Phase C (not yet scoped in detail)

- **EVOLVE-BLOCK marker support** -- annotated regions in the Lean file
  constraining what the agent may edit, strengthening the tamper contract
  beyond the current name-keyed check. See AlphaProof Nexus paper
  section 3.2.
- **Attempt Elo ranking** -- score partial proof sketches, seed the next
  subagent generation from the highest-scoring partial instead of always
  restarting from the initial file.
- **AlphaProof Nexus unsolved batch runner** + **overnight scheduler** --
  both blocked on C4 (cost accounting) landing first.
- **Fleet integration** -- `meta_mcp` hook to trigger jobs from other
  agents; `advanced-memory-mcp` note on `status=complete` tagged
  `[leanforge-mcp, lean4, proof, result]`.
- **Population-based agent** (Agent D from AlphaProof Nexus) -- shared
  proof sketch population instead of independent subagents.
- **`lean4checker` re-verification** for proofs of genuinely open
  problems, using only kernel axioms for stronger assurance.
- **erdosproblems.com scraper + formalizer** -- fetch open problems, use
  an LLM to write the correct Lean 4 theorem STATEMENT (the hard part),
  then submit for proof search.

---

## CONTEXT FOR CURSOR / any coding agent

### Architecture in one paragraph

leanforge-mcp is a FastMCP 3.4 server. On startup, `lifespan()` in
`server.py` creates a `JobManager` (SQLite via `aiosqlite`), a `LeanClient`
(wraps `lake env lean`), and a `Runner` (orchestrates parallel proof
search), stored in the FastMCP lifespan context. Tool handlers retrieve
the runner via `get_runner(ctx)`. `submit_theorem` starts a background
`asyncio.Task` via `Runner.start_job()` and returns a `job_id` immediately.
The task runs `run_parallel_agents()` from `agent.py`, which spawns N
independent subagents. Each subagent loops: build a prompt from the
current file + last error + a rolling summary of failed strategies -> call
LLM -> parse the search-replace response -> check for an exact-repeat of a
previously-failed edit -> apply the edit -> verify it doesn't touch a
protected declaration (name-keyed tamper guard) -> `lake env lean <tmpfile>`
-> feed compiler output back to the LLM. Every turn also polls a
cross-process `cancel_requested` DB flag. First subagent to produce a
sorry-free compile wins; others are cancelled. All attempts persist to
SQLite via the `on_attempt` callback. Two OS processes (the stdio MCP
server and the webapp FastAPI backend) can share the same `jobs.db`; job
ownership (`owner_pid`/`owner_started_at`) and the cancel flag are what
make that safe.

### Key files

```
src\leanforge_mcp\
  server.py          # FastMCP entry point, lifespan, mount()
  core\
    agent.py          # proof loop: tamper guard, repeated-edit detection,
                       #   failed-strategies summary, parallel orchestration
    lean_lexer.py      # bracket/comment/string-aware Lean 4 signature scanner
                       #   (agent.py's tamper guard is built on this)
    lean_client.py     # lake env lean subprocess wrapper, semaphore
    llm_client.py      # Ollama / DeepSeek / Anthropic, tier escalation
    job_manager.py     # SQLite CRUD for jobs/attempts; owner_pid liveness
                       #   sweep and cancel_requested flag (cross-process)
    runner.py          # Runner class, start_job(), cancel(), get_runner(ctx)
    config.py          # TOML loader, LeanConfig/LLMConfig/AgentConfig dataclasses
  tools\
    submit.py          # submit_theorem, submit_lean_file
    status.py          # get_proof_status, list_attempts, list_jobs, validate_lean
    control.py          # cancel_job
    mathlib.py          # get_mathlib_search (LeanSearch API)
webapp\backend\
  routes\jobs.py        # REST job submission/cancel -- shares Runner.cancel()
                       #   with the MCP control.py tool
scripts\
  smoke_test.py         # standalone validation, run before anything else (C1)
tests\
  test_pipeline.py               # legacy pure-Python tests (statement hash, edit apply)
  test_lean_lexer.py             # lean_lexer.py + tamper guard, 21 tests
  test_job_manager_cross_process.py  # owner liveness sweep + cancel flag, 7 tests
  test_cancel_poll.py            # is_cancelled short-circuits before llm/lean, 3 tests
  test_p2_4_stateless_prompting.py   # error classifier + repeated-edit skip, 11 tests
  test_server_integration.py     # boots the real server in-process
docs\
  ASSESSMENT_2026-06-24.md  # the bug list this session worked through; now
                             # carries a "Fixed in this session" ledger per item
  ARCHITECTURE.md           # detailed architecture + one-time workspace setup
  LEAN_PRIMER.md             # Lean 4 intro for engineers
  BENCHMARK_RESULTS.md       # proof success tracking table
```

### Do not

- Do not call `lean` directly -- always `lake env lean <file>` via `LeanClient`
- Do not hardcode paths -- always read from `Config` (loaded from `config.toml`)
- Do not block the FastMCP event loop -- all Lean and LLM calls are async
- Do not call `asyncio.run()` inside async code -- the server runs in one loop
- Do not modify theorem statements in agent edits -- `check_tamper()` in
  `agent.py` will reject any change to an original declaration's signature
  under its original name; this is intentional. New helper lemmas/theorems
  under NEW names are fine.
- Do not write to `workspace\` directly from tools -- go through `Runner.start_job()`
- Do not pip install -- use `uv sync` and `uv run`
- Do not add a second in-memory job dict or bypass `JobManager` for status
  -- the whole point of the P1-4/P1-6 fixes is that SQLite is the single
  source of truth shared across processes; a process-local shortcut
  reintroduces the bug those fixes closed.

---

## ARCHIVED: 2026-06-10 original TODO (superseded, kept for history)

Most of this is now DONE (Mathlib workspace, initial deps, config, git
repo) or superseded by Phase C above. The "known issues" section's
`lean_client.py` exit-code questions were resolved during Phase A/B work
without needing the originally-planned manual smoke-test-driven
investigation -- see CHANGELOG.md and ASSESSMENT_2026-06-24.md instead.

<details>
<summary>Click to expand original 2026-06-10 content</summary>

### Manual steps (historical -- repo/deps/config/workspace all DONE now)

Git repo init, `uv sync --extra web --extra dev`, `config.toml` copy, and
the one-time Mathlib workspace setup are all complete. The workspace
setup command that was originally documented here:

```powershell
cd D:\Dev\repos\leanforge-mcp\workspace
lake new leanforge_workspace math
cd leanforge_workspace
lake exe cache get
lake build
```

turned out to need one correction in practice: `lake new ... math`
itself triggers Mathlib's post-clone hook, which runs the equivalent of
`cache get` automatically during project creation -- so the explicit
`lake exe cache get` line is usually a no-op by the time you'd run it
(harmless to run anyway as a safety check). `lake build` was not needed
for the `.olean` cache to be usable.

### Original Phase 1/2/3 tasks (numbering clashed with ASSESSMENT.md;
see Phase C/D+ above for the current equivalents)

- Old P1-1 (lean_client.py exit codes) -> resolved during Phase A/B, see CHANGELOG
- Old P1-2 (MiniF2F validation test) -> still worth doing, folded into C1 above
- Old P1-3 (Ollama e2e test) -> folded into C1 above
- Old P1-4 (entry point verification) -> `leanforge-mcp --help` -- untested this
  cycle, worth a quick check but not blocking
- Old P1-5 (Claude Desktop config) -> assumed done since the server has been
  in active use this session; verify `validate_lean` tool appears if in doubt
- Old P2-1 (EVOLVE-BLOCK) -> now Phase D+
- Old P2-2 (Attempt Elo) -> now Phase D+
- Old P2-3 (Erdos batch runner) -> now Phase D+, blocked on C4
- Old P2-4 (Overnight scheduler) -> now Phase D+, blocked on C4
- Old P2-5 (Fleet integration) -> now Phase D+
- Old P3-1/2/3 (population agent, lean4checker, erdos scraper) -> now Phase D+

</details>

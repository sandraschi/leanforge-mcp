# leanforge-mcp -- TODO for Cursor

Generated: 2026-06-10. Pick up from here after the smoke test passes.

## WEBAPP (added 2026-06-10)

A full-stack webapp was added in `webapp/`:
- **Backend** (FastAPI, port 10855): REST API for jobs + problem CRUD + SSE live updates
- **Frontend** (Vite React, port 10856): Dashboard, Job Inspector, Problem Library, New Theorem
- Runner now accepts optional `event_bus` for real-time SSE push
- Start with: `cd webapp && .\start.ps1` or `just web-dev`
- The backend shares the same SQLite DB as the stdio MCP server
- `uv sync --extra web --extra dev` needed before first run

---

## MANUAL STEPS FIRST (human, not Cursor)

These cannot be automated -- do them before asking Cursor to do anything.

### 0. Create the git repo and push to GitHub (DO THIS FIRST per GIT_REPOSITORY_SAFETY.md)

```powershell
cd D:\Dev\repos\leanforge-mcp

# Init
git init -b main

# Stage everything
git add .

# Initial commit
git commit -m "feat: initial scaffold -- leanforge-mcp v0.1.0"

# Create GitHub repo (requires gh auth login)
gh repo create sandraschi/leanforge-mcp --public --description "MCP server for AI-driven formal proof search in Lean 4. Implements AlphaProof Nexus Agent A architecture." --push --source .
```

If `gh repo create --push` fails, do it in two steps:
```powershell
gh repo create sandraschi/leanforge-mcp --public
git remote add origin https://github.com/sandraschi/leanforge-mcp.git
git push -u origin main
```

### 1. Install dependencies (core + web + dev)

```powershell
cd D:\Dev\repos\leanforge-mcp
"C:\Users\sandr\.local\bin\uv.exe" sync --extra web --extra dev
```

This installs FastAPI, uvicorn, sse-starlette for the web backend, plus
pytest and ruff for development.

### 2. Copy and verify config

```powershell
Copy-Item config.example.toml config.toml
```

Open `config.toml` and confirm:
- `[lean] lake_path` = `C:\Users\sandr\.elan\bin\lake.exe` (verify this path exists)
- `[lean] workspace_dir` = `D:\Dev\repos\leanforge-mcp\workspace\leanforge_workspace`
- `[llm.tier1]` Ollama model pulled: `ollama pull deepseek-prover-v2:7b`
- `[llm.tier2]` `DEEPSEEK_API_KEY` env var set
- `[llm.tier3]` `ANTHROPIC_API_KEY` env var set

### 3. One-time Lean + Mathlib workspace setup (~4GB download, takes 20-40 min)

```powershell
cd D:\Dev\repos\leanforge-mcp\workspace
lake new leanforge_workspace math
cd leanforge_workspace
lake exe cache get
lake build
cd D:\Dev\repos\leanforge-mcp
```

This only needs to be done once. The workspace persists across server restarts.

### 4. Run pure-Python tests (no Lean needed)

```powershell
"C:\Users\sandr\.local\bin\uv.exe" run pytest tests\ -v
```

Expected: all 8 tests pass. These test agent.py logic only (statement hashing, edit
application) -- no LLM or Lean involved.

### 5. Run smoke test (needs Lean workspace from step 3)

```powershell
"C:\Users\sandr\.local\bin\uv.exe" run python scripts\smoke_test.py
```

Tests 1-2 and 6 pass without Lean. Tests 3-5 need the workspace.
**The smoke test is the gate** -- don't proceed to Cursor tasks until it passes.

---

## KNOWN ISSUES TO VERIFY AGAINST REAL OUTPUT

These are assumptions that may need tuning once smoke test runs:

### lean_client.py -- exit code semantics

Lean 4 may return exit code 0 even on tactic failures, signalling errors only via
diagnostic output. Current code treats non-zero exit OR presence of "error:" lines
as failure. If the smoke test shows `success=True` on a proof with errors, fix
`_extract_errors()` in `lean_client.py` -- look at `raw_stdout` and `raw_stderr` from
the smoke test output and adjust the detection logic accordingly.

### lean_client.py -- stdout vs stderr

Current code combines `stdout + stderr` for error extraction. Lean 4 emits
diagnostics to stdout in the format `file:line:col: error: ...`. If extraction
misses errors, check which stream they appear in from the smoke test raw output.

### server.py -- FastMCP 3.x lifespan import -- RESOLVED 2026-06-10

Verified against installed fastmcp in .venv: `fastmcp.server.lifespan.lifespan`
exists and works as used. No fallback needed.

HOWEVER: the Context attribute for reading lifespan state is
`ctx.lifespan_context` (property), NOT `ctx.lifespan`. This was a P0 bug --
every tool call would AttributeError. FIXED 2026-06-10: all tools now use
`get_runner(ctx)` from core/runner.py, which reads `ctx.lifespan_context`.
See docs/ASSESSMENT_2026-06-10.md P0-1 for the mounted-child fallback nuance.

### server.py -- mount() with no prefix -- RESOLVED 2026-06-10

Verified against installed fastmcp source: `mount(server, namespace=None)` --
with no namespace, tool names are preserved unprefixed (`submit_theorem`, not
`submit_submit_theorem`). No change needed; `import_server` fallback obsolete.

---

## PHASE 1 TASKS (for Cursor, after smoke test passes)

### P1-1: Fix lean_client.py based on smoke test output

File: `src\leanforge_mcp\core\lean_client.py`

After running the smoke test, read the raw compiler output and fix:
- Error detection if exit code is unreliable
- Warning/sorry detection if `WARNING_SORRY` string differs in installed Lean version
- Stdout vs stderr routing

Run `scripts\smoke_test.py` after each fix. All 8 tests must pass before proceeding.

### P1-2: Add MiniF2F validation test

File: `scripts\validate_miniF2F.py` (create)

1. Clone MiniF2F if not present:
   ```powershell
   cd D:\Dev\repos
   git clone https://github.com/leanprover-community/miniF2F.git
   ```

2. Create a script that:
   - Takes the first 5 `.lean` files from `miniF2F\lean4\valid\`
   - Submits each via `LeanClient.compile()` directly (not MCP) to confirm they
     compile as-is (the files have proofs -- they should all return `proven=True`)
   - Then tests the sorry-detection: strip the proof body and replace with `sorry`,
     recompile, confirm `has_sorry=True` and `proven=False`

This validates the full compile pipeline before involving an LLM.

### P1-3: Wire Ollama tier-1 end-to-end test

File: `scripts\test_agent_e2e.py` (create)

Prerequisites: Ollama running with `deepseek-prover-v2:7b` pulled.

Test: submit a trivial theorem through the full agent loop (not MCP, direct Python):

```python
from leanforge_mcp.core.agent import run_subagent
from leanforge_mcp.core.lean_client import LeanClient
from leanforge_mcp.core.llm_client import LLMClient
from leanforge_mcp.core.config import load_config

# source: a theorem with sorry that should be trivially provable
source = "import Mathlib\ntheorem foo : 1 + 1 = 2 := by\n  sorry\n"
# expected: agent fills sorry with norm_num or decide in 1-3 turns
```

Log every turn's edit and compiler output. Confirm `proven=True` on success.

### P1-4: Add `__module__` entry point to pyproject.toml

File: `pyproject.toml`

The `[project.scripts]` entry currently points at `leanforge_mcp.server:main`.
Verify this resolves after `uv sync` by running:
```powershell
"C:\Users\sandr\.local\bin\uv.exe" run leanforge-mcp --help
```
If it errors, check that `src\leanforge_mcp\__main__.py` and `server.py` are both
correctly structured.

### P1-5: Add to Claude Desktop config

File: `C:\Users\sandr\AppData\Roaming\Claude\claude_desktop_config.json`

Add this entry to `mcpServers`:
```json
"leanforge": {
  "command": "C:\\Users\\sandr\\.local\\bin\\uv.exe",
  "args": ["--directory", "D:\\Dev\\repos\\leanforge-mcp", "run", "python", "-m", "leanforge_mcp"],
  "env": {
    "ANTHROPIC_API_KEY": "YOUR_KEY_HERE",
    "DEEPSEEK_API_KEY": "YOUR_KEY_HERE"
  }
}
```

After adding, restart Claude Desktop and confirm `validate_lean` tool appears.
First call to make: `validate_lean("import Mathlib\nexample : 1 = 1 := rfl\n")`
Expected: `{"proven": true, "has_sorry": false, "errors": []}`

---

## PHASE 2 TASKS (after Phase 1 complete and MCP working in Claude Desktop)

### P2-1: EVOLVE-BLOCK marker support

File: `src\leanforge_mcp\core\agent.py`

Add support for annotated regions in the Lean file that constrain what the agent
can and cannot modify. See AlphaProof Nexus paper (arXiv:2605.22763) section 3.2.

```lean
-- EVOLVE-BLOCK-START
-- agent may add helper lemmas here
-- EVOLVE-BLOCK-END
theorem foo : ... := by
  sorry  -- agent fills this
```

The agent should only be allowed to edit within EVOLVE-BLOCK regions and the
sorry placeholders. Strengthens the tamper-detection contract.

### P2-2: Attempt Elo ranking

File: `src\leanforge_mcp\core\job_manager.py`

Add an `elo_score` column to the `attempts` table. After each compile:
- Failed attempt with useful error (model made progress): +10
- Failed attempt, same error repeated: -5
- New tactic tried after stuck: +5
- Proven: +100

Use scores to rank partial proof sketches and seed the next subagent generation
with the highest-scoring partial rather than always starting from scratch.

### P2-3: AlphaProof Nexus unsolved batch runner

File: `scripts\run_erdos_batch.py` (create)

1. Clone the results repo if not present:
   ```powershell
   cd D:\Dev\repos
   git clone https://github.com/google-deepmind/alphaproof-nexus-results.git
   ```

2. Read `erdos_problems_attempted.txt` from the repo
3. For each problem in the unsolved set (those without a proof in the repo):
   - Load the `.lean` stub file
   - Submit via `Runner.start_job()` with tier=2, parallel_agents=4, max_turns=200
   - Log result to `docs\BENCHMARK_RESULTS.md`
4. Run overnight. Any `status=complete` result is a novel theorem.

### P2-4: Overnight scheduler

File: `scripts\overnight_batch.py` (create)

Wraps `run_erdos_batch.py` with:
- Start time: 23:00 local
- Stop time: 07:00 local (or on keyboard interrupt)
- Budget cap: configurable max total API spend (count output tokens × $50/M)
- Progress checkpoint: write `data\batch_progress.json` after each job so run
  is resumable if interrupted
- Summary email via `telephony-mcp` or log to `cursor_inbox` on completion

### P2-5: Fleet integration

- `meta_mcp` hook: expose `submit_theorem` and `get_proof_status` via meta_mcp
  orchestration so other fleet agents can trigger proof jobs
- `advanced-memory-mcp` persistence: on `status=complete`, write a note tagged
  `[leanforge-mcp, lean4, proof, result]` with the theorem statement and proof
- `cursor_inbox` drop: when a job completes, write result to
  `D:\Dev\repos\mcp-central-docs\cursor_inbox\leanforge_result_{job_id}.md`

---

## PHASE 3 TASKS (research-grade, after Phase 2)

### P3-1: Population-based agent (Agent D from AlphaProof Nexus)

Replace the current independent-subagents model with a shared proof sketch population.
See AlphaProof Nexus paper section 4 for the full Agent D description.
Key addition: a `PopulationDB` SQLite table that stores partial proof sketches with
Elo ratings; subagents seed from the highest-rated sketch rather than always from
the initial file.

### P3-2: Lean formal checker integration

Currently we rely on the Lean compiler for correctness. Add a secondary verification
step using `lean4checker` for proofs of open problems before declaring success:

```powershell
lake env lean4checker Proof.lean
```

This re-verifies the proof using only the kernel axioms, providing stronger
assurance for genuinely novel results.

### P3-3: erdosproblems.com scraper + formalizer

File: `scripts\formalize_erdos.py` (create)

Fetch open problems from erdosproblems.com, use Fable 5 to write the Lean 4
theorem stub (the hardest part is stating the theorem correctly before any proof
attempt), then submit for proof search.

---

## CONTEXT FOR CURSOR

### Architecture in one paragraph

leanforge-mcp is a FastMCP 3.2 server. On startup, `lifespan()` in `server.py`
creates a `JobManager` (SQLite), `LeanClient` (wraps `lake env lean`), and `Runner`
(orchestrates parallel proof search). These are stored in the FastMCP lifespan
context (`ctx.lifespan["runner"]`). Tool handlers retrieve the runner from context.
`submit_theorem` starts a background `asyncio.Task` via `Runner.start_job()` and
returns a `job_id` immediately. The task runs `run_parallel_agents()` from `agent.py`,
which spawns N independent subagents. Each subagent loops: call LLM with current
Lean file → parse search-replace response → apply edit → `lake env lean <tmpfile>`
→ feed compiler output back to LLM. First subagent to produce a sorry-free compile
wins; others are cancelled. All attempts persist to SQLite via `on_attempt` callback.

### Key files

```
src\leanforge_mcp\
  server.py          # FastMCP entry point, lifespan, mount()
  core\
    agent.py         # proof loop, statement hash, parallel agent orchestration
    lean_client.py   # lake env lean subprocess wrapper, semaphore
    llm_client.py    # Ollama / DeepSeek / Anthropic, tier escalation
    job_manager.py   # SQLite CRUD for jobs and attempts
    runner.py        # Runner class, start_job(), cancel(), get_runner(ctx)
    config.py        # TOML loader, LeanConfig/LLMConfig/AgentConfig dataclasses
  tools\
    submit.py        # submit_theorem, submit_lean_file
    status.py        # get_proof_status, list_attempts, list_jobs, validate_lean
    control.py       # cancel_job
    mathlib.py       # get_mathlib_search (LeanSearch API)
scripts\
  smoke_test.py      # standalone validation, run before anything else
tests\
  test_pipeline.py   # pure Python pytest, no Lean needed
docs\
  ARCHITECTURE.md    # detailed architecture + one-time workspace setup
  LEAN_PRIMER.md     # Lean 4 intro for engineers
  BENCHMARK_RESULTS.md  # proof success tracking table
```

### Do not

- Do not call `lean` directly -- always `lake env lean <file>` via `LeanClient`
- Do not hardcode paths -- always read from `Config` (loaded from `config.toml`)
- Do not block the FastMCP event loop -- all Lean and LLM calls are async
- Do not call `asyncio.run()` inside async code -- the server runs in one loop
- Do not modify theorem statements in agent edits -- the statement hash check
  in `agent.py` will reject them; this is intentional
- Do not write to `workspace\` directly from tools -- go through `Runner.start_job()`
- Do not pip install -- use `uv sync` and `uv run`

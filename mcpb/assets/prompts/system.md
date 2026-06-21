# leanforge-mcp System Guide

## Identity

You are leanforge-mcp, an AI-driven formal proof search server for Lean 4. Your purpose is to take natural-language theorem statements and return machine-verified Lean 4 proofs. You are an implementation of the Agent A architecture from AlphaProof Nexus (arXiv:2605.22763). You run parallel subagents: an LLM proposes proof steps, and the Lean compiler acts as an oracle that judges each attempt.

You are NOT a general-purpose Lean tutor or an interactive theorem prover shell. You are a proof-finding service: submit a theorem, poll for status, receive a verified proof. You do not host a webapp -- your interface is purely MCP tools. The server runs on Windows (Goliath) and uses absolute paths for all external tooling.

## Architecture

### Core Loop

1. User submits a theorem via `submit_theorem(statement, proof_attempt)`. The statement is a Lean 4 theorem syntax string. The optional proof_attempt gives the LLM a starting point. The theorem must be a valid `theorem`, `lemma`, `example`, or `def` statement that the LLM can attempt to prove.

2. The server creates a job in SQLite (UUID job_id) and spawns N independent subagents in the Runner. Each subagent operates independently and in parallel -- the first one to find a valid proof wins.

3. Each subagent enters a propose-compile loop:
   - Propose: call the LLM (Ollama / OpenAI-compat / Anthropic) with the theorem and the current error context. The LLM returns a complete proof attempt.
   - Hash-verify: the server hashes the theorem statement before and after the edit. If the hash changed (meaning the LLM modified the theorem statement rather than just filling sorries), the edit is rejected, a SECURITY warning is logged, and the subagent is terminated with a tamper error.
   - Compile: run `lean --stdin` on the proposed proof, capturing stdout and stderr. The compile has a configurable timeout (default 30s) because Lean can hang on malformed input. The `lean --stdin` mode is significantly faster than `lake build` for single-theorem compilation.
   - If the Lean compiler accepts (exit code 0, no errors on stderr), the proof is done. The result is logged and the job completes.
   - If the compiler rejects, the error (stdout+stderr combined) is captured, truncated to a manageable size, and fed back to the LLM as context for the next iteration.
   - The subagent tracks how many retries it has used at the current LLM tier. If it exceeds `max_retries_per_tier` (default 5), it escalates to the next tier.

4. Tier escalation is central to the architecture:
   - Tier 1 (default): Ollama (local, fast, free). Base URL http://127.0.0.1:11434/v1, model configurable.
   - Tier 2: OpenAI-compatible (DeepSeek, OpenAI, etc.). Requires `base_url` and `api_key` in config.
   - Tier 3: Anthropic Claude. Requires `api_key` in config.
   - Escalation is irreversible within a job. If Ollama runs out of retries, the subagent moves to OpenAI-compat and never returns to Ollama.
   - If a tier is not configured (empty api_key), it is silently skipped.
   - If all tiers are exhausted, the job is marked as "failed" with the last error from each tier.

5. The user polls `get_proof_status(job_id)` every 10-30 seconds. The recommended polling interval is 10 seconds for simple theorems (Nat arithmetic, basic algebra) and 30 seconds for complex theorems (analysis, category theory). Polling faster than 5 seconds is not recommended as it wastes server resources.

6. When status is "completed", the result contains the verified proof, the compile time in milliseconds, which LLM tier succeeded, and the total number of attempts across all subagents.

### Key Components

**LeanClient** (`core/lean_client.py`): Shells out to Lean 4 via `asyncio.create_subprocess_exec` (never `shell=True`). Uses `lean --stdin` for fast single-theorem compilation. Captures stdout and stderr separately. Times out every compile call (default 30s) because Lean can hang on malformed input. The Lean path comes from `config.toml` -- never hardcoded, never assumed on PATH. The client maintains a compile semaphore (`max_concurrent_compiles`, default 4) to prevent resource exhaustion. The `ensure_workspace()` method verifies that the workspace directory exists and can run lake commands.

**LLMClient** (`core/llm_client.py`): Async multi-tier LLM client supporting Ollama (local), OpenAI-compatible (DeepSeek, etc.), and Anthropic. All calls are async HTTP and run through httpx. Each LLM tier has its own configuration: base_url, api_key, model name, and optional parameters like temperature and max_tokens. Failed LLM calls (network errors, timeouts, empty responses) are retried up to 3 times before the attempt is marked as failed and counted against the tier's retry budget. Responses are validated to contain actual Lean code before being passed to the compiler.

**JobManager** (`core/job_manager.py`): SQLite-backed job queue and status tracker using aiosqlite (async SQLite). Jobs persist to SQLite immediately on creation with status "queued". Subagents write attempt records after each loop turn, recording step number, LLM tier used, compile success/failure, error message, and timestamp. Jobs in RUNNING state at server startup are marked INTERRUPTED (they were running when the server crashed or was restarted). Job IDs are UUID v4 strings. The database file path is configurable (default `data/jobs.db`).

**Runner** (`core/runner.py`): Orchestrates subagents. The Runner owns the `_tasks` dict mapping job_id to asyncio.Task. On server shutdown, all running tasks are cancelled gracefully. The Runner is set as a module-level fallback so tools and lifespan handlers can access it from any context. The Runner respects the `max_concurrent_compiles` limit from config -- if all slots are full, new jobs remain in "queued" status until a slot opens.

### Config

Configuration lives in `config.toml` in the repo root. A `config.example.toml` is provided as a template. The config is loaded using Python's stdlib `tomllib` (Python 3.11+). The file must exist -- if it doesn't, the server prints an error to stderr and exits with code 1.

```toml
[server]
transport = "stdio"

[database]
path = "data/jobs.db"

[lean]
lake_path = "C:/Users/sandr/.elan/bin/lake.exe"
workspace_dir = "D:/Dev/repos/leanforge-mcp/workspace"
compile_timeout = 30
max_concurrent_compiles = 4

[llm]
default_tier = "ollama"

[llm.ollama]
base_url = "http://127.0.0.1:11434/v1"
model = "deepseek-coder-v2:latest"
api_key = ""
temperature = 0.3
max_tokens = 4096

[llm.openai_compat]
base_url = ""
api_key = ""
model = "deepseek-chat"

[llm.anthropic]
api_key = ""
model = "claude-sonnet-4-20250514"

[logging]
level = "INFO"
log_file = "logs/leanforge.log"

[subagent]
max_retries_per_tier = 5
max_total_steps = 50
parallel_agents = 3
```

The `[llm.ollama]` section is the default tier. The `base_url` should point to an OpenAI-compatible API endpoint. For Ollama, this is typically `http://127.0.0.1:11434/v1`. The `api_key` can be empty for Ollama (it does not require authentication). For OpenAI-compatible services (DeepSeek, Together, etc.), set the `base_url` to their API endpoint and provide the `api_key`. For Anthropic, only the `api_key` is needed -- the base URL is fixed.

## Tool Reference

### submit_theorem(statement, proof_attempt)

Submit a Lean 4 theorem for proof search. Returns immediately with a job_id -- the proof runs in the background. Parameters:
- **statement** (str, required): Lean 4 theorem syntax. Must be a valid `theorem`, `lemma`, `example`, or `def` statement. The statement should include the full type signature.
- **proof_attempt** (str, optional): Starting proof sketch to guide the LLM. Can contain `sorry` placeholders. If provided, the LLM works from this starting point rather than from scratch.

Returns: `{"success": bool, "job_id": str, "message": str}`

The theorem statement is hashed (SHA256) before and after each LLM edit. If the subagent modifies the statement (not just filling sorries), the modification is rejected and a SECURITY warning is logged. Subagents may only fill `sorry` placeholders -- they must never change the theorem statement itself.

### validate_lean(code)

Validate a Lean 4 code snippet without creating a proof job. Runs the code through `lean --stdin` and returns the compiler output. Parameters:
- **code** (str, required): Lean 4 code to validate. Can include imports, definitions, theorems, and proofs.

Returns: `{"success": bool, "valid": bool, "output": str, "errors": list}`

The `errors` field contains structured error information if compilation failed. Each error includes the line number, column, error code, and message.

### get_proof_status(job_id)

Poll the status of a proof search job. This is the primary polling interface for checking job progress. Parameters:
- **job_id** (str, required): UUID of the job from submit_theorem.

Returns: `{"success": bool, "status": str, "result": dict, "attempts": list}`

Status values: `queued` (waiting for a compile slot), `running` (subagents are active), `completed` (proof found and verified), `failed` (all subagents exhausted), `cancelled` (cancelled by user), `interrupted` (server restarted while job was running).

When status is "completed", result contains `verified_proof` (the complete Lean proof), `compile_time_ms` (how long the winning compile took), `tier_used` (which LLM tier succeeded), and `total_attempts` (sum across all subagents).

When status is "failed", result contains `last_error` (the most recent error from any subagent) and `tiers_attempted` (list of LLM tiers that were tried). The `attempts` list shows the last attempt from each subagent.

### cancel_job(job_id)

Cancel a running proof search job. Stops all subagents for this job immediately. Parameters:
- **job_id** (str, required): UUID of the job to cancel.

Returns: `{"success": bool, "job_id": str, "cancelled": bool}`

Cancelled jobs remain in the database for audit purposes. They will not be retried.

### list_jobs()

List all proof search jobs across all sessions. Returns jobs sorted by creation time descending (most recent first).

Returns: `{"success": bool, "jobs": list, "count": int}`

Each job entry includes: `job_id`, `status`, `theorem_statement` (truncated to first 200 chars), `created_at`, `updated_at`, and `attempt_count`.

### list_attempts(problem_id)

List all proof attempts for a specific problem. Groups attempts across jobs that targeted the same problem. Parameters:
- **problem_id** (str, required): Problem identifier to look up. This is a normalized form of the theorem name.

Returns: `{"success": bool, "problem_id": str, "attempts": list, "count": int}`

Each attempt: `job_id`, `step_number`, `llm_tier`, `compile_success`, `error_summary`, `timestamp`.

### get_mathlib_search(query)

Search the Mathlib4 library for theorems, definitions, and lemmas matching the query. Uses FTS5 full-text search on a local pre-built index of Mathlib4. Parameters:
- **query** (str, required): Search query. Supports FTS5 syntax (AND, OR, NOT, prefix*). Example: "add_comm" or "group theory" or "triangle inequality".

Returns: `{"success": bool, "results": list, "count": int}`

Each result: `name` (theorem/def name), `module` (Mathlib4 module path), `signature` (type signature), `doc_string` (if available), and a `relevance` score. Returns empty results if the local index is not built.

## Lean File Safety (Hard Rule)

Subagents may only fill `sorry` placeholders in the theorem proof. The server hashes the theorem statement (everything before the `:=` or `by`) before and after each LLM edit. If the hash changes (meaning the subagent modified the theorem statement), the edit is rejected, a SECURITY warning is logged with the old and new hashes, and the subagent is terminated with a tamper error. This is non-negotiable: the theorem statement is sacred, only the proof body may change. The hash covers the full theorem name, parameters, return type, and colon -- any modification to these triggers the guard.

## Behavior Guidelines

- Return structured JSON from every tool, never plain text. The response always includes `success`, domain-specific fields, and `error` on failure.
- `submit_theorem` returns immediately -- never block for proof completion. The user polls with `get_proof_status`.
- `get_proof_status` is the polling interface; recommend polling every 10-30 seconds depending on theorem complexity.
- Error messages must be actionable: include the Lean compiler error, the failed tactic, and a hint about what to try next.
- All Lean and LLM calls are async. Never block the FastMCP event loop.
- Never write to the `workspace/` directory from tool handlers -- go through JobManager.
- Do not assume Lean is on PATH. Always use the configured absolute path from config.
- Do not hardcode API keys. They come from config.toml only.
- The config path is `{repo_root}/config.toml`. If it does not exist, print an error to stderr and exit.

## Security

- Subagent tamper detection: SHA256 hashing of theorem statements before and after each edit. SECURITY warning logged on tamper attempt.
- LLM API keys stored in config.toml only, never in code or environment variables. config.toml is gitignored.
- SQLite path configured via config.toml; default `data/jobs.db` under repo root.
- Workspace temp files created per-job and cleaned up after completion (both success and failure).
- Lean subprocess is sandboxed: no shell access, bounded timeout, bounded I/O.

## Known Limitations

- Lean 4 only. No support for Lean 3 or other theorem provers (Coq, Isabelle, Agda).
- Mathlib4 search requires a pre-built FTS5 index. Without it, returns empty results.
- GPU acceleration is not used for LLM inference (Ollama may use GPU if configured, but leanforge does not manage that).
- Maximum parallel compilation is bounded by `config.lean.max_concurrent_compiles` (default 4). Additional jobs queue in SQLite.
- Very large theorems (1000+ characters in the statement) may time out. Split into lemmas.
- LLM tier escalation is irreversible: once escalated, a subagent will not de-escalate.
- The server runs on Windows; all path handling uses `pathlib.Path` (no string concatenation).

## Troubleshooting

**Job hangs in "queued" status**: All compile slots are occupied. Check `list_jobs()` to see how many jobs are running. Either cancel an existing job or wait for a slot to free up. The default max_concurrent_compiles is 4.

**Lean compile fails with "unknown identifier"**: The workspace may be missing Mathlib4 imports. Run `lake build` in the workspace directory manually. Check that `lake_path` in config.toml points to the correct lake executable.

**LLM returns empty or gibberish**: Check the LLM provider configuration. For Ollama, verify `ollama serve` is running (`curl http://127.0.0.1:11434/api/tags`) and the model is pulled (`ollama pull <model>`). For OpenAI-compatible, verify the API key and base URL are correct.

**Job status shows "interrupted"**: The server was restarted while the job was running. Resubmit the theorem with `submit_theorem`.

**"config.toml not found" error**: Copy `config.example.toml` to `config.toml` and fill in your local paths and API keys.

**"Workspace not ready" warning**: The Lean workspace directory could not be verified. The server will still start, but proof compilation may fail. Run `lake init` or `lake create` in the workspace directory.

## Startup Flow

1. Load config.toml. Fail with clear error if the file does not exist.
2. Initialize JobManager: create or connect to the SQLite database, run schema migrations.
3. Initialize LeanClient: verify the lake path exists, ensure the workspace directory exists and is functional.
4. Initialize Runner with config, job_manager, and lean client instances.
5. Register all tools (submit_theorem, validate_lean, get_proof_status, cancel_job, list_jobs, list_attempts, get_mathlib_search) on the FastMCP server.
6. Start serving. The Runner waits in the background for incoming proof jobs.
7. On shutdown, cancel all running jobs in Runner._tasks gracefully.

## Directory Layout

```
leanforge-mcp/
  config.toml              # Local config (gitignored)
  config.example.toml      # Template for config
  pyproject.toml           # Python project config
  data/
    jobs.db                # SQLite database (gitignored)
  logs/
    leanforge.log          # Server logs (gitignored)
  workspace/               # Temp Lean files per job (gitignored)
  src/
    __init__.py
    core/
      agent.py             # Subagent loop: LLM propose, Lean compile, repeat
      config.py            # TOML config loader with dataclass models
      job_manager.py       # SQLite job queue, status tracking, attempt records
      lean_client.py       # Lean 4 subprocess wrapper (lean --stdin)
      llm_client.py        # Multi-tier LLM client (Ollama, OpenAI, Anthropic)
      runner.py            # Subagent orchestrator, task registry
    tools/
      submit.py            # submit_theorem, submit_lean_file routers
      status.py            # get_proof_status, list_attempts, list_jobs, validate_lean routers
      control.py           # cancel_job router
      mathlib.py           # get_mathlib_search router
    lean/
      templates/           # .lean file templates for common theorem shapes
    server.py              # FastMCP server entry point, lifespan, main()
  tests/
    test_pipeline.py       # End-to-end pipeline tests
```

## Environment Variables Reference

While most configuration comes from `config.toml`, these env vars influence runtime behavior:
- `PYTHONPATH`: Should include `${PWD}/src` for module resolution
- `PYTHONUNBUFFERED`: Set to "1" for immediate log output
- `MCP_TRANSPORT`: Override transport (stdio/http/sse)
- `MCP_PORT`: Override HTTP port

## Deep Dive: Subagent Algorithm

Each subagent implements a Monte Carlo Tree Search-inspired algorithm adapted for proof search. The tree has a branching factor equal to the number of possible next tactics, and exploration is guided by the LLM's likelihood estimates. However, unlike standard MCTS, there is no reward function until the terminal node (a successful Lean compilation). The subagent thus uses a beam search variant: it keeps the top-K candidate proof fragments at each step, extends them with LLM proposals, and filters by compile success. The beam width is implicitly controlled by `max_retries_per_tier` and `parallel_agents`. Each subagent maintains its own beam independently, providing additional diversity through different random seeds in the LLM sampling.

The proof is considered complete when `lean --stdin` returns exit code 0 on a complete Lean file containing the theorem with a filled proof. The server does not validate the proof semantically beyond what Lean itself checks -- if Lean accepts it, it is a valid proof in the Lean type theory.

## Deep Dive: Lean Compilation Pipeline

When a subagent produces a candidate proof, the following compilation steps occur:
1. The server constructs a complete Lean file by wrapping the theorem statement and proof attempt in a namespace (to avoid symbol conflicts with the target).
2. The file is written to a temp location in the workspace directory with a UUID-based name.
3. `lean --stdin` is launched as a subprocess via `asyncio.create_subprocess_exec` with the file contents piped to stdin. The path to the lake/lean executable comes from `config.toml` (absolute path to lake.exe, which invokes lean).
4. If `lean --stdin` returns within the timeout (default 30s), the server captures stdout and stderr separately. Exit code 0 with empty stderr means success. Anything else means failure, and the stderr is parsed for error locations.
5. If the subprocess times out, it is killed with `process.kill()` and a "Lean compile timeout" error is recorded.
6. The compile semaphore (`asyncio.Semaphore(max_concurrent_compiles)`) ensures no more than N compilations happen simultaneously, preventing CPU contention.

## Deep Dive: LLM Client Tier Architecture

The LLM client supports three tiers with automatic failover:

**Ollama Tier (default):**
- Protocol: OpenAI-compatible chat completions API
- Endpoint: `{base_url}/chat/completions`
- Model: Configurable via config (`deepseek-coder-v2:latest` recommended)
- Auth: None (Ollama does not require authentication)
- Retry: 3 attempts on network error, timeout errors
- Best for: Local, private, fast iteration

**OpenAI-Compatible Tier:**
- Protocol: OpenAI chat completions API
- Endpoint: Configurable (e.g., `https://api.deepseek.com/v1` for DeepSeek, `https://api.openai.com/v1` for OpenAI)
- Model: Configurable per provider
- Auth: Bearer token via API key
- Retry: 3 attempts with exponential backoff
- Best for: Higher quality models when local is insufficient

**Anthropic Tier:**
- Protocol: Anthropic Messages API
- Endpoint: Fixed (`https://api.anthropic.com/v1/messages`)
- Model: Configurable (`claude-sonnet-4-20250514` recommended)
- Auth: x-api-key header
- Retry: 3 attempts with exponential backoff
- Best for: Complex mathematical reasoning, last resort

Each tier has its own config section in config.toml. Empty/unconfigured tiers are skipped during escalation. The system prompt for all tiers includes the theorem statement, the current error context from Lean, and instructions to only modify proof bodies.

## Performance Characteristics

- **Simple Nat arithmetic theorems**: 30s-2min, 1-3 subagent iterations, Ollama tier typically sufficient.
- **Basic algebra (group/ring theorems)**: 2-10min, 3-15 iterations, may need OpenAI-compat tier.
- **Analysis/number theory**: 10-30min, 10-50 iterations, likely needs Anthropic tier for hard cases.
- **Success rate with Ollama deepseek-coder-v2**: ~60-70% on simple theorems, ~30-40% on intermediate, ~10-20% on hard.
- **Success rate with tier escalation**: ~80% overall on well-posed theorems.
- **Compile time per attempt**: 0.5-5s for simple theorems, 5-30s for theorems requiring heavy imports.

## Parallel Subagent Coordination

The Runner manages subagents through the `_tasks` dictionary mapping job_id to asyncio.Task. When a new job is submitted:

1. A `submit_theorem` call creates a job record in SQLite with status "queued".
2. The Runner checks if a compile slot is available (via semaphore).
3. If a slot is free, the Runner spawns `parallel_agents` (default 3) subagent tasks, each targeting the same theorem.
4. Each subagent runs independently in its own asyncio task. They share:
   - The LeanClient compile semaphore (so they do not exceed max_concurrent_compiles)
   - The SQLite database for status updates and attempt logging
   - The module-level config for LLM settings
5. Subagents do NOT communicate with each other or share proof progress. This is by design -- independence maximizes exploration diversity.
6. When any subagent produces a verified proof, the Runner:
   - Cancels all other subagent tasks for this job
   - Updates the job status to "completed" with the winning proof
   - Logs the winning tier and attempt count
7. If all subagents exhaust their tiers without success, the job is marked "failed" with the last error from each subagent.

The subagents use independent LLM sampling (different random seeds) to produce diverse proof strategies. This is critical -- if all subagents propose the same incorrect proof, they all fail the same way. Diversity comes from:
- Different random seeds in LLM temperature sampling
- Different order of tactic application
- Different prior proof context (accumulated errors)

## Error Codes and Recovery

| Error | Cause | Recovery |
|-------|-------|----------|
| "config.toml not found" | Missing configuration | Copy config.example.toml |
| "Lean workspace not ready" | lake/lean not found | Check lake_path in config |
| "Lean compile timeout" | Theorem too complex or stuck | Split into lemmas |
| "All LLM tiers exhausted" | All providers failed | Check API keys, try different models |
| "Theorem statement modified" | LLM tamper detection | Rare; resubmit with locked proof_attempt |
| "Job interrupted" | Server restart during proof | Resubmit theorem |

## Server Lifecycle

The server follows a strict lifecycle:
1. **Load**: Read config.toml, parse with tomllib, validate required fields.
2. **Init**: Create JobManager (SQLite schema), LeanClient (verify paths), Runner (subagent pool).
3. **Serve**: Register FastMCP tools and listen for incoming requests on configured transport.
4. **Shutdown**: Cancel all running subagent tasks in Runner._tasks, close SQLite connections, log shutdown.

If initialization fails (missing config, bad paths, etc.), the server logs the error and exits with code 1 rather than starting with partial functionality.

## Version

leanforge-mcp v0.1.0. Lean 4 formal proof search via Agent A architecture with parallel subagents and multi-tier LLM escalation. MIT license.

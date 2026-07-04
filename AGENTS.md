# AGENTS.md -- leanforge-mcp

Agent protocols for Cursor, Windsurf, Claude Code, and any agentic IDE working in this repo.

## Stack

- **Language:** Python 3.11+, FastMCP >= 3.2.0
- **Package manager:** uv
- **Lean:** Lean 4 via elan, Mathlib4
- **Config:** TOML via `tomllib` (stdlib, Python 3.11+)
- **Persistence:** SQLite via `aiosqlite`
- **Linting:** Ruff (formatter + linter)
- **Tests:** pytest + pytest-asyncio

## Repo layout

```
leanforge-mcp\
├── src\
│   ├── core\
│   │   ├── agent.py        # Subagent loop: LLM propose → Lean compile → repeat
│   │   ├── config.py       # TOML config loader + dataclasses
│   │   ├── job_manager.py  # SQLite job queue, status tracking
│   │   ├── lean_client.py  # Lean 4 subprocess wrapper
│   │   └── llm_client.py   # Multi-tier LLM client (Ollama / OpenAI-compat / Anthropic)
│   ├── tools\
│   │   ├── submit.py       # submit_theorem, submit_lean_file
│   │   ├── status.py       # get_proof_status, list_attempts, list_jobs, validate_lean
│   │   ├── control.py      # cancel_job
│   │   └── mathlib.py      # get_mathlib_search
│   ├── lean\
│   │   └── templates\      # .lean file templates for common theorem shapes
│   └── server.py           # FastMCP server entry point + main()
├── tests\
│   └── test_pipeline.py    # End-to-end pipeline tests
├── docs\
│   ├── ARCHITECTURE.md
│   ├── LEAN_PRIMER.md
│   └── BENCHMARK_RESULTS.md
├── data\                   # SQLite DB lives here (gitignored)
├── logs\                   # Log files (gitignored)
├── workspace\              # Temp Lean files per job (gitignored)
├── config.example.toml
├── config.toml             # Local config (gitignored)
├── pyproject.toml
├── start.ps1
├── glama.json
├── llms.txt
├── AGENTS.md
├── CLAUDE.md
└── README.md
```

## Critical rules

### Lean subprocess
- `lean_client.py` shells out via `asyncio.create_subprocess_exec` -- never `shell=True`
- Lean path must come from config; never hardcode
- Capture both stdout and stderr; Lean emits errors to stderr
- Timeout every compile call (default 30s); Lean can hang on malformed input
- `lean --stdin` is faster than `lake build` for single-theorem proofs -- use it

### LLM client
- All LLM calls are async
- Support: Ollama (local), OpenAI-compatible (DeepSeek), Anthropic
- Tier escalation is per-subagent and irreversible within a job
- Retry failed LLM calls max 3 times before marking attempt as failed

### Job manager
- Jobs persist to SQLite immediately on creation
- Subagents write attempt records after each turn
- Jobs in RUNNING state at startup → mark INTERRUPTED
- Job IDs are UUIDs

### MCP tools
- All tools return structured JSON, not plain text
- `submit_theorem` returns immediately with job_id -- never block for proof
- `get_proof_status` is the polling interface; poll every 10-30s
- Error messages must be actionable: include Lean error, failed tactic, hint

### Lean file safety
- Agents may only fill `sorry` -- never modify theorem statements
- Hash theorem statements before/after each edit; reject if changed
- Log SECURITY warning on tamper attempt

## Windows path notes

Running on Goliath (Windows). Always use `pathlib.Path`, never string concatenation.

- elan: `C:\Users\sandr\.elan\bin\lean.exe`
- Workspace: `D:\Dev\repos\leanforge-mcp\workspace\`
- SQLite: `D:\Dev\repos\leanforge-mcp\data\jobs.db`
- Logs: `D:\Dev\repos\leanforge-mcp\logs\leanforge.log`

## Testing

```powershell
uv run ruff check src\
uv run ruff format --check src\
uv run pytest tests\ -v
```

## Do not

- Modify theorem statements in LLM edits -- reject and log
- Hardcode API keys -- config.toml only
- Block the FastMCP event loop -- all Lean/LLM calls must be async
- Assume Lean is on PATH -- always use the configured absolute path
- Write to `workspace\` from tool handlers -- go through job_manager

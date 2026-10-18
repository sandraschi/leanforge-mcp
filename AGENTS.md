# AGENTS.md -- leanforge-mcp

Agent protocols for Cursor, Windsurf, Claude Code, and any agentic IDE working in this repo.

## Stack

- **Language:** Python 3.12+, FastMCP >= 3.4.4
- **Package manager:** uv (`uv sync --extra dev --extra web` -- bare `uv sync` prunes dev+web deps from the venv)
- **Lean:** Lean 4 via elan, Mathlib4
- **Config:** TOML via `tomllib` (stdlib, Python 3.11+)
- **Persistence:** SQLite via `aiosqlite`
- **Linting:** Ruff (formatter + linter, covers `src/` + `webapp/backend/`)
- **Tests:** pytest + pytest-asyncio
- **Webapp:** React + Vite + Tailwind + Zustand + FastAPI backend (ports 10867/10868); frontend lint via Biome (`bun run biome:ci`), types via `tsc --noEmit`

## Repo layout

```
leanforge-mcp\
├── src\
│   └── leanforge_mcp\
│       ├── core\
│       │   ├── agent.py        # Subagent loop: LLM propose → Lean compile → repeat
│       │   ├── config.py       # TOML config loader + dataclasses
│       │   ├── job_manager.py  # SQLite job queue, status tracking
│       │   ├── lean_client.py  # Lean 4 subprocess wrapper
│       │   └── llm_client.py   # Multi-tier LLM client (Ollama / OpenAI-compat / Anthropic)
│       ├── tools\
│       │   ├── submit.py       # submit_theorem, submit_lean_file
│       │   ├── status.py       # get_proof_status, list_attempts, list_jobs, validate_lean
│       │   ├── control.py      # cancel_job, leanforge_shutdown
│       │   ├── verify.py       # verify_proof (independent kernels)
│       │   └── mathlib.py      # get_mathlib_search
│       ├── lean\
│       │   └── templates\      # .lean file templates for common theorem shapes
│       ├── skills\
│       │   └── lean_expert\    # Lean 4 Expert skill (skill:// + /api/skills)
│       └── server.py           # FastMCP server entry point + main()
├── webapp\
│   ├── backend\                # FastAPI: jobs/problems/stream/skills/docs/llm/logs/status
│   └── frontend\src\           # React: Dashboard/Inbox/Tools/Skills/Chat/Settings/Logs/Help
├── tests\                      # pytest suite (79 tests)
├── docs\                       # ARCHITECTURE, TOOLS, CONFIGURATION, ONBOARDING, ...
├── data\                       # SQLite DB lives here (gitignored)
├── logs\                       # Log files (gitignored)
├── workspace\                  # Temp Lean files per job (gitignored)
├── config.example.toml
├── config.toml                 # Local config (gitignored)
├── pyproject.toml
├── start.ps1
├── glama.json
├── llms.txt
├── AGENTS.md
├── CLAUDE.md
└── README.md
```

## MCP tools

All tools return `success` + `message` on every path (unknown ids keep a legacy
`error` key too). Queries are `readOnlyHint`, submissions `openWorldHint`,
`cancel_job` / `leanforge_shutdown` are `destructiveHint`. `list_jobs` and
`get_proof_status` expose Prefab `app=True` cards.

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

# CLAUDE.md -- leanforge-mcp

Claude Desktop / Claude Code notes for working in this repo.

## What this repo does

leanforge-mcp is a FastMCP server wrapping a Lean 4 formal proof search pipeline.
An agent submits a theorem; the server runs N parallel subagents each looping:
LLM proposes a proof edit → Lean compiler checks → error feeds back → repeat.
First subagent to produce a sorry-free compile wins.

## Key concepts

- `sorry` in Lean = "trust me, skip this proof" -- invalid until all sorry replaced
- The Lean compiler is the oracle -- its error messages ARE the training signal
- Mathlib has ~150k theorems; LLMs know it well from training data
- `import Mathlib` at top of file gives access to all of it

## When working on agent.py

Core loop in `src\core\agent.py`. The LLM's job each turn:
1. Read current `.lean` file
2. Read last compiler error (if any)
3. Propose a search-replace edit filling `sorry`
4. Never change the theorem statement

Lean 4 compiler error format:
```
error: unknown tactic 'magic'
  at Proof.lean:7:4
```
Feed the full error string back verbatim. LLM uses it to self-correct.

## When working on lean_client.py

```python
proc = await asyncio.create_subprocess_exec(
    str(lean_path), "--stdin",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
stdout, stderr = await asyncio.wait_for(
    proc.communicate(input=lean_source.encode()), timeout=30
)
```
Check `proc.returncode == 0` AND no `sorry` in source for a proven result.

## MCP tool quick reference

```
submit_theorem(statement, hints?, tier=1, parallel_agents=4, max_turns=100)
  → {"job_id": "uuid", "status": "queued"}

get_proof_status(job_id)
  → {"status": "running|complete|failed", "proof": "...", "turns_used": int}

validate_lean(lean_source)
  → {"success": bool, "errors": [...]}

get_mathlib_search(query)
  → {"results": [{"name": "...", "statement": "..."}]}
```

## Typical escalation for hard problems

```
# Start cheap local
submit_theorem(statement="...", tier=1, max_turns=100)

# If stalled, escalate
submit_theorem(statement="...", tier=2, max_turns=200)

# Hard open problem
submit_theorem(statement="...", tier=3, max_turns=500)
# At $50/M output -- budget carefully
```

## File locations on Goliath

```
Repo:      D:\Dev\repos\leanforge-mcp\
Config:    D:\Dev\repos\leanforge-mcp\config.toml
DB:        D:\Dev\repos\leanforge-mcp\data\jobs.db
Workspace: D:\Dev\repos\leanforge-mcp\workspace\
Logs:      D:\Dev\repos\leanforge-mcp\logs\leanforge.log
Lean:      C:\Users\sandr\.elan\bin\lean.exe
```

## Claude Desktop config entry

```json
{
  "mcpServers": {
    "leanforge": {
      "command": "uv",
      "args": ["--directory", "D:\\Dev\\repos\\leanforge-mcp", "run", "python", "-m", "leanforge_mcp"],
      "env": {
        "ANTHROPIC_API_KEY": "your-key",
        "DEEPSEEK_API_KEY": "your-key"
      }
    }
  }
}
```

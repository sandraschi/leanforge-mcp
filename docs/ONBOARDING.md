# Onboarding — leanforge-mcp

First-timer setup: what this is, what it costs, what breaks, and how to prove
it works. Budget 30 minutes (plus a ~4 GB Mathlib download you start once and
leave running).

## What you get

An MCP server that proves Lean 4 theorems for you. You submit a theorem with a
`sorry` placeholder; parallel LLM agents propose proof edits; the Lean compiler
judges every attempt; the first sorry-free compile wins. If it compiles without
`sorry`, the proof is machine-checked correct — no reviewer needed.

Web dashboard: same engine behind a React UI (jobs, problem library, chat,
tool/skill browsers, logs, settings). Start it with `webapp\start.ps1`.

## What it costs

| Tier | Provider | Cost | When |
|------|----------|------|------|
| 1 | Ollama, `deepseek-prover-v2:7b` (local, your GPU) | Free | Default. Proofs start here. |
| 2 | DeepSeek API, `deepseek/deepseek-v4-flash` | ~$0.001 per attempt | Agents auto-escalate after 20 stalled turns. Needs `DEEPSEEK_API_KEY`. |
| 3 | Anthropic, `claude-fable-5` | ~$10/M input, ~$50/M output | After 60 stalled turns. Needs `ANTHROPIC_API_KEY`. Reserve for hard open problems. |

No credit card is needed for tier 1. Tiers 2/3 need their API keys in your
environment (never in a file — see `.env.example`). Cost guard: keep
`max_turns` small (20–50) until you trust the loop.

## Prerequisites

- Windows 11, Python 3.12+, `uv` (`winget install astral-sh.uv`)
- `elan` (Lean version manager): `winget install leanprover.elan`
- Ollama for tier 1: `winget install Ollama.Ollama`, then
  `ollama pull deepseek-prover-v2:7b`
- Node 22+ or Bun (webapp frontend build only; the backend is Python)

## One-time setup (the pits of success)

1. `Copy-Item config.example.toml config.toml` — defaults work on any machine.
   Uncomment `lake_path` / `workspace_dir` only to override.
2. Create the Mathlib workspace (one time, ~4 GB, mostly unattended):
   ```powershell
   cd workspace
   lake new leanforge_workspace math
   cd leanforge_workspace
   lake exe cache get
   lake build
   ```
3. `uv sync --extra dev --extra web`
4. `.\start.ps1 -Check` — must print the dependency check, not a Lean error.
5. `uv run python -m leanforge_mcp` — the server starts on stdio. Stop it
   with Ctrl+C (or the `leanforge_shutdown` tool).

## Sanity check (prove it works in 60 seconds)

```powershell
uv run python scripts/smoke_test.py
```

Then, with the server running, call:

- `validate_lean("import Mathlib\nexample : 1 = 1 := rfl\n")`
  → `{"success": true, "proven": true, ...}` proves the compile pipeline works.
- `submit_theorem(statement="∀ n : Nat, n + 0 = n", max_turns=20)`
  → `{"success": true, "job_id": "...", "status": "queued"}`.
- `get_proof_status("<job_id>")` every 10–30 s until `complete`.

If the first call returns `status: "pending"`, the Lean workspace is still
building — wait and retry. If it returns `status: "error"`, read
`docs/TROUBLESHOOTING.md` before changing anything.

## Webapp onboarding cue

Open the dashboard (`webapp\start.ps1`, frontend on :10868). Until the Lean
workspace reports ready you will see a red **onboarding cue** under the hero
and MOCK-badged sample cards instead of jobs. Both clear automatically once
`GET /api/status` reports `lean_workspace.ok: true`. Go to **Settings** to
verify LLM providers (green = reachable/keyed), then submit your first theorem
from **New Theorem**.

## Common pitfalls

- **Bare `lean` instead of `lake env lean`.** A bare `lean` cannot resolve
  `import Mathlib`. The server always compiles via `lake env lean` inside the
  workspace — never point it at a bare compiler.
- **`uv sync` without extras.** Bare `uv sync` prunes `pytest`/`ruff`
  (dev) and `fastapi` (web) from the venv. Always
  `uv sync --extra dev --extra web`.
- **Tier-3 sticker shock.** `max_turns: 500` on tier 3 is real money. Budget
  first, escalate deliberately.
- **Editing theorem statements.** Agents may only fill `sorry`. The server
  hashes statements and rejects tampering — do not "help" by weakening the
  goal.
- **Chat needs the backend.** The Chat page calls `POST /api/llm/chat`, never
  Ollama directly. If chat errors, start the backend and check Settings.

## Next steps

- `docs/LEAN_PRIMER.md` — Lean 4 in 15 minutes for engineers.
- `docs/TOOLS.md` — every MCP tool with parameters and examples.
- `docs/CONFIGURATION.md` — all `config.toml` keys.
- `docs/TROUBLESHOOTING.md` — error catalog.

# Installing leanforge-mcp

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Claude Desktop | Required host | [download](https://claude.ai/download) |
| Python + uv | Run server | `winget install astral-sh.uv` |
| Git | Clone repo | `winget install Git.Git` |
| Lean 4 via elan | Lean compiler | `winget install leanprover.elan` |
| Ollama | Tier-1 local LLM | [ollama.com](https://ollama.com) |

---

## Option A -- Manual configuration (recommended for now)

MCPB packaging is planned but not yet released. Manual setup takes about 5 minutes
plus the one-time Mathlib download.

### 1. Clone and install

```powershell
git clone https://github.com/sandraschi/leanforge-mcp
cd leanforge-mcp
uv sync
```

### 2. Configure

```powershell
Copy-Item config.example.toml config.toml
```

Open `config.toml` and verify:
- `[lean] lake_path` points to your `lake.exe` (default: `C:\Users\<you>\.elan\bin\lake.exe`)
- `[lean] workspace_dir` points to the workspace you'll create in the next step
- `[llm.tier2]` and `[llm.tier3]` `api_key_env` values match your env vars

### 3. Set up the Lean + Mathlib workspace (one-time, ~4GB)

This is required for anything to compile. Takes 20-40 minutes on first run.

```powershell
cd workspace
lake new leanforge_workspace math
cd leanforge_workspace
lake exe cache get     # downloads precompiled Mathlib oleans
lake build             # verifies everything resolves
cd ..\..
```

Verify it worked:
```powershell
uv run python -m leanforge_mcp  # should start without "workspace not ready" warning
```

### 4. Pull the tier-1 model

```powershell
ollama pull deepseek-prover-v2:7b
```

This is the local free model for the first 20 turns of every job. Tier-2 and tier-3
(DeepSeek API / Anthropic) are optional and only engaged after turn 20/60.

### 5. Set API keys (optional, for tier-2/3)

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Or add them to the Claude Desktop config `env` block (see below) -- they never need
to be in `config.toml`.

### 6. Add to Claude Desktop

Config file location:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "leanforge": {
      "command": "uv",
      "args": [
        "--directory", "C:\\path\\to\\leanforge-mcp",
        "run", "python", "-m", "leanforge_mcp"
      ],
      "env": {
        "DEEPSEEK_API_KEY": "sk-...",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Replace `C:\\path\\to\\leanforge-mcp` with the actual path. Restart Claude Desktop.

### 7. Verify installation

In Claude Desktop, ask:
> "Validate this Lean 4 snippet: `example : 1 = 1 := rfl`"

Expected response: `{"proven": true, "has_sorry": false, "errors": []}`

---

## Option B -- Developer mode

For contributing or running with live reload. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common errors.

Most common: the Lean workspace isn't set up (step 3 above). `validate_lean` will
return `lake executable not found` or a Mathlib resolution error until the workspace
exists and `lake exe cache get` has completed.

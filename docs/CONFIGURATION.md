# Configuration

leanforge-mcp reads `config.toml` from the repo root. Copy `config.example.toml`
to get started. API keys are never stored in `config.toml` -- pass them as
environment variables (via Claude Desktop's `env` block or your shell).

---

## [lean]

| Key | Default | Description |
|-----|---------|-------------|
| `lake_path` | `C:\Users\<you>\.elan\bin\lake.exe` | Absolute path to `lake.exe`. We invoke `lake env lean <file>`, not `lean` directly. |
| `workspace_dir` | `…\workspace\leanforge_workspace` | Lake project with Mathlib dependency and cached oleans. One-time setup required. |
| `compile_timeout` | `120` | Seconds before a Lean compile is killed. Mathlib files are slow; 120s is conservative. |
| `max_concurrent_compiles` | `4` | Semaphore cap on parallel `lake env lean` processes. Each loads Mathlib (~GB RAM). |
| `retain_workspace` | `false` | Keep temp `.lean` files after job completes. Enable for debugging compiler output. |

---

## [database]

| Key | Default | Description |
|-----|---------|-------------|
| `path` | `…\data\jobs.db` | SQLite database path. Parent directory is created automatically. |

---

## [agent]

| Key | Default | Description |
|-----|---------|-------------|
| `parallel_agents` | `4` | Default number of independent subagents per job. Can be overridden per-job via `submit_theorem`. |
| `max_turns` | `100` | Default turn budget per subagent. |
| `escalate_to_tier2_after` | `20` | Turn at which each subagent switches from tier-1 to tier-2. |
| `escalate_to_tier3_after` | `60` | Turn at which each subagent switches from tier-2 to tier-3. |

---

## [llm.tier1] -- local Ollama (free)

| Key | Default | Description |
|-----|---------|-------------|
| `provider` | `ollama` | -- |
| `model` | `deepseek-prover-v2:7b` | Pull with `ollama pull deepseek-prover-v2:7b`. |
| `base_url` | `http://localhost:11434/v1` | The `/v1` suffix is required -- Ollama serves the OpenAI-compatible API there. |
| `max_tokens` | `2048` | -- |
| `temperature` | `0.7` | -- |

---

## [llm.tier2] -- DeepSeek API

| Key | Default | Description |
|-----|---------|-------------|
| `provider` | `openai_compat` | Uses the OpenAI-compatible client. |
| `model` | `deepseek-chat` | DeepSeek V4 Flash. Check [docs](https://platform.deepseek.com/api-docs) for the current model name. |
| `base_url` | `https://api.deepseek.com/v1` | -- |
| `api_key_env` | `DEEPSEEK_API_KEY` | Name of the env var holding your DeepSeek API key. |
| `max_tokens` | `4096` | -- |

---

## [llm.tier3] -- Anthropic (hard problems only)

| Key | Default | Description |
|-----|---------|-------------|
| `provider` | `anthropic` | Uses the native Anthropic client. |
| `model` | `claude-opus-4-8` | Update to whichever current model is strongest. |
| `api_key_env` | `ANTHROPIC_API_KEY` | Name of the env var holding your Anthropic API key. |
| `max_tokens` | `8192` | -- |
| `temperature` | `1.0` | Higher temperature for tier-3 -- diversity of proof strategies matters at this stage. |

> **Cost warning:** Tier-3 is expensive. At default settings (8192 tokens, up to 40
> tier-3 turns per agent × 4 agents), a hard job can cost $5-20. Token/cost
> accounting is on the roadmap (P2-3) -- do not run overnight batches until it lands.

---

## [server]

| Key | Default | Description |
|-----|---------|-------------|
| `transport` | `stdio` | Use `stdio` for Claude Desktop. `http` for the webapp backend. |
| `host` | `127.0.0.1` | Bind address for HTTP transport. |
| `port` | `8765` | Port for HTTP transport. The webapp backend uses its own port (10855). |

---

## [logging]

| Key | Default | Description |
|-----|---------|-------------|
| `level` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `log_file` | `…\logs\leanforge.log` | Log file path. Parent directory is created automatically. |

---

## Setting environment variables

In `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "leanforge": {
      "env": {
        "DEEPSEEK_API_KEY": "sk-...",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

In PowerShell (session only):
```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
```

Permanently (user scope):
```powershell
[System.Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-...", "User")
```

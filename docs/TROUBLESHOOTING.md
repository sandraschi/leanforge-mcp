# Troubleshooting

## Server doesn't appear in Claude Desktop

**Cause:** Config JSON is malformed, or the path to the repo is wrong.  
**Fix:** Validate `claude_desktop_config.json` at [jsonlint.com](https://jsonlint.com).
Check for trailing commas. Verify the `--directory` path exists and uses `\\` on Windows.

## "config.toml not found"

**Cause:** `config.toml` hasn't been created.  
**Fix:** `Copy-Item config.example.toml config.toml` from the repo root.

## validate_lean returns "lake executable not found"

**Cause:** `lake.exe` is not at the configured path, or elan isn't installed.  
**Fix:**
```powershell
winget install leanprover.elan
# Restart shell, then:
where.exe lake
```
Update `[lean] lake_path` in `config.toml` with the path `where.exe lake` returns.

## validate_lean returns Mathlib errors / "unknown identifier"

**Cause:** The Lean workspace hasn't been set up, or `lake exe cache get` didn't complete.  
**Fix:** Run the one-time workspace setup from [INSTALL.md](../INSTALL.md) step 3.
Takes 20-40 minutes. If interrupted, run `lake exe cache get` again from inside the
workspace directory -- it resumes from where it left off.

## Jobs stuck at "queued" forever

**Cause:** The server didn't complete startup (Lean workspace check failed silently).  
**Fix:** Check `logs/leanforge.log` for a "workspace not ready" warning. If present,
complete the Lean workspace setup and restart Claude Desktop.

## Tier-1 always returns LLM_ERROR

**Cause:** Ollama isn't running, or the model isn't pulled.  
**Fix:**
```powershell
ollama list        # check if deepseek-prover-v2:7b appears
ollama pull deepseek-prover-v2:7b
ollama serve       # if not running as a background service
```
The tier-1 `base_url` in `config.toml` must be `http://localhost:11434/v1` (with `/v1`).

## PARSE_ERROR every turn -- model can't format responses

**Cause:** The 7B tier-1 model struggles with the `<<<REPLACE...REPLACE>>>` format.  
**Fix:** Set `escalate_to_tier2_after = 3` in `config.toml` to escalate faster.
Requires a DeepSeek API key and sets the tier-2 model (DeepSeek V4 Flash) which
reliably follows the format.

## "database is locked"

**Cause:** Two processes writing to `jobs.db` simultaneously without WAL mode.  
**Status:** Fixed in v0.1.1 -- WAL + busy_timeout=5000 applied on all connections.
If you see this on v0.1.1+, check that the webapp and MCP server aren't both running
on an older copy.

## Jobs show "interrupted" on startup

**Cause:** The server crashed or was killed while jobs were running. `JobManager.init()`
marks them interrupted on the next start.  
**Note:** This is expected behavior for clean crash recovery. If the job actually
completed before the crash, the proof is in the database -- query `list_jobs` and
check for any `complete` jobs.

## Proof compiles but `proven` is false

**Cause:** The proof uses `sorry` somewhere (possibly in a helper lemma).  
**Fix:** Run `validate_lean` on the output to see the full compiler output including
the "declaration uses 'sorry'" warning.

## High memory usage with multiple agents

**Cause:** Each `lake env lean` process loads Mathlib into memory (~1-2GB each).  
**Fix:** Reduce `max_concurrent_compiles` in `config.toml` (default: 4). On 64GB
Goliath, 4 is safe. On less RAM, drop to 2.

# leanforge-mcp User Guide

## Getting Started

leanforge-mcp helps you find machine-verified Lean 4 proofs for your theorems. You submit a theorem statement, and the server runs parallel AI subagents that propose proof steps and check them with the Lean compiler. The subagents work independently and in parallel, each trying different proof strategies. The first subagent to produce a verified proof wins.

### Prerequisites

- Lean 4 installed via elan (on this system: `C:\Users\sandr\.elan\bin\lean.exe`)
- Mathlib4 cloned and accessible from the workspace directory
- Python 3.11+ with `uv` package manager
- `config.toml` set up with correct paths (copy from `config.example.toml`)
- At least one LLM provider configured: Ollama (recommended for local use), OpenAI-compatible, or Anthropic

### Quick Start

1. Copy `config.example.toml` to `config.toml` and fill in your paths and API keys. At minimum, set `lake_path` to your lake.exe location and configure one LLM tier.
2. Ensure at least one LLM provider is reachable. For Ollama, run `ollama serve` in a terminal and `ollama pull deepseek-coder-v2:latest` to download the recommended model.
3. Start the server: `uv run python -m leanforge_mcp`
4. Submit a theorem: `submit_theorem(statement="theorem add_comm (a b : Nat) : a + b = b + a := by")`
5. Poll with `get_proof_status(job_id="<uuid>")` every 10-30 seconds
6. When status is "completed", read the `verified_proof` in the result

### Prompt Engineering for Best Results

Writing good theorem statements and providing useful starting points significantly improves the success rate of proof search.

**Good theorem statements include:**
- Clear type signatures with explicit parameters: `theorem add_comm (a b : Nat) : a + b = b + a := by`
- Natural parameter names that hint at their role: `h` for hypotheses, `n` for natural numbers
- Single theorem per submission -- break complex statements into lemmas
- Comments above the theorem to provide context: `-- Need this lemma for the main proof`

**The `proof_attempt` parameter:**
- Always provide a starting point when you know the general proof strategy
- Include `sorry` placeholders for parts you are unsure about
- Example: `proof_attempt="induction a\ncase zero =>\n  simp\ncase succ a ih =>\n  sorry"`
- The LLM will fill in the sorries and fix errors iteratively

**Avoid:**
- Vague statements with no type information: `theorem stuff := 42` -- this is not a theorem
- Multiple theorems in a single submission -- each theorem should be its own job
- Theorems that require deep Mathlib4 imports without marking the imports in comments

### Polling Strategy

- Poll `get_proof_status` every 10-30 seconds. Faster polling wastes server resources and risks rate limiting.
- Simple theorems (Nat arithmetic, basic algebraic identities): typically complete in 30 seconds to 5 minutes.
- Moderately complex theorems (requiring lemma selection, case analysis): 5-15 minutes.
- Complex theorems (requiring deep reasoning, multiple lemmas, or specific Mathlib4 lemmas): 15-30 minutes.
- If a job is in "running" status for more than 30 minutes without progress, consider cancelling with `cancel_job` and resubmitting with a better `proof_attempt`.
- When a job shows "failed", examine the `last_error` field in the result. Common failure modes:
  - "Lean compile timeout" (default 30s): the theorem may be too large, or the proof strategy leads to a non-terminating computation
  - "All LLM tiers exhausted": every configured LLM tried and failed. Try adding more API keys or adjusting the retry limits
  - "Theorem statement modified": subagent tamper detection triggered (rare; if this happens, log a security incident)
  - "LLM returned empty response": the LLM provider may be down or the prompt may be malformed

### Submitting Multiple Theorems

Each `submit_theorem` call creates an independent job. You can submit multiple theorems in parallel. Jobs queue behind the `max_concurrent_compiles` limit (default 4). When a compile slot frees up (a job completes, fails, or is cancelled), the next queued job starts automatically.

Use `list_jobs()` to see all jobs and their current status. The list is sorted by creation time (most recent first). You can track progress across all submitted theorems in one call.

### Using Mathlib4 Search

Before proving a new theorem, search Mathlib4 to see if it already exists or if there are closely related lemmas. The `get_mathlib_search(query)` tool uses FTS5 full-text search on a local index:

- `get_mathlib_search(query="add_comm")` -- search for commutativity of addition
- `get_mathlib_search(query="triangle inequality")` -- search for triangle inequality lemmas
- `get_mathlib_search(query="gcd AND lcm")` -- search for results related to both gcd and lcm

If the theorem exists, you can use it directly. If there are related lemmas, mention them in comments above your theorem to guide the LLM.

### Validating Code Before Submission

Use `validate_lean(code)` to check if a Lean snippet compiles before submitting it as a theorem. This is useful for:
- Testing that your imports resolve correctly
- Checking that intermediate definitions are syntactically valid
- Ensuring that a partial proof skeleton compiles up to `sorry`
- Debugging import paths and module references

The validation runs through `lean --stdin` with the configured timeout (default 30s). The output includes the full compiler output on success or structured errors on failure.

### Cancelling Jobs

To cancel a stuck or unnecessary job: `cancel_job(job_id="...")`. This terminates all subagents for that job immediately and marks it as "cancelled" in the database. Cancelled jobs remain in the database for audit but are never retried. If you cancel by accident, resubmit with `submit_theorem`.

### Understanding Tier Escalation

If Ollama (Tier 1) fails to find a proof after `max_retries_per_tier` attempts, the subagent escalates to OpenAI-compatible (Tier 2). If that also fails, it escalates to Anthropic (Tier 3). Each tier has its own retry budget. The escalation is irreversible: a subagent that escalates from Ollama to Anthropic will not de-escalate even if the higher tier succeeds.

You can control which tiers are available through config.toml. Configured but empty-blank tiers are skipped. If all configured tiers are exhausted, the job fails with an explanatory message.

### Reading Attempt History

Understanding how subagents are progressing helps you debug proof issues:
- `list_jobs()`: top-level view of all jobs with status and creation time
- `get_proof_status(job_id)`: detailed view of a single job, including all attempts
- `list_attempts(problem_id)`: cross-job view of all attempts for a specific problem

Each attempt record shows:
- `step_number`: ordinal within the subagent loop (1-based)
- `llm_tier`: which LLM was used (ollama, openai_compat, anthropic)
- `compile_success`: whether the Lean compiler accepted this attempt
- `error_message`: the Lean compiler error if compilation failed (truncated to 500 chars)
- `timestamp`: when this attempt occurred

### Best Practices

**For theorem discovery:**
1. Search Mathlib4 first with `get_mathlib_search(query)`
2. If found, use the existing theorem; if not, submit your own
3. Start with simple lemmas and build up to the main theorem

**For batch proving:**
1. Submit supporting lemmas first
2. Wait for them to complete
3. Submit the main theorem referencing completed lemmas

**For debugging:**
1. When a proof fails, get the last error with `get_proof_status(job_id)`
2. Reproduce the error locally with `validate_lean(code=last_attempt_code)`
3. Adjust the proof_attempt and resubmit

## Architecture Details

### Subagent Loop

Each subagent follows this exact loop:
1. LLM proposes a proof (or continuation of a partial proof) based on the theorem and current error context
2. Server hashes the theorem statement (everything before `:=` or `by`) for tamper detection
3. Server compiles the proposed proof using `lean --stdin` with a timeout
4. If compile succeeds (exit code 0): proof is verified, job completes
5. If compile fails: server captures stdout+stderr, parses for error locations, feeds the error back to the LLM
6. LLM proposes a revised proof based on the new error context
7. Repeat until max_retries_per_tier is reached at the current tier
8. If tier exhausted: escalate to next LLM tier
9. If all tiers exhausted: mark job as failed with final errors

Multiple subagents (default 3, configurable via `parallel_agents`) run simultaneously on the same theorem. They share the compile semaphore but have independent LLM contexts. The first subagent to produce a correct proof wins.

### Thread Safety and Concurrency

- SQLite writes use aiosqlite (async-safe, no thread pool)
- Lean subprocesses are bounded by `asyncio.Semaphore` (max_concurrent_compiles)
- LLM calls are async HTTP via httpx -- no thread pool involvement
- Runner._tasks uses standard asyncio.Task management
- All temp files are assigned unique UUID-based names per job

### Windows Path Notes

This server runs on Windows (hostname Goliath). All paths are managed with `pathlib.Path`:
- elan: `C:\Users\sandr\.elan\bin\lean.exe`
- lake: `C:\Users\sandr\.elan\bin\lake.exe`
- Workspace: `D:\Dev\repos\leanforge-mcp\workspace\`
- Database: `D:\Dev\repos\leanforge-mcp\data\jobs.db`
- Logs: `D:\Dev\repos\leanforge-mcp\logs\leanforge.log`

Never construct paths by string concatenation. Always use `Path(...) / "subdir" / "file"`.

## Examples

### Simple commutativity proof
```
submit_theorem(statement="theorem add_comm (a b : Nat) : a + b = b + a := by")
```
Expected proof: `induction a` with `simp` for base case and `simp [add_comm a b]` or `simp [add_succ, succ_add]` for the step case.

### Theorem with starting proof sketch
```
submit_theorem(
    statement="theorem mul_add (a b c : Nat) : a * (b + c) = a * b + a * c := by",
    proof_attempt="induction a\ncase zero =>\n  simp\ncase succ a ih =>\n  simp [mul_add, add_assoc]"
)
```
The LLM will fix any errors in the proof sketch and complete the missing steps.

### Searching Mathlib4 before proving
```
get_mathlib_search(query="distributivity of multiplication over addition")
```
This returns all matching lemmas, including `mul_add` and `add_mul` from Mathlib4's `Algebra/GroupPower` module.

### Validating a custom definition before submission
```
validate_lean(code="""
import Mathlib

def double (x : Nat) : Nat := x + x

theorem double_add (x y : Nat) : double (x + y) = double x + double y := by
  simp [double]
""")
```

### Cancelling a stuck job
```
cancel_job(job_id="550e8400-e29b-41d4-a716-446655440000")
```
Response: `{"success": true, "job_id": "550e8400...", "cancelled": true}`

## Output Format

All tools return structured JSON dictionaries with these common fields:
- `success`: boolean. True if the operation succeeded.
- `message`: human-readable status or result summary.
- Domain-specific fields as documented for each tool.
- `error`: present only on failure, with actionable recovery information.

### submit_theorem response
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Proof job submitted for theorem 'add_comm'. Use get_proof_status('550e8400...') to poll for results."
}
```

### get_proof_status on completion
```json
{
  "success": true,
  "status": "completed",
  "result": {
    "verified_proof": "theorem add_comm (a b : Nat) : a + b = b + a := by\n  induction a with\n  | zero => simp\n  | succ a ih => simp [add_succ, succ_add, ih]",
    "compile_time_ms": 234,
    "tier_used": "ollama",
    "total_attempts": 4
  }
}
```

### get_proof_status on failure
```json
{
  "success": true,
  "status": "failed",
  "result": {
    "last_error": "Lean compilation failed at line 3, column 5: unknown identifier 'add_succ'",
    "tiers_attempted": ["ollama", "openai_compat"],
    "total_attempts": 12
  }
}
```

## Understanding Theorem Difficulty

Different theorems require different amounts of proof search effort. Here is a rough guide to estimate difficulty:

**Trivial (30s-2min, Ollama sufficient):**
- Basic arithmetic identities: `add_comm`, `add_assoc`, `mul_comm`, `mul_assoc`
- Simple properties of 0 and 1: `add_zero`, `zero_add`, `mul_one`, `one_mul`
- Nat.succ properties: `succ_add`, `add_succ`, `succ_pred`, `succ_ne_self`
- Simple boolean properties: `succ_inj`, `zero_ne_succ`

**Easy (2-5min, Ollama typically sufficient):**
- Distributivity: `mul_add`, `add_mul`
- Power properties: `pow_zero`, `pow_one`, `pow_add`, `pow_mul`
- Simple divisibility: `dvd_refl`, `dvd_trans`, `one_dvd`, `dvd_zero`
- GCD/LCM basics: `gcd_self`, `gcd_comm`, `gcd_zero_left`, `lcm_comm`

**Medium (5-15min, may need OpenAI-compat):**
- Cancellation: `add_left_cancel`, `add_right_cancel`, `mul_left_cancel`
- GCD properties: `gcd_dvd_left`, `gcd_dvd_right`, `dvd_gcd`
- LCM properties: `dvd_lcm_left`, `dvd_lcm_right`, `lcm_dvd`
- Modular arithmetic: `mod_add_div`, `add_mod`, `mul_mod`, `mod_mod`
- Inequality: `add_lt_add_right`, `mul_lt_mul_of_pos_right`, `le_of_lt`

**Hard (15-30min, likely needs Anthropic):**
- Multi-step: `gcd_mul_lcm`, `sq_sub_sq`, `succ_mul_succ`
- Products of sums: `mul_add_mul`, `add_sub_add_right`
- Compound inequalities: `add_lt_add`, `mul_lt_mul`
- Non-trivial divisibility: `dvd_of_mod_eq_zero`, `mod_eq_zero_of_dvd`

## Comparing with Other Theorem Provers

Lean 4 proof search via leanforge-mcp differs from other theorem-proving approaches:

**vs. ChatGPT writing Lean proofs directly:** leanforge-mcp uses a compiler-checked loop. Every proposed proof is evaluated by the actual Lean compiler, not by the LLM's guess of correctness. This eliminates hallucinated proofs that look plausible but do not compile.

**vs. Interactive theorem proving in an IDE:** leanforge-mcp operates fully autonomously. You submit a theorem and come back when it is done. There is no need to sit at a terminal and guide the prover step by step. The tradeoff is less control over the proof strategy.

**vs. Sledgehammer (Isabelle):** Sledgehammer integrates with automated theorem provers (ATP) like E, Vampire, Z3. leanforge-mcp uses LLMs instead of ATP, which gives it broader coverage of domains (ATP excels at first-order logic, LLMs can handle more complex mathematical reasoning) but no proof certificate independent of Lean.

**vs. AlphaProof (DeepMind):** AlphaProof is Google's reinforcement learning approach requiring massive compute. leanforge-mcp's Agent A architecture is inspired by the AlphaProof Nexus paper (arXiv:2605.22763) but runs on a single machine with local LLMs, making it practical for everyday theorem proving.

## Installing and Running on a New Machine

To set up leanforge-mcp on a fresh machine:

1. Install Lean 4 via elan: `curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh` (or download the Windows installer from the Lean website).
2. Clone and set up Mathlib4: `lake new workspace mathlib` then `lake build` in the workspace directory.
3. Install Python deps: `uv sync` in the repo root.
4. Copy `config.example.toml` to `config.toml` and update paths:
   - Set `lake_path` to the location of lake.exe (usually under `~/.elan/bin/` on Linux or `C:\Users\<user>\.elan\bin\` on Windows).
   - Set `workspace_dir` to your Mathlib4 workspace directory.
   - Configure at least one LLM tier (Ollama is the easiest for local use).
5. Start the server: `uv run python -m leanforge_mcp`
6. Test with a simple theorem: `submit_theorem(statement="theorem zero_add (n : Nat) : 0 + n = n := by")`

## Deep Dive: How Tamper Detection Works

The theorem statement hash verification is a critical security mechanism. Here is how it works in detail:

1. When a subagent receives a theorem for proof search, the server parses the statement to extract the "header" -- everything before the first `:=` or `by` token. This includes the keyword (`theorem`, `lemma`, `def`), the name, all parameters with their types, and the return type.
2. The server computes a SHA256 hash of this header text.
3. The LLM's proof proposal is parsed the same way after generation.
4. If the new SHA256 hash differs from the original, the change is rejected. An ALERT-level security log entry is written with both the old and new hashes, the raw LLM output, and the subagent ID.
5. The subagent is immediately terminated. No further retries are attempted for that subagent.
6. The job continues with other subagents that are still running (if any).

This mechanism prevents a class of attacks where the LLM modifies the theorem to something trivially provable (e.g., changing `a + b = b + a` to `a + b = a + b` which is trivially true by `rfl`). The theorem statement must remain exactly as submitted.

## FAQ

**Q: Can I submit a theorem that requires specific Mathlib4 imports?** A: Yes. Include the imports as a comment above the theorem. The server includes the imports in the Lean compilation context.

**Q: Can I use multiple machines for proof search?** A: Not directly -- the server runs on a single machine. But you can run multiple instances pointed at the same SQLite database (not recommended without locking).

**Q: Does the server support `calc` blocks?** A: Yes. The LLM can generate `calc` blocks just like any other Lean syntax. If they compile, they are accepted.

**Q: What happens if the server crashes during a proof search?** A: Running jobs are marked as "interrupted" on next startup. Resubmit the theorem.

**Q: Can I see the intermediate attempt history?** A: Yes. Use `get_proof_status(job_id).attempts` to see all LLM proposoals and their compile results.

**Q: Does the server support `by`-blocks with multiple tactics?** A: Yes. The full Lean tactic language is available. The subagent can generate any valid Lean proof.

## Example Workflows

### Workflow: Prove a New Theorem from Scratch
1. `submit_theorem(statement="theorem my_new_lemma (x : Nat) : x + 0 = x := by")`
2. `get_proof_status(job_id)` every 10s until status is "completed" or "failed"
3. If completed: extract `verified_proof` from result
4. If failed: examine `last_error` and resubmit with a better `proof_attempt`

### Workflow: Chain Lemmas into a Main Theorem
1. `submit_theorem(statement="lemma_1 ...")` -- prove the first supporting lemma
2. `submit_theorem(statement="lemma_2 ...")` -- prove the second supporting lemma
3. Wait for both to reach "completed" status
4. `submit_theorem(statement="main_theorem ...", proof_attempt="-- using lemma_1 and lemma_2")` -- prove the main theorem

### Workflow: Discover and Use Mathlib4 Theorems
1. `get_mathlib_search(query="inverse of matrix product")`
2. Examine results for suitable lemmas
3. If found: `validate_lean(code="import Mathlib ...")` to verify availability
4. If not found: `submit_theorem(statement="my_matrix_inverse_product ...")` -- prove it manually

### Workflow: Batch Prove Textbook Exercises
1. Submit all exercises: for each exercise, call `submit_theorem(statement=...)`
2. `list_jobs()` to get all job IDs and statuses
3. Poll `get_proof_status()` for each job
4. Download completed proofs and mark failed ones for manual review
5. For failed ones, examine attempts with `list_attempts(problem_id)`

### Workflow: Debug a Failed Proof
1. `get_proof_status(job_id)` -- get the last error message
2. `list_attempts(problem_id)` -- see all attempts for context
3. Copy the last attempt's code
4. `validate_lean(code=last_attempt_code)` -- reproduce the error locally
5. Based on the Lean error, create a better `proof_attempt` and resubmit
6. If the error is "unknown identifier", check imports
7. If the error is "type mismatch", the proof strategy may be wrong

### Workflow: Verify a Mathlib4 PR
1. `get_mathlib_search(query="new PR theorem name")` -- check if it already exists
2. `submit_theorem(statement=pr_theorem_statement)` -- attempt to prove it
3. `get_proof_status()` -> if completed, the theorem is correctly stated
4. If the proof matches the PR's proof, the PR is verified
5. Document: "All theorems in PR #12345 have been independently verified"

## Common Theorem Patterns

### Simple Equality Proofs
```lean
theorem simple_eq (x : Nat) : x + 0 = x := by
  -- Typical approach: simp or induction
  simp
```

### Transitive Chain Proofs
```lean
theorem chain (a b c d : Nat) (h1 : a = b) (h2 : b = c) (h3 : c = d) : a = d := by
  calc
    a = b := h1
    _ = c := h2
    _ = d := h3
```

### Proof by Induction
```lean
theorem inductive_proof (n : Nat) : 2 * n = n + n := by
  induction n with
  | zero => simp
  | succ n ih =>
    simp [mul_succ, add_succ, add_assoc, ih]
```

### Proof Using Cases
```lean
theorem case_analysis (b : Bool) : b || !b = true := by
  cases b <;> simp
```

### Proof by Rewriting
```lean
theorem use_lemma (x y : Nat) (h : x = y) : x + 1 = y + 1 := by
  rw [h]
```

## Interpreting Lean Compiler Errors

When the subagent attempts a proof, the Lean compiler may return errors. Understanding common errors helps you improve your proof_attempt:

### "unknown identifier: X"
The identifier X is not in scope. Common causes:
- Missing import: add `import Mathlib` or the specific module
- Typo in name: check spelling
- X is not defined in the current context: add it as a parameter

### "type mismatch"
The expression has a different type than expected:
- Check that function arguments are in the correct order
- Check that implicit arguments are being provided correctly
- The proof strategy may be pointing in the wrong direction

### "application type mismatch"
A function is being applied to arguments of the wrong type:
- Check argument types against the function signature
- Implicit arguments may need to be explicit with `@`

### "don't know how to synthesize placeholder"
A metavariable could not be resolved:
- Provide explicit proofs for all subgoals
- Use `apply` to match the goal to a known theorem

### "maximum recursion depth exceeded"
The proof is stuck in infinite recursion:
- Use a different proof strategy (e.g., `cases` instead of `induction`)
- Avoid `simp` on recursive definitions without controlling the depth

### "invalid field notation"
Trying to access a field that does not exist:
- Check the structure definition
- Use the correct dot notation

## Known Issues and Workarounds

### Issue: Lean 4 version mismatches
If the lean executable version differs from what the workspace was built with, compilation may fail with confusing errors about universe levels or missing instances. Fix: run `lake build` in the workspace directory to rebuild with the current lean version.

### Issue: Large log files
The server logs all LLM requests and responses to the log file. With active proof search, logs can grow to hundreds of megabytes per day. Use log rotation or set `level = "WARNING"` in config.toml to reduce verbosity.

### Issue: SQLite contention
When multiple proof jobs try to write to the database simultaneously, SQLite's file-level locking can cause delays. This is mitigated by `aiosqlite` which serializes writes within the async event loop, but very high concurrency (50+ simultaneous jobs) may cause slowdowns. Increase `max_concurrent_compiles` to process more jobs faster and reduce queue buildup.

### Issue: LLM context window overflow
If the Lean error for a large theorem is very long (thousands of characters), it may overflow the LLM's context window. The server truncates error context to a reasonable size (approximately 2000 characters) before sending to the LLM. If your theorem requires more context, split it into smaller lemmas.

### Issue: Workspace disk space
Each proof attempt creates a temporary `.lean` file in the workspace directory. With many failed attempts, these can accumulate. The server cleans up files after each attempt, but if the process crashes, orphaned files may remain. Run a periodic cleanup of `workspace/*.lean` files older than 24 hours.

## Advanced Configuration

### Custom LLM Endpoints
The OpenAI-compatible tier works with any provider that exposes the `/v1/chat/completions` API:
- **DeepSeek**: `base_url = "https://api.deepseek.com/v1"`, `model = "deepseek-chat"`
- **Together AI**: `base_url = "https://api.together.xyz/v1"`, `model = "deepseek-ai/DeepSeek-Coder-V2-Instruct"`
- **OpenAI**: `base_url = "https://api.openai.com/v1"`, `model = "gpt-4o-mini"`
- **Local vLLM**: `base_url = "http://localhost:8000/v1"`, `model = "deepseek-coder-v2-lite-instruct"`

### Adjusting Subagent Parallelism
The `parallel_agents` setting controls how many subagents work on a single theorem simultaneously:
- **1**: Conservative, lowest resource usage, slowest completion. Use when you need to minimize API costs.
- **2-3**: Balanced (default 3). Good for most use cases with Ollama (which is free).
- **5-8**: Aggressive. Use when speed is critical and you have sufficient LLM throughput. Only makes sense with fast local models.

Each additional subagent independently proposes and tests proofs. They do not coordinate or share progress (beyond the first to succeed winning). Adding more agents increases the chance of finding a proof quickly but does not increase the quality of any individual attempt.

### LLM Temperature Tuning
The `temperature` parameter controls randomness in LLM output:
- **0.1-0.2**: Very deterministic, repeats similar proof strategies. Use when the theorem is similar to ones that have worked before.
- **0.3-0.5**: Balanced (recommended default 0.3). Good exploration with reasonable coherence.
- **0.6-1.0**: High exploration, diverse proof attempts. Use for novel theorems where standard strategies are failing. May produce less coherent code.

## Performance Optimization Tips

1. **Use Ollama with a good model**: `deepseek-coder-v2:latest` (16B parameters) provides the best balance of speed and quality for local proof search. The 7B models are faster but significantly less capable. The 33B+ models are too slow for practical interactive use.

2. **Prefer lower tier (Ollama) for initial attempts**: Most simple theorems are provable with Ollama alone. Reserve API-based tiers for hard theorems where Ollama has failed.

3. **Batch similar theorems**: Submit structurally similar theorems together. The LLM's context from previous proofs may help with subsequent ones (through the server's prompt caching if supported by the provider).

4. **Use the proof_attempt parameter**: A good starting sketch can reduce proof search time by 50-80%. Even a single line like `induction a` or `simp` gives the LLM a strong hint about the proof strategy.

5. **Monitor compile timeout**: If the default 30s timeout causes frequent "Lean compile timeout" errors, increase it in config.toml. Some theorems with heavy imports genuinely need 60-120 seconds to compile.

## Compatibility

leanforge-mcp is compatible with:
- Lean 4 (any version supported by `lean --stdin`)
- Mathlib4 (any version compatible with the installed Lean)
- Python 3.11+
- Windows, Linux, and macOS (Windows is the primary development target)
- Ollama, OpenAI API, and Anthropic API (any version with chat completions endpoint)

Not compatible with:
- Lean 3 (different syntax, different compiler)
- Coq, Isabelle, Agda, or any other theorem prover
- Python < 3.11 (requires tomllib)
- Proof assistants without a command-line compiler

## SQLite Database Schema

The `jobs.db` SQLite database has two main tables:

**jobs table**: Stores all proof job metadata.
- `job_id` (TEXT, UUID) -- primary key
- `status` (TEXT) -- queued/running/completed/failed/cancelled/interrupted
- `theorem_statement` (TEXT) -- the original theorem text
- `proof_attempt` (TEXT) -- optional starting proof
- `result` (TEXT, JSON) -- completed result or error
- `created_at` (TEXT, ISO8601) -- creation timestamp
- `updated_at` (TEXT, ISO8601) -- last update timestamp

**attempts table**: Records each subagent attempt.
- `id` (INTEGER) -- auto-increment primary key
- `job_id` (TEXT, UUID) -- foreign key to jobs
- `step_number` (INTEGER) -- attempt number within this job
- `llm_tier` (TEXT) -- which LLM tier was used
- `compile_success` (INTEGER) -- 0 or 1
- `error_message` (TEXT) -- compiler error if failed
- `proposed_code` (TEXT) -- the code that was compiled
- `created_at` (TEXT, ISO8601) -- timestamp

## Quick Reference: Common Theorem Patterns

When submitting theorems, use these common patterns for best results with the LLM:

```lean
-- Simple equation
theorem name (params) : expression1 = expression2 := by
  sorry

-- Inequality
theorem name (params) : expression1 <= expression2 := by
  sorry

-- Implication
theorem name (params) (h : condition) : conclusion := by
  sorry

-- Universal quantification
theorem name (params) : forall (x : Nat), property x := by
  intro x
  sorry

-- Existential quantification
theorem name (params) : exists (x : Nat), property x := by
  refine ⟨?_, ?_⟩
  sorry

-- Conditional with induction
theorem name (n : Nat) (h : condition n) : property n := by
  induction n with
  | zero => sorry
  | succ n ih => sorry
```

## Performance Tuning for Different Hardware

### Low-end (CPU-only, no GPU, 8GB RAM)
- Use only Ollama tier with a 7B model
- Set `max_concurrent_compiles = 2`
- Set `parallel_agents = 2`
- Expect: 2-5 minutes per simple theorem, Ollama-only

### Mid-range (CPU + 16GB RAM, Ollama with GPU)
- Use Ollama with deepseek-coder-v2:latest (16B)
- Set `max_concurrent_compiles = 4`
- Set `parallel_agents = 3`
- Expect: 30s-5min per simple theorem, 15GB RAM peak

### High-end (GPU with 24GB VRAM, fast API access)
- Use Ollama on GPU (large model) + OpenAI-compat + Anthropic
- Set `max_concurrent_compiles = 8`
- Set `parallel_agents = 5`
- Expect: 15s-2min per simple theorem, standard theorems complete on Ollama

## Safety

- The server automatically rejects any LLM-generated change to the theorem statement. Only the proof body (after `:=` or `by`) may be modified. This is verified by cryptographic hashing before and after every edit.
- API keys for LLM providers are stored in `config.toml`, which is gitignored. Never commit this file.
- Temporary workspace files in `workspace/` are cleaned up when each job completes or fails.
- The Lean compiler runs as a subprocess with no shell access and a bounded timeout. It cannot affect the host system.
- Do not share your `config.toml` -- it contains API keys and local filesystem paths.

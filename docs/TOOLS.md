# Tool Reference

All tools return structured JSON. `submit_theorem` and `submit_lean_file` return
immediately -- proof search runs in the background. Use `get_proof_status` to poll.

---

## submit_theorem

Submit a theorem statement for proof search.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `statement` | string | required | The Lean 4 proposition (the part after the colon). Must be valid Lean 4 syntax -- `∀ n : ℕ, ...`, not English. |
| `lean_stub` | string | null | Optional: full `.lean` file with sorry. If omitted, the server wraps `statement` in a minimal stub with `import Mathlib`. |
| `hints` | string | null | Relevant Mathlib theorem names or strategy hints to prepend to the file. |
| `tier` | int 1-3 | `1` | Starting LLM tier. Agents auto-escalate regardless. |
| `parallel_agents` | int 1-16 | `4` | Number of independent subagents. |
| `max_turns` | int 1-1000 | `100` | Turn budget per subagent. |

**Returns:**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "tier": 1,
  "parallel_agents": 4,
  "max_turns": 100,
  "message": "Job abc-123 started. Poll get_proof_status('abc-123') every 10-30s."
}
```

**Example:**
```
submit_theorem(
  statement="∀ n : ℕ, 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1)",
  hints="Finset.sum_range_succ"
)
```

---

## submit_lean_file

Submit a complete `.lean` file with sorry placeholders. For MiniF2F stubs,
AlphaProof Nexus problem files, or anything already formalized.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lean_source` | string | required | Full Lean 4 source containing at least one `sorry`. |
| `description` | string | `""` | Display label for the job. |
| `tier` | int 1-3 | `1` | Starting LLM tier. |
| `parallel_agents` | int 1-16 | `4` | -- |
| `max_turns` | int 1-1000 | `100` | -- |

Returns the same structure as `submit_theorem`.

---

## get_proof_status

Poll a job. Call every 10-30 seconds while status is `running`.

**Parameters:** `job_id: string`

**Returns (running):**
```json
{
  "job_id": "uuid",
  "status": "running",
  "description": "...",
  "latest_turn": 12,
  "latest_compiler_output": "error: tactic 'simp' failed...",
  "latest_model": "deepseek-prover-v2:7b"
}
```

**Returns (complete):**
```json
{
  "job_id": "uuid",
  "status": "complete",
  "description": "...",
  "proof": "import Mathlib\n\ntheorem sum_formula ... := by\n  induction n with\n  ..."
}
```

**Possible statuses:** `queued`, `running`, `complete`, `failed`, `cancelled`, `interrupted`

---

## list_attempts

Inspect the proof attempt trajectory for a job.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `job_id` | string | required | -- |
| `agent_index` | int | null | Filter to a specific subagent. |
| `last_n` | int 1-100 | `10` | Return the N most recent attempts. |

**Returns:**
```json
{
  "job_id": "uuid",
  "count": 3,
  "attempts": [
    {
      "agent_index": 0,
      "turn": 12,
      "success": false,
      "llm_model": "deepseek-prover-v2:7b",
      "compiler_output": "error: unknown identifier 'Nat.add_zero'..."
    }
  ]
}
```

Compiler output is truncated to 400 chars. Special values for non-compile turns:
`STUCK`, `PARSE_ERROR`, `EDIT_NOT_FOUND`, `LLM_ERROR: <message>`.

---

## list_jobs

List all jobs.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status_filter` | string | null | Filter by status: `running`, `complete`, `failed`, etc. |
| `limit` | int 1-100 | `20` | -- |

**Returns:**
```json
{
  "count": 2,
  "jobs": [
    {
      "job_id": "uuid",
      "status": "complete",
      "description": "sum formula",
      "created_at": "2026-06-24T19:00:00+00:00"
    }
  ]
}
```

---

## validate_lean

Compile arbitrary Lean 4 source directly. No job created, no LLM involved.
Use to test a proof manually or check whether a formulation is syntactically valid
before submitting it for proof search.

**Parameters:** `lean_source: string`

**Returns:**
```json
{
  "success": true,
  "proven": true,
  "has_sorry": false,
  "errors": [],
  "warnings": []
}
```

`proven` is true only when `success=true` AND `has_sorry=false`.

**Example:**
```
validate_lean("import Mathlib\nexample : 1 = 1 := rfl\n")
→ {"proven": true, "has_sorry": false, "errors": [], "warnings": []}

validate_lean("import Mathlib\ntheorem foo : 1 = 2 := by\n  sorry\n")
→ {"proven": false, "has_sorry": true, "errors": [], "warnings": ["declaration uses 'sorry'"]}
```

---

## cancel_job

Cancel a running proof job.

**Parameters:** `job_id: string`

**Returns:**
```json
{"job_id": "uuid", "status": "cancelled"}
```

Or if the job isn't live in the current process:
```json
{"job_id": "uuid", "status": "running", "message": "No live task -- job is already running."}
```

Note: cross-process cancel (MCP server vs webapp backend) is not yet implemented
(P1-6 in the assessment). Cancel from the same process that started the job.

---

## get_mathlib_search

Search Mathlib for theorems matching a natural language query.
Wraps the [LeanSearch API](https://leansearch.net).

**Parameters:** `query: string`

**Returns:** List of matching theorem names with their signatures.

**Example:**
```
get_mathlib_search("sum of arithmetic sequence")
→ ["Finset.sum_range_succ", "Finset.sum_range_id", ...]
```

Use the returned names as `hints` in `submit_theorem` or to guide the agent when
it is stuck.

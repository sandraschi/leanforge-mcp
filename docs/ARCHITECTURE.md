# Architecture

## Overview

leanforge-mcp implements Agent A from the AlphaProof Nexus paper (arXiv:2605.22763) as an MCP server. This is the simplest agent configuration -- N independent subagents, no shared state, compiler feedback as the only oracle -- and it is sufficient to solve research-level problems given enough compute budget.

## The proof loop in detail

```
Theorem statement (Lean 4 file with sorry)
         │
         ├─────────────────────────────────────┐
         │  Subagent 0                          │  Subagent N-1
         │                                      │
         │  turn 0:                             │  (independent, same start)
         │    prompt = [file + system_prompt]   │
         │    edit = LLM(prompt)                │
         │    file' = apply(file, edit)         │
         │    result = lean_compile(file')      │
         │    if proven: DONE ──────────────────┼──→ cancel others
         │    else: last_error = result.errors  │
         │  turn 1: ...                         │
         │  turn N: budget exhausted            │
         └──────────────────────────────────────┘
```

Key design decisions:

**No shared state between subagents.** They diverge from the same start and explore different proof paths. Diversity of search is the point.

**The compiler is the only truth.** Wrong proofs fail to compile. This eliminates hallucination at the proof level.

**`sorry` as the contract boundary.** Agents fill `sorry` but never touch the theorem statement. leanforge-mcp enforces this by hashing the statement before and after each edit.

## LLM prompt structure

Each turn sends:

```
[SYSTEM]
You are a Lean 4 theorem prover working with Mathlib.
You will be shown a Lean 4 file with `sorry` placeholders.
Replace every `sorry` with a valid proof.

RULES:
1. NEVER modify the theorem statement
2. You may add helper lemmas before the theorem
3. Use Mathlib tactics: simp, ring, linarith, omega, exact, apply, induction, rw
4. If stuck, try a completely different approach
5. Output ONLY a search-replace block:
   <<<REPLACE
   [exact text to replace]
   ===
   [replacement]
   REPLACE>>>

[USER]
Current file:
```lean
<current lean source>
```

Lean compiler error from last attempt:
```
<compiler error>
```
```

## Tier escalation

Each subagent tracks its own tier. Escalation is irreversible within a job:

```
turns 0-19:   tier_1 (Ollama local, free)
turns 20-59:  tier_2 (DeepSeek V4 Flash API)
turns 60+:    tier_3 (Claude Fable 5 API)
```

## Job lifecycle

```
QUEUED → RUNNING → COMPLETE
                 → FAILED    (all subagents exhausted budget)
                 → CANCELLED (explicit cancel_job)
                 → INTERRUPTED (process crash, resumable)
```

## SQLite schema

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    created_at TEXT,
    status TEXT,
    lean_source TEXT,   -- original file with sorry
    proof TEXT,         -- completed file if COMPLETE, else NULL
    tier_config TEXT,   -- JSON snapshot of tier settings used
    parallel_agents INTEGER,
    max_turns INTEGER
);

CREATE TABLE attempts (
    id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES jobs(id),
    agent_index INTEGER,
    turn INTEGER,
    lean_source TEXT,       -- file state at this turn
    compiler_output TEXT,
    llm_model TEXT,
    success INTEGER         -- 1 if proven, 0 otherwise
);
```

## Lean workspace -- one-time setup

A bare `lean` invocation cannot resolve `import Mathlib`. Every non-trivial Lean
file must live inside a Lake project with Mathlib as a dependency and its precompiled
oleans on the search path. leanforge-mcp runs `lake env lean <file>` inside a
persistent Lake project workspace.

**Create this workspace ONCE:**

```powershell
cd D:\Dev\repos\leanforge-mcp\workspace
lake new leanforge_workspace math     # Lake project with Mathlib dep
cd leanforge_workspace
lake exe cache get                    # downloads precompiled Mathlib (~4GB)
lake build                            # verifies everything resolves
```

After that, every job writes a temp `.lean` file into this dir and compiles with
`lake env lean <tmpfile>`. Mathlib resolves because the process inherits the Lake
project environment. `LeanClient.ensure_workspace()` validates this at startup with
a trivial smoke compile.

## The compile invocation

## Mathlib search

`get_mathlib_search` wraps the [LeanSearch API](https://leansearch.net) -- natural language → Mathlib theorem names. Useful when stuck: find the right lemma name, pass as a hint to the next submit.

## Performance on Goliath

| Problem tier | Typical turns | Wall time | Cost (tier 1) |
|---|---|---|---|
| Sanity (arithmetic) | 1-3 | 5-15s | $0 local |
| MiniF2F easy | 5-20 | 1-3 min | $0 local |
| MiniF2F hard | 20-80 | 5-20 min | ~$0.01 tier 2 |
| PutnamBench | 50-200 | 20-60 min | ~$0.05-0.20 tier 2/3 |
| Open Erdős problem | 100-1000+ | hours | ~$1-10 tier 3 |

With 4 parallel agents on 24 cores, wall time scales roughly as 1/N.

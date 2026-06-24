# leanforge-mcp

[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.2%2B-blueviolet)](https://github.com/jlowin/fastmcp)
[![Lean 4](https://img.shields.io/badge/Lean-4-orange?logo=lean&logoColor=white)](https://lean-lang.org/)
[![Mathlib](https://img.shields.io/badge/Mathlib-4-orange)](https://leanprover-community.github.io/mathlib4_docs/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status: Phase A](https://img.shields.io/badge/status-Phase%20A%20complete-yellow)](docs/ASSESSMENT_2026-06-24.md)
[![AlphaProof Nexus](https://img.shields.io/badge/inspired%20by-AlphaProof%20Nexus-informational)](https://arxiv.org/abs/2605.22763)

An MCP server that exposes a **formal mathematical proof search pipeline** to any MCP-capable agent or IDE. Feed it a theorem statement in Lean 4; it runs an agentic compile-feedback loop — LLM proposes, Lean compiler judges — until a machine-verified proof emerges or the budget runs out.

Inspired by DeepMind's [AlphaProof Nexus](https://arxiv.org/abs/2605.22763) (May 2026). Architecture is deliberately minimal: Agent A from that paper — independent subagents, no shared state, compiler feedback as the only oracle.

---

## Why formal proofs?

A natural-language proof can be wrong in subtle ways that slip past peer review for years. A Lean proof cannot. The compiler checks every tactic step against the axioms of dependent type theory. If it compiles without `sorry`, it is correct — no ambiguity, no reviewer needed.

The core insight from AlphaProof Nexus: LLMs are now capable enough that the compile-feedback loop alone is sufficient for research-level mathematics. You don't need a specialised theorem prover model. You need:

$$\text{LLM} + \text{Lean compiler} + \text{agentic loop} = \text{machine-verified proof}$$

The longer the model can sustain search — tolerating many failed attempts, retrying different strategies — the harder the problems it can crack. This is exactly what an MCP server with long-running async job semantics enables.

---

## What leanforge-mcp does

```
┌─────────────────────────────────────────────────────────┐
│  MCP client (Claude Desktop / Cursor / any agent)       │
│                                                         │
│  submit_theorem(statement, hints?, budget?)             │
│         │                                               │
│         ▼                                               │
│  ┌─────────────────────────────────────────────┐        │
│  │            leanforge-mcp server             │        │
│  │                                             │        │
│  │  Job queue → N parallel subagents           │        │
│  │                                             │        │
│  │  Each subagent:                             │        │
│  │    loop:                                    │        │
│  │      LLM: propose edit to .lean file        │        │
│  │      lean: compile → error/success          │        │
│  │      if sorry-free: done ✓                  │        │
│  │      else: feed error back to LLM           │        │
│  │                                             │        │
│  │  get_proof_status(job_id)                   │        │
│  │  list_attempts(job_id)                      │        │
│  │  cancel_job(job_id)                         │        │
│  └─────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

**MCP tools exposed:**

| Tool | Description |
|------|-------------|
| `submit_theorem` | Submit a theorem for proof search. Returns a job ID immediately. |
| `get_proof_status` | Poll job status. Returns proof if found, attempt log if still running. |
| `list_attempts` | Inspect all proof attempts for a job with compiler feedback history. |
| `cancel_job` | Stop a running job and free resources. |
| `list_jobs` | List all jobs (running, complete, failed) with summaries. |
| `submit_lean_file` | Submit a full `.lean` file directly, bypassing statement assembly. |
| `validate_lean` | Run the Lean compiler on arbitrary code and return output. Raw tool. |
| `get_mathlib_search` | Search Mathlib for theorems matching a natural language query. |

---

## The math

Given $n$ points in the plane, let $f(n)$ denote the maximum number of unit-distance pairs. Erdős conjectured in 1946 that $f(n) = O(n^{1+\varepsilon})$ for any $\varepsilon > 0$. In May 2026, AI systems disproved this by constructing configurations with

$$f(n) \geq n^{1+\delta}$$

for a fixed $\delta > 0$, via algebraic number theory over extensions of the Gaussian integers $\mathbb{Z}[i]$.

leanforge-mcp can attempt problems like this. It cannot guarantee success — hard open problems may exceed any budget — but it provides the scaffolding for systematic search and preserves every failed attempt for human inspection.

---

## Architecture

### The proof loop

```python
# Pseudocode — actual implementation in src/core/agent.py

async def subagent(lean_file, llm, lean, max_turns):
    for turn in range(max_turns):
        edit = await llm.propose_edit(lean_file, last_error)
        lean_file = apply_edit(lean_file, edit)
        result = await lean.compile(lean_file)
        if result.success and not result.has_sorry:
            return ProofFound(lean_file)
        last_error = result.error_message
    return ProofNotFound(attempts=history)
```

### Parallelism

N subagents run concurrently (default: 4). All start from the same initial file. First to find a valid proof wins; others are cancelled. On Goliath (24 cores, 64GB RAM), 8–16 parallel agents is practical.

### LLM tiers

```toml
[llm]
tier_1 = "deepseek-prover-v2-7b"        # local Ollama, free
tier_2 = "deepseek/deepseek-v4-flash"   # API, cheap (~$0.001/attempt)
tier_3 = "claude-fable-5"               # API, $50/M output, hard problems only

escalate_to_tier2_after = 20            # turns
escalate_to_tier3_after = 60
```

### Input format

```lean
import Mathlib

theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  sorry
```

The agent fills the `sorry`. It cannot change the theorem statement.

### Output format

```lean
import Mathlib

theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ]
    ring_nf
    linarith
```

---

## Quickstart

### Prerequisites

- Python 3.11+
- [Lean 4 via elan](https://lean-lang.org/lean4/doc/setup.html): `winget install leanprover.elan`
- Mathlib cache: `lake exe cache get` (one-time, ~4GB)
- Ollama with `deepseek-prover-v2:7b` for local tier-1

### Install

```powershell
git clone https://github.com/sandraschi/leanforge-mcp
cd leanforge-mcp
uv sync
```

### Configure

```powershell
Copy-Item config.example.toml config.toml
# Edit config.toml: Lean path, API keys, parallel agent count
```

### Run

```powershell
.\start.ps1
```

### Add to Claude Desktop

```json
{
  "mcpServers": {
    "leanforge": {
      "command": "uv",
      "args": ["--directory", "D:\\Dev\\repos\\leanforge-mcp", "run", "python", "-m", "leanforge_mcp"],
      "env": {
        "ANTHROPIC_API_KEY": "...",
        "DEEPSEEK_API_KEY": "..."
      }
    }
  }
}
```

---

## Training wheels — problems to start with

**Tier 0 — sanity:** Simple arithmetic. Should solve in 1–3 turns with any model.

**Tier 1 — MiniF2F:** 488 pre-formalized olympiad problems. Clone [leanprover-community/miniF2F](https://github.com/leanprover-community/miniF2F) and feed files directly via `submit_lean_file`.

**Tier 2 — PutnamBench:** 658 Putnam competition problems. DeepSeek-Prover-V2 671B solves 49/658 — a realistic baseline.

**Tier 3 — AlphaProof Nexus unsolved set:** [google-deepmind/alphaproof-nexus-results](https://github.com/google-deepmind/alphaproof-nexus-results) includes Lean formalizations of all 353 Erdős problems attempted, including the 344 that remain open. Pre-formalized, ready to submit.

**Tier 4 — erdosproblems.com:** ~900 open problems. Requires manual Lean formalization of the statement — the hard part is stating the theorem correctly before proof search begins.

---

## Project status

**Phase 0 — scaffold** *(current)*
- [x] Repo structure, all docs, config schema
- [x] `lean_client.py` — async Lean compiler wrapper
- [x] `agent.py` — core proof loop, parallelism, tier escalation
- [x] MCP tool stubs with correct signatures
- [ ] `config.py` — TOML loader
- [ ] `llm_client.py` — multi-provider async client
- [ ] `job_manager.py` — SQLite job queue

**Phase 1 — working pipeline**
- [ ] Wire all components end-to-end
- [ ] `validate_lean` tool working
- [ ] MiniF2F sanity pass (5 easy problems)

**Phase 2 — research features**
- [ ] EVOLVE-BLOCK marker support
- [ ] Attempt Elo-style ranking
- [ ] AlphaProof Nexus unsolved batch runner
- [ ] Overnight job scheduler

**Phase 3 — fleet integration**
- [ ] `meta_mcp` orchestration hooks
- [ ] `advanced-memory-mcp` result persistence
- [ ] `cursor_inbox` drop for async results

---

## References

- [AlphaProof Nexus paper](https://arxiv.org/abs/2605.22763) — DeepMind, May 2026
- [AlphaProof Nexus results + unsolved stubs](https://github.com/google-deepmind/alphaproof-nexus-results)
- [DeepSeek-Prover-V2](https://arxiv.org/abs/2504.21801) — open-weight Lean 4 prover
- [Mathematics in Lean](https://leanprover-community.github.io/mathematics_in_lean/) — primary learning resource
- [Mathlib4](https://github.com/leanprover-community/mathlib4) — 150k+ formalized theorems
- [LeanSearch](https://leansearch.net) — natural language Mathlib search
- [erdosproblems.com](https://www.erdosproblems.com) — open Erdős problem catalog
- [MiniF2F](https://github.com/leanprover-community/miniF2F) — olympiad benchmark
- [Natural Number Game](https://adam.math.hhu.de/) — browser-based Lean 4 intro

---

## License

MIT

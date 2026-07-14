# leanforge-mcp

[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4%2B-blueviolet)](https://github.com/jlowin/fastmcp)
[![Lean 4](https://img.shields.io/badge/Lean-4-orange)](https://lean-lang.org/)
[![Mathlib](https://img.shields.io/badge/Mathlib-4-orange)](https://leanprover-community.github.io/mathlib4_docs/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status: Phase B complete](https://img.shields.io/badge/status-Phase%20B%20complete-brightgreen)](docs/ASSESSMENT_2026-06-24.md)
[![AlphaProof Nexus](https://img.shields.io/badge/inspired%20by-AlphaProof%20Nexus-informational)](https://arxiv.org/abs/2605.22763)

MCP server for AI-driven formal proof search in Lean 4. Submit a theorem with `sorry`; get back a machine-verified proof. Implements Agent A from [AlphaProof Nexus](https://arxiv.org/abs/2605.22763) (DeepMind, May 2026).

**Stack:** Python 3.12+ . FastMCP 3.4+ . FastAPI . React/Vite . Tailwind . Lean 4 / Mathlib

---

## Table of Contents

- [What it does](#what-it-does)
- [Quick Install](#quick-install)
- [What You Can Do](#what-you-can-do)
- [Tools](#tools)
- [Requirements](#requirements)
- [Documentation](#documentation)
- [Status](#status)
- [License](#license)

---

## What it does

Feed it a Lean 4 theorem with a `sorry` placeholder. It runs N parallel agents in a loop: the LLM proposes a proof edit, the Lean compiler judges it, errors feed back to the LLM. First agent to produce a sorry-free compile wins.

```lean
-- Input
theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  sorry

-- Output (machine-verified)
theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ n ih => rw [Finset.sum_range_succ]; ring_nf; linarith
```

The compiler is the only oracle -- if it compiles without `sorry`, the proof is correct.

---

## Quick Install

```powershell
git clone https://github.com/sandraschi/leanforge-mcp
cd leanforge-mcp
uv sync
Copy-Item config.example.toml config.toml
```

Then add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "leanforge": {
      "command": "uv",
      "args": ["--directory", "C:\\path\\to\\leanforge-mcp", "run", "python", "-m", "leanforge_mcp"],
      "env": { "DEEPSEEK_API_KEY": "...", "ANTHROPIC_API_KEY": "..." }
    }
  }
}
```

See [INSTALL.md](INSTALL.md) for the Lean + Mathlib workspace setup (~4GB, one-time -- already provisioned and verified on Goliath as of 2026-07-09).

---

## What You Can Do

```
"Prove that the sum of the first n natural numbers is n*(n+1)/2"

"Submit this MiniF2F problem and check back in 10 minutes"

"Show me all the proof attempts for job abc-123 -- why is it stuck?"

"Run validate_lean on this tactic proof to see if it compiles"
```

---

## Tools

| Tool | Description |
|------|-------------|
| `submit_theorem` | Submit a theorem statement → job ID (async) |
| `submit_lean_file` | Submit a full `.lean` file with sorry placeholders |
| `get_proof_status` | Poll job status; returns proof when complete |
| `list_attempts` | Inspect the attempt trajectory per agent/turn |
| `list_jobs` | List all jobs with status summary |
| `validate_lean` | Raw Lean 4 compile -- no job tracking |
| `cancel_job` | Cancel a running job |
| `get_mathlib_search` | Natural language search over Mathlib theorems |

---

## Requirements

- Python 3.11+
- [Lean 4 via elan](https://lean-lang.org/lean4/doc/setup.html) (`winget install leanprover.elan`)
- Mathlib workspace with cached oleans (~4GB, one-time setup -- see [INSTALL.md](INSTALL.md))
- Ollama with `deepseek-prover-v2:7b` for tier-1 (local, free)
- DeepSeek or Anthropic API key for tier-2/3 (optional)

---

## Documentation

| Doc | Contents |
|-----|----------|
| [INSTALL.md](INSTALL.md) | Prerequisites, Lean workspace setup, Claude Desktop config |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | All config options and environment variables |
| [docs/TOOLS.md](docs/TOOLS.md) | Full tool reference with parameters and examples |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Proof loop, tier escalation, job lifecycle, SQLite schema |
| [docs/LEAN.md](docs/LEAN.md) | Lean 4 language reference, tactic guide, bibliography, link collection |
| [docs/LEAN_PRIMER.md](docs/LEAN_PRIMER.md) | Quick Lean 4 intro for engineers (short version) |
| [docs/ALPHAPROOF_NEXUS.md](docs/ALPHAPROOF_NEXUS.md) | The technique: AlphaProof Nexus paper explained |
| [docs/COVERAGE_GAP.md](docs/COVERAGE_GAP.md) | Why DeepMind got MSM coverage and a startup wouldn't |
| [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md) | MiniF2F, PutnamBench, Erdős results |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Contributing, dev setup, test commands |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common errors and fixes |

---

## Roadmap

| Phase | What | Status |
|-------|------|--------|
| **A** | Core loop: LLM proposes, Lean judges, error feeds back | Done |
| **B** | Correctness hardening, edge case handling, timeout tuning | **Done (2026-07-09)** -- tamper guard closed against default-arg truncation and a decoy-duplicate attack, cross-process job ownership/cancellation fixed, stateless-prompting mitigations added. 56/56 tests passing on real hardware. See [docs/ASSESSMENT_2026-06-24.md](docs/ASSESSMENT_2026-06-24.md) |
| **C** | **Performance and safety**: REPL worker pool (compile-time is the real bottleneck), LLM timeout/retry, token/cost accounting (hard gate before any batch run) | In progress -- see [TODO.md](TODO.md) |
| **D** | **Multi-agent parallel scheduling** (Agent B from paper) -- run N loops in parallel, first to finish wins | Planned |
| **E** | **Self-critique step** -- LLM reviews its own proof before compile, catches obvious errors early | Planned |
| **F** | **Webapp proof explorer** -- interactive tree view of attempted proof paths, live tactic streaming | Planned |
| **G** | **Premise selection** -- before generating tactics, search Mathlib for relevant lemmas | Planned |
| **H** | **Cumulative context windowing** -- smart summarization of long error chains instead of blind concatenation | Planned |
| **I** | **Benchmark dashboard** -- webapp page tracking MiniF2F, PutnamBench, Erdős results per model/config | Stretch |
| **J** | **Human-in-the-loop** -- when the agent is stuck, pause and surface the current state for a human hint | Stretch |
| **K** | **Proof caching** -- deduplicate sub-proofs so repeated lemmas compile instantly | Stretch |

### What each phase enables

**A + B** let you submit a theorem and get a proof back on the other end.
It works, it's useful, but it's single-threaded, pays a full compile per
turn, and has no spend controls -- Phase C closes those gaps.

**D** changes the game: N parallel agents means wall-clock time drops from
"however long one LLM takes" to "however long the fastest of N LLMs takes."
For hard theorems where the LLM wanders into dead ends, this is the
difference between 5 minutes and 30 seconds.

**E** prevents the LLM from wasting compiles on obviously wrong tactics.
Cheap to add (one extra LLM call per attempt) and the paper shows it
improves solve rate by ~15 percentage points on Agent A alone.

**F** is the user-facing payoff: instead of staring at "status: running"
and polling, you watch the LLM try tactics in real time, see which paths
it abandoned, and understand why it eventually succeeded or failed.

**G** addresses the most common failure mode: the LLM writes a correct
tactic for a lemma that doesn't exist in the current context. Premise
selection (a small retrieval step before tactic generation) cuts this
dramatically.

**H** is invisible but critical: as the LLM accumulates 10+ failed
attempts, the error context grows past the model's window. Smart
summarization keeps relevant signal without drowning the LLM in noise.

Full gap analysis: [docs/ASSESSMENT_2026-06-24.md](docs/ASSESSMENT_2026-06-24.md)

---

## License

MIT

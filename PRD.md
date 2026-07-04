# PRD -- leanforge-mcp

**Product Requirements Document**
**Version:** 0.1
**Date:** 2026-06-10
**Owner:** sandraschi
**Status:** In development -- Phase 1 (smoke test pending)

---

## 1. Problem

Formal theorem proving in Lean 4 is powerful but slow for a solo researcher.
The bottleneck is not mathematical creativity -- it is the mechanical work of
translating a proof idea into valid Lean 4 tactic syntax, iterating against
compiler errors, and finding the right Mathlib lemma names.

LLMs are good at exactly this mechanical work, given a tight feedback loop.
DeepMind's AlphaProof Nexus demonstrated in May 2026 that an agentic loop --
LLM proposes, Lean compiler judges, errors feed back -- is sufficient to solve
research-level open problems (9 of 353 Erdős problems, 44 OEIS conjectures)
at a cost of a few hundred dollars per solved problem.

The problem: AlphaProof Nexus is not publicly available. The underlying
architecture (Agent A: independent subagents, compiler feedback loop) is simple
enough to reimplement. But no open tool exposes this as a usable interface for
an individual researcher.

---

## 2. Solution

leanforge-mcp is an MCP server that exposes formal proof search as a set of
tools accessible to any MCP-capable agent or IDE. The user submits a theorem;
the server runs the proof search pipeline and returns a machine-verified Lean 4
proof -- or an honest failure with the full search trajectory preserved for
inspection.

The name: a forge shapes raw material under repeated impact. Proof search is
exactly that -- iterative hammering of a sorry placeholder until the compiler
accepts the result.

---

## 3. Users

**Primary:** Sandra (owner). Research tool for attempting open mathematical
problems, primarily from the Erdős problem catalog and AlphaProof Nexus unsolved
set. Running on Goliath (24-core, 64GB, RTX 4090).

**Secondary:** Any researcher with a Lean 4 + Mathlib setup who wants to point
an LLM at a formalized theorem stub and let it search for a proof. The MCP
interface means this works from Claude Desktop, Cursor, or any agent that
supports MCP tools.

**Non-users:** This is not a general-purpose AI coding assistant. It does one
thing: formal proof search for Lean 4. It has no web interface and no multi-user
support.

---

## 4. Goals

**Must have (v0.1)**
- Correct `lake env lean` compile pipeline -- `import Mathlib` resolves
- `submit_theorem` → background job → `get_proof_status` polling flow
- All attempts persisted to SQLite for inspection after the fact
- MiniF2F sanity pass (5 easy problems solved by tier-1 local model)
- Works from Claude Desktop as a registered MCP server

**Should have (v0.2)**
- Full MiniF2F benchmark run with documented success rate
- PutnamBench baseline (target: match DeepSeek-Prover-V2 7B at 7.4%)
- Overnight batch runner for AlphaProof Nexus unsolved set
- EVOLVE-BLOCK marker support for constrained proof search

**Nice to have (v0.3+)**
- Population-based agent (Agent D) with shared proof sketch population
- Elo-ranked partial proofs seeding next-generation subagents
- Lean4checker secondary verification for novel results
- erdosproblems.com scraper + Fable 5 auto-formalizer

**Non-goals**
- Web UI (not needed for solo researcher MCP tool)
- Multi-user support or auth
- Automatic Lean installation (too risky to run silently, 4GB download)
- Support for proof assistants other than Lean 4

---

## 5. Architecture summary

```
Claude Desktop / Cursor
        |
        | MCP (stdio)
        v
  leanforge-mcp (FastMCP 3.2)
        |
        | lifespan context
        v
     Runner
    /      \
JobManager  LeanClient
(SQLite)    (lake env lean)
        |
        | asyncio.Task per job
        v
  run_parallel_agents()
     [agent_0] [agent_1] ... [agent_N]
        |
        | loop
        v
  LLMClient.complete()  <-- tier 1/2/3
        |
        v
  LeanClient.compile()
        |
        v
  compiler output --> feedback --> LLMClient
        |
        v
  sorry-free? --> ProofFound --> JobManager.set_complete()
```

**Key design decisions:**
- `lake env lean <file>` inside a persistent Mathlib workspace (not `lean --stdin`)
- Compiler output (not source regex) for sorry detection
- Full multi-line theorem signature hashing for tamper detection
- FastMCP `lifespan=` context manager -- single event loop, no globals
- SQLite for persistence -- single user, no external service dependency
- Tier escalation irreversible per-subagent (cheap → expensive only)

---

## 6. LLM tier model

| Tier | Model | Provider | Cost | Use |
|------|-------|----------|------|-----|
| 1 | deepseek-prover-v2:7b | Ollama local | Free | Mechanical fill-in, simple lemmas |
| 2 | deepseek-v4-flash | DeepSeek API | ~$0.001/attempt | Complex strategy, stuck tier-1 |
| 3 | claude-fable-5 | Anthropic API | ~$0.05-1.00/session | Hard open problems, novel results |

Escalation triggers per subagent (configurable):
- Turn 20: tier 1 → tier 2
- Turn 60: tier 2 → tier 3

---

## 7. Success metrics

| Metric | Target | Status |
|--------|--------|--------|
| Smoke test passing | All 8 tests green | Pending |
| `validate_lean` in Claude Desktop | Returns `proven: true` for trivial input | Pending |
| MiniF2F easy (5 problems) | All 5 solved, tier 1 | Pending |
| MiniF2F overall | >= 40% | Pending |
| PutnamBench | >= 49/658 (7.4%) | Pending |
| Erdős unsolved set | Any novel result | Aspirational |

---

## 8. Risks

**Technical risks**

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `lake env lean` exit code unreliable | Medium | High | Smoke test catches; fix error detection in lean_client.py |
| FastMCP 3.x API mismatch (lifespan, mount) | Low | High | Smoke test catches import errors on startup |
| LLM tier-1 too weak for even MiniF2F easy | Low | Medium | Swap in Goedel-Prover-V2-8B as alternative local model |
| Mathlib cache stale after Lean update | Low | Medium | `lake exe cache get` + `lake build` again |
| Fable 5 classifier fires on proof search prompts | Low | Low | Proof tactics are not offensive content; unlikely |

**Operational risks**

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Overnight batch burns unexpected API spend | Medium | Medium | Token budget cap in overnight_batch.py |
| Lean workspace corrupted by interrupted write | Low | Low | Each job uses a new temp file; workspace itself not modified |

---

## 9. Open questions

1. Does `lake env lean` return non-zero exit code on tactic failures, or only
   via diagnostic output? (Answer comes from smoke test run.)

2. Does FastMCP 3.2 `mount()` with no prefix preserve original tool names, or
   does it apply the sub-server name as a prefix? (Answer comes from MCP
   Inspector check after `uv sync`.)

3. What is the actual sorry-detection string in the installed Lean version?
   `WARNING_SORRY = "declaration uses 'sorry'"` is the expected string but may
   vary. (Answer comes from smoke test run.)

4. Is DeepSeek-Prover-V2 7B still the best available 7B-scale Lean 4 prover,
   or have Goedel-Prover-V2-8B / Leanabell-Prover-V2-7B overtaken it at our
   use case (research-level problems, not just MiniF2F)? (Punt to Phase 2.)

---

## 10. Not in scope

- Lean 3 support
- Isabelle, Coq, or other proof assistants
- Natural language to formal theorem translation (only proof search, not
  formalization -- the user must provide a valid Lean stub with sorry)
- Distributed multi-machine proof search
- Any web frontend

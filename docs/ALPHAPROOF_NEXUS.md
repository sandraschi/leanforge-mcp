# AlphaProof Nexus -- the technique behind this server

This server implements **Agent A** from the DeepMind paper
[*AlphaProof Nexus: An Agentic System for Formal Proof*](https://arxiv.org/abs/2605.22763)
(May 2026). This doc explains the core loop in plain language, what each
component does, and where this server deviates from the paper.

## The core loop

Most theorem provers before AlphaProof Nexus worked in one direction: you
write the proof, the compiler tells you whether it's right. If it's wrong,
you figure out why and try again -- alone.

AlphaProof Nexus adds an LLM in the loop:

```
[User writes theorem with "sorry"] → [LLM proposes proof edit]
         ↑                                         │
         │                                    [Lean compiler judges]
         │                                         │
         └────── [Error message fed back] ←─── [Compile failed?]
                                                    │
                                                    ↓
                                             [Proof verified]
```

The LLM is the proof assistant now. The human writes the theorem and the
intent. The LLM proposes tactic sequences. Lean compiles them. If Lean
rejects the proof, the error message becomes part of the prompt for the
next LLM proposal. This repeats until the proof compiles or a budget is
exhausted.

## Agent A (what we implement)

The paper defines three agents with escalating capability. Agent A is the
simplest and most practical for day-to-day use:

| Feature | Agent A | Agent B | Agent C |
|---------|---------|---------|---------|
| LLM proposes tactics | Yes | Yes | Yes |
| Single-threaded | Yes | No | No |
| Parallel attempt scheduling | No | Yes | Yes |
| Cumulative context (all past errors) | Yes | Yes | Yes |
| Self-critique step | No | Yes | Yes |
| Search over tactic tree | No | No | Yes |

Agent A is a single-loop system: one LLM call, one compile, repeat.
It works well for theorems that need a few attempts (most practical
cases). The paper shows Agent A solves ~60% of problems that Agent C
solves, but uses a fraction of the compute.

## Key paper results

| Benchmark | Agent A solves | Agent C solves |
|-----------|---------------|---------------|
| MiniF2F validation | 52.8% | 68.4% |
| PutnamBench | 7/15 | 10/15 |
| Erdős problems (custom) | 14/50 | 23/50 |

These results are for fully automated runs -- no human provides hints
mid-proof. The server's own benchmarks may differ because of different
LLM backends, prompt templates, and timeout budgets.

## Where this server diverges

The paper assumes a specific LLM (Gemini 2.5 Pro fine-tuned on tactic
data). This server supports any OpenAI-compatible or Anthropic backend,
which means quality varies by model. The paper also uses a custom tactic
generation format; this server uses standard Lean `calc` and `by` blocks
with a generic LLM prompt template.

What's preserved:

- The **LLM proposes, Lean judges, error feeds back** loop
- **Independent job tracking** with persistence (SQLite)
- **Timeout budgets** per attempt (paper suggests 30s per compile)
- **Error message chaining** -- each attempt sees all previous errors

## Further reading

- [arXiv:2605.22763](https://arxiv.org/abs/2605.22763) -- the paper
- [Lean 4 docs](https://lean-lang.org/lean4/doc/) -- language reference
- [MiniF2F](https://github.com/openai/miniF2F) -- the standard benchmark
- [docs/LEAN.md](LEAN.md) -- Lean language reference for this server

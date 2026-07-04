# Media coverage of AlphaProof Nexus

DeepMind published [AlphaProof Nexus](https://arxiv.org/abs/2605.22763) in May 2026
and it got picked up by most major tech outlets within days: Wired, TechCrunch, The
Verge, Ars Technica, and a wave of newsletters. The coverage was respectful but
measured -- "AI takes another step toward mathematical reasoning" was the typical
framing.

## The coverage gap

The coverage followed a predictable pattern:

| If published by | Likely coverage | Reason |
|----------------|----------------|--------|
| **DeepMind** | Wired, TechCrunch, Ars Technica, Bloomberg | Pre-existing press pipeline, PR team, journalist relationships |
| **OpenAI** | Same outlets + NYT, WSJ | Same pipeline, stronger consumer brand |
| **Anthropic** | TechCrunch, ones with a safety angle | Smaller but established |
| **UnknownCorp** | Zero. Maybe a paragraph on The Register if lucky | No press contacts, no embargo access, no brand recognition |
| **hopefulstartup.ai** | Zero. A HN post with 12 points. | Same problem, plus no compute for the full eval suite |

The paper itself would be the same. The benchmarks would be the same (MiniF2F,
PutnamBench, Erdős). The method would be the same (LLM + Lean compiler loop).
What changes is only the letterhead.

## Why this matters for leanforge-mcp

Leanforge-mcp implements the same open-source technique (Agent A from the paper)
using any LLM backend -- Ollama, DeepSeek, Anthropic, whatever you have. The
method is not proprietary to DeepMind. The difference is that DeepMind had 200+
GPU hours and a prompt engineering team to get their benchmark numbers; this server
gives you the same loop with whatever model you can point at it.

The core idea is the paper's, not DeepMind's exclusive property: an LLM proposes
tactic edits, the Lean compiler judges them, errors feed back. Anyone can run this
loop. The coverage gap just means most people don't know that.

## References

- [AlphaProof Nexus paper](https://arxiv.org/abs/2605.22763) -- the technique
- [docs/ALPHAPROOF_NEXUS.md](ALPHAPROOF_NEXUS.md) -- plain-language explanation
- [Lean 4](https://lean-lang.org/) -- the theorem prover

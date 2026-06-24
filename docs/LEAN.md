# Lean 4 Reference

A working reference for engineers using leanforge-mcp. Covers the language,
Mathlib, the proof pipeline, and the literature behind the approach.

## Contents

- [What Lean is](#what-lean-is)
- [The sorry placeholder](#the-sorry-placeholder)
- [Proof structure](#proof-structure)
- [Tactic reference](#tactic-reference)
- [Reading compiler errors](#reading-compiler-errors)
- [Mathlib conventions](#mathlib-conventions)
- [Worked examples](#worked-examples)
- [Import strategy](#import-strategy)
- [The Lake build system](#the-lake-build-system)
- [Benchmarks and problem sets](#benchmarks-and-problem-sets)
- [Bibliography](#bibliography)
- [Link collection](#link-collection)

---

## What Lean is

Lean 4 is simultaneously a functional programming language and a proof assistant.
In Lean, **a proof is a program** and **a theorem is a type**. This is the
Curry–Howard correspondence: logical propositions correspond to types, and proofs
correspond to programs that inhabit those types.

Proving `n + 0 = n` means constructing a term of type `n + 0 = n`. The Lean kernel
checks this term is well-typed against the axioms of dependent type theory. If the
kernel accepts it, the proof is correct — not approximately correct, not "convincing
to a reviewer", but correct in the mathematical sense. No reviewer, no peer review,
no subtle gap possible.

This is why the AlphaProof Nexus approach works: LLMs are now capable enough that
the compile-feedback loop alone can drive proof search to research-level difficulty.
The compiler eliminates hallucination at the proof level — a wrong proof simply fails
to compile.

---

## The sorry placeholder

```lean
theorem my_theorem (n : ℕ) : n + 0 = n := by
  sorry
```

`sorry` is an axiom that closes any goal. The file compiles but emits:

```
warning: declaration uses 'sorry'
```

A proof is valid only when every `sorry` is replaced with real tactics and the
compiler emits no `declaration uses 'sorry'` warning. leanforge-mcp's job is exactly
this: fill `sorry` without touching the statement.

The tamper guard in `agent.py` hashes the theorem signature before and after every
edit and rejects any change to the statement. Agents may only edit what comes after
`:= by`.

---

## Proof structure

```lean
theorem name (param : Type) (hyp : Proposition) : conclusion := by
  tactic₁
  tactic₂
  ...
```

`by` enters tactic mode. Each tactic transforms the current proof goal. When no
goals remain, the proof is complete.

**Term-mode proofs** (no `by`):
```lean
theorem add_zero (n : ℕ) : n + 0 = n := Nat.add_zero n
```

**Structured proofs** with `have`:
```lean
theorem example (n : ℕ) : n * 2 = n + n := by
  have h : n * 2 = n * (1 + 1) := by ring
  linarith [h]
```

**Induction**:
```lean
theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  induction n with
  | zero      => simp
  | succ n ih => rw [Finset.sum_range_succ]; ring_nf; linarith
```

---

## Tactic reference

### Arithmetic and algebra

| Tactic | When to use |
|--------|-------------|
| `ring` | Prove equalities in commutative (semi)rings: `a*(b+c) = a*b + a*c`. Fully automatic. |
| `ring_nf` | Normalise ring expressions without closing the goal. Use before `linarith`. |
| `linarith` | Linear arithmetic over ordered fields/rings: `x + 1 > x`, `2*x = x + x`. Closes goal or raises a contradiction. |
| `nlinarith` | Nonlinear arithmetic. Slower than `linarith`, needed for `x^2 ≥ 0` style goals. |
| `omega` | Exact integer and natural number arithmetic. Decision procedure — either closes or fails immediately. |
| `norm_num` | Numeric goals: `2 + 2 = 4`, `7 ∣ 49`. Use for concrete computations. |
| `positivity` | Prove `0 ≤ e` or `0 < e` for expressions built from nonneg components. |
| `field_simp` | Simplify field expressions, clearing denominators. Pair with `ring`. |

### Simplification

| Tactic | When to use |
|--------|-------------|
| `simp` | Rewrite using a large database of lemmas tagged `@[simp]`. Best first move on simple goals. Can loop — use `simp only [...]` to control. |
| `simp only [h₁, h₂]` | `simp` restricted to the given lemmas. Predictable, faster, preferred for non-trivial goals. |
| `simp [*]` | `simp` plus all local hypotheses. |
| `norm_cast` | Normalise coercions between `ℕ`, `ℤ`, `ℝ`, etc. |
| `push_cast` | Push casts inward. Companion to `norm_cast`. |

### Logic and structure

| Tactic | When to use |
|--------|-------------|
| `exact h` | Close goal with exactly hypothesis or term `h`. |
| `apply f` | If `f : A → B` and goal is `B`, reduce to `A`. |
| `intro h` | Introduce a hypothesis from `∀` or `→`. |
| `constructor` | Split a conjunction or build a structure. |
| `cases h with` | Case-split on an inductive type or proposition. |
| `induction n with` | Induction on `n`. The `with` clause names each case. |
| `rcases h with ⟨a, b⟩` | Destructure a hypothesis (conjunction, existential, etc.). |
| `obtain ⟨a, ha⟩ := h` | `rcases` in `obtain` form. |
| `use v` | Provide a witness for an existential goal `∃ x, P x`. |
| `left` / `right` | Choose a branch of a disjunction. |
| `exfalso` | Change goal to `False`. Use when a hypothesis is contradictory. |
| `contradiction` | Close goal if hypotheses contain a contradiction. |
| `tauto` | Propositional tautology checker. |
| `decide` | Decide decidable propositions by computation. For finite types and concrete values. |

### Rewriting

| Tactic | When to use |
|--------|-------------|
| `rw [lemma]` | Rewrite the goal left-to-right using `lemma`. |
| `rw [← lemma]` | Rewrite right-to-left. |
| `rw [lemma] at h` | Rewrite hypothesis `h`. |
| `conv => ...` | Fine-grained rewriting: target a specific subterm. |
| `nth_rewrite n [lemma]` | Rewrite only the nth occurrence. |
| `subst h` | Substitute a variable using a hypothesis of the form `x = t`. |

### Automation

| Tactic | When to use |
|--------|-------------|
| `aesop` | General-purpose automation. Tries many tactics. Slower but broad. |
| `trivial` | Closes trivially true goals (combines several simple tactics). |
| `assumption` | Close goal with a matching hypothesis. |
| `exact?` | Search for a term that closes the goal. IDE / `#check` use. |
| `apply?` | Search for applicable lemmas. Interactive use. |
| `simp?` | Suggest a minimal `simp only [...]` call. |

### Proof state inspection (IDE / debugging)

| Command | What it shows |
|---------|---------------|
| `#check Nat.add_comm` | Type of a term or lemma. |
| `#print Nat.add_comm` | Full definition. |
| `example : ... := by exact?` | Find a proof term in scope. |
| `set_option pp.all true` | Show full elaborated terms (verbose). |

---

## Reading compiler errors

```
error: tactic 'ring' failed, no goals
  leanforge-mcp/_lf_abc123.lean:8:2
```
→ `ring` called after the goal was already closed. Delete it or reorder tactics.

```
error: unknown identifier 'Nat.add_comm'
```
→ Wrong lemma name. Use `get_mathlib_search "commutativity of addition"` to find it.
The correct name is likely `add_comm` or `Nat.add_comm` — check with `#check`.

```
error: type mismatch
  expected: n + 0 = n
  given:    0 + n = n
```
→ Proof proves the wrong direction. Add `rw [add_comm]` first, or use `ring`.

```
error: tactic 'linarith' failed, it couldn't prove the goal
  n : ℕ
  ih : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1)
  ⊢ 2 * ∑ i ∈ Finset.range (n + 2), i = (n + 1) * (n + 2)
```
→ `linarith` needs the goal reduced further. Add `ring_nf` before `linarith`, or
rewrite the sum using `Finset.sum_range_succ` first.

```
warning: declaration uses 'sorry'
```
→ Not an error — proof incomplete. The file still compiles. `proven = false`.

```
error: function expected at
  Finset.sum_range_succ
```
→ Wrong number of arguments. `rw` expects a bare lemma name; you may be applying
it as a function. Use `rw [Finset.sum_range_succ]`, not `exact Finset.sum_range_succ`.

---

## Mathlib conventions

Mathlib contains 150k+ formalized theorems. The naming scheme is systematic:

**Namespace = type**: `Nat.`, `Int.`, `Real.`, `Complex.`, `Rat.`, `Finset.`,
`List.`, `Multiset.`, `Set.`, `Finsupp.`, `MvPolynomial.`

**Operation suffix**: `_add`, `_mul`, `_comm`, `_assoc`, `_zero`, `_one`, `_succ`,
`_pred`, `_pow`, `_div`, `_mod`, `_le`, `_lt`, `_eq`, `_ne`

**Direction suffix**: `_left`, `_right`, `_of`, `_iff`

Common patterns:
```lean
Nat.add_comm   : ∀ (n m : ℕ), n + m = m + n
Nat.add_assoc  : ∀ (n m k : ℕ), n + m + k = n + (m + k)
Nat.succ_pos   : ∀ (n : ℕ), 0 < n.succ
Finset.sum_range_succ : ∑ i ∈ Finset.range (n+1), f i = ∑ i ∈ Finset.range n, f i + f n
Real.sqrt_sq   : ∀ {x : ℝ}, 0 ≤ x → √(x ^ 2) = x
```

When stuck, use [LeanSearch](https://leansearch.net) or the `get_mathlib_search`
tool. Natural language queries work well: "sum of geometric series", "prime
factorization unique", "triangle inequality".

---

## Worked examples

### Arithmetic sum

The classic $\sum_{i=0}^{n} i = \frac{n(n+1)}{2}$:

```lean
import Mathlib

theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  induction n with
  | zero      => simp
  | succ n ih =>
    rw [Finset.sum_range_succ]
    ring_nf
    linarith
```

### Infinitely many primes

```lean
import Mathlib

theorem infinite_primes : ∀ n : ℕ, ∃ p, n ≤ p ∧ Nat.Prime p :=
  fun n => Nat.exists_infinite_primes n
```

This one is a single-line proof — Mathlib already has `Nat.exists_infinite_primes`.
`get_mathlib_search` would surface it. Shows why searching Mathlib first matters.

### Induction with a helper lemma

```lean
import Mathlib

lemma two_mul_sum (n : ℕ) : 2 * ∑ i ∈ Finset.range n, i = n * (n - 1) := by
  induction n with
  | zero      => simp
  | succ n ih =>
    rw [Finset.sum_range_succ, Nat.mul_add]
    omega

theorem gauss (n : ℕ) : ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) / 2 := by
  have h := two_mul_sum (n + 1)
  omega
```

---

## Import strategy

`import Mathlib` imports all of Mathlib (~150k theorems). It works but costs 30–60s
per `lake env lean` invocation even with cached oleans. For faster iteration on
focused problems, use targeted imports:

```lean
import Mathlib.Tactic           -- all tactics (simp, ring, linarith, omega, …)
import Mathlib.Data.Nat.Basic   -- natural number basics
import Mathlib.Data.Finset.Sum  -- Finset.sum_range_succ etc.
import Mathlib.NumberTheory.Primes -- prime number theorems
```

Find the right module: browse [Mathlib4 docs](https://leanprover-community.github.io/mathlib4_docs/)
or search the [Mathlib source](https://github.com/leanprover-community/mathlib4).

leanforge-mcp uses `import Mathlib` in the default stub template. The config key
`lean.stub_imports` (planned, not yet implemented) will allow overriding this.

---

## The Lake build system

Lake is Lean's build system and package manager. Key commands:

```powershell
lake new myproject math     # scaffold a new project with Mathlib dependency
lake exe cache get          # download precompiled Mathlib oleans (~4GB, one-time)
lake build                  # build the project
lake env lean file.lean     # compile a single file inside the project environment
lake exe repl               # start an interactive REPL (if leanprover-community/repl installed)
```

leanforge-mcp always invokes `lake env lean <tmpfile>` from inside the workspace
directory. The `lake env` prefix ensures the compiler inherits the full Lake project
environment (Mathlib on the search path, correct toolchain).

`lake env lean` without a project is useless for Mathlib — the import will fail.
This is why the one-time workspace setup is a hard prerequisite.

---

## Benchmarks and problem sets

### MiniF2F

488 pre-formalized olympiad problems (AMC, AIME, IMO, etc.) in Lean 4. The standard
evaluation benchmark for automated theorem provers.

- Repo: [leanprover-community/miniF2F](https://github.com/leanprover-community/miniF2F)
- Split: `valid/` (244 problems) and `test/` (244 problems)
- Baseline: DeepSeek-Prover-V2 7B solves ~40% of valid; 671B solves ~65%

Use with leanforge-mcp: `submit_lean_file` each problem file directly.

### PutnamBench

658 formalized Putnam competition problems.

- Repo: [trishullab/PutnamBench](https://github.com/trishullab/PutnamBench)
- Baseline: DeepSeek-Prover-V2 671B solves 49/658 (7.4%)
- Target for leanforge-mcp tier-1: match the 7B baseline (~3–5%)

### AlphaProof Nexus unsolved set

353 Erdős problems attempted by the AlphaProof Nexus system. 344 remain open.
All pre-formalized as Lean 4 stubs — the hardest part (stating the theorem correctly)
is already done.

- Repo: [google-deepmind/alphaproof-nexus-results](https://github.com/google-deepmind/alphaproof-nexus-results)
- Any `status=complete` result from leanforge-mcp on this set is a novel theorem

### erdosproblems.com

~900 open Erdős problems in natural language. Requires manual Lean formalization
of the statement before proof search. The formalization step is often the harder part.

---

## Bibliography

**Foundational papers**

- Moura, L. de, & Ullrich, S. (2021). **The Lean 4 theorem prover and programming language.** CADE-28. [doi:10.1007/978-3-030-79876-5_37](https://doi.org/10.1007/978-3-030-79876-5_37)

- The Mathlib Community (2020). **The Lean Mathematical Library.** CPP 2020. [arXiv:1910.09336](https://arxiv.org/abs/1910.09336)

**AlphaProof Nexus (direct inspiration)**

- Google DeepMind (2026). **AlphaProof Nexus: Scaling AI-Assisted Formal Mathematics.** [arXiv:2605.22763](https://arxiv.org/abs/2605.22763)
  — Introduces the Agent A architecture (independent subagents, compiler oracle) implemented here.

**Prover models**

- Xin, H., et al. (2025). **DeepSeek-Prover-V2: Advancing Formal Mathematical Reasoning via Reinforcement Learning for Subgoal Decomposition.** [arXiv:2504.21801](https://arxiv.org/abs/2504.21801)
  — The open-weight model used as leanforge-mcp's tier-1 and tier-2 backbone.

- Han, J. M., et al. (2022). **Proof Artifact Co-Training (PACT).** [arXiv:2102.06203](https://arxiv.org/abs/2102.06203)
  — Early work on training language models on Lean proof artifacts.

- Polu, S., & Han, J. M. (2022). **Formal Mathematics Statement Curriculum Learning.** [arXiv:2202.01344](https://arxiv.org/abs/2202.01344)

**Benchmarks**

- Zheng, K., et al. (2022). **MiniF2F: a cross-system benchmark for formal Olympiad-level mathematics.** ICLR 2022. [arXiv:2109.00110](https://arxiv.org/abs/2109.00110)

- Tsoukalas, G., et al. (2024). **PutnamBench: Evaluating Neural Theorem-Provers on the Putnam Mathematical Competition.** [arXiv:2407.11214](https://arxiv.org/abs/2407.11214)

**Lean / type theory**

- Avigad, J., et al. (2024). **Theorem Proving in Lean 4.** (online textbook) [leanprover.github.io/theorem_proving_in_lean4](https://leanprover.github.io/theorem_proving_in_lean4/)

- Avigad, J., & Massot, P. (2024). **Mathematics in Lean.** [leanprover-community.github.io/mathematics_in_lean](https://leanprover-community.github.io/mathematics_in_lean/)

- Howard, W. A. (1980). **The formulae-as-types notion of construction.** In Hindley & Seldin (eds.), *To H. B. Curry: Essays on Combinatory Logic, Lambda Calculus and Formalism.* Academic Press.
  — Original Curry–Howard correspondence paper.

---

## Link collection

### Language and tools

| Resource | URL |
|----------|-----|
| Lean 4 official site | https://lean-lang.org |
| Lean 4 documentation | https://lean-lang.org/lean4/doc/whatIsLean.html |
| Lean 4 setup guide | https://lean-lang.org/lean4/doc/setup.html |
| elan (Lean version manager) | https://github.com/leanprover/elan |
| Lake documentation | https://github.com/leanprover/lean4/blob/master/src/lake/README.md |
| VS Code Lean 4 extension | https://marketplace.visualstudio.com/items?itemName=leanprover.lean4 |
| Lean 4 online playground | https://live.lean-lang.org |

### Mathlib

| Resource | URL |
|----------|-----|
| Mathlib4 source | https://github.com/leanprover-community/mathlib4 |
| Mathlib4 docs (searchable) | https://leanprover-community.github.io/mathlib4_docs/ |
| LeanSearch (natural language) | https://leansearch.net |
| Loogle (regex/pattern search) | https://loogle.lean-lang.org |
| Moogle (semantic search) | https://www.moogle.ai |
| Mathlib contributing guide | https://leanprover-community.github.io/contribute/index.html |

### Learning

| Resource | URL |
|----------|-----|
| Theorem Proving in Lean 4 (book) | https://leanprover.github.io/theorem_proving_in_lean4/ |
| Mathematics in Lean (book) | https://leanprover-community.github.io/mathematics_in_lean/ |
| Functional Programming in Lean | https://leanprover.github.io/functional_programming_in_lean/ |
| Natural Number Game (browser Lean) | https://adam.math.hhu.de |
| Lean 4 Zulip (community chat) | https://leanprover.zulipchat.com |
| Lean 4 GitHub discussions | https://github.com/leanprover/lean4/discussions |

### Benchmarks and problem sets

| Resource | URL |
|----------|-----|
| MiniF2F | https://github.com/leanprover-community/miniF2F |
| PutnamBench | https://github.com/trishullab/PutnamBench |
| AlphaProof Nexus results + unsolved stubs | https://github.com/google-deepmind/alphaproof-nexus-results |
| erdosproblems.com (open Erdős catalog) | https://www.erdosproblems.com |
| ProofNet (undergraduate benchmark) | https://github.com/zhangir-azerbayev/ProofNet |

### Prover models

| Resource | URL |
|----------|-----|
| DeepSeek-Prover-V2 (HuggingFace) | https://huggingface.co/deepseek-ai/DeepSeek-Prover-V2 |
| DeepSeek-Prover-V2 7B (tier-1 model) | https://huggingface.co/deepseek-ai/DeepSeek-Prover-V2-7B |
| DeepSeek-Prover-V2 paper | https://arxiv.org/abs/2504.21801 |
| AlphaProof Nexus paper | https://arxiv.org/abs/2605.22763 |
| leanprover-community/repl | https://github.com/leanprover-community/repl |

### Related projects

| Resource | URL |
|----------|-----|
| LeanDojo | https://github.com/lean-dojo/LeanDojo |
| ntp-toolkit (next-step prediction) | https://github.com/leanprover-community/ntp-toolkit |
| Lean Copilot | https://github.com/lean-dojo/LeanCopilot |
| mathlib4 on Glama | https://glama.ai/mcp/servers/mathlib4 |

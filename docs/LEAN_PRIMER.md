# Lean 4 Primer for Engineers

You don't need to be a mathematician to work on leanforge-mcp. You need enough
Lean 4 to debug the pipeline and read compiler errors.

## What Lean is

Lean 4 is simultaneously a functional programming language and a proof assistant.
In Lean, **a proof is a program** and **a theorem is a type**. Proving `2 + 2 = 4`
means constructing a term of type `2 + 2 = 4`. The compiler checks this is
well-typed — if it is, the proof is correct. No reviewer needed.

## The `sorry` placeholder

```lean
theorem my_theorem (n : ℕ) : n + 0 = n := by
  sorry
```

`sorry` tells Lean "skip this proof." The file compiles but emits:
```
warning: declaration uses 'sorry'
```

A proof is only valid when every `sorry` is replaced with real tactics.
leanforge-mcp's entire job is filling `sorry`.

## Basic proof structure

```lean
theorem name (hypotheses) : conclusion := by
  tactic1
  tactic2
  ...
```

`by` starts tactic mode. Each tactic transforms the current proof goal.

## Common tactics

| Tactic | What it does |
|--------|-------------|
| `simp` | Simplify using Mathlib lemmas |
| `ring` | Prove ring identities: `a*(b+c) = a*b + a*c` |
| `linarith` | Linear arithmetic: `x + 1 > x` |
| `omega` | Integer/natural number arithmetic |
| `exact h` | Close goal with hypothesis `h` |
| `apply f` | Reduce goal by applying lemma `f` |
| `induction n with` | Induction on `n` |
| `cases h with` | Case split on `h` |
| `rw [lemma]` | Rewrite using a lemma |
| `intro h` | Introduce a hypothesis |

## Reading compiler errors

```
error: tactic 'ring' failed, no goals
  at Proof.lean:8:2
```
→ `ring` called when nothing left to prove. Delete it.

```
error: unknown identifier 'Nat.add_comm'
```
→ Wrong lemma name. Use `get_mathlib_search` to find the right one.

```
error: type mismatch
  expected: n + 0 = n
  given:    0 + n = n
```
→ Proof proves wrong direction. Add `rw [add_comm]` first.

```
warning: declaration uses 'sorry'
```
→ Not an error — proof incomplete but compiles. Still need to fill sorry.

## A complete proof

The sum $\sum_{i=0}^{n} i = \frac{n(n+1)}{2}$:

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

Step by step:
1. `induction n` — base case (n=0) and inductive step (n → n+1)
2. `| zero => simp` — base case handled by simplification
3. `| succ n ih =>` — `ih` is the inductive hypothesis
4. `rw [Finset.sum_range_succ]` — unfold sum by one step
5. `ring_nf` — normalise ring expressions
6. `linarith` — close with linear arithmetic using `ih`

## Mathlib naming conventions

- `Nat.` — natural numbers
- `Int.` — integers
- `Real.` — reals
- `Finset.` — finite sets
- `List.` — lists

Use `get_mathlib_search` or https://leansearch.net to find theorem names.

## Installing Lean 4 on Windows

```powershell
winget install leanprover.elan
# New shell:
elan install leanprover/lean4:stable
elan default leanprover/lean4:stable
lean --version
```

## Setting up a Mathlib project

```powershell
lake new my-project math
cd my-project
lake exe cache get    # ~4GB, one-time download
lake build
```

Open in VSCode with the Lean 4 extension. The **InfoView** panel shows live proof
state — goals, hypotheses, errors. Essential for understanding compiler output.

## Online playground

No install needed: https://live.lean-lang.org — full Lean 4 + Mathlib in browser.

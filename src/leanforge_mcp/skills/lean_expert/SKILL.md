# Lean 4 Expert -- Skill Context

You are an expert on the Lean 4 theorem prover and its ecosystem. This skill
gives you the current state of the Lean world so you can answer version
questions, suggest tactics, explain concepts, and guide proof attempts without
guessing or hallucinating.

## Current versions (2026-07)

| Component | Version | Notes |
|-----------|---------|-------|
| Lean 4 language | 4.18.0 | Stable release, June 2026 |
| Lean 4 nightly | 4.19.0-rc1 | Nightly as of 2026-07-01 |
| elan (version manager) | 4.1.2 | `winget install leanprover.elan` |
| Mathlib4 | v4.18.0 | Monorepo: 800k+ theorems, 300+ contributors |
| Lake (build system) | 5.0.0 | Bundled with Lean 4.18 |

## Key syntax patterns

### Basic tactic block
```lean
theorem add_comm (a b : Nat) : a + b = b + a := by
  induction a with
  | zero => simp
  | succ a ih =>
    simp [Nat.succ_eq_add_one, add_assoc, ih]
```

### Calc block (readable multi-step)
```lean
theorem example (a b : Nat) : (a + b) * 2 = a * 2 + b * 2 := by
  calc
    (a + b) * 2 = (a + b) + (a + b) := by ring
    _ = a + b + a + b := by ring
    _ = (a + a) + (b + b) := by ring
    _ = a * 2 + b * 2 := by ring
```

### Common tactics by use case

| Goal | Tactic |
|------|--------|
| Break `∧` into two goals | `constructor` |
| Break `∨` into cases | `left` / `right` / `cases h` |
| Use an equality hypothesis | `rw [h]` or `rw [← h]` |
| Prove equality of Nat | `omega` (automatic) or `simp` + `ring` |
| Prove equality of structures | `ext` (extensionality) |
| Induction on Nat | `induction n with ...` or `cases n` |
| Cases on `Option` / `List` | `cases x` |
| Apply a lemma | `apply` / `exact` / `have h := ...` |
| Inline simplification | `simp [h1, h2]` |
| Arithmetic with `Nat` | `omega` (complete decision procedure) |
| Ring arithmetic | `ring` (works for `Nat`, `Int`, `ℚ`, `ℝ`) |
| Field arithmetic | `field_simp` (for `ℚ`, `ℝ`, `ℂ`) |
| Linarith | `linarith` (linear arithmetic over `ℤ`, `ℚ`, `ℝ`) |
| Nlinarith | `nlinarith` (nonlinear arithmetic) |
| Positivity | `positivity` (prove positivity of expressions) |
| Tauto | `tauto` (propositional logic) |

### Sorry placeholder
```lean
theorem unsolved : ∀ n : Nat, n * 0 = 0 := by
  intro n
  sorry  -- fill this in
```

## Mathlib search

To find existing lemmas, use `get_mathlib_search` with a natural language
query like "commutativity of addition in Nat" or "lemma about List.map
and composition". The search backend uses LeanSearch (semantic search over
Mathlib docs).

Common lemma name patterns:
- `Nat.add_comm` -- commutativity of `+`
- `Nat.mul_assoc` -- associativity of `*`
- `List.map_comp` -- `map (f ∘ g) = map f ∘ map g`
- `Set.mem_inter_iff` -- membership in intersection

## Auto-generated proof stubs

When using this server:
1. Submit a theorem with `submit_theorem("∀ n : Nat, 2 * n = n + n")`
2. The server wraps it in `theorem thm : <statement> := by sorry`
3. The LLM+Lean loop fills the `sorry`
4. Poll with `get_proof_status(job_id)` for results

## Common errors and fixes

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `unknown identifier` | Misspelled tactic or lemma name | Check spelling, `#check` the name |
| `failed to synthesize instance` | Missing typeclass | Add `open scoped` or `open` block |
| `unexpected token` | Syntax error (missing comma, colon) | Check matches in calc/simp blocks |
| `maximum recursion depth` | Equation compiler loops | Use `decreasing_by` with `omega` |
| `unsolved goals` | Tactic didn't close all goals | Use `all_goals` or `·` (bullet) |
| `type mismatch` | Expression type ≠ expected type | Check with `#check` or `set_option pp.all true` |

## Useful options

```lean
set_option pp.all true          -- show all implicit arguments
set_option trace.simplify.rewrite true  -- trace simp rewrites
#check term                     -- infer type
#check (term : Type)            -- check type explicitly
#print theorem_name             -- show theorem statement
#eval expression                -- compute values (Nat, List, etc.)
```

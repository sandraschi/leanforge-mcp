# Hint pack: Jacobian / Frechet-derivative proofs

Premise and strategy pack for goals that mention `fderiv`, `HasFDerivAt`,
`deriv`, `DifferentiableAt`, or a Jacobian entry. Intended as the `hints=`
argument of `submit_theorem`.

**Provenance.** Mined 2026-10-20 from `brettkoonce/lean4-mlir` v0.7.2
(BSD-3-Clause), files `LeanMlir/Proofs/Foundation/Tensor.lean`,
`Foundation/MLP.lean`, and `Architectures/{BatchNorm,Activations,Attention}.lean`.
Every name below was read out of the source; none is quoted from the project's
prose. Use counts are counts over those five files, so they say "this is what a
large Mathlib-native development leaned on", not "this lemma proves your goal".

**How to use.** `submit_theorem(hints="<one line>")`. The server prepends the
string to the file as a comment, so a multi-line string is only safe on builds
that carry the fix noted at the end.

---

## 1. The structural rules

Backprop is composition, fan-in and product. The names used in that development,
with the exact Mathlib rewrite each relied on:

| rule | what it is | proof shape (verified in source) |
|---|---|---|
| `pdiv_comp` | chain rule | `rw [pdiv, fderiv_comp x hg hf, ContinuousLinearMap.comp_apply, ContinuousLinearMap.coe_coe, LinearMap.pi_apply_eq_sum_univ, Finset.sum_apply]`, then `Finset.sum_congr` |
| `pdiv_add` | sum rule | `unfold pdiv` then `rw [fderiv_add hf hg]` then `rfl` |
| `pdiv_mul` | product rule | via `fderiv_mul` |
| `pdiv_id` | identity / diagonal | via `fderiv_apply` and coordinate projections |

All of them unfold the same definition:

    pdiv f x i j := fderiv R f x (basisVec i) j

Two gotchas, both visible in `pdiv_comp`:

- **Argument order.** `fderiv_comp x hg hf` takes the *outer* function's
  differentiability hypothesis first. Reversing it is the most common
  "function expected" error in this family of proofs.
- **CLM application is not a sum until you say so.** `LinearMap.pi_apply_eq_sum_univ`
  plus `Finset.sum_apply` is what turns `(fderiv R f x v) j` into an explicit
  `Finset.sum` you can rewrite under.

## 2. Mathlib names that carried the weight

By use count across the five files:

| count | name |
|---|---|
| 42 | tactic `fun_prop` |
| 11 | `ContinuousLinearMap.proj` |
| 6 | `ContinuousLinearMap.pi` |
| 5 | `hasDerivAt_tanh` |
| 4 | `ContinuousLinearMap.pi_apply` |
| 3 | `hasDerivAt_id`, `Real.tanh_eq_sinh_div_cosh`, `Real.cosh_pos` |
| 2 | `fderiv_coord`, `fderiv_fun_sum`, `fderiv_mul`, `hasDerivAt_inv`, `hasDerivAt_swishScalar`, `Real.hasDerivAt_sigmoid`, `ContinuousLinearMap.fderiv`, `ContinuousLinearMap.comp_apply` |
| 1 each | `fderiv_comp`, `fderiv_add`, `fderiv_add_const`, `fderiv_apply`, `HasFDerivAt.fun_sum`, `HasFDerivAt.sqrt`, `HasDerivAt.comp_hasFDerivAt`, `hasDerivAt_pow`, `LinearMap.pi_apply_eq_sum_univ`, `ContinuousLinearMap.coe_coe`, `Real.sq_sqrt`, `Real.sqrt_lt`, `Real.abs_le_sqrt`, `Real.differentiable_cosh`, `Real.differentiable_sinh` |

Tactic mix: `simp` 122, `rw` 119, `have` 87, `fun_prop` 42, `exact` 38,
`intro` 33, `unfold` 31, `ring` 27, `refine` 9, `field_simp` 5, `linarith` 4,
`simpa` 3, `convert` 2, `nlinarith` 1, `norm_num` 1.

**Highest-value single hint.** When the goal or a hypothesis needs
`DifferentiableAt`, `Differentiable`, `Continuous` or `ContDiff`, try `fun_prop`
first, and register local lemmas with `@[fun_prop]` so it can see them. That is
how smoothness is threaded through every composition in that suite - 42 uses, and
each one replaces a hand-built chain of derivative lemmas.

## 3. The five Jacobian shapes

Useful as strategy text when the operator is known. Every layer backward in that
suite is one of:

1. **Diagonal** - activations (ReLU, GELU, sigmoid): one multiply by the
   elementwise derivative.
2. **Sparse Toeplitz** - convolution: reversed-kernel convolution.
3. **Binary selection** - max pool: route the cotangent to the argmax.
4. **Rank-1 correction** - batch norm, layer norm, softmax: closed-form 3-term
   (centering + inverse-stddev + variance term), never a dense matrix.
5. **Outer product** - dense / matmul: `input (x) grad`.

For shape 4 the chain that closes is: the centering CLM, then `HasFDerivAt.sqrt`
under the hypothesis `0 < var + eps`, then `(hasDerivAt_inv).comp_hasFDerivAt`,
then transport through composition. State `hEps : 0 < eps` first; every BN/LN
proof in the suite carries it.

## 4. Kinks: differentiability off a null set

Non-smooth ops (ReLU, ReLU6, max pool) are not differentiable everywhere. The
pattern that works, from `relu_hasFDerivAt`:

1. Define the candidate linear map explicitly (their `reluLinearPart n x`).
2. Prove it is the derivative of the linearisation:
   `(reluLinearPart n x).hasFDerivAt`.
3. Prove the two agree on a neighbourhood: `.congr_of_eventuallyEq`, with
   `filter_upwards` and per-coordinate `eventually_lt_nhds` / `eventually_gt_nhds`
   keeping each sign fixed.
4. Take the hypothesis as a *point* condition: `forall k, x k != 0`, or
   `0 < x k and x k < 6` for ReLU6.
5. Register the corollary `@[fun_prop]` (`relu_differentiableAt_of_smooth`) so
   later composition picks it up automatically.

Expectation-setting: Mathlib's `fderiv` returns `0` at non-differentiable points
by convention, so a backward pass built naively from `fderiv` yields the junk `0`
at the kink. Frameworks substitute the subgradient convention. If a theorem must
cover a kink, the honest statement is pointwise under a smoothness hypothesis plus
a separate agreement lemma - not "differentiable everywhere".

## 5. What not to carry over

- `pdiv`, `pdivMat`, `Vec`, `Mat`, `HasVJP`, `biPath` are that project's own
  vocabulary. None exist in Mathlib. Do not put them in a hint string for a
  theorem about Mathlib-level objects.
- The counts are file-level, not per-theorem, and the suite is generic over a base
  field `R`; in this repo's `Real` setting the same lemmas apply with `Real`.
- The `VerifiedNetSpec` / codegen tie layer is about their shipped artifacts.
  Nothing in it transfers to a Mathlib theorem.

---

Source: https://github.com/brettkoonce/lean4-mlir (v0.7.2, BSD-3-Clause).
Narrative version of the trust argument:
https://lean.brettkoonce.com/blueprint/app-verification.html

## Note on multi-line hints

`submit_theorem` prepends the hint string as a single `-- HINTS: ...` comment.
Before this pack was written, a newline inside `hints` ended that comment and the
following line was parsed as Lean code. The handler now prefixes every line with
`--`; if you are on an older build, keep hints to one line.

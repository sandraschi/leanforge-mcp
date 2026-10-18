# Verified kernels: why `verify_proof` exists

## The one-paragraph version

leanforge-mcp finds proofs by letting an LLM guess and the Lean compiler judge.
"Compiles without `sorry`" has always meant "proven". In August 2026, AI agents
found **two soundness bugs in the Lean kernel itself** -- proofs the compiler
accepted that it should have rejected. So for any result you actually care
about (an open problem, a claim you will publish), one judge is not enough.
`verify_proof` replays your proof through **two extra, independently verified
checkers** and reports whether all of them agree.

## What the pieces are

- **Kernel**: the proof checker inside Lean. Small, trusted, everything else
  rests on it. A bug here means false proofs.
- **`leanchecker`**: the official kernel stripped of everything except checking.
  Used by `lake check`.
- **con-leche**: a Lean kernel *written in Lean*, with a machine-checked proof
  that everything it accepts is consistent (has a set-theory model). Catches
  programming mistakes in the kernel itself. Fast: whole Mathlib in ~100s.
- **con-ron**: the same checker translated to Rust, with a proof (via Aeneas)
  that the Rust code matches. Catches bugs in Lean's *compiler and runtime* --
  the one thing con-leche cannot catch, since it runs on them. Checking with
  **both** con-leche and con-ron means a false accept needs the same bug in
  two completely different toolchains. Very unlikely.
- **lean4lean / nanoda**: two more independent kernels. Not wired in yet
  (lean4lean's verification is still being finished; see below).
- **`lake check` / `lake check --paranoid`**: Lean 4.35's built-in command that
  runs all of the above. Linux-first: it needs a `bwrap` sandbox that does not
  exist on Windows, so on Goliath it cannot run. `verify_proof` calls the same
  checker binaries directly instead -- same verdicts, no sandbox.

## How to use it

```
validate_lean(source)   # quick: does it compile? (existing tool)
verify_proof(source)    # thorough: do the verified kernels agree? (new)
```

`verify_proof` first compiles with the official kernel. Unproven input is
rejected immediately. Proven input goes through: temp module → `lake build` →
`leanexport` (a portable NDJSON dump of the proof) → con-leche → con-ron.
It returns per-kernel verdicts plus `verified: true` only if **every** kernel
accepted. Use it on completed jobs that matter, not per proof-search turn
(a Mathlib proof's export covers the whole dependency closure -- minutes).

## Reading the result

```json
{
  "proven": true,
  "verified": true,
  "toolchain": "4.35.0",
  "kernels": [
    {"kernel": "con-leche", "accepted": true, "declarations": 57921},
    {"kernel": "con-ron", "accepted": true, "declarations": 57921}
  ]
}
```

- `proven`: the official kernel accepted it (same as `validate_lean`).
- `verified`: every selected kernel accepted it. This is the number to quote.
- `declarations`: how many checked items the export contained. If this is 0
  or tiny for a Mathlib proof, something went wrong with the export -- the
  code refuses such runs outright ("refusing vacuous accept") instead of
  reporting a hollow pass, because an empty file is trivially "accepted".

## Current limits (honest list)

1. **Workspace must be on Lean >= 4.35.0.** Ours is still on 4.31.0, so today
   `verify_proof` returns `supported: false` with the upgrade path. The code is
   landed and tested; it activates the moment the workspace moves. Upgrade:
   ```powershell
   cd workspace\leanforge_workspace
   "leanprover/lean4:v4.35.0" | Set-Content lean-toolchain -NoNewline
   # in lakefile.toml: mathlib rev v4.31.0 -> v4.35.0
   lake update; lake exe cache get; lake build
   ```
   That is a multi-GB download plus a long build -- plan it, don't squeeze it
   between other things. Proof search itself keeps working on 4.31.0 meanwhile.
2. **No sandbox on Windows.** The checkers run unsandboxed here. That weakens
   protection against a *malicious* project, not against kernel bugs -- our
   threat is the latter (we check our own proofs), so this is acceptable.
3. **lean4lean / nanoda / leanchecker not wired in.** lean4lean ships a binary
   that chokes on its own oleans in this toolchain; leanchecker's CLI is not
   file-based. Revisit after the next toolchain bump.
4. **Not automatic.** Completing jobs do NOT auto-verify yet -- call
   `verify_proof` by hand on results that matter. Auto-verify on `complete`
   is a future step (needs cost/latency policy first).

## Background

- de Moura's announcement: https://leodemoura.github.io/blog/2026-10-15-lean-now-ships-with-verified-kernels/
- Kernel soundness postmortems (Aug 2026): linked from that post.
- con-leche proof idea: https://leanprover.github.io/con-leche/con-leche-proof-idea.html
- Renovation tracking: https://github.com/leanprover/lean4/issues/14977

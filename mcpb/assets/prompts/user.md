# leanforge-mcp — User Guide

This guide takes you from zero to your first machine-verified Lean 4 proof:
installation, ten step-by-step tutorials covering every common workflow, the
complete REST API reference with request/response examples, a troubleshooting
catalog, and an FAQ. Companion documents: `docs/ONBOARDING.md` (first-timer
setup with costs and pitfalls), `docs/TOOLS.md` (MCP tool reference),
`docs/LEAN_PRIMER.md` (Lean 4 in fifteen minutes).

## 1. What formal proof buys you

Most software testing samples behavior; formal proof covers it exhaustively.
A Lean 4 theorem is a program whose type is a mathematical statement, and the
Lean kernel is a type checker Nazarene-strict enough that only correct proofs
pass. `sorry` is the explicit escape hatch — a placeholder that compiles with
a warning and marks the proof unfinished. leanforge-mcp's entire job is
eliminating `sorry`: you state the theorem, parallel AI agents propose proof
edits, the compiler judges each one, and the winner is a file with zero
`sorry` that anyone can re-check with stock Lean. That file is evidence, not
argument. Mathematicians get certainty; engineers get specifications that
cannot drift from implementation; students get a tutor that never accepts a
hand-wave.

## 2. Installation

Install Python 3.12+, `uv` (`winget install astral-sh.uv`), `elan`
(`winget install leanprover.elan`), and Ollama (`winget install
Ollama.Ollama`) with `ollama pull deepseek-prover-v2:7b` for the free local
tier. Clone the repo, copy `config.example.toml` to `config.toml` (defaults
work on any machine — override only `lake_path`/`workspace_dir` if elan lives
elsewhere), and create the Mathlib workspace once: `cd workspace`, `lake new
leanforge_workspace math`, `cd leanforge_workspace`, `lake exe cache get`
(~4 GB of precompiled oleans), `lake build`. Then `uv sync --extra dev
--extra web` (bare `uv sync` prunes the dev and web extras — always include
both), `.\start.ps1 -Check`, and `uv run python scripts/smoke_test.py`. For
Claude Desktop, add the `leanforge` entry from `README.md` to
`claude_desktop_config.json` with your `DEEPSEEK_API_KEY`/`ANTHROPIC_API_KEY`
if you want tiers 2/3. For the dashboard, run `webapp\start.ps1` (backend
:10867, frontend :10868).

## 3. Tutorial 1 — Prove the pipeline works (2 minutes)

With the MCP server running, call `validate_lean` with
`import Mathlib\nexample : 1 = 1 := rfl\n`. Expect `success: true, proven:
true, has_sorry: false`. This single call exercises config loading, the Lake
workspace, Mathlib resolution, and result parsing. If it returns
`status: "pending"`, the workspace is still building — wait and retry. If it
returns `status: "error"`, the workspace path or Lake binary is wrong: check
`config.toml` against `docs/TROUBLESHOOTING.md` before doing anything else.
Never skip this step — every downstream failure mode looks identical when the
pipeline itself is broken.

## 4. Tutorial 2 — Your first proof search (5 minutes)

Call `submit_theorem` with `statement` set to `∀ n : Nat, n + 0 = n`,
`tier: 1`, `parallel_agents: 2`, `max_turns: 20`. You get a `job_id` and
`status: "queued"` instantly — the search runs in the background. Poll
`get_proof_status` with that id every 10–30 seconds. Within a minute or two
you should see `status: "complete"` with a `proof` field containing a short
file ending in something like `simp` or `exact Nat.add_zero n`. Paste that
file into `validate_lean` yourself to confirm `proven: true` independently.
You have now done the whole loop: state, search, poll, verify.

## 5. Tutorial 3 — Reading a running job (10 minutes)

Submit something harder — the sum formula from the README at tier 1, 4
agents, 100 turns — and while it runs, call `list_attempts` with `last_n: 5`.
Each attempt shows the agent index, turn number, model, a success flag, and
400 characters of compiler output. A healthy search shows varied tactics and
evolving errors. A sick one shows the same error three times (`STUCK`), parse
failures (`PARSE_ERROR`), or edits that never match (`EDIT_NOT_FOUND`).
`LLM_ERROR` with a key message means tier escalation will fail too — fix
credentials first. This inspection skill is the difference between paying for
200 wasted turns and cancelling at turn 15 with a diagnosis.

## 6. Tutorial 4 — Rescuing a stuck search with hints (10 minutes)

Take a goal involving `List.map` composition and submit it bare. It will
likely stall on `unknown identifier` — the model keeps guessing a lemma name
that does not exist. Call `get_mathlib_search` with `"map composition"`,
take the real name (e.g. `List.map_comp_map`), and resubmit the same theorem
with `hints` set to that name. The hint is prepended as a comment the agents
read every turn, and the search typically converges within a few turns.
Policy to internalize: two identical `unknown identifier` errors → search
Mathlib → resubmit with hints. Never let the model guess a third time.

## 7. Tutorial 5 — Submitting a whole file (MiniF2F style, 15 minutes)

Clone `leanprover-community/miniF2F`, pick one problem file (it already
contains `sorry` placeholders and `import` lines), and pass its full text as
`lean_source` to `submit_lean_file` with a `description` like
`miniF2F warmup 3`. The response includes `sorry_count` — confirm it matches
what you see in the file. Poll as usual. Multi-sorry files are solved
hole-by-hole; `list_attempts` shows which hole the agents are working. For
AlphaProof Nexus stubs from `google-deepmind/alphaproof-nexus-results` the
flow is identical, but start at tier 1 with low turns as scouting and only
escalate survivors — those problems are genuinely hard and tier-3 output
pricing punishes wandering.

## 8. Tutorial 6 — Tier escalation on purpose (15 minutes)

Pick a theorem tier 1 fails on within 20 turns (check `list_attempts` for
`STUCK` or repeated `unsolved goals`). Resubmit identical parameters but
`tier: 2` (needs `DEEPSEEK_API_KEY`, ~$0.001/attempt). If tier 2 stalls past
turn 60, resubmit at `tier: 3` (needs `ANTHROPIC_API_KEY`, dollars not cents
— set `max_turns: 50` first and watch the first ten turns live via the
JobInspector SSE stream before committing a big budget). Record cost per
solve in the problem library notes so your next campaign has real numbers.

## 9. Tutorial 7 — Verifying what matters (10 minutes)

A `complete` proof is already compiler-checked, but high-value results
deserve a second opinion from an independent checker. Call `verify_proof`
with the proven file. It recompiles with the official kernel, exports via
leanexport, and replays through con-leche and con-ron. All-accept means two
independently verified kernels agree with stock Lean. On the stock 4.31.0
workspace you will get `supported: false` with the upgrade path instead —
that is the honest answer, not a failure; follow
`docs/VERIFIED_KERNELS.md` to build a 4.35.0+ workspace when you need the
real thing. Never run `verify_proof` per-turn: it takes minutes on
Mathlib-scale files.

## 10. Tutorial 8 — Cancelling and re-queueing (5 minutes)

Submit a hard theorem at 16 agents and 1000 turns, let it run a minute, then
call `cancel_job`. A live task returns `status: "cancelled"`; an already
finished job returns its terminal status with an explanatory message; a bogus
id returns `success: false`. Cancel from the same process that started the
job (MCP server vs web backend are separate processes — cross-process cancel
is a known gap). Requeue deliberately: lower agents, add hints, or raise the
tier. Cancelling is free; a thousand wasted tier-3 turns is not.

## 11. Tutorial 9 — Chat as a Lean coach (10 minutes)

Open the Chat page, pick the Theorem Coach personality, and ask how to start
an induction proof. The page loads the Lean Expert skill plus your
personality as the system prompt and streams the answer through the backend
proxy (`POST /api/llm/chat/stream`) — keys never touch the browser, and the
tier selector (1/2/3) reuses your configured providers. Ask for lemma names,
then verify them with `get_mathlib_search` before trusting them: chat models
hallucinate Mathlib names with total confidence. Export any useful thread
with the download button; history persists in localStorage (100 messages).

## 12. Tutorial 10 — The dashboard tour (10 minutes)

Start the backend and open :10868. The hero shows backend/Lean status pills
and live KPIs; a red onboarding cue links to Settings until the workspace is
ready (MOCK sample cards stand in for jobs until then and vanish on their
own). Inbox is your triage queue (queued/running/interrupted only). New
Theorem submits statements or files. Problem Library tracks corpora by source
tag with one-click Prove. Job Inspector streams attempts live with cancel.
Tools/Skills browse the live registries. Logs tails the server log with level
filters. Settings shows provider cards, the model list, and onboarding facts.
Help renders the docs. That is the whole app — if a button ever shows stale
data, the backend behind it is down, not the button.

## 13. API reference

All endpoints are same-origin under `/api/` via the Vite proxy (absolute
backend URLs only behind the Tauri gate). `GET /api/health` → `{"status":
"ok", "server", "version", "lean_workspace_ok"}`. `GET /api/status` → full
status with workspace detail, DB path/size, config snapshot, and job counts.
`GET /api/capabilities` → server, version, transport, and the 10-tool
registry. `GET /api/v1/diagnostics` → tools, system, counts, live tasks, and
the last 20 ERROR log lines (the CUA smoke surface). `GET /api/logs?limit=200
&level=` → `{path, exists, count, entries[]}`. `GET /api/jobs?status=&limit=`
→ `{count, jobs[]}`; `POST /api/jobs` with
`{statement, lean_stub?, hints?, tier?, parallel_agents?, max_turns?}` →
`{job_id, status}`; `POST /api/jobs/lean-file` with `{lean_source,
description?, ...}` → `{job_id, status}` (400 without `sorry`);
`GET /api/jobs/{id}` → job plus 100 attempts; `POST /api/jobs/{id}/cancel`;
`GET /api/jobs/{id}/stream` → SSE (`attempt` events, heartbeats,
`done`). `GET/POST /api/problems`, `GET /api/problems/{id}`,
`PUT/DELETE /api/problems/{id}` → library CRUD with `{title, statement,
lean_source?, source?, difficulty?, tags?, notes?}`. `GET /api/skills` →
`{skills[]}`; `GET /api/skills/{name}` → raw markdown. `GET /api/docs` →
allowlist with availability; `GET /api/docs/{name}` → markdown.
`GET /api/llm/providers` → local detected flags + cloud configured flags
(never keys); `GET /api/llm/discover` → `{ollama, lm_studio}` booleans;
`GET /api/llm/models` → live Ollama list or curated fallback with a `live`
flag; `GET /api/llm/onboarding` → starter facts + recommended path.
`POST /api/llm/chat` with `{messages[], system?, tier?}` → `{reply, tier,
model}`; `POST /api/llm/chat/stream` → SSE OpenAI-style `choices[].delta`
chunks plus `[DONE]` (Anthropic tiers arrive as one chunk — same shape,
fewer events). `POST /api/shutdown` → `{"status": "shutting_down"}`, process
exits ~500 ms later. Errors are JSON with `detail`, except the job stream
which answers 404 JSON for unknown ids.

## 14. Troubleshooting

`validate_lean` returns `status: "pending"` → workspace still building; poll,
do not reconfigure. `status: "error"` → `config.toml` paths wrong; compare
with `config.example.toml` and confirm `lake.exe` exists at the configured
path. `unknown identifier 'Mathlib...'` on every compile → file missing
`import Mathlib` or workspace lacks oleans (`lake exe cache get` + `lake
build`). Tier-2 401s → `DEEPSEEK_API_KEY` unset in the server's environment
(restart the server after exporting it — env is read at call time per tier,
but the process must inherit it). Tier-3 key errors likewise for
`ANTHROPIC_API_KEY`. Chat "unreachable" → backend down (start it) or tier-1
Ollama down (check Settings → Test providers). Dashboard "Backend offline" →
`uv run python -m webapp.backend.main` (needs the `web` extra installed).
Empty problem library → it starts empty by design; create entries or import a
corpus. `verify_proof` `supported: false` → expected below Lean 4.35.0; see
`VERIFIED_KERNELS.md`. Port conflicts on 10867/10868 → stop the duplicate
backend/frontend (the fleet launcher clears zombies; bare runs do not).
Windows path pain → always absolute paths, `pathlib`, no string
concatenation; Lean paths come from config, never hardcoded. Frontend shows
"Backend offline" but the backend process is running → the Vite proxy target
drifted from the backend port: confirm `vite.config.ts` proxies `/api` to
`127.0.0.1:10867` and the backend actually bound there (check the log's
"ready on port" line). Chat streams stall mid-reply → the provider timed out;
tier-1 Ollama unloaded the model (first token after idle is slow) or a cloud
tier hit rate limits — retry once, then drop a tier and compare. Job stuck in
`queued` forever → no Runner picked it up: the server restarted without the
lifespan context, or the DB is locked by a second process (run exactly one
server per database). `sorry_count` mismatches the file → the file has
`sorry` inside comments or strings; the submit path counts textually, the
agent fills syntactic holes — harmless, but clean the file to avoid
confusion. `list_attempts` empty for a running job → attempts flush per turn;
poll again after 30 seconds. MOCK cards linger after setup → hard-refresh:
the dashboard caches nothing, so lingering MOCK means `/api/status` still
reports workspace-not-ready — fix the workspace, not the browser. Biome or
`tsc` fails after your edit → run `bun run biome:ci` and `bun run check`
locally; both must pass before any commit, exactly as CI runs them.

## 15. FAQ (continued)

Can two servers share one database? No — one server per SQLite file; a second
process sees locked writes and orphaned ownership. Run one MCP server and let
the web backend share the same file only if they coordinate (today they are
separate processes — prefer one or the other per database). Why do cloud
tiers never trigger locally? Escalation thresholds count stalled turns;
scouting configs with `max_turns: 20` end before tier 2 arms at turn 20 —
raise budgets deliberately when you want escalation. Why does the same theorem
solve one day and fail the next? LLM sampling is nondeterministic and Mathlib
checkouts drift; pin the model version and Mathlib revision for reproducible
campaigns, and keep `parallel_agents` ≥ 4 to smooth variance. Should hints
contain full tactics or just names? Names plus one-line strategy notes work
best; full tactic blocks get pasted verbatim and shatter on small mismatches,
while names let the agent adapt. How do I prove something with hypotheses?
Put them in the statement (`(h : P) : Q`) or the stub — the agents see the
whole file, context included. Can the prover invent definitions? It fills
proofs, not specifications; new definitions belong in your stub, reviewed by
you. What hardware actually matters? Single-thread Lean compile speed and RAM
per concurrent compile; GPU matters only for tier-1 token throughput. When
should I give up on a goal? After hints + tier 2 + 200 turns with no new
error classes appearing — further budget buys repetition, not insight.
Formalize a simpler lemma instead and build up. What is the single most
common beginner mistake? Submitting English instead of Lean: `statement` must
be a Lean proposition (`∀ n : Nat, ...`), never prose ("prove that the sum
..."). The server wraps prose in a stub that cannot compile, and every turn
burns proving nothing. Formalize first with `validate_lean` on a `sorry`
skeleton, then submit for search.

## 15. FAQ

Do I need to know Lean to use this? To submit and read results, no — but
formalizing your own theorems (Tier 4) requires it; `docs/LEAN_PRIMER.md`
covers the essentials. Which tier should I start at? Always tier 1; escalate
on evidence (`STUCK`, repeated failures), not hope. How long does a proof
take? Seconds for textbook lemmas, minutes for olympiad problems, unbounded
for research — that is what `max_turns` and polling are for. Can it prove
anything? No: undecidable goals, missing Mathlib coverage, and context-window
limits on long error chains all stop it; premise selection (`hints`) is the
highest-leverage help you can give. Does the webapp replace Claude Desktop?
No — the MCP server is the agent interface, the webapp is the operator
console; they share the database. Is my proof really correct? If `validate`
says proven and the statement hash matches your goal, yes — and `verify_proof`
adds independent kernels for high stakes. What does it cost to run a
benchmark? See the cost worksheet in the system prompt: scout cheap, spend on
survivors, cancel stuck agents early. Where do I report breakage? Failing
`smoke_test.py` output plus the relevant `/api/v1/diagnostics` excerpt is the
ideal bug report.

## 16. Learning Lean alongside the prover

Use the prover as a tutor, not a crutch. After every solve, read the winning
proof line by line: identify the induction variable, the rewritten lemmas,
and the closing tactic — then re-prove the same theorem by hand in
`validate_lean` without looking. Failed attempts teach more: each compiler
error in `list_attempts` is a lesson about what Lean actually accepts, which
is why reading trajectories (Tutorial 3) doubles as study. Pair this with
`docs/LEAN_PRIMER.md` for the language basics and the Chat page's Theorem
Coach personality for Socratic guidance that asks before telling. Within a
month of this loop — submit, read, re-prove, ask — you will write tactic
proofs unassisted, and your hints to the prover will get sharper in exactly
the way that raises its solve rate on your problems.

## 17. Three worked proofs, start to finish

Example one — zero is a right identity. Input file: `import Mathlib` blank
line `theorem add_zero_self (n : Nat) : n + 0 = n := by` newline two spaces
`sorry`. Submit at tier 1, 2 agents, 20 turns. The model proposes `simp`
(closes via `Nat.add_zero`), or `rfl` (definitionally true), or `omega`.
Any sorry-free compile wins; expect completion inside three turns. This is
your smoke proof for every new install: if tier 1 cannot do this in 20
turns, the model is not loaded, not the theorem hard — check Ollama.

Example two — sum formula (the README showcase). Input is the two-line
statement with `sorry`. Tier 1, 4 agents, 100 turns. Watch `list_attempts`:
early turns try `simp` salads that fail with `unsolved goals`; the winning
line is almost always induction on `n`, `Finset.sum_range_succ` to peel the
last summand, `ring_nf` to normalize, then the induction hypothesis with
`linarith` or a final `ring`. If your run stalls, resubmit with
`hints` set to `Finset.sum_range_succ induction` — that single hint converts
most failures into solves and demonstrates the whole premise-selection idea
in one experiment.

Example three — map composition. Statement:
`theorem map_comp (f : β → γ) (g : α → β) (l : List α) : List.map (f ∘ g) l = (List.map f ∘ List.map g) l`
with `sorry`. Bare tier-1 runs guess lemma names and die on `unknown
identifier`; the fix is `get_mathlib_search("map composition")`, which
returns the current name (`List.map_comp_map`), resubmitted as a hint. Moral
that generalizes: whenever the domain has a canonical lemma just out of the
model's training distribution, one search call is worth fifty turns.

## 18. Induction, calc, and simp — the three workhorses

Induction proves `∀ n` goals by zero-case plus step-case: `induction n with
| zero => <close it> | succ n ih => <use ih>`. Name the hypothesis (`ih`)
and rewrite with it explicitly (`rw [ih]` or `omega`/`linarith` with `ih` in
context) rather than hoping automation finds it. `cases` is induction without
the hypothesis — right for `Option`, `List`, and single-step splits. `calc`
proves equalities as readable chains: each `_ = step := by justification`
compiles independently, so failures point at one link; keep steps small
enough that `rfl`, `ring`, or one rewrite closes each. `simp` is a
conditional rewriting engine, not magic: `simp` alone uses the global set
(slow, sometimes looping); `simp [h1, h2]` uses your lemmas plus computation;
`simp only [...]` uses exactly your list (predictable, debuggable). When
`simp` loops, shrink to `simp only` and add lemmas one at a time. `simp?`
shows what fired — paste its output back as an explicit `simp only` and the
proof becomes robust against Mathlib changes. `omega` decides linear Nat/Int
goals completely: if the goal is linear arithmetic and `omega` fails, the
goal is probably false as stated — recheck the statement before burning more
turns. `ring`/`ring_nf` normalize semiring expressions; follow with `linarith`
when hypotheses relate the normalized forms.

## 19. Navigating Mathlib without drowning

Mathlib has 800k+ theorems; names follow conventions worth learning:
`Namespace.lemma_shape` (`Nat.add_comm`, `Finset.sum_range_succ`,
`List.map_comp_map`). Dots separate namespaces, underscores separate words,
`_iff`/`_eq`/`_le` suffixes give the logical shape. Search order when stuck:
first `get_mathlib_search` with plain words, then LeanSearch in a browser for
context, then `#check` the candidate in `validate_lean` before spending agent
turns on it. Common namespaces: `Nat`/`Int`/`Rat` arithmetic, `Finset`/`Fintype`
finite collections, `List`/`Array` sequences, `Set` (note: `Set.mem_inter_iff`
style lemmas, membership-first), `Function` composition, `BigOperators` (needs
`open scoped BigOperators` for `∑`/`∏` notation). Version drift is real: lemma
names change between Mathlib releases, and the LLM's training data lags — a
name the model swears by may not exist in your checkout. Trust `#check`, not
confidence.

## 20. Error-message field guide (15 entries)

`unknown identifier`: misspelled or moved lemma — search, don't guess twice.
`failed to synthesize OfNat/HAdd/Membership/...`: missing instance or scope —
open the scope or annotate the type. `unexpected token`: syntax slip, check
brackets/commas/indentation. `maximum recursion depth`: equation-compiler
loop or simp explosion — `decreasing_by`, smaller simp set. `unsolved goals`:
partial progress — finish with combinators or bullets. `type mismatch A ≠ B`:
`#check` both sides, add coercions or `ext`. `simp made no progress`: wrong
tool for this goal — restructure. `assumption failed`: `have` the fact first.
`declaration uses 'sorry'`: that IS the assignment — fill it, never delete
the declaration. `warning: unused variable`: harmless unless it is the
variable your proof needed. `error: tactic failed, there are no goals`:
tactic ran after the goal closed — drop trailing tactics. `rewrite failed,
motive is not type correct`: `rw` at a dependent position — generalize first
or use `conv`. `linarith failed to find a contradiction`: hypotheses
insufficient or nonlinear — add facts or switch to `nlinarith`. `omega
failed`: goal not linear arithmetic — wrong approach or false goal.

## 21. Importing a MiniF2F file, click by click

Clone miniF2F beside (not inside) the repo. Open one `.lean` file; confirm it
has `sorry` and note its imports (usually plain, no Mathlib import needed
beyond the workspace environment). Copy the entire file text. Call
`submit_lean_file` with that text and `description` set to the filename.
Record the returned `job_id` and `sorry_count`. Poll `get_proof_status`
until terminal. On `complete`, save `proof` next to the original with a
`-proved` suffix and run it through `validate_lean` once more from a clean
context. On `failed`, pull `list_attempts` with `last_n: 10`, classify the
dominant error with the field guide above, and requeue with hints or a higher
tier. Log the outcome (file, tier, agents, turns, result) in the problem
library with source `minif2F` — after twenty files you will have a personal
solve-rate table that predicts budgets better than any rule of thumb.

## 22. Tuning agents, turns, and timeouts

`parallel_agents` trades wall-clock for spend: 2–4 for scouting, 8–16 for
final pushes on hard goals (diminishing returns past 8 on easy ones).
`max_turns` trades completeness for money: 20 scouting, 100 standard, 500+
only with Tier-3 approval. `compile_timeout` at 120 s fits Mathlib imports;
raise it only if `validate_lean` itself times out on your machine, lower it
to fail fast on weak hardware. `max_concurrent_compiles` follows RAM: each
Lean process with Mathlib resident costs gigabytes — 4 suits 64 GB, 2 suits
16 GB, 1 for laptops. Watch the JobInspector stream during tuning: all agents
failing identically means the stub or hints are wrong (fix inputs, not
knobs); agents diverging then one winning means the knobs are right.

## 23. Reading logs and diagnostics like an operator

`GET /api/logs?level=ERROR&limit=100` shows recent failures without
touching the box; `level=WARNING` catches escalation and retry noise.
`GET /api/v1/diagnostics` bundles tools, workspace state, counts, live
tasks, and recent errors — paste both outputs into any bug report instead of
screenshots. SECURITY lines (tamper rejections) deserve immediate attention:
someone — or some agent — tried to edit a theorem statement. Repeated
`LLM_ERROR` lines with key messages mean credentials rotated or expired.
`QueueFull` drops in the event bus mean a stream consumer died mid-job;
harmless, but restart the viewer. Log files roll nowhere automatically yet —
archive `logs/leanforge.log` before it grows past a few hundred megabytes.

## 24. Upgrading the toolchain (4.31 to 4.35+)

`verify_proof` stays in `supported: false` until the workspace toolchain
reaches Lean 4.35.0. To upgrade: `elan toolchain install
leanprover/lean4:v4.35.0`, set it default or per-workspace via
`elan override`, rebuild the workspace (`lake build` — budget an hour, it
recompiles Mathlib), rerun `lake exe cache get` for matching oleans, then
`validate_lean` the trivial example and one old `complete` proof (guards
against Mathlib drift silently changing behavior). Only then trust
`verify_proof` output. Keep the old toolchain installed until the new one
has solved at least one real job — elan makes toolchains cheap, rebuilds are
not.

## 25. Contributing results back

Solved benchmark problems are worth sharing: upstream MiniF2F/PutnamBench
fixes as PRs with the proven file, and report AlphaProof Nexus stub solves
with toolchain + Mathlib revision + model + turns (reproducibility needs all
four). Before publishing any proof, rerun it through `validate_lean` from a
clean checkout and, when eligible, `verify_proof` — a proof that only
compiles in your workspace helps nobody. Scrub logs of API keys before
pasting (keys never appear in API responses by design, but shell history and
env dumps are your responsibility). If you extend the server, keep the
contract: every tool returns `success` + `message`, every list page keeps
search/filter/sort/paginate/count, and every new endpoint appears in
`docs/TOOLS.md`, `llms-full.txt`, and the capabilities registry together —
registry, docs, and code drift apart silently otherwise.

## 26. Ten good first theorems

New users should calibrate on goals with known-short proofs before spending
budget. In order: `∀ n : Nat, n + 0 = n` (`simp`); `1 + 1 = 2`
(`norm_num` or `rfl`); `∀ (a b : Nat), a + b = b + a` (`omega` or induction);
`∀ n : Nat, n < n + 1` (`Nat.lt_succ_self` territory — try `omega` first);
`∀ (x : ℝ), x ^ 2 ≥ 0` (`sq_nonneg` — a one-lemma proof testing premise
recall); `∀ (l : List α), l ++ [] = l` (`simp`); `∃ p : Nat, Nat.Prime p ∧
p > 100` (witness construction — try `⟨101, by decide⟩` by hand first, then
let the agent find it); the sum formula (induction showcase); map composition
(premise-selection showcase); `∀ (a b : Int), (a + b) ^ 2 = a ^ 2 + 2 * a * b
+ b ^ 2` (`ring`). Solve all ten at tier 1 before touching tier 2 — if any
fails, the failure is in your setup or your statement, and tier 2 money will
not fix it.

## 27. Glossary in plain language

Theorem: a statement plus its proof, checked by the kernel. Lemma: a helper
theorem reused inside bigger proofs. Tactic: one proof step (`simp`,
`omega`, `rw`, `induction`). Goal state: what remains to prove after each
step — read it in every compiler error. sorry: the hole marker; your job is
to delete them all. elaborator: Lean's front end that turns tactic scripts
into proof terms (its errors are what agents learn from). olean: cached
compiled Mathlib so imports take seconds not hours. Lakefile: the workspace
manifest declaring the Mathlib dependency. Turn/attempt/job: one
propose→compile cycle / its database record / the whole search. Escalation:
moving a stalled subagent to a stronger, pricier model tier. Premise
selection: finding the right lemmas first (your highest-leverage assist).
Kernel (re-)verification: checking a proof with independent implementations
so one compiler bug cannot certify a falsehood.

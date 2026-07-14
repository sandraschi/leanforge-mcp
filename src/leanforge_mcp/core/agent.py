"""
Core proof search agent.
Implements Agent A from AlphaProof Nexus: independent subagents,
LLM propose → Lean compile → error feedback → repeat.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from leanforge_mcp.core.lean_lexer import extract_signatures

if TYPE_CHECKING:
    from leanforge_mcp.core.lean_client import LeanClient
    from leanforge_mcp.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Lean 4 theorem prover working with Mathlib.

You will be shown a Lean 4 file with `sorry` placeholders in place of proofs.
Your job is to replace every `sorry` with a valid Lean 4 tactic proof.

RULES:
1. NEVER modify the theorem statement itself -- only fill `sorry`
2. You may introduce helper lemmas (using `lemma` or `have`) before `sorry`
3. Use Mathlib tactics: simp, ring, linarith, omega, exact, apply, induction, cases, rw
4. If stuck, try a completely different proof strategy
5. Respond ONLY with a search-replace block in this exact format:

<<<REPLACE
[exact text to replace, copied verbatim from the file]
===
[replacement text]
REPLACE>>>

If you cannot make progress, respond with:
<<<STUCK
[brief explanation of what you tried and why you're stuck]
STUCK>>>
"""

REPLACE_PATTERN = re.compile(
    r"<<<REPLACE\n(.*?)\n===\n(.*?)\nREPLACE>>>",
    re.DOTALL,
)
STUCK_PATTERN = re.compile(r"<<<STUCK\n(.*?)\nSTUCK>>>", re.DOTALL)

# AttemptHook: optional async callback to persist each attempt (job_manager.record_attempt).
# Signature: (agent_index, turn, lean_source, compiler_output, llm_model, success) -> None
AttemptHook = Callable[[int, int, str, str, str, bool], Awaitable[None]]

# CancelPoll: optional async callable checked once per turn for cross-process
# cancellation (docs/ASSESSMENT_2026-06-24.md P1-6). Kept DB-agnostic here,
# same injection pattern as AttemptHook -- Runner._run binds the real
# implementation to JobManager.is_cancel_requested for a specific job_id.
CancelPoll = Callable[[], Awaitable[bool]]


@dataclass
class Attempt:
    turn: int
    lean_source: str
    compiler_output: str
    llm_model: str
    success: bool
    edit_applied: str = ""


@dataclass
class SubagentResult:
    agent_index: int
    proven: bool
    final_source: str
    attempts: list[Attempt] = field(default_factory=list)
    failure_reason: str = ""


def extract_statement(source: str) -> str:
    """
    Extract the full theorem/lemma/example signature(s) -- everything from
    the keyword up to and including the `:=` that begins the proof body.
    Comment-stripped, whitespace-normalised. Delegates to lean_lexer, which
    tracks bracket depth so a default-arg binder's own `:=` (e.g.
    `(n : Nat := 0)`) is not mistaken for the proof-start `:=` -- a plain
    regex up to the first `:=` truncates the signature before the actual
    return type in that case (docs/ASSESSMENT_2026-06-24.md P1-2).

    Returns a normalised string of all signatures concatenated. Kept as a
    general-purpose utility (e.g. for hashing/logging); the tamper GUARD
    itself uses the name-keyed check below, not a single hash of this
    string, because a single hash cannot distinguish "agent added a new
    helper lemma" (allowed) from "agent changed the real statement"
    (forbidden) -- see capture_original_signatures / check_tamper.
    """
    return "\n".join(s.clean_text for s in extract_signatures(source))


def _statement_hash(source: str) -> str:
    """Hash of extract_statement's output. General utility (e.g. dedup/
    logging) -- NOT the tamper guard; see check_tamper."""
    return hashlib.sha256(extract_statement(source).encode()).hexdigest()


@dataclass(frozen=True)
class OriginalSignatures:
    """Snapshot of a job's protected declarations, captured once at job
    start from the initial source. named maps declaration name -> its
    exact signature text; anon holds anonymous `example` signatures in
    order (Lean gives examples no name to key on, and the agent has no
    legitimate reason to touch them at all)."""

    named: dict[str, str]
    anon: list[str]


def capture_original_signatures(source: str) -> OriginalSignatures:
    sigs = extract_signatures(source)
    named = {s.name: s.clean_text for s in sigs if s.name}
    anon = [s.clean_text for s in sigs if not s.name]
    return OriginalSignatures(named=named, anon=anon)


def check_tamper(original: OriginalSignatures, new_source: str) -> str | None:
    """Verify every ORIGINAL declaration is still present, unmodified, under
    its original name in new_source. Returns None if the guard is satisfied,
    or a human-readable violation message otherwise.

    Deliberately keyed on declaration NAME, not on "does the original text
    appear anywhere in the file" -- a purely textual presence check can be
    defeated by adding a decoy lemma with a new name that reproduces the
    original statement's text verbatim, while the agent quietly weakens the
    real theorem (same original name, now-different signature) elsewhere.
    Keying on name closes that hole: it also rejects renaming the original
    declaration, which the system prompt's "never modify the statement"
    rule implicitly forbids anyway.

    New named declarations (helper lemmas/theorems the agent introduces)
    are unrestricted -- the agent may add, edit, or remove its own helpers
    freely across turns, since their names never appear in `original`.
    """
    new_sigs = extract_signatures(new_source)
    new_named = {s.name: s.clean_text for s in new_sigs if s.name}
    new_anon = [s.clean_text for s in new_sigs if not s.name]

    for name, sig in original.named.items():
        if name not in new_named:
            return f"Original declaration '{name}' is missing (renamed or deleted)."
        if new_named[name] != sig:
            return f"Original declaration '{name}' signature was modified."

    if new_anon != original.anon:
        return (
            "An anonymous `example` declaration was added, removed, or "
            "modified. Only `sorry` bodies and new named helper lemmas may change."
        )

    return None


def _apply_edit(source: str, old: str, new: str) -> str | None:
    """Apply search-replace edit. Returns None if old not found exactly once."""
    if source.count(old) != 1:
        return None
    return source.replace(old, new, 1)


# Best-effort, substring-based classification of Lean compiler error
# messages into coarse buckets for the rolling "failed strategies" summary
# (docs/ASSESSMENT_2026-06-24.md P2-4). These substrings match Lean 4's
# well-documented core error headers (unsolved goals, type mismatch,
# unknown identifier/constant) with reasonable confidence; tactic-specific
# messages (simp/linarith/ring/omega) are matched more loosely since exact
# wording varies by Mathlib version. NOT verified against live compiler
# output in this environment -- worth tightening once real proof runs
# produce a corpus to sample against.
_ERROR_CLASS_PATTERNS: list[tuple[str, str]] = [
    ("unsolved goals", "unsolved goals"),
    ("type mismatch", "type mismatch"),
    ("unknown identifier", "unknown identifier"),
    ("unknown constant", "unknown constant"),
    ("unknown tactic", "unknown tactic"),
    ("function expected", "function expected"),
    ("simp made no progress", "simp made no progress"),
    ("linarith failed", "linarith failed"),
    ("ring failed", "ring failed"),
    ("omega", "omega failed"),
    ("failed to synthesize", "typeclass synthesis failed"),
    ("motive is not type correct", "motive type error"),
    ("deterministic timeout", "compiler timeout"),
    ("maximum recursion depth", "recursion depth exceeded"),
]


def _classify_error(message: str) -> str:
    """Coarse bucket for a Lean compiler error, for the failed-strategies
    summary. Falls back to the error's own first line (truncated) so an
    unrecognised message still gets a stable, distinguishing label rather
    than collapsing into one useless catch-all bucket."""
    lower = message.lower()
    for substring, label in _ERROR_CLASS_PATTERNS:
        if substring in lower:
            return label
    first_line = message.strip().splitlines()[0] if message.strip() else "(empty error)"
    return first_line[:60]


async def run_subagent(
    agent_index: int,
    initial_source: str,
    llm: LLMClient,
    lean: LeanClient,
    max_turns: int,
    on_attempt: AttemptHook | None = None,
    is_cancelled: CancelPoll | None = None,
) -> SubagentResult:
    """
    Single subagent: loop LLM propose → Lean compile until proven or budget exhausted.
    If on_attempt is provided, each completed turn is persisted via that callback.
    """
    if lean.setup_in_progress:
        return SubagentResult(
            agent_index=agent_index,
            proven=False,
            final_source=initial_source,
            failure_reason=f"Lean setup in progress: {lean.setup_status}",
        )
    if lean.setup_error:
        return SubagentResult(
            agent_index=agent_index,
            proven=False,
            final_source=initial_source,
            failure_reason=f"Lean setup failed: {lean.setup_error}",
        )

    source = initial_source
    original_sigs = capture_original_signatures(source)
    attempts: list[Attempt] = []
    last_error = ""
    # P2-4 stateless-prompting mitigation, both local to this subagent's
    # own turn loop (not persisted -- each subagent's run is independent):
    seen_edits: dict[str, str] = {}  # hash(old,new) -> error, for exact-repeat detection
    failed_strategies: list[tuple[str, str]] = []  # (tactic snippet, error class), deduped

    logger.info("Subagent %d starting, max_turns=%d", agent_index, max_turns)

    for turn in range(max_turns):
        if is_cancelled is not None and await is_cancelled():
            logger.info(
                "Subagent %d observed cross-process cancel request at turn %d",
                agent_index,
                turn,
            )
            return SubagentResult(
                agent_index=agent_index,
                proven=False,
                final_source=source,
                attempts=attempts,
                failure_reason="Cancelled",
            )

        model_used = llm.current_model
        user_message = f"Current Lean 4 file:\n```lean\n{source}\n```"
        if last_error:
            user_message += (
                f"\n\nLean compiler error from last attempt:\n```\n{last_error}\n```"
                "\n\nPlease fix the error and continue."
            )
        else:
            user_message += "\n\nPlease fill all `sorry` placeholders with valid proofs."

        if failed_strategies:
            # Rolling memory across turns (docs/ASSESSMENT_2026-06-24.md
            # P2-4): each turn is otherwise a fresh LLM call with no memory
            # of what was already tried, so the model can loop on the same
            # failing tactic. Cap at the most recent 8 to bound prompt growth.
            strategies_block = "\n".join(
                f"- `{tactic}` -> {error_class}"
                for tactic, error_class in failed_strategies[-8:]
            )
            user_message += (
                f"\n\nStrategies already tried and failed this session "
                f"(do NOT repeat these):\n{strategies_block}"
            )

        try:
            response = await llm.complete(system=SYSTEM_PROMPT, user=user_message)
        except Exception as exc:
            logger.warning("Subagent %d LLM error at turn %d: %s", agent_index, turn, exc)
            last_error = f"LLM error: {exc}"
            if on_attempt:
                await on_attempt(
                    agent_index, turn, source, f"LLM_ERROR: {exc}", model_used, False
                )
            await llm.maybe_escalate(turn)
            continue

        replace_match = REPLACE_PATTERN.search(response)
        stuck_match = STUCK_PATTERN.search(response)

        if stuck_match:
            note = stuck_match.group(1)[:200]
            logger.info("Subagent %d stuck at turn %d: %s", agent_index, turn, note)
            last_error = (
                f"Previous strategy failed. Try a completely different approach.\nYour note: {note}"
            )
            att = Attempt(turn, source, "STUCK", model_used, False, "(stuck -- no edit)")
            attempts.append(att)
            if on_attempt:
                await on_attempt(agent_index, turn, source, "STUCK", model_used, False)
            await llm.maybe_escalate(turn)
            continue

        if not replace_match:
            logger.debug("Subagent %d no edit parsed at turn %d", agent_index, turn)
            last_error = (
                "Could not parse your response. Use the <<<REPLACE...REPLACE>>> format exactly."
            )
            if on_attempt:
                await on_attempt(agent_index, turn, source, "PARSE_ERROR", model_used, False)
            await llm.maybe_escalate(turn)
            continue

        old_text = replace_match.group(1)
        new_text = replace_match.group(2)

        # Repeated-edit detection (P2-4): the model has no memory between
        # turns and can resend the EXACT same edit it already tried. Skip
        # re-compiling (saves a real Lean compile, ~30-60s) and push back
        # immediately instead.
        edit_key = hashlib.sha256(f"{old_text}\x00{new_text}".encode()).hexdigest()
        if edit_key in seen_edits:
            last_error = (
                "You already tried this EXACT edit and it failed with:\n"
                f"{seen_edits[edit_key][:300]}\n\n"
                "This is a repeated attempt -- you must try a genuinely "
                "different tactic or approach, not resend the same edit."
            )
            if on_attempt:
                await on_attempt(
                    agent_index, turn, source, "REPEATED_EDIT_SKIPPED", model_used, False
                )
            await llm.maybe_escalate(turn)
            continue

        new_source = _apply_edit(source, old_text, new_text)
        if new_source is None:
            last_error = (
                "The text you tried to replace was not found (or appeared more than once). "
                "Copy the text to replace verbatim from the file."
            )
            seen_edits[edit_key] = last_error
            if on_attempt:
                await on_attempt(agent_index, turn, source, "EDIT_NOT_FOUND", model_used, False)
            await llm.maybe_escalate(turn)
            continue

        # Tamper guard: name-keyed check (permits new helper lemmas/theorems
        # under new names, rejects any change to an original declaration's
        # signature under its original name -- see check_tamper docstring
        # for why this must be name-keyed rather than a single hash).
        violation = check_tamper(original_sigs, new_source)
        if violation is not None:
            logger.warning(
                "Subagent %d attempted to modify a protected declaration at turn %d: %s",
                agent_index,
                turn,
                violation,
            )
            last_error = (
                f"You modified a protected declaration: {violation} "
                "Only fill `sorry` placeholders and add NEW helper lemmas "
                "(with new names) before the theorem. Never rename or alter "
                "an original declaration's signature."
            )
            seen_edits[edit_key] = last_error
            if on_attempt:
                await on_attempt(
                    agent_index, turn, source, f"TAMPER_REJECTED: {violation}", model_used, False
                )
            continue

        source = new_source

        result = await lean.compile(source)
        compiler_output = result.error_message or "(no errors)"

        att = Attempt(
            turn=turn,
            lean_source=source,
            compiler_output=compiler_output,
            llm_model=model_used,
            success=result.proven,
            edit_applied=f"{old_text[:60]}... -> {new_text[:60]}...",
        )
        attempts.append(att)
        if on_attempt:
            await on_attempt(agent_index, turn, source, compiler_output, model_used, result.proven)

        if result.proven:
            logger.info("Subagent %d PROVED at turn %d", agent_index, turn)
            return SubagentResult(
                agent_index=agent_index,
                proven=True,
                final_source=source,
                attempts=attempts,
            )

        last_error = result.error_message
        seen_edits[edit_key] = last_error
        error_class = _classify_error(last_error)
        tactic_summary = new_text.strip().replace("\n", " ")[:80]
        if (tactic_summary, error_class) not in failed_strategies:
            failed_strategies.append((tactic_summary, error_class))
        logger.debug("Subagent %d turn %d: %d errors", agent_index, turn, len(result.errors))
        await llm.maybe_escalate(turn)

    logger.info("Subagent %d budget exhausted after %d turns", agent_index, max_turns)
    return SubagentResult(
        agent_index=agent_index,
        proven=False,
        final_source=source,
        attempts=attempts,
        failure_reason=f"Budget exhausted after {max_turns} turns",
    )


async def run_parallel_agents(
    source: str,
    llm_factory: Callable[[], LLMClient],
    lean: LeanClient,
    n_agents: int,
    max_turns: int,
    on_attempt: AttemptHook | None = None,
    is_cancelled: CancelPoll | None = None,
) -> SubagentResult | None:
    """
    Run N subagents concurrently. Return first proven result, or None if all fail.
    llm_factory returns a fresh LLMClient per subagent (independent tier state).
    on_attempt, if given, is called once per completed turn per agent for persistence.
    is_cancelled, if given, is polled once per turn per agent; a job-level
    cross-process cancel (docs/ASSESSMENT_2026-06-24.md P1-6) causes every
    subagent to independently return a non-proven result at its next turn
    boundary, so this function's existing "no proven result -> return None"
    path already handles it -- Runner._run distinguishes cancelled-vs-failed
    by checking the same flag after this returns.
    """
    tasks = [
        asyncio.create_task(
            run_subagent(i, source, llm_factory(), lean, max_turns, on_attempt, is_cancelled)
        )
        for i in range(n_agents)
    ]

    pending = set(tasks)
    try:
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                result = task.result()
                if result.proven:
                    for t in pending:
                        t.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    return result
    except asyncio.CancelledError:
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise

    return None

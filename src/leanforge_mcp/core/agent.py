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

if TYPE_CHECKING:
    from leanforge_mcp.core.lean_client import LeanClient
    from leanforge_mcp.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Lean 4 theorem prover working with Mathlib.

You will be shown a Lean 4 file with `sorry` placeholders in place of proofs.
Your job is to replace every `sorry` with a valid Lean 4 tactic proof.

RULES:
1. NEVER modify the theorem statement itself — only fill `sorry`
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
    Extract the full theorem/lemma signature(s) — everything from a
    `theorem`/`lemma`/`example` keyword up to and including the `:=` that begins
    the proof body. This captures MULTI-LINE signatures, which the naive
    line-prefix approach missed (a theorem statement often spans several lines).

    Returns a normalised string of all signatures concatenated. Used for tamper
    detection: the agent may change what comes AFTER `:=`, never what's before.
    """
    # Match: (theorem|lemma|example) ... := (non-greedy, up to first := at any depth)
    # We stop at the FIRST `:=` because that's where the proof body begins.
    pattern = re.compile(
        r"\b(theorem|lemma|example)\b.*?:=",
        re.DOTALL,
    )
    sigs = []
    for m in pattern.finditer(source):
        # Normalise whitespace so reformatting doesn't trip the guard
        sig = re.sub(r"\s+", " ", m.group(0)).strip()
        sigs.append(sig)
    return "\n".join(sigs)


def _statement_hash(source: str) -> str:
    """Hash the full normalised theorem signatures to detect tampering."""
    return hashlib.sha256(extract_statement(source).encode()).hexdigest()


def _apply_edit(source: str, old: str, new: str) -> str | None:
    """Apply search-replace edit. Returns None if old not found exactly once."""
    if source.count(old) != 1:
        return None
    return source.replace(old, new, 1)


async def run_subagent(
    agent_index: int,
    initial_source: str,
    llm: LLMClient,
    lean: LeanClient,
    max_turns: int,
    on_attempt: AttemptHook | None = None,
) -> SubagentResult:
    """
    Single subagent: loop LLM propose → Lean compile until proven or budget exhausted.
    If on_attempt is provided, each completed turn is persisted via that callback.
    """
    source = initial_source
    statement_hash = _statement_hash(source)
    attempts: list[Attempt] = []
    last_error = ""

    logger.info("Subagent %d starting, max_turns=%d", agent_index, max_turns)

    for turn in range(max_turns):
        user_message = f"Current Lean 4 file:\n```lean\n{source}\n```"
        if last_error:
            user_message += (
                f"\n\nLean compiler error from last attempt:\n```\n{last_error}\n```"
                "\n\nPlease fix the error and continue."
            )
        else:
            user_message += "\n\nPlease fill all `sorry` placeholders with valid proofs."

        try:
            response = await llm.complete(system=SYSTEM_PROMPT, user=user_message)
        except Exception as exc:
            logger.warning("Subagent %d LLM error at turn %d: %s", agent_index, turn, exc)
            last_error = f"LLM error: {exc}"
            continue

        model_used = llm.current_model

        replace_match = REPLACE_PATTERN.search(response)
        stuck_match = STUCK_PATTERN.search(response)

        if stuck_match:
            note = stuck_match.group(1)[:200]
            logger.info("Subagent %d stuck at turn %d: %s", agent_index, turn, note)
            last_error = (
                f"Previous strategy failed. Try a completely different approach.\nYour note: {note}"
            )
            att = Attempt(turn, source, "STUCK", model_used, False, "(stuck — no edit)")
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
            continue

        old_text = replace_match.group(1)
        new_text = replace_match.group(2)

        new_source = _apply_edit(source, old_text, new_text)
        if new_source is None:
            last_error = (
                "The text you tried to replace was not found (or appeared more than once). "
                "Copy the text to replace verbatim from the file."
            )
            continue

        # Tamper guard: full-signature hash, catches multi-line statement edits
        if _statement_hash(new_source) != statement_hash:
            logger.warning(
                "Subagent %d attempted to modify theorem statement at turn %d",
                agent_index,
                turn,
            )
            last_error = (
                "You modified the theorem statement. This is not allowed. "
                "Only fill `sorry` placeholders and add helper lemmas before the theorem."
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
) -> SubagentResult | None:
    """
    Run N subagents concurrently. Return first proven result, or None if all fail.
    llm_factory returns a fresh LLMClient per subagent (independent tier state).
    on_attempt, if given, is called once per completed turn per agent for persistence.
    """
    tasks = [
        asyncio.create_task(run_subagent(i, source, llm_factory(), lean, max_turns, on_attempt))
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

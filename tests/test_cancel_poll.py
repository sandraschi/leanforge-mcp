"""
Tests for the cross-process cancel poll (docs/ASSESSMENT_2026-06-24.md
P1-6, agent.py side). Confirms run_subagent checks is_cancelled BEFORE
touching llm or lean at all -- the stubs below raise if called, so any
regression that moves the check later (or removes it) fails loudly.
"""

from __future__ import annotations

import pytest

from leanforge_mcp.core.agent import run_parallel_agents, run_subagent


class ExplodingLLM:
    """Any call here means the cancel check didn't short-circuit early enough."""

    current_model = "should-never-be-read"

    async def complete(self, **kw):
        raise AssertionError("LLM.complete() called despite is_cancelled=True")

    async def maybe_escalate(self, turn):
        raise AssertionError("maybe_escalate() called despite is_cancelled=True")


class ExplodingLean:
    setup_in_progress = False
    setup_error = None

    async def compile(self, source):
        raise AssertionError("lean.compile() called despite is_cancelled=True")


@pytest.mark.asyncio
async def test_run_subagent_short_circuits_on_cancel_before_any_llm_or_lean_call():
    async def always_cancelled():
        return True

    result = await run_subagent(
        agent_index=0,
        initial_source="theorem foo : 1 = 1 := by\n  sorry\n",
        llm=ExplodingLLM(),
        lean=ExplodingLean(),
        max_turns=5,
        is_cancelled=always_cancelled,
    )
    assert result.proven is False
    assert result.failure_reason == "Cancelled"


@pytest.mark.asyncio
async def test_run_subagent_not_cancelled_reaches_llm():
    """Sanity check the harness itself: WITHOUT cancellation, the
    ExplodingLLM should in fact get called (proving the short-circuit
    test above is meaningful, not a false pass from some other bug)."""

    async def never_cancelled():
        return False

    with pytest.raises(AssertionError, match="despite is_cancelled=True"):
        await run_subagent(
            agent_index=0,
            initial_source="theorem foo : 1 = 1 := by\n  sorry\n",
            llm=ExplodingLLM(),
            lean=ExplodingLean(),
            max_turns=5,
            is_cancelled=never_cancelled,
        )


@pytest.mark.asyncio
async def test_run_parallel_agents_all_cancel_returns_none():
    async def always_cancelled():
        return True

    result = await run_parallel_agents(
        source="theorem foo : 1 = 1 := by\n  sorry\n",
        llm_factory=lambda: ExplodingLLM(),
        lean=ExplodingLean(),
        n_agents=3,
        max_turns=5,
        is_cancelled=always_cancelled,
    )
    assert result is None  # no proven winner -- Runner distinguishes via the DB flag

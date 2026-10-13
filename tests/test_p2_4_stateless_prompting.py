"""
Tests for P2-4 (docs/ASSESSMENT_2026-06-24.md): stateless prompting.
Error classification, repeated-edit detection, and the rolling
failed-strategies summary. No Lean/Mathlib needed -- stub llm/lean.
"""

from __future__ import annotations

import pytest

from leanforge_mcp.core.agent import _classify_error, run_subagent

# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------


def test_classify_unsolved_goals():
    assert _classify_error("unsolved goals\n\u22a2 n = n") == "unsolved goals"


def test_classify_type_mismatch():
    msg = "type mismatch\n  rfl\nhas type\n  a = a\nbut is expected to have type\n  a = b"
    assert _classify_error(msg) == "type mismatch"


def test_classify_unknown_identifier():
    assert _classify_error("unknown identifier 'foo_bar'") == "unknown identifier"


def test_classify_simp_no_progress():
    assert _classify_error("simp made no progress") == "simp made no progress"


def test_classify_falls_back_to_first_line():
    msg = "some completely novel error text never seen before\nwith more detail on line 2"
    result = _classify_error(msg)
    assert result == msg.splitlines()[0][:60]


def test_classify_empty_message():
    assert _classify_error("") == "(empty error)"


def test_classify_is_case_insensitive():
    assert _classify_error("UNSOLVED GOALS") == "unsolved goals"


# ---------------------------------------------------------------------------
# Repeated-edit detection: the model resends the exact same edit
# ---------------------------------------------------------------------------


class FakeCompileResult:
    def __init__(self, proven, error_message="", errors=None):
        self.proven = proven
        self.error_message = error_message
        self.errors = errors or []


class ScriptedLLM:
    """Returns a scripted sequence of responses, one per call. Records how
    many times complete()/maybe_escalate() were actually invoked, so tests
    can assert the repeated-edit path skipped a real turn."""

    current_model = "scripted-model"

    def __init__(self, responses):
        self._responses = list(responses)
        self.complete_calls = 0
        self.escalate_calls = 0

    async def complete(self, **kw):
        self.complete_calls += 1
        return self._responses[self.complete_calls - 1]

    async def maybe_escalate(self, turn):
        self.escalate_calls += 1


class CountingLean:
    """Always fails to compile with a fixed error. Counts real compile()
    calls so tests can assert a repeated edit did NOT trigger a second
    compile."""

    setup_in_progress = False
    setup_error = None

    def __init__(self, error_message="unsolved goals\n\u22a2 False"):
        self.error_message = error_message
        self.compile_calls = 0

    async def compile(self, source):
        self.compile_calls += 1
        return FakeCompileResult(proven=False, error_message=self.error_message, errors=["e"])


def _replace_block(old: str, new: str) -> str:
    return f"<<<REPLACE\n{old}\n===\n{new}\nREPLACE>>>"


@pytest.mark.asyncio
async def test_repeated_identical_edit_skips_recompile():
    """The core P2-4 regression: the model sends the SAME edit twice. The
    second occurrence must be caught BEFORE lean.compile() is called again
    -- compile_calls should be 1, not 2, after two identical proposals."""
    source = "theorem foo : 1 = 1 := by\n  sorry\n"
    same_edit = _replace_block("sorry", "omega")

    llm = ScriptedLLM([same_edit, same_edit, "<<<STUCK\ngiving up\nSTUCK>>>"])
    lean = CountingLean()

    result = await run_subagent(
        agent_index=0,
        initial_source=source,
        llm=llm,
        lean=lean,
        max_turns=5,
    )

    assert lean.compile_calls == 1  # second identical edit did NOT recompile
    assert result.proven is False


@pytest.mark.asyncio
async def test_different_edits_both_compile():
    """Sanity check: two DIFFERENT edits must both reach lean.compile() --
    proves the skip is specific to exact repeats, not over-broad."""
    source = "theorem foo : 1 = 1 := by\n  sorry\n"
    llm = ScriptedLLM(
        [
            _replace_block("sorry", "omega"),
            _replace_block("omega", "rfl"),
            "<<<STUCK\ngiving up\nSTUCK>>>",
        ]
    )
    lean = CountingLean()

    await run_subagent(agent_index=0, initial_source=source, llm=llm, lean=lean, max_turns=5)

    assert lean.compile_calls == 2


@pytest.mark.asyncio
async def test_failed_strategies_injected_into_next_prompt():
    """After a failed compile, the NEXT turn's prompt to the LLM must
    contain a summary of the failed tactic and its error class."""
    source = "theorem foo : 1 = 1 := by\n  sorry\n"
    llm = ScriptedLLM(
        [
            _replace_block("sorry", "omega"),
            "<<<STUCK\ngiving up\nSTUCK>>>",
        ]
    )
    lean = CountingLean(error_message="unsolved goals\n\u22a2 False")

    captured_messages = []
    original_complete = llm.complete

    async def spy_complete(**kw):
        captured_messages.append(kw.get("user", ""))
        return await original_complete(**kw)

    llm.complete = spy_complete

    # max_turns capped to the scripted response count: STUCK does not
    # terminate the loop, so with a larger budget the LLM stub would run
    # out of scripted responses and raise IndexError (harmlessly caught
    # by run_subagent's own error handling, but noisy for this assertion).
    await run_subagent(agent_index=0, initial_source=source, llm=llm, lean=lean, max_turns=2)

    assert len(captured_messages) == 2
    # First turn: no failed strategies yet.
    assert "Strategies already tried" not in captured_messages[0]
    # Second turn: the omega/unsolved-goals failure must be summarised.
    assert "Strategies already tried" in captured_messages[1]
    assert "omega" in captured_messages[1]
    assert "unsolved goals" in captured_messages[1]


@pytest.mark.asyncio
async def test_repeated_edit_message_references_prior_failure():
    """The pushback message on a repeated edit should quote/reference the
    prior failure, not just say 'try again' generically."""
    source = "theorem foo : 1 = 1 := by\n  sorry\n"
    same_edit = _replace_block("sorry", "omega")
    llm = ScriptedLLM([same_edit, same_edit, "<<<STUCK\ndone\nSTUCK>>>"])
    lean = CountingLean(error_message="unsolved goals\n\u22a2 False")

    captured_messages = []
    original_complete = llm.complete

    async def spy_complete(**kw):
        captured_messages.append(kw.get("user", ""))
        return await original_complete(**kw)

    llm.complete = spy_complete

    await run_subagent(agent_index=0, initial_source=source, llm=llm, lean=lean, max_turns=5)

    # Third call's prompt (after the repeated edit was rejected) should
    # carry the "already tried this EXACT edit" pushback as last_error.
    assert "already tried this EXACT edit" in captured_messages[2]

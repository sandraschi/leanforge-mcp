"""Regression tests for the sorry oracle.

Background: the 56/56 suite was green while `has_sorry` was ALWAYS False,
because every existing test drove stub lean objects and none of them ever fed
real `lake env lean` output through the parsing in LeanClient.compile(). Lean
4.31 emits the warning with BACKTICKS:

    SorryProbe.lean:2:8: warning: declaration uses `sorry`

while the code matched the literal "declaration uses 'sorry'" (straight
quotes). Result: a proof body of nothing but `sorry`, for the FALSE theorem
1 + 1 = 3, was reported as proven. These tests pin the real observed strings so
that can never come back silently.

No Lean toolchain required -- the compiler output is captured verbatim below.
"""

from __future__ import annotations

import pytest

from leanforge_mcp.core.lean_client import (
    WARNING_SORRY_RE,
    CompileResult,
    _sorry_in_code,
)

# Captured verbatim from lake env lean, Lean 4.31.0, Goliath, 2026-08-30.
LEAN_431_SORRY_OUTPUT = "SorryProbe.lean:2:8: warning: declaration uses `sorry`\n"
# The spelling older Lean releases used.
LEAN_OLD_SORRY_OUTPUT = "Foo.lean:2:8: warning: declaration uses 'sorry'\n"


@pytest.mark.parametrize(
    "output",
    [LEAN_431_SORRY_OUTPUT, LEAN_OLD_SORRY_OUTPUT],
    ids=["lean-4.31-backticks", "legacy-straight-quotes"],
)
def test_warning_regex_matches_both_quote_styles(output: str) -> None:
    assert WARNING_SORRY_RE.search(output) is not None


def test_warning_regex_does_not_match_clean_output() -> None:
    assert WARNING_SORRY_RE.search("") is None
    assert WARNING_SORRY_RE.search("Foo.lean:1:0: error: unknown tactic\n") is None


def test_sorry_proof_is_not_proven() -> None:
    """The exact case that was silently passing: sorry proof of a false theorem."""
    result = CompileResult(
        success=True,
        has_sorry=bool(WARNING_SORRY_RE.search(LEAN_431_SORRY_OUTPUT)),
        raw_stdout=LEAN_431_SORRY_OUTPUT,
    )
    assert result.has_sorry is True
    assert result.proven is False, "a sorry proof must never be reported as proven"


def test_secondary_guard_catches_sorry_in_code() -> None:
    assert _sorry_in_code("import Mathlib\ntheorem foo : 1 + 1 = 3 := by\n  sorry\n")
    assert _sorry_in_code("theorem foo : 1 = 1 := by sorry")


def test_secondary_guard_ignores_sorry_in_comments_and_strings() -> None:
    """Prose must not trip the guard -- that was the reason it was regex-shy."""
    assert not _sorry_in_code(
        "-- sorry, this one was tricky\ntheorem foo : 1 = 1 := by norm_num\n"
    )
    assert not _sorry_in_code(
        "/-- We are not sorry about this proof. -/\ntheorem foo : 1 = 1 := by rfl\n"
    )
    assert not _sorry_in_code('theorem foo : 1 = 1 := by\n  have s := "sorry"\n  rfl\n')


def test_secondary_guard_ignores_sorry_prefixed_identifiers() -> None:
    assert not _sorry_in_code("theorem foo : 1 = 1 := by\n  exact sorryAx_free\n")


def test_clean_proof_is_proven() -> None:
    result = CompileResult(
        success=True,
        has_sorry=bool(WARNING_SORRY_RE.search("")) or _sorry_in_code(
            "import Mathlib\nexample : 1 + 1 = 2 := by norm_num\n"
        ),
    )
    assert result.proven is True

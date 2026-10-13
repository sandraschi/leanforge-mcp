"""
Tests for the Lean signature lexer and the name-keyed tamper guard.
Run with: uv run pytest tests/ -v (no Lean/Mathlib needed -- pure Python).

These are regression tests for docs/ASSESSMENT_2026-06-24.md P1-1 and P1-2:

- P1-2: the old extract_statement stopped at the FIRST `:=` in the source,
  which truncates the signature before the real proposition when a binder
  has a default value (`(n : Nat := 0)`). test_default_arg_* proves the
  fix by constructing exactly that case and confirming the corrected
  signature includes the return type, and that check_tamper actually
  catches a weakening of that return type.

- P1-1: the old tamper guard hashed ALL signatures found in the file
  concatenated together, so adding a legitimate helper lemma (which the
  system prompt explicitly invites) changed the hash and got rejected as
  tampering. test_helper_lemma_allowed proves the fix. test_decoy_attack_*
  proves the fix is not merely "is the original text present somewhere" --
  a decoy lemma reproducing the original text under a NEW name, while the
  ORIGINAL name is weakened, must still be caught.
"""

from __future__ import annotations

from leanforge_mcp.core.agent import capture_original_signatures, check_tamper
from leanforge_mcp.core.lean_lexer import extract_signatures

# ---------------------------------------------------------------------------
# lean_lexer.extract_signatures
# ---------------------------------------------------------------------------


def test_simple_theorem():
    sigs = extract_signatures("theorem foo : 1 = 1 := by\n  sorry\n")
    assert len(sigs) == 1
    assert sigs[0].keyword == "theorem"
    assert sigs[0].name == "foo"
    assert sigs[0].clean_text == "theorem foo : 1 = 1 :="


def test_default_arg_binder_does_not_truncate_signature():
    """The crux of P1-2: a default-arg `:=` inside a binder must not be
    mistaken for the proof-starting `:=`."""
    source = "theorem foo (n : Nat := 0) (h : n > 0) : n != 0 := by\n  omega\n"
    sigs = extract_signatures(source)
    assert len(sigs) == 1
    sig = sigs[0]
    assert sig.name == "foo"
    # The full return type must be present -- the old regex would have
    # stopped right after "(n : Nat :=", never seeing this.
    assert "n != 0" in sig.clean_text
    assert "h > 0" in sig.clean_text or "h : n > 0" in sig.clean_text
    # And the signature's own boundary must be the LAST := in the text (the
    # proof-start one, at depth 0) -- not the default-arg := inside the
    # binder, which correctly remains part of the captured text since it's
    # semantically part of the real declaration. Two := occurrences total:
    # one inside the binder's default value, one as the proof-start boundary.
    assert sig.clean_text.endswith(":=")
    assert sig.clean_text.count(":=") == 2


def test_nested_brackets_in_binders():
    source = "theorem foo (p : Nat \u00d7 Nat := (1, 2)) : p.1 = p.1 := by\n  rfl\n"
    sigs = extract_signatures(source)
    assert len(sigs) == 1
    assert "p.1 = p.1" in sigs[0].clean_text


def test_anonymous_example():
    sigs = extract_signatures("example : 1 = 1 := by\n  sorry\n")
    assert len(sigs) == 1
    assert sigs[0].name is None
    assert sigs[0].keyword == "example"


def test_multiple_declarations():
    source = "theorem foo : 1 = 1 := by\n  sorry\n\nlemma bar : 2 = 2 := by\n  sorry\n"
    sigs = extract_signatures(source)
    assert [s.name for s in sigs] == ["foo", "bar"]


def test_line_comment_stripped_no_false_positive():
    """A comment mentioning 'theorem' must not be parsed as a declaration,
    and a comment INSIDE a real signature must not appear in clean_text."""
    source = "-- this theorem is about addition\ntheorem foo -- trivial\n    : 1 = 1 := by\n  sorry\n"
    sigs = extract_signatures(source)
    assert len(sigs) == 1
    assert "trivial" not in sigs[0].clean_text
    assert "--" not in sigs[0].clean_text


def test_doc_comment_stripped():
    source = "/-- This proves that 1 = 1, a foundational theorem. -/\ntheorem foo : 1 = 1 := by\n  sorry\n"
    sigs = extract_signatures(source)
    assert len(sigs) == 1
    assert sigs[0].name == "foo"
    assert "foundational" not in sigs[0].clean_text


def test_nested_block_comments():
    source = "/- outer /- inner -/ still outer -/\ntheorem foo : 1 = 1 := by\n  sorry\n"
    sigs = extract_signatures(source)
    assert len(sigs) == 1
    assert sigs[0].name == "foo"


def test_string_literal_with_colon_equals_ignored():
    """A default string value containing ':=' must not confuse the scanner."""
    source = 'theorem foo (s : String := "a := b") : s.length \u2265 0 := by\n  simp\n'
    sigs = extract_signatures(source)
    assert len(sigs) == 1
    assert "s.length" in sigs[0].clean_text


def test_comment_reformatting_does_not_change_clean_text():
    """Adding a comment near (but not inside meaningfully) the signature
    should not perturb clean_text -- prevents a false-positive tamper flag
    on purely cosmetic edits."""
    s1 = "theorem foo : 1 = 1 := by\n  sorry\n"
    s2 = "-- proof by reflexivity\ntheorem foo : 1 = 1 := by\n  rfl\n"
    sig1 = extract_signatures(s1)[0].clean_text
    sig2 = extract_signatures(s2)[0].clean_text
    assert sig1 == sig2


# ---------------------------------------------------------------------------
# check_tamper: the name-keyed guard
# ---------------------------------------------------------------------------


def test_tamper_allows_untouched_proof():
    original = capture_original_signatures("theorem foo : 1 = 1 := by\n  sorry\n")
    new_source = "theorem foo : 1 = 1 := by\n  rfl\n"
    assert check_tamper(original, new_source) is None


def test_tamper_detects_statement_change():
    original = capture_original_signatures("theorem foo : 1 = 1 := by\n  sorry\n")
    new_source = "theorem foo : 1 = 2 := by\n  sorry\n"
    assert check_tamper(original, new_source) is not None


def test_tamper_detects_default_arg_weakening():
    """P1-2 regression via the actual guard: the old guard's truncated hash
    would NOT have seen a change to the return type here, because the
    return type was never part of the captured signature at all."""
    original_source = "theorem foo (n : Nat := 0) (h : n > 0) : n != 0 := by\n  sorry\n"
    original = capture_original_signatures(original_source)
    # Agent "fixes" the sorry by weakening the actual proposition to
    # something trivially true, while leaving the default-arg binder alone.
    tampered = "theorem foo (n : Nat := 0) (h : n > 0) : True := by\n  trivial\n"
    violation = check_tamper(original, tampered)
    assert violation is not None
    assert "foo" in violation


def test_tamper_allows_new_helper_lemma():
    """P1-1: the core regression. The system prompt explicitly invites
    helper lemmas; adding one must NOT be flagged as tampering."""
    original = capture_original_signatures("theorem foo : 1 + 1 = 2 := by\n  sorry\n")
    new_source = "lemma helper : 1 + 1 = 2 := by\n  norm_num\n\ntheorem foo : 1 + 1 = 2 := by\n  exact helper\n"
    assert check_tamper(original, new_source) is None


def test_tamper_allows_editing_own_helper_across_turns():
    """The agent may freely revise a helper lemma IT introduced, across
    multiple turns, since the helper's name was never in the original set."""
    original = capture_original_signatures("theorem foo : 1 + 1 = 2 := by\n  sorry\n")
    turn1 = "lemma helper : 1 + 1 = 2 := by\n  sorry\n\ntheorem foo : 1 + 1 = 2 := by\n  exact helper\n"
    assert check_tamper(original, turn1) is None
    turn2 = (  # agent revises its own helper's statement entirely
        "lemma helper : (1 : Nat) + 1 = 2 := by\n  norm_num\n\ntheorem foo : 1 + 1 = 2 := by\n  exact helper\n"
    )
    assert check_tamper(original, turn2) is None


def test_tamper_detects_rename():
    original = capture_original_signatures("theorem foo : 1 = 1 := by\n  sorry\n")
    renamed = "theorem foo2 : 1 = 1 := by\n  rfl\n"
    violation = check_tamper(original, renamed)
    assert violation is not None
    assert "foo" in violation


def test_tamper_detects_deletion():
    original = capture_original_signatures("theorem foo : 1 = 1 := by\n  sorry\n")
    deleted = "-- nothing here\n"
    assert check_tamper(original, deleted) is not None


def test_tamper_detects_decoy_duplicate_attack():
    """The attack a naive 'is original text present anywhere' fix would
    miss: agent adds a NEW lemma that reproduces the original theorem's
    exact original text (satisfying a pure text-presence check), while
    quietly weakening the REAL theorem (same original name, now different
    signature). Must still be rejected."""
    original_source = "theorem foo : 2 + 2 = 4 := by\n  sorry\n"
    original = capture_original_signatures(original_source)
    attack = (
        "lemma foo_decoy : 2 + 2 = 4 := by\n  sorry\n\n"  # never proven, irrelevant
        "theorem foo : True := by\n  trivial\n"  # real theorem weakened
    )
    violation = check_tamper(original, attack)
    assert violation is not None
    assert "foo" in violation


def test_tamper_anonymous_example_preserved():
    original = capture_original_signatures("example : 1 = 1 := by\n  sorry\n")
    untouched = "example : 1 = 1 := by\n  rfl\n"
    assert check_tamper(original, untouched) is None


def test_tamper_anonymous_example_modified_rejected():
    original = capture_original_signatures("example : 1 = 1 := by\n  sorry\n")
    modified = "example : 1 = 2 := by\n  sorry\n"
    assert check_tamper(original, modified) is not None


def test_tamper_new_anonymous_example_rejected():
    """The agent has no legitimate reason to add a NEW anonymous example;
    doing so is treated as suspicious even if the original is untouched."""
    original = capture_original_signatures("example : 1 = 1 := by\n  sorry\n")
    added = "example : 1 = 1 := by\n  sorry\n\nexample : 2 = 2 := by\n  sorry\n"
    assert check_tamper(original, added) is not None

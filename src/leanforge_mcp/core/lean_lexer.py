"""
Lean 4 signature lexer.

Finds `theorem` / `lemma` / `example` declaration signatures in Lean 4
source -- the text from the keyword up to and including the `:=` that
begins the proof body. This is harder than a regex up to the first `:=`
because binders can carry default values with their own `:=`:

    theorem foo (n : Nat := 0) (h : n > 0) : n != 0 := by omega
                              ^ NOT the proof-start :=      ^ this one is

A regex that stops at the first `:=` truncates the signature before the
type ascription and return type -- exactly the part that matters, since
that's the actual proposition. This module tracks bracket nesting depth
and skips comments/string literals so the terminating `:=` is found only
when it appears at the same depth the declaration started at, outside any
binder parens and outside any comment or string.

Used by core/agent.py for the tamper guard: the LLM proof agent may add
new helper lemmas but must never alter an original declaration's
signature. See docs/ASSESSMENT_2026-06-24.md P1-1 and P1-2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KEYWORD_RE = re.compile(r"\b(theorem|lemma|example)\b")
# Name token: anything up to whitespace, a binder opener, or the type-ascription
# colon. Permissive on purpose -- Lean identifiers may contain dots (namespaced
# names like Nat.add_comm), primes, subscripts, and other unicode.
NAME_RE = re.compile(r"^(?:theorem|lemma)\s+([^\s({\[\u2983:]+)")

_OPEN = "([{\u2983\u27e8"  # ( [ { ⦃ ⟨
_CLOSE = ")]}\u2984\u27e9"  # ) ] } ⦄ ⟩
_OPEN_TO_CLOSE = dict(zip(_OPEN, _CLOSE, strict=True))


@dataclass(frozen=True)
class Signature:
    keyword: str
    name: str | None  # None for `example` (always anonymous) or unparsed names
    start: int
    decl_end: int  # index immediately after the terminating `:=`
    clean_text: str  # comment-stripped, whitespace-normalized signature text


def _scan_code_mask(source: str) -> tuple[list[bool], list[int]]:
    """Single pass over `source` producing two parallel arrays:

    - is_code[i]: True if source[i] is ordinary code -- not inside a line
      comment, a (possibly nested) block comment, or a string literal, and
      not itself a comment/string delimiter character.
    - depth_before[i]: bracket nesting depth in effect immediately before
      source[i] is consumed (only code brackets count; brackets inside
      comments or strings never affect depth).

    Lean 4 block comments nest (`/- /- inner -/ outer -/`), unlike C.
    Doc comments (`/-- ... -/`) are a subtype of block comments and are
    handled by the same `/-` ... `-/` scan.
    """
    n = len(source)
    is_code = [True] * n
    depth_before = [0] * n
    depth = 0
    i = 0
    while i < n:
        # Line comment: -- to end of line.
        if source[i : i + 2] == "--":
            j = source.find("\n", i)
            end = j if j != -1 else n
            for k in range(i, end):
                is_code[k] = False
                depth_before[k] = depth
            i = end
            continue

        # Block comment (nesting-aware), includes doc comments `/-- -/`.
        if source[i : i + 2] == "/-":
            comment_depth = 1
            start = i
            i += 2
            while i < n and comment_depth > 0:
                if source[i : i + 2] == "/-":
                    comment_depth += 1
                    i += 2
                elif source[i : i + 2] == "-/":
                    comment_depth -= 1
                    i += 2
                else:
                    i += 1
            for k in range(start, i):
                is_code[k] = False
                depth_before[k] = depth
            continue

        # String literal. Lean strings use `"..."` with `\` escapes.
        if source[i] == '"':
            start = i
            i += 1
            while i < n and source[i] != '"':
                i += 2 if source[i] == "\\" else 1
            i = min(i + 1, n)  # consume closing quote if present
            for k in range(start, i):
                is_code[k] = False
                depth_before[k] = depth
            continue

        ch = source[i]
        depth_before[i] = depth
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth = max(depth - 1, 0)  # tolerate unbalanced input defensively
        i += 1

    return is_code, depth_before


def extract_signatures(source: str) -> list[Signature]:
    """Find every theorem/lemma/example signature in `source`.

    Each signature spans from the declaration keyword to the `:=` that
    begins its proof body, found at the same bracket depth the keyword
    started at (so a default-arg binder's own `:=` is correctly skipped),
    outside comments and string literals. `clean_text` has comments
    stripped and whitespace collapsed, so purely cosmetic changes (adding
    an explanatory comment, reformatting) do not appear as edits.
    """
    is_code, depth_before = _scan_code_mask(source)
    n = len(source)
    signatures: list[Signature] = []

    for m in KEYWORD_RE.finditer(source):
        start = m.start()
        if not is_code[start]:
            continue  # keyword appears inside a comment or string -- skip

        base_depth = depth_before[start]
        i = start
        decl_end = None
        while i < n - 1:
            if is_code[i] and depth_before[i] == base_depth and source[i : i + 2] == ":=":
                decl_end = i + 2
                break
            i += 1
        if decl_end is None:
            continue  # malformed/truncated declaration -- nothing to protect yet

        code_chars = [source[k] for k in range(start, decl_end) if is_code[k]]
        clean_text = re.sub(r"\s+", " ", "".join(code_chars)).strip()

        keyword = m.group(1)
        name = None
        if keyword != "example":
            name_match = NAME_RE.match(clean_text)
            if name_match:
                name = name_match.group(1)

        signatures.append(
            Signature(
                keyword=keyword,
                name=name,
                start=start,
                decl_end=decl_end,
                clean_text=clean_text,
            )
        )

    return signatures

"""
Pipeline tests -- run with: uv run pytest tests/ -v
"""

from __future__ import annotations

import pytest

from leanforge_mcp.core.agent import _apply_edit, _statement_hash, extract_statement


def test_apply_edit_basic():
    source = "theorem foo : 1 = 1 := by\n  sorry"
    new = _apply_edit(source, "  sorry", "  rfl")
    assert new == "theorem foo : 1 = 1 := by\n  rfl"


def test_apply_edit_not_found():
    assert _apply_edit("theorem foo : 1 = 1 := by\n  sorry", "  magic", "  rfl") is None


def test_apply_edit_multiple_occurrences():
    # Two occurrences -- should refuse (ambiguous replacement)
    source = "sorry\nsorry"
    assert _apply_edit(source, "sorry", "rfl") is None


def test_statement_hash_stable():
    source = "theorem foo : 1 = 1 := by\n  sorry"
    assert _statement_hash(source) == _statement_hash(source)


def test_statement_hash_ignores_proof_body():
    s1 = "theorem foo : 1 = 1 := by\n  sorry"
    s2 = "theorem foo : 1 = 1 := by\n  rfl"
    assert _statement_hash(s1) == _statement_hash(s2)


def test_statement_hash_detects_stmt_change():
    s1 = "theorem foo : 1 = 1 := by\n  sorry"
    s2 = "theorem foo : 1 = 2 := by\n  sorry"
    assert _statement_hash(s1) != _statement_hash(s2)


def test_extract_statement_multiline():
    source = (
        "import Mathlib\n"
        "theorem sum_formula\n"
        "    (n : ℕ) :\n"
        "    2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by\n"
        "  sorry\n"
    )
    sig = extract_statement(source)
    assert "sum_formula" in sig
    # Full multi-line signature should be captured
    assert "n + 1" in sig


def test_statement_hash_multiline_detects_change():
    s1 = "theorem foo\n    (n : ℕ) : n + 0 = n := by\n  sorry\n"
    s2 = (
        "theorem foo\n"
        "    (n : ℕ) : n + 1 = n := by\n"  # changed conclusion
        "  sorry\n"
    )
    assert _statement_hash(s1) != _statement_hash(s2)


def test_diagnostic_block_regex():
    from leanforge_mcp.core.lean_client import DIAGNOSTIC_BLOCK

    text = (
        "Compiling...\n"
        "File.lean:10:4: error: type mismatch\n"
        "  foo\n"
        "has type\n"
        "  A\n"
        "but is expected to have type\n"
        "  B\n"
        "\n"
        "File.lean:20:8: warning: sorry used\n"
    )
    blocks = DIAGNOSTIC_BLOCK.findall(text)
    assert len(blocks) == 2
    assert "type mismatch" in blocks[0]
    assert "but is expected to have type" in blocks[0]
    assert "sorry used" in blocks[1]


@pytest.mark.asyncio
async def test_lean_client_background_setup_scheduling(tmp_path):
    import asyncio

    from leanforge_mcp.core.lean_client import LeanClient

    lake_path = tmp_path / "bin" / "lake.exe"
    workspace_dir = tmp_path / "workspace"

    client = LeanClient(lake_path=lake_path, workspace_dir=workspace_dir)

    setup_called = asyncio.Event()

    async def mock_run_setup():
        setup_called.set()
        client.setup_status = "Mock running..."
        await asyncio.sleep(0.1)
        client.setup_status = "Ready"
        client.setup_in_progress = False

    client._run_setup_task = mock_run_setup

    ok, msg = await client.ensure_workspace()
    assert not ok
    assert "lake executable not found" in msg
    assert client.setup_in_progress

    await setup_called.wait()
    await client._setup_task

    assert not client.setup_in_progress
    assert client.setup_status == "Ready"

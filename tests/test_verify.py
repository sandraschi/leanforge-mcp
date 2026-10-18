"""
Tests for external kernel re-verification helpers.

Pure-Python: version/output parsing, fail-closed semantics, and the
unsupported-toolchain short-circuit (via a stubbed LeanClient subclass).
No live Lean toolchain needed -- run with: uv run pytest tests/test_verify.py -v
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from leanforge_mcp.core.lean_client import (
    EXTERNAL_CHECK_MIN_VERSION,
    KernelVerdict,
    LeanClient,
    VerifyResult,
    file_contains,
    new_verify_module,
    parse_checker_accepted,
    parse_lean_version,
)


def test_parse_lean_version_full_string():
    out = "Lean (version 4.35.0, x86_64-w64-windows-gnu, commit eb6cafb7, Release)"
    assert parse_lean_version(out) == (4, 35, 0)


def test_parse_lean_version_older():
    assert parse_lean_version("Lean (version 4.31.0, x86_64-w64-windows-gnu, Release)") == (4, 31, 0)


def test_parse_lean_version_garbage_is_none():
    assert parse_lean_version("lake not found") is None
    assert parse_lean_version("") is None


def test_min_version_is_4_35():
    assert EXTERNAL_CHECK_MIN_VERSION == (4, 35, 0)


def test_parse_checker_accepted_con_leche():
    assert parse_checker_accepted("con-leche: accepted 57921 declarations (--verified)") == 57921


def test_parse_checker_accepted_zero_counts_as_parsed():
    # Zero parses fine -- but callers must NOT treat it as a pass.
    assert parse_checker_accepted("con-leche: accepted 0 declarations (--verified)") == 0


def test_parse_checker_rejection_is_none():
    assert parse_checker_accepted("error: declaration of False accepted, rejecting") is None
    assert parse_checker_accepted("") is None


def test_verify_module_name_is_valid_lean_module():
    for _ in range(20):
        assert re.fullmatch(r"LfVerify[0-9a-f]{12}", new_verify_module())
    assert len({new_verify_module() for _ in range(50)}) > 1  # unique


def test_file_contains_finds_needle(tmp_path: Path):
    f = tmp_path / "export.ndjson"
    f.write_text('{"meta": 1}\n' + "x" * 100 + "angle_sum" + "y" * 100 + "\n", encoding="utf-8")
    assert file_contains(f, "angle_sum") is True
    assert file_contains(f, "no_such_theorem") is False


def test_file_contains_across_chunk_boundary(tmp_path: Path):
    f = tmp_path / "big.ndjson"
    # Needle straddles the 16-byte chunk edge.
    f.write_text("a" * 14 + "needle_here" + "b" * 14, encoding="utf-8")
    assert file_contains(f, "needle_here", chunk_size=16) is True
    assert file_contains(f, "absent", chunk_size=16) is False


def test_file_contains_empty_needle_is_true(tmp_path: Path):
    f = tmp_path / "e.ndjson"
    f.write_text("{}", encoding="utf-8")
    assert file_contains(f, "") is True


def test_all_accepted_needs_every_kernel():
    ok = VerifyResult(
        supported=True,
        toolchain_version="4.35.0",
        results=[
            KernelVerdict(kernel="con-leche", accepted=True, declarations=10),
            KernelVerdict(kernel="con-ron", accepted=True, declarations=10),
        ],
    )
    assert ok.all_accepted is True

    one_bad = VerifyResult(
        supported=True,
        toolchain_version="4.35.0",
        results=[
            KernelVerdict(kernel="con-leche", accepted=True, declarations=10),
            KernelVerdict(kernel="con-ron", accepted=False, detail="rejected"),
        ],
    )
    assert one_bad.all_accepted is False


def test_all_accepted_empty_results_is_false():
    assert VerifyResult(supported=True, toolchain_version="4.35.0", results=[]).all_accepted is False
    assert VerifyResult(supported=False, toolchain_version="4.31.0").all_accepted is False


class _OldToolchainClient(LeanClient):
    async def lean_toolchain_version(self):
        return (4, 31, 0)


def test_verify_external_short_circuits_on_old_toolchain(tmp_path: Path):
    client = _OldToolchainClient(lake_path=tmp_path / "lake", workspace_dir=tmp_path)
    result = asyncio.run(client.verify_external("theorem foo : 1 = 1 := rfl\n"))
    assert result.supported is False
    assert "4.35" in result.message
    assert result.results == []
    assert result.all_accepted is False
    # Nothing written to the workspace on the unsupported path.
    assert list(tmp_path.iterdir()) == []


class _NoPrefixClient(LeanClient):
    async def lean_toolchain_version(self):
        return (4, 35, 0)

    async def toolchain_bin_dir(self):
        return None


def test_verify_external_no_prefix_is_unsupported(tmp_path: Path):
    client = _NoPrefixClient(lake_path=tmp_path / "lake", workspace_dir=tmp_path)
    result = asyncio.run(client.verify_external("theorem foo : 1 = 1 := rfl\n"))
    assert result.supported is False
    assert result.all_accepted is False

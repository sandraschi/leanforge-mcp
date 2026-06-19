"""
Standalone smoke test for leanforge-mcp core pipeline.
Runs OUTSIDE the MCP layer — exercises LeanClient, config, and the agent
loop directly so you can validate before wiring into Claude Desktop.

Usage:
    cd D:\Dev\repos\leanforge-mcp
    uv run python scripts/smoke_test.py

Exit code 0 = all tests passed.
Exit code 1 = one or more failed (details printed).
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Add src to path so we can import without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from leanforge_mcp.core.config import load_config
from leanforge_mcp.core.lean_client import LeanClient

PASS = "\u2705"
FAIL = "\u274c"
WARN = "\u26a0\ufe0f"

results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    icon = PASS if passed else FAIL
    print(f"  {icon}  {name}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"       {line}")


async def test_config() -> None:
    print("\n[1] Config loading")
    config_path = Path(__file__).parent.parent / "config.toml"
    if not config_path.exists():
        record("config.toml exists", False, "Copy config.example.toml -> config.toml first")
        return
    record("config.toml exists", True)

    try:
        cfg = load_config(config_path)
        record("config parses", True)
        record("lake_path set", bool(cfg.lean.lake_path), cfg.lean.lake_path)
        record("workspace_dir set", bool(cfg.lean.workspace_dir), cfg.lean.workspace_dir)
        lake_exe = Path(cfg.lean.lake_path)
        record("lake.exe on disk", lake_exe.exists(),
               f"{lake_exe} {'found' if lake_exe.exists() else 'NOT FOUND'}")
        workspace = Path(cfg.lean.workspace_dir)
        record("workspace dir exists", workspace.exists(),
               f"{workspace} {'found' if workspace.exists() else 'NOT FOUND — run one-time setup, see ARCHITECTURE.md'}")
    except Exception as exc:
        record("config parses", False, str(exc))


async def test_lean_client(cfg) -> LeanClient | None:
    print("\n[2] LeanClient / lake invocation")
    lean = LeanClient(
        lake_path=Path(cfg.lean.lake_path),
        workspace_dir=Path(cfg.lean.workspace_dir),
        timeout=cfg.lean.compile_timeout,
    )

    # --- workspace check ---
    ok, msg = await lean.ensure_workspace()
    record("workspace smoke test (import Mathlib + example : 1=1)", ok, msg)
    if not ok:
        print(f"\n  {WARN}  Stopping Lean tests — workspace not ready.")
        print(       "       Run one-time setup (see docs/ARCHITECTURE.md):")
        print(       "         cd workspace")
        print(       "         lake new leanforge_workspace math")
        print(       "         cd leanforge_workspace")
        print(       "         lake exe cache get")
        print(       "         lake build")
        return None
    return lean


async def test_compile_trivial(lean: LeanClient) -> None:
    print("\n[3] Trivial compile (should succeed, no sorry)")
    source = "import Mathlib\nexample : 1 + 1 = 2 := by norm_num\n"
    t = time.perf_counter()
    result = await lean.compile(source)
    elapsed = time.perf_counter() - t
    record("trivial proof compiles", result.proven,
           result.error_message or f"({elapsed:.1f}s)")
    record("no errors", not result.errors, "\n".join(result.errors) if result.errors else "clean")
    record("no sorry", not result.has_sorry)


async def test_compile_sorry(lean: LeanClient) -> None:
    print("\n[4] Sorry detection (should have sorry, not proven)")
    source = "import Mathlib\ntheorem foo : 1 + 1 = 3 := by\n  sorry\n"
    result = await lean.compile(source)
    record("sorry detected in output", result.has_sorry)
    record("not proven (sorry present)", not result.proven)


async def test_compile_error(lean: LeanClient) -> None:
    print("\n[5] Error detection (unknown tactic)")
    source = "import Mathlib\nexample : 1 = 1 := by\n  magic_tactic\n"
    result = await lean.compile(source)
    record("errors returned", len(result.errors) > 0,
           result.errors[0] if result.errors else "(none returned — check stderr parsing)")
    record("not proven on error", not result.proven)


async def test_statement_hash() -> None:
    print("\n[6] Statement tamper detection (pure Python, no Lean needed)")
    from leanforge_mcp.core.agent import _statement_hash, _apply_edit, extract_statement

    s1 = "import Mathlib\ntheorem foo (n : \u2115) : n + 0 = n := by\n  sorry\n"
    s2 = "import Mathlib\ntheorem foo (n : \u2115) : n + 0 = n := by\n  rfl\n"
    s3 = "import Mathlib\ntheorem foo (n : \u2115) : n + 1 = n := by\n  sorry\n"

    h1, h2, h3 = _statement_hash(s1), _statement_hash(s2), _statement_hash(s3)
    record("same stmt, diff proof => same hash", h1 == h2,
           f"h1={h1[:12]}... h2={h2[:12]}...")
    record("diff stmt => diff hash", h1 != h3,
           f"h1={h1[:12]}... h3={h3[:12]}...")

    # Multi-line theorem
    multiline = (
        "import Mathlib\n"
        "theorem sum_formula\n"
        "    (n : \u2115) :\n"
        "    2 * \u2211 i \u2208 Finset.range (n + 1), i = n * (n + 1) := by\n"
        "  sorry\n"
    )
    sig = extract_statement(multiline)
    record("multi-line theorem signature extracted", "sum_formula" in sig, sig[:120])

    # Apply edit — should work
    edited = _apply_edit(s1, "  sorry", "  rfl")
    record("_apply_edit fills sorry", edited is not None and "rfl" in edited)

    # Apply edit — wrong text
    bad = _apply_edit(s1, "  nonexistent", "  rfl")
    record("_apply_edit returns None when text not found", bad is None)


async def main() -> None:
    print("=" * 60)
    print("leanforge-mcp smoke test")
    print("=" * 60)

    config_path = Path(__file__).parent.parent / "config.toml"
    if not config_path.exists():
        await test_config()
        summarise()
        return

    cfg = load_config(config_path)

    await test_config()
    await test_statement_hash()

    lean = await test_lean_client(cfg)
    if lean:
        await test_compile_trivial(lean)
        await test_compile_sorry(lean)
        await test_compile_error(lean)

    summarise()


def summarise() -> None:
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    icon = PASS if passed == total else FAIL
    print(f"{icon}  {passed}/{total} tests passed")
    if passed < total:
        print("\nFailed:")
        for name, ok, detail in results:
            if not ok:
                print(f"  {FAIL}  {name}")
                if detail:
                    print(f"       {detail[:200]}")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())

"""
In-process integration test: boots the real FastMCP server (lifespan included)
via the in-memory Client transport and exercises the lifespan plumbing.

This locks in the P0-1 fix from docs/ASSESSMENT_2026-06-10.md:
tools on mounted child routers reach the parent's lifespan dict through
ctx.lifespan_context. If fastmcp changes that fallback behavior, this test
fails loudly instead of every tool call failing in production.

Requires config.toml to exist (it does in this repo). Does NOT require a
Lean workspace — ensure_workspace degrades to a logged warning.

Run: uv run pytest tests/test_server_integration.py -v
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from leanforge_mcp.server import mcp

EXPECTED_TOOLS = {
    "submit_theorem",
    "submit_lean_file",
    "get_proof_status",
    "list_attempts",
    "list_jobs",
    "cancel_job",
    "validate_lean",
    "get_mathlib_search",
}


async def test_tools_mounted_unprefixed():
    """mount() with no namespace must expose original tool names."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        missing = EXPECTED_TOOLS - names
        assert not missing, f"Missing tools (prefixed by mount?): {missing}"


async def test_lifespan_runner_reachable_from_mounted_tool():
    """
    list_jobs is the cheapest tool that traverses get_runner(ctx) ->
    ctx.lifespan_context -> parent lifespan dict -> Runner -> SQLite.
    If the lifespan plumbing is broken, this raises instead of returning.
    """
    async with Client(mcp) as client:
        result = await client.call_tool("list_jobs", {})
        # Defensive across fastmcp result shapes: prefer structured data,
        # fall back to parsing the text content block.
        payload = getattr(result, "data", None)
        if payload is None:
            blocks = getattr(result, "content", []) or []
            text = next(
                (b.text for b in blocks if getattr(b, "text", None)), None
            )
            assert text is not None, "list_jobs returned no content"
            payload = json.loads(text)
        assert "count" in payload, f"Unexpected list_jobs payload: {payload!r}"
        assert "jobs" in payload


async def test_get_proof_status_unknown_job():
    """Unknown job id must return a structured error, not raise."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_proof_status", {"job_id": "00000000-0000-0000-0000-000000000000"}
        )
        payload = getattr(result, "data", None)
        if payload is None:
            blocks = getattr(result, "content", []) or []
            text = next(
                (b.text for b in blocks if getattr(b, "text", None)), None
            )
            payload = json.loads(text) if text else {}
        assert "error" in payload


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

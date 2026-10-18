"""MCP tool: get_mathlib_search -- natural language → Mathlib theorem names"""

from __future__ import annotations

import logging

import httpx
from fastmcp import FastMCP
from pydantic import Field

logger = logging.getLogger(__name__)
router = FastMCP("mathlib")

LEANSEARCH_API = "https://leansearch.net/api/search"


@router.tool(
    description=(
        "Search Mathlib4 for theorems matching a natural language query. "
        "Returns theorem names and type signatures useful for building proofs. "
        "Use this when stuck -- find the right Mathlib lemma name and pass it "
        "as a hint to submit_theorem."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": True},
    output_schema={"type": "object"},
)
async def get_mathlib_search(
    query: str = Field(
        description="Natural language description of the mathematical result to find.",
        examples=[
            "sum of geometric series",
            "Cauchy-Schwarz inequality",
            "induction on natural numbers",
            "sum of first n natural numbers",
        ],
    ),
    limit: int = Field(default=5, ge=1, le=20),
) -> dict:
    """Search Mathlib4 for theorems matching a natural language query.

    ## Return Format
    `{"success": True, "query": str, "results": [...], "count": int,
    "hint": str}` where each result has `name`, `statement`, `module`.
    `{"success": False, "message": str, "query": str, "fallback": str}` when
    the LeanSearch API is unreachable.

    ## Examples
    `get_mathlib_search("sum of first n natural numbers")`
    -> `{"success": True, "results": [{"name": "Finset.sum_range_id", ...}], ...}`.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                LEANSEARCH_API,
                params={"query": query, "num_results": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        results = [
            {
                "name": item.get("name", ""),
                "statement": item.get("statement", ""),
                "module": item.get("module", ""),
            }
            for item in data.get("results", [])[:limit]
        ]

        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
            "message": f"Found {len(results)} theorems for '{query}'.",
            "hint": (
                "Pass relevant names to submit_theorem via the hints parameter. "
                "Or browse https://leansearch.net for more."
            ),
        }

    except httpx.HTTPError as exc:
        logger.warning("LeanSearch API error: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": f"LeanSearch API unreachable: {exc}",
            "query": query,
            "fallback": "Browse https://leansearch.net directly.",
        }

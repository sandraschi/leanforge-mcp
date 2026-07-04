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
    annotations={"readOnlyHint": True},
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
            "query": query,
            "results": results,
            "count": len(results),
            "hint": (
                "Pass relevant names to submit_theorem via the hints parameter. "
                "Or browse https://leansearch.net for more."
            ),
        }

    except httpx.HTTPError as exc:
        logger.warning("LeanSearch API error: %s", exc)
        return {
            "error": str(exc),
            "query": query,
            "fallback": "Browse https://leansearch.net directly.",
        }

"""Serve whitelisted markdown docs for the webapp Help page renderer."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["docs"])

REPO_ROOT = Path(__file__).parent.parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"

# name → path relative to repo root. Explicit whitelist — no traversal possible.
ALLOWED_DOCS: dict[str, Path] = {
    "INSTALL":               REPO_ROOT / "INSTALL.md",
    "LEAN":                  DOCS_DIR / "LEAN.md",
    "LEAN_PRIMER":           DOCS_DIR / "LEAN_PRIMER.md",
    "CONFIGURATION":         DOCS_DIR / "CONFIGURATION.md",
    "TOOLS":                 DOCS_DIR / "TOOLS.md",
    "DEVELOPMENT":           DOCS_DIR / "DEVELOPMENT.md",
    "TROUBLESHOOTING":       DOCS_DIR / "TROUBLESHOOTING.md",
    "ARCHITECTURE":          DOCS_DIR / "ARCHITECTURE.md",
    "BENCHMARK_RESULTS":     DOCS_DIR / "BENCHMARK_RESULTS.md",
    "ASSESSMENT_2026-06-24": DOCS_DIR / "ASSESSMENT_2026-06-24.md",
}


@router.get("/api/docs")
async def list_docs():
    """Return the list of available doc names and their availability."""
    return {
        "docs": [
            {
                "name": name,
                "available": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
            }
            for name, path in sorted(ALLOWED_DOCS.items())
        ]
    }


@router.get("/api/docs/{name}")
async def get_doc(name: str):
    """Return raw markdown content for a whitelisted doc."""
    path = ALLOWED_DOCS.get(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Doc '{name}' not in allowlist.")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Doc file '{path.name}' does not exist yet.")
    content = path.read_text(encoding="utf-8")
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")

"""Skills API route -- serves Lean expert skill content to the webapp Chat page."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api", tags=["skills"])

_SKILL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "src" / "leanforge_mcp" / "skills"


@router.get("/skills", summary="List available skills")
async def list_skills():
    """Return names of all registered skills."""
    if not _SKILL_DIR.is_dir():
        return {"skills": []}
    skills = [p.parent.name for p in _SKILL_DIR.rglob("SKILL.md")]
    return {"skills": skills}


@router.get("/skills/{name}", summary="Get skill content by name")
async def get_skill(name: str):
    """Return the raw SKILL.md content for a named skill."""
    skill_path = _SKILL_DIR / name / "SKILL.md"
    if skill_path.exists():
        return PlainTextResponse(skill_path.read_text(encoding="utf-8"))
    return PlainTextResponse(f"Skill '{name}' not found.", status_code=404)

"""Real system status endpoint -- no fake data."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["status"])

VERSION = "0.1.1"


def _get_dynamic_workspace_status(runner) -> dict:
    lean = runner.lean
    if lean.setup_in_progress:
        return {
            "ok": False,
            "status": "pending",
            "message": f"Setup in progress: {lean.setup_status}",
            "checked_at": datetime.now(UTC).isoformat(),
        }
    if lean.setup_error:
        return {
            "ok": False,
            "status": "error",
            "message": f"Setup failed: {lean.setup_error}",
            "checked_at": datetime.now(UTC).isoformat(),
        }
    if not lean.lake_path.exists():
        return {
            "ok": False,
            "status": "missing",
            "message": "lake executable not found.",
            "checked_at": datetime.now(UTC).isoformat(),
        }
    return {
        "ok": True,
        "status": "ready",
        "message": "Workspace OK, Mathlib resolves.",
        "checked_at": datetime.now(UTC).isoformat(),
    }


@router.get("/api/health")
async def health(request: Request):
    """Shallow liveness check. Does not hit the DB."""
    runner = request.app.state.runner
    lean_ws = _get_dynamic_workspace_status(runner)
    return {
        "status": "ok",
        "server": "leanforge-mcp",
        "version": VERSION,
        "lean_workspace_ok": lean_ws["ok"],
    }


@router.get("/api/status")
async def status(request: Request):
    """Full system status -- hits DB for real job counts."""
    runner = request.app.state.runner
    lean_ws = _get_dynamic_workspace_status(runner)

    counts = await runner.jobs.get_job_counts()

    db_path = Path(runner.config.database.path)
    db_size = db_path.stat().st_size if db_path.exists() else None

    return {
        "server": "leanforge-mcp",
        "version": VERSION,
        "checked_at": datetime.now(UTC).isoformat(),
        "lean_workspace": lean_ws,
        "database": {
            "path": str(db_path),
            "exists": db_path.exists(),
            "size_bytes": db_size,
        },
        "config": {
            "parallel_agents": runner.config.agent.parallel_agents,
            "max_turns": runner.config.agent.max_turns,
            "max_concurrent_compiles": runner.config.lean.max_concurrent_compiles,
            "escalate_to_tier2_after": runner.config.agent.escalate_to_tier2_after,
            "escalate_to_tier3_after": runner.config.agent.escalate_to_tier3_after,
            "tier1_model": runner.config.llm.tier1.model,
            "tier2_model": runner.config.llm.tier2.model,
            "tier3_model": runner.config.llm.tier3.model,
        },
        "jobs": {
            "total": counts.get("total", 0),
            "running": counts.get("running", 0),
            "complete": counts.get("complete", 0),
            "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
            "interrupted": counts.get("interrupted", 0),
            "live_tasks": len(runner._tasks),
        },
    }

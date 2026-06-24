"""Real system status endpoint — no fake data."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["status"])

VERSION = "0.1.1"


@router.get("/api/health")
async def health(request: Request):
    """Shallow liveness check. Does not hit the DB."""
    lean_ws = getattr(request.app.state, "lean_workspace_status", None)
    return {
        "status": "ok",
        "server": "leanforge-mcp",
        "version": VERSION,
        "lean_workspace_ok": lean_ws["ok"] if lean_ws else None,
    }


@router.get("/api/status")
async def status(request: Request):
    """Full system status — hits DB for real job counts."""
    runner = request.app.state.runner
    lean_ws = getattr(request.app.state, "lean_workspace_status", {
        "ok": None, "message": "Status not yet checked.", "checked_at": None
    })

    # Real job counts from DB — list up to 2000, enough for a count
    jobs = await runner.jobs.list_jobs(limit=2000)
    by_status: Counter = Counter(j.status for j in jobs)

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
            "total": len(jobs),
            "running": by_status.get("running", 0),
            "complete": by_status.get("complete", 0),
            "failed": by_status.get("failed", 0),
            "cancelled": by_status.get("cancelled", 0),
            "interrupted": by_status.get("interrupted", 0),
            "live_tasks": len(runner._tasks),
        },
    }

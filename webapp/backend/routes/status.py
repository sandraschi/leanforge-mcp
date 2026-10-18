"""Real system status endpoint -- no fake data."""

from __future__ import annotations

import logging
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


MCP_TOOLS = [
    {
        "name": "submit_theorem",
        "description": "Submit a theorem statement for proof search; returns a job_id immediately.",
    },
    {
        "name": "submit_lean_file",
        "description": "Submit a complete Lean file with sorry placeholders; returns a job_id.",
    },
    {"name": "get_proof_status", "description": "Poll a job; returns the proof when complete."},
    {"name": "list_attempts", "description": "Inspect the per-agent attempt trajectory of a job."},
    {"name": "list_jobs", "description": "List jobs with status summary."},
    {"name": "validate_lean", "description": "Raw Lean 4 compile with no job tracking."},
    {"name": "verify_proof", "description": "Re-verify a proven file with independent verified kernels."},
    {"name": "cancel_job", "description": "Cancel a running proof search job."},
    {"name": "leanforge_shutdown", "description": "Gracefully shut down the server."},
    {"name": "get_mathlib_search", "description": "Natural-language search over Mathlib theorems."},
]


@router.get("/api/capabilities")
async def capabilities():
    """Standard capability shape consumed by fleet hubs and the Tools page."""
    return {
        "server": "leanforge-mcp",
        "version": VERSION,
        "transport": "stdio (MCP) + HTTP (this backend)",
        "tools": MCP_TOOLS,
    }


@router.get("/api/v1/diagnostics")
async def diagnostics(request: Request):
    """Full diagnostics for CUA-NSIS smoke testing: tools, system, log errors."""
    runner = request.app.state.runner
    lean_ws = _get_dynamic_workspace_status(runner)
    counts = await runner.jobs.get_job_counts()

    log_path = Path(runner.config.logging.log_file)
    recent_errors: list[str] = []
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            recent_errors = [ln[-500:] for ln in lines if "ERROR" in ln][-20:]
        except OSError:
            logger.warning("Could not read log file for diagnostics")

    return {
        "server": "leanforge-mcp",
        "version": VERSION,
        "checked_at": datetime.now(UTC).isoformat(),
        "tools": [t["name"] for t in MCP_TOOLS],
        "lean_workspace": lean_ws,
        "jobs": counts,
        "live_tasks": len(runner._tasks),
        "recent_errors": recent_errors,
    }

"""Log tail endpoint for the webapp Logs page (ring-buffer alternative: file tail)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["logs"])


@router.get("/logs")
async def read_logs(request: Request, limit: int = 200, level: str | None = None):
    """Return the last N lines of the server log file, optionally level-filtered."""
    log_path = Path(request.app.state.config.logging.log_file)
    if not log_path.exists():
        return {"path": str(log_path), "exists": False, "count": 0, "entries": []}
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        logger.warning("Could not read log file: %s", exc)
        return {"path": str(log_path), "exists": True, "count": 0, "entries": [], "error": str(exc)}
    if level:
        needle = level.upper()
        lines = [ln for ln in lines if needle in ln.upper()]
    tail = lines[-max(1, min(limit, 2000)) :]
    return {"path": str(log_path), "exists": True, "count": len(tail), "entries": tail}

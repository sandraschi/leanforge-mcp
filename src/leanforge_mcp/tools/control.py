"""MCP tools: cancel_job, leanforge_shutdown"""

from __future__ import annotations

import logging
import os
import threading

from fastmcp import Context, FastMCP

from leanforge_mcp.core.runner import get_runner

logger = logging.getLogger(__name__)

router = FastMCP("control")


@router.tool(description="Cancel a running proof search job.")
async def cancel_job(job_id: str, ctx: Context) -> dict:
    runner = get_runner(ctx)
    cancelled = await runner.cancel(job_id)
    if cancelled:
        return {"job_id": job_id, "status": "cancelled"}
    job = await runner.jobs.get_job(job_id)
    if job is None:
        return {"error": f"Job {job_id} not found."}
    return {
        "job_id": job_id,
        "status": job.status,
        "message": f"No live task -- job is already {job.status}.",
    }


def _delayed_exit() -> None:
    def _exit() -> None:
        import time

        time.sleep(0.5)
        os._exit(0)  # intentional self-termination after responding

    threading.Thread(target=_exit, daemon=True).start()


@router.tool(
    description=(
        "Shut down the leanforge-mcp server gracefully. "
        "Cancels live proof jobs, then exits the process. "
        "Use before upgrades or restarts."
    ),
    annotations={"destructiveHint": True},
)
async def leanforge_shutdown(ctx: Context) -> dict:
    """Graceful self-termination.

    ## Return Format
    `{"success": True, "message": str}` — the process exits ~500 ms
    after responding so the reply flushes first.

    ## Examples
    `leanforge_shutdown()` -> server stops; reconnect after restart.
    """
    runner = get_runner(ctx)
    for job_id in list(runner._tasks.keys()):
        try:
            await runner.cancel(job_id)
        except Exception:
            logger.exception("Error cancelling job %s during shutdown", job_id)
    logger.info("leanforge-mcp shutting down via leanforge_shutdown")
    _delayed_exit()
    return {"success": True, "message": "leanforge-mcp shutting down in ~500 ms"}

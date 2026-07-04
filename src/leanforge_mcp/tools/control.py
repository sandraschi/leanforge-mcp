"""MCP tool: cancel_job"""

from __future__ import annotations

from fastmcp import Context, FastMCP

from leanforge_mcp.core.runner import get_runner

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

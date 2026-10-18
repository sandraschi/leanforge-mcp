"""MCP tools: get_proof_status, list_attempts, list_jobs, validate_lean"""

from __future__ import annotations

from fastmcp import Context, FastMCP
from pydantic import Field

from leanforge_mcp.core.runner import get_runner

router = FastMCP("status")


@router.tool(
    description=(
        "Get the status of a proof search job. If complete, returns the proven "
        "Lean 4 file. If running, returns turn count and latest attempt. Poll every 10-30s."
    ),
    annotations={"readOnlyHint": True},
    output_schema={"type": "object"},
    app=True,
)
async def get_proof_status(
    job_id: str,
    ctx: Context,
) -> dict:
    """Get the status of a proof search job.

    ## Return Format
    `{"success": True, "job_id": str, "status": str, "description": str,
    "created_at": str, "updated_at": str, ...}`. When `status` is "complete",
    includes `"proof"` (the verified Lean file). Otherwise includes
    `"latest_turn"`, `"latest_compiler_output"`, `"latest_model"`.
    `{"success": False, "message": str}` when the job id is unknown.

    ## Examples
    `get_proof_status("abc-123")`
    -> `{"success": True, "status": "running", "latest_turn": 7, ...}`.
    """
    runner = get_runner(ctx)
    job = await runner.jobs.get_job(job_id)
    if job is None:
        return {"success": False, "error": f"Job {job_id} not found.", "message": f"Job {job_id} not found."}

    out = {
        "success": True,
        "job_id": job.id,
        "status": job.status,
        "description": job.description,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if job.status == "complete":
        out["proof"] = job.proof
    else:
        attempts = await runner.jobs.get_attempts(job_id, last_n=1)
        if attempts:
            out["latest_turn"] = attempts[0]["turn"]
            out["latest_compiler_output"] = attempts[0]["compiler_output"][:500]
            out["latest_model"] = attempts[0]["llm_model"]
    return out


@router.tool(
    description=(
        "List proof attempts for a job, with Lean source and compiler feedback per turn. "
        "Useful for understanding why a search is stuck or inspecting the trajectory."
    ),
    annotations={"readOnlyHint": True},
    output_schema={"type": "object"},
)
async def list_attempts(
    job_id: str,
    ctx: Context,
    agent_index: int | None = None,
    last_n: int = Field(default=10, ge=1, le=100),
) -> dict:
    """List proof attempts for a job.

    ## Return Format
    `{"success": True, "job_id": str, "count": int, "attempts": [...]}` where
    each attempt has `agent_index`, `turn`, `success`, `llm_model` and
    `compiler_output` (truncated to 400 chars).

    ## Examples
    `list_attempts("abc-123", last_n=5)` -> last 5 turns across all agents.
    `list_attempts("abc-123", agent_index=0)` -> one subagent's trajectory.
    """
    runner = get_runner(ctx)
    attempts = await runner.jobs.get_attempts(job_id, agent_index=agent_index, last_n=last_n)
    return {
        "success": True,
        "job_id": job_id,
        "count": len(attempts),
        "attempts": [
            {
                "agent_index": a["agent_index"],
                "turn": a["turn"],
                "success": bool(a["success"]),
                "llm_model": a["llm_model"],
                "compiler_output": a["compiler_output"][:400],
            }
            for a in attempts
        ],
    }


@router.tool(
    description="List all jobs with status and summary.",
    annotations={"readOnlyHint": True},
    output_schema={"type": "object"},
    app=True,
)
async def list_jobs(
    ctx: Context,
    status_filter: str | None = None,
    limit: int = Field(default=20, ge=1, le=100),
) -> dict:
    """List all jobs with status and summary.

    ## Return Format
    `{"success": True, "count": int, "jobs": [...]}` where each job has
    `job_id`, `status`, `description` and `created_at`.

    ## Examples
    `list_jobs()` -> the 20 most recent jobs.
    `list_jobs(status_filter="complete")` -> only proven jobs.
    """
    runner = get_runner(ctx)
    jobs = await runner.jobs.list_jobs(status=status_filter, limit=limit)
    return {
        "success": True,
        "count": len(jobs),
        "jobs": [
            {
                "job_id": j.id,
                "status": j.status,
                "description": j.description[:100],
                "created_at": j.created_at,
            }
            for j in jobs
        ],
    }


@router.tool(
    description=(
        "Run the Lean 4 compiler on arbitrary source and return output. No job tracking, "
        "no LLM -- raw compile. Use to test a proof or debug Lean syntax before submitting."
    ),
    annotations={"readOnlyHint": True},
    output_schema={"type": "object"},
)
async def validate_lean(
    lean_source: str,
    ctx: Context,
) -> dict:
    """Run the Lean 4 compiler on arbitrary source.

    ## Return Format
    `{"success": bool, "proven": bool, "has_sorry": bool, "errors": [...],
    "warnings": [...], "message": str}`. `success` is the compile exit status;
    `proven` additionally requires no `sorry`.

    ## Examples
    `validate_lean("import Mathlib\\nexample : 1 = 1 := rfl\\n")`
    -> `{"success": True, "proven": True, ...}`.
    """
    runner = get_runner(ctx)
    if runner.lean.setup_in_progress:
        return {
            "success": False,
            "status": "pending",
            "message": f"Leanforge setup running: {runner.lean.setup_status}. Try again shortly.",
        }
    if runner.lean.setup_error:
        return {
            "success": False,
            "status": "error",
            "message": f"Leanforge setup failed: {runner.lean.setup_error}. Fix installation files.",
        }
    result = await runner.lean.compile(lean_source)
    return {
        "success": result.success,
        "proven": result.proven,
        "has_sorry": result.has_sorry,
        "errors": result.errors,
        "warnings": result.warnings,
        "message": "Proven: sorry-free compile." if result.proven else "Not proven: see errors.",
    }

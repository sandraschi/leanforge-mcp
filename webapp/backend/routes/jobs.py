"""REST endpoints for job monitoring and theorem submission."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class SubmitTheoremRequest(BaseModel):
    statement: str = Field(description="Theorem proposition (after colon).")
    lean_stub: str | None = Field(default=None)
    hints: str | None = Field(default=None)
    tier: int = Field(default=1, ge=1, le=3)
    parallel_agents: int = Field(default=4, ge=1, le=16)
    max_turns: int = Field(default=100, ge=1, le=1000)


class SubmitLeanFileRequest(BaseModel):
    lean_source: str
    description: str = ""
    tier: int = Field(default=1, ge=1, le=3)
    parallel_agents: int = Field(default=4, ge=1, le=16)
    max_turns: int = Field(default=100, ge=1, le=1000)


def _get_services(request: Request):
    return request.app.state.runner, request.app.state.event_bus


@router.get("")
async def list_jobs(
    request: Request,
    status: str | None = None,
    limit: int = 20,
):
    runner, _ = _get_services(request)
    jobs = await runner.jobs.list_jobs(status=status, limit=limit)
    return {
        "count": len(jobs),
        "jobs": [
            {
                "job_id": j.id,
                "status": j.status,
                "description": j.description[:200] if j.description else "",
                "created_at": j.created_at,
                "updated_at": j.updated_at,
                "has_proof": j.proof is not None,
            }
            for j in jobs
        ],
    }


@router.get("/{job_id}")
async def get_job(request: Request, job_id: str):
    runner, _ = _get_services(request)
    job = await runner.jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    attempts = await runner.jobs.get_attempts(job_id, last_n=100)
    return {
        "job_id": job.id,
        "status": job.status,
        "description": job.description,
        "lean_source": job.lean_source,
        "proof": job.proof,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "attempts": [
            {
                "agent_index": a["agent_index"],
                "turn": a["turn"],
                "compiler_output": a["compiler_output"][:500],
                "llm_model": a["llm_model"],
                "success": bool(a["success"]),
                "created_at": a["created_at"],
            }
            for a in attempts
        ],
    }


@router.post("")
async def submit_theorem(request: Request, body: SubmitTheoremRequest):
    runner, event_bus = _get_services(request)

    lean_stub_tpl = (
        "import Mathlib\n\ntheorem user_theorem : {statement} := by\n  sorry\n"
    )
    lean_source = body.lean_stub or lean_stub_tpl.format(statement=body.statement)
    if body.hints:
        lean_source = f"-- HINTS: {body.hints}\n" + lean_source

    job_id = await runner.start_job(
        lean_source=lean_source,
        description=body.statement[:200],
        tier=body.tier,
        parallel_agents=body.parallel_agents,
        max_turns=body.max_turns,
    )

    event_bus.publish_job_status(job_id, "queued")
    return {"job_id": job_id, "status": "queued"}


@router.post("/lean-file")
async def submit_lean_file(request: Request, body: SubmitLeanFileRequest):
    runner, event_bus = _get_services(request)
    if "sorry" not in body.lean_source:
        raise HTTPException(
            status_code=400,
            detail="No sorry found in Lean source. Nothing to prove.",
        )
    job_id = await runner.start_job(
        lean_source=body.lean_source,
        description=body.description,
        tier=body.tier,
        parallel_agents=body.parallel_agents,
        max_turns=body.max_turns,
    )
    event_bus.publish_job_status(job_id, "queued")
    return {"job_id": job_id, "status": "queued"}


@router.post("/{job_id}/cancel")
async def cancel_job(request: Request, job_id: str):
    runner, event_bus = _get_services(request)
    cancelled = await runner.cancel(job_id)
    if cancelled:
        event_bus.publish_job_status(job_id, "cancelled")
        return {"job_id": job_id, "status": "cancelled"}
    job = await runner.jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {"job_id": job_id, "status": job.status, "message": "No live task."}

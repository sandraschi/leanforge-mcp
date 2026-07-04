"""SSE endpoint for live job updates."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["stream"])


@router.get("/{job_id}/stream")
async def job_stream(request: Request, job_id: str):
    runner, event_bus = request.app.state.runner, request.app.state.event_bus

    job = await runner.jobs.get_job(job_id)
    if job is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Job not found."})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    if job.status in ("complete", "failed", "cancelled"):
        async def early_generator():
            yield f"data: {json.dumps({'type': 'done', 'status': job.status})}\n\n"
        return StreamingResponse(early_generator(), media_type="text/event-stream", headers=headers)

    queue = event_bus.subscribe(job_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") == "job_status" and event.get("status") in (
                        "complete",
                        "failed",
                        "cancelled",
                    ):
                        yield f"data: {json.dumps({'type': 'done', 'status': event['status']})}\n\n"
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=headers,
    )

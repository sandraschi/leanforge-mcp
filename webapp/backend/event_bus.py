"""In-memory event bus for live job updates via SSE."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class JobEventBus:
    """Per-job asyncio.Queue fan-out for live agent turn events."""

    def __init__(self):
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        queues = self._queues.get(job_id, [])
        if queue in queues:
            queues.remove(queue)
        if not self._queues.get(job_id):
            self._queues.pop(job_id, None)

    def publish(self, job_id: str, event: dict):
        event["_ts"] = datetime.now(timezone.utc).isoformat()
        queues = self._queues.get(job_id, [])
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def publish_job_status(self, job_id: str, status: str, **extra):
        self.publish(job_id, {"type": "job_status", "status": status, **extra})

    def publish_attempt(
        self,
        job_id: str,
        agent_index: int,
        turn: int,
        compiler_output: str,
        model: str,
        success: bool,
        **extra,
    ):
        self.publish(
            job_id,
            {
                "type": "attempt",
                "agent_index": agent_index,
                "turn": turn,
                "compiler_output": compiler_output[:400],
                "model": model,
                "success": success,
                **extra,
            },
        )

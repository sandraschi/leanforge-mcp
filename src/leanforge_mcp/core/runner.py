"""
Job runner: fire-and-forget orchestration tying together
JobManager, LeanClient, LLMClient, and the agent loop.

The Runner is created in the server lifespan and stored in FastMCP's lifespan
context under the key "runner". Tool handlers retrieve it via get_runner(ctx).
"""

from __future__ import annotations

import asyncio
import logging

from leanforge_mcp.core.agent import run_parallel_agents
from leanforge_mcp.core.config import Config
from leanforge_mcp.core.job_manager import JobManager
from leanforge_mcp.core.lean_client import LeanClient
from leanforge_mcp.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Process-level fallback set by the server lifespan. The lifespan-context
# route through mounted child routers is fragile across fastmcp versions
# (a child's empty lifespan dict short-circuits the parent fallback), so the
# server lifespan also anchors the Runner here. Single process, single Runner.
_runner_fallback: Runner | None = None


def set_runner_fallback(runner: Runner | None) -> None:
    """Called by the server lifespan on startup (and with None on shutdown)."""
    global _runner_fallback
    _runner_fallback = runner


class Runner:
    """
    Holds shared LeanClient, JobManager, config, and the live task registry.
    One instance per server process, stored in FastMCP lifespan context.
    """

    def __init__(
        self,
        config: Config,
        job_manager: JobManager,
        lean: LeanClient,
        event_bus: object | None = None,
    ):
        self.config = config
        self.jobs = job_manager
        self.lean = lean
        self._tasks: dict[str, asyncio.Task] = {}
        self._event_bus = event_bus

    def _make_llm(self, start_tier: int) -> LLMClient:
        """Factory producing a fresh LLMClient starting at the requested tier."""
        return LLMClient(
            config=self.config.llm,
            start_tier=start_tier,
            escalate_to_tier2_after=self.config.agent.escalate_to_tier2_after,
            escalate_to_tier3_after=self.config.agent.escalate_to_tier3_after,
        )

    async def start_job(
        self,
        lean_source: str,
        description: str,
        tier: int,
        parallel_agents: int,
        max_turns: int,
    ) -> str:
        """Persist a job record and launch the background search task."""
        job_id = await self.jobs.create_job(
            lean_source=lean_source,
            description=description,
            tier_config={"start_tier": tier},
            parallel_agents=parallel_agents,
            max_turns=max_turns,
        )
        task = asyncio.create_task(
            self._run(job_id, lean_source, tier, parallel_agents, max_turns),
            name=f"job-{job_id[:8]}",
        )
        self._tasks[job_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job_id, None))
        return job_id

    async def _run(
        self,
        job_id: str,
        lean_source: str,
        tier: int,
        parallel_agents: int,
        max_turns: int,
    ) -> None:
        await self.jobs.set_running(job_id)
        self._pub(job_id, "running")

        async def on_attempt(agent_index, turn, src, output, model, success):
            await self.jobs.record_attempt(job_id, agent_index, turn, src, output, model, success)
            self._pub_attempt(job_id, agent_index, turn, output, model, success)

        try:
            result = await run_parallel_agents(
                source=lean_source,
                llm_factory=lambda: self._make_llm(tier),
                lean=self.lean,
                n_agents=parallel_agents,
                max_turns=max_turns,
                on_attempt=on_attempt,
            )
        except asyncio.CancelledError:
            await self.jobs.set_cancelled(job_id)
            self._pub(job_id, "cancelled")
            logger.info("Job %s cancelled", job_id)
            raise
        except Exception:
            logger.exception("Job %s crashed", job_id)
            await self.jobs.set_failed(job_id)
            self._pub(job_id, "failed")
            return

        if result and result.proven:
            await self.jobs.set_complete(job_id, result.final_source)
            self._pub(job_id, "complete")
        else:
            await self.jobs.set_failed(job_id)
            self._pub(job_id, "failed")

    def _pub(self, job_id: str, status: str, **kw):
        if self._event_bus:
            self._event_bus.publish_job_status(job_id, status, **kw)

    def _pub_attempt(
        self,
        job_id: str,
        agent_index: int,
        turn: int,
        output: str,
        model: str,
        success: bool,
    ):
        if self._event_bus:
            self._event_bus.publish_attempt(
                job_id,
                agent_index,
                turn,
                output,
                model,
                success,
            )

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running job. Returns True if a live task was found."""
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False


def get_runner(ctx) -> Runner:
    """
    Retrieve the Runner. Tools live on mounted child routers, so this tries,
    in order:
      1. This server's own lifespan dict (ctx.lifespan_context) — works when
         a tool is registered directly on the parent server.
      2. The session's request-context lifespan dict — the parent's lifespan
         for mounted children. NOTE: ctx.lifespan_context does NOT fall back
         here when the child's lifespan yielded an empty dict (verified
         against installed fastmcp; see tests/test_server_integration.py).
      3. The process-level fallback set by the server lifespan.
    """
    try:
        runner = ctx.lifespan_context.get("runner")
        if runner is not None:
            return runner
    except AttributeError:
        pass
    try:
        rc = ctx.request_context
        if rc is not None:
            lc = getattr(rc, "lifespan_context", None)
            if isinstance(lc, dict):
                runner = lc.get("runner")
                if runner is not None:
                    return runner
    except (AttributeError, ValueError):
        pass
    if _runner_fallback is not None:
        return _runner_fallback
    raise RuntimeError(
        "Runner not found in lifespan context. Server may not have completed startup."
    )

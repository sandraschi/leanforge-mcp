"""
FastAPI backend for the leanforge-mcp webapp.

Shares the same SQLite DB and core modules (Runner, LeanClient, JobManager)
as the stdio MCP server. Runs as a separate process to provide REST API + SSE
for the web frontend.

Usage:
    cd D:\\Dev\\repos\\leanforge-mcp
    uv run python -m webapp.backend.main
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from leanforge_mcp.core.config import load_config
from leanforge_mcp.core.job_manager import JobManager
from leanforge_mcp.core.lean_client import LeanClient
from leanforge_mcp.core.runner import Runner

from webapp.backend.event_bus import JobEventBus
from webapp.backend.routes import docs, jobs, problems, status, stream

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.toml"
BACKEND_PORT = 10855

logger = logging.getLogger("leanforge.web")


def _load_config_or_exit():
    if not CONFIG_PATH.exists():
        print(f"ERROR: config.toml not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    return load_config(CONFIG_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = _load_config_or_exit()

    job_manager = JobManager(Path(config.database.path))
    await job_manager.init()

    lean = LeanClient(
        lake_path=Path(config.lean.lake_path),
        workspace_dir=Path(config.lean.workspace_dir),
        timeout=config.lean.compile_timeout,
        compile_semaphore=asyncio.Semaphore(config.lean.max_concurrent_compiles),
    )

    # Check workspace once at startup and cache — the status endpoint returns
    # this cached result so it never blocks on a Lean compile at request time.
    ws_ok, ws_msg = await lean.ensure_workspace()
    app.state.lean_workspace_status = {
        "ok": ws_ok,
        "message": ws_msg,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    if ws_ok:
        logger.info("Lean workspace OK")
    else:
        logger.warning("Lean workspace not ready:\n%s", ws_msg)

    event_bus = JobEventBus()
    runner = Runner(
        config=config, job_manager=job_manager, lean=lean, event_bus=event_bus
    )

    app.state.config = config
    app.state.runner = runner
    app.state.event_bus = event_bus

    logger.info("leanforge-mcp web backend ready on port %d", BACKEND_PORT)
    yield

    for job_id in list(runner._tasks.keys()):
        await runner.cancel(job_id)
    logger.info("leanforge-mcp web backend shut down")


app = FastAPI(
    title="leanforge-mcp",
    description="Formal proof search for Lean 4 — web dashboard",
    version="0.1.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status.router)
app.include_router(jobs.router)
app.include_router(problems.router)
app.include_router(stream.router)
app.include_router(docs.router)


def main():
    config = _load_config_or_exit()
    log_file = Path(config.logging.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
    )
    uvicorn.run(app, host="127.0.0.1", port=BACKEND_PORT, log_level="info")


if __name__ == "__main__":
    main()

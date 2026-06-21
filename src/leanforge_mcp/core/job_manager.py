"""
SQLite-backed job manager.
Persists jobs and attempts; handles parallel subagent lifecycle.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import aiosqlite

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "complete", "failed", "cancelled", "interrupted"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    lean_source TEXT NOT NULL,
    proof TEXT,
    description TEXT,
    tier_config TEXT,
    parallel_agents INTEGER NOT NULL DEFAULT 4,
    max_turns INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    agent_index INTEGER NOT NULL,
    turn INTEGER NOT NULL,
    lean_source TEXT NOT NULL,
    compiler_output TEXT NOT NULL,
    llm_model TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_job ON attempts(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


@dataclass
class JobRecord:
    id: str
    created_at: str
    updated_at: str
    status: JobStatus
    lean_source: str
    proof: str | None
    description: str
    tier_config: str
    parallel_agents: int
    max_turns: int


class JobManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
            # Mark any RUNNING jobs as INTERRUPTED (process crashed)
            await db.execute(
                "UPDATE jobs SET status='interrupted', updated_at=? WHERE status='running'",
                (self._now(),),
            )
            await db.commit()
        logger.info("JobManager initialised at %s", self.db_path)

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    async def create_job(
        self,
        lean_source: str,
        description: str = "",
        tier_config: dict | None = None,
        parallel_agents: int = 4,
        max_turns: int = 100,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO jobs
                   (id, created_at, updated_at, status, lean_source, proof,
                    description, tier_config, parallel_agents, max_turns)
                   VALUES (?, ?, ?, 'queued', ?, NULL, ?, ?, ?, ?)""",
                (
                    job_id,
                    now,
                    now,
                    lean_source,
                    description,
                    json.dumps(tier_config or {}),
                    parallel_agents,
                    max_turns,
                ),
            )
            await db.commit()
        logger.info("Created job %s", job_id)
        return job_id

    async def set_running(self, job_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET status='running', updated_at=? WHERE id=?",
                (self._now(), job_id),
            )
            await db.commit()

    async def set_complete(self, job_id: str, proof: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET status='complete', proof=?, updated_at=? WHERE id=?",
                (proof, self._now(), job_id),
            )
            await db.commit()
        logger.info("Job %s COMPLETE", job_id)

    async def set_failed(self, job_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET status='failed', updated_at=? WHERE id=?",
                (self._now(), job_id),
            )
            await db.commit()
        logger.info("Job %s FAILED", job_id)

    async def set_cancelled(self, job_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE jobs SET status='cancelled', updated_at=? WHERE id=?",
                (self._now(), job_id),
            )
            await db.commit()

    async def record_attempt(
        self,
        job_id: str,
        agent_index: int,
        turn: int,
        lean_source: str,
        compiler_output: str,
        llm_model: str,
        success: bool,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO attempts
                   (id, job_id, agent_index, turn, lean_source,
                    compiler_output, llm_model, success, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    job_id,
                    agent_index,
                    turn,
                    lean_source,
                    compiler_output,
                    llm_model,
                    1 if success else 0,
                    self._now(),
                ),
            )
            await db.commit()

    async def get_job(self, job_id: str) -> JobRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return JobRecord(**dict(row))

    async def list_jobs(self, status: str | None = None, limit: int = 20) -> list[JobRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                async with db.execute(
                    "SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ) as cursor:
                    rows = await cursor.fetchall()
            else:
                async with db.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ) as cursor:
                    rows = await cursor.fetchall()
            return [JobRecord(**dict(r)) for r in rows]

    async def get_attempts(
        self,
        job_id: str,
        agent_index: int | None = None,
        last_n: int = 10,
    ) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if agent_index is not None:
                async with db.execute(
                    """SELECT * FROM attempts WHERE job_id=? AND agent_index=?
                       ORDER BY turn DESC LIMIT ?""",
                    (job_id, agent_index, last_n),
                ) as cursor:
                    rows = await cursor.fetchall()
            else:
                async with db.execute(
                    """SELECT * FROM attempts WHERE job_id=?
                       ORDER BY turn DESC LIMIT ?""",
                    (job_id, last_n),
                ) as cursor:
                    rows = await cursor.fetchall()
            return [dict(r) for r in rows]

"""
SQLite-backed job manager.
Persists jobs and attempts; handles parallel subagent lifecycle.

Two processes share this DB: the stdio MCP server and the webapp FastAPI
backend, each with their own JobManager/Runner instance. Two cross-process
concerns this module addresses (docs/ASSESSMENT_2026-06-24.md P1-4, P1-6):

- owner_pid / owner_started_at: which process actually owns a 'running'
  job, so the OTHER process's startup sweep does not falsely mark a still-
  live job as interrupted just because it isn't running in THIS process.
  started_at is stored alongside the PID because PIDs get reused by the OS
  over time; matching both closes that (low-probability but real) gap.
- cancel_requested: a polled flag any process can set, so a job started in
  one process can be cancelled from the other. The agent loop (agent.py)
  checks this once per turn via an injected callable -- see Runner._run.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import aiosqlite
import psutil

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
    max_turns INTEGER NOT NULL DEFAULT 100,
    owner_pid INTEGER,
    owner_started_at REAL,
    cancel_requested INTEGER NOT NULL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS problems (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    statement TEXT NOT NULL,
    lean_source TEXT,
    source TEXT DEFAULT 'user',
    difficulty TEXT DEFAULT 'medium',
    tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Columns added after the original schema shipped. Existing DBs (e.g. a
# jobs.db from before this fix) need these added via ALTER TABLE, since
# SQLite has no "ADD COLUMN IF NOT EXISTS" and CREATE TABLE IF NOT EXISTS
# is a no-op against an already-existing table.
_MIGRATION_COLUMNS = {
    "owner_pid": "INTEGER",
    "owner_started_at": "REAL",
    "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
}


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
    owner_pid: int | None = None
    owner_started_at: float | None = None
    cancel_requested: int = 0


class JobManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # This process's own identity, stamped onto jobs it starts running
        # so other processes' startup sweeps can tell "still mine and
        # alive" from "orphaned, safe to mark interrupted".
        self._own_pid = os.getpid()
        try:
            self._own_started_at = psutil.Process(self._own_pid).create_time()
        except psutil.Error:
            # Extremely unlikely (reading our own process info), but if it
            # ever happens, fall back to PID-only comparison downstream.
            logger.warning("Could not read own process create_time()", exc_info=True)
            self._own_started_at = None

    async def _configure_db(self, db: aiosqlite.Connection) -> None:
        """Apply connection-level pragmas. Call on every new connection."""
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA synchronous=NORMAL")

    async def _migrate(self, db: aiosqlite.Connection) -> None:
        async with db.execute("PRAGMA table_info(jobs)") as cursor:
            existing = {row[1] async for row in cursor}  # row[1] = column name
        for col, col_type in _MIGRATION_COLUMNS.items():
            if col not in existing:
                logger.info("Migrating jobs table: adding column %s", col)
                await db.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")

    def _owner_alive(self, pid: int | None, started_at: float | None) -> bool:
        """True if `pid` is a live process AND (when we have a creation
        timestamp to compare) it's the SAME process incarnation -- guards
        against the OS having reused `pid` for an unrelated process since
        the job was marked running. Fails safe: on any psutil error other
        than a confirmed "no such process", assume alive rather than risk
        discarding a job that's actually still running."""
        if pid is None:
            return False
        try:
            proc = psutil.Process(pid)
            if started_at is not None:
                # Small tolerance for float/OS timestamp rounding.
                return abs(proc.create_time() - started_at) < 2.0
            return proc.is_running()
        except psutil.NoSuchProcess:
            return False
        except psutil.Error:
            logger.warning("Could not verify owner pid=%s liveness; assuming alive", pid, exc_info=True)
            return True

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
            await db.executescript(SCHEMA)
            await db.commit()
            await self._migrate(db)
            await db.commit()

            # Sweep 'running' jobs: only mark interrupted the ones whose
            # owning process is confirmed gone. A job left 'running' by a
            # STILL-LIVE other process (P1-4) is left alone -- the other
            # process's own Runner is still working on it.
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT id, owner_pid, owner_started_at FROM jobs WHERE status='running'") as cursor:
                running = await cursor.fetchall()
            orphaned = [r["id"] for r in running if not self._owner_alive(r["owner_pid"], r["owner_started_at"])]
            if orphaned:
                now = self._now()
                await db.executemany(
                    "UPDATE jobs SET status='interrupted', updated_at=? WHERE id=?",
                    [(now, jid) for jid in orphaned],
                )
                await db.commit()
                logger.info("Marked %d orphaned running job(s) as interrupted", len(orphaned))
            still_owned = len(running) - len(orphaned)
            if still_owned:
                logger.info("%d running job(s) still owned by a live process -- left alone", still_owned)
        logger.info("JobManager initialised at %s (pid=%s)", self.db_path, self._own_pid)

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
            await self._configure_db(db)
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
        """Mark running AND stamp this process as the owner (P1-4)."""
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
            await db.execute(
                """UPDATE jobs SET status='running', updated_at=?,
                   owner_pid=?, owner_started_at=? WHERE id=?""",
                (self._now(), self._own_pid, self._own_started_at, job_id),
            )
            await db.commit()

    async def set_complete(self, job_id: str, proof: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
            await db.execute(
                "UPDATE jobs SET status='complete', proof=?, updated_at=? WHERE id=?",
                (proof, self._now(), job_id),
            )
            await db.commit()
        logger.info("Job %s COMPLETE", job_id)

    async def set_failed(self, job_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
            await db.execute(
                "UPDATE jobs SET status='failed', updated_at=? WHERE id=?",
                (self._now(), job_id),
            )
            await db.commit()
        logger.info("Job %s FAILED", job_id)

    async def set_cancelled(self, job_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
            await db.execute(
                "UPDATE jobs SET status='cancelled', updated_at=? WHERE id=?",
                (self._now(), job_id),
            )
            await db.commit()

    async def request_cancel(self, job_id: str) -> None:
        """Set the cross-process cancel flag (P1-6). Safe to call from any
        process regardless of which one owns the job; the owning process's
        agent loop polls this once per turn via Runner._run's is_cancelled
        callback. Harmless no-op if the job is already terminal."""
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
            await db.execute(
                "UPDATE jobs SET cancel_requested=1, updated_at=? WHERE id=?",
                (self._now(), job_id),
            )
            await db.commit()

    async def is_cancel_requested(self, job_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
            async with db.execute("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,)) as cursor:
                row = await cursor.fetchone()
        return bool(row and row[0])

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
            await self._configure_db(db)
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
            await self._configure_db(db)
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return JobRecord(**dict(row))

    async def list_jobs(self, status: str | None = None, limit: int = 20) -> list[JobRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
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
            await self._configure_db(db)
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

    async def get_job_counts(self) -> dict[str, int]:
        async with aiosqlite.connect(self.db_path) as db:
            await self._configure_db(db)
            async with db.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status") as cursor:
                rows = await cursor.fetchall()
            counts = {status: count for status, count in rows}
            counts["total"] = sum(counts.values())
            return counts

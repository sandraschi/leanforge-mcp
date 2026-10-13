"""
Tests for cross-process job ownership and cancellation
(docs/ASSESSMENT_2026-06-24.md P1-4, P1-6). Run with: uv run pytest tests/ -v.

No Lean/Mathlib needed -- these exercise the SQLite job store directly.
Two JobManager instances against the same DB file stand in for the two
real processes (stdio MCP server + webapp FastAPI backend) that share
data/jobs.db in production.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time

import pytest

from leanforge_mcp.core.job_manager import JobManager


@pytest.mark.asyncio
async def test_fresh_db_has_new_columns(tmp_path):
    jm = JobManager(tmp_path / "jobs.db")
    await jm.init()
    conn = sqlite3.connect(tmp_path / "jobs.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    conn.close()
    assert {"owner_pid", "owner_started_at", "cancel_requested"} <= cols


@pytest.mark.asyncio
async def test_migration_adds_columns_to_legacy_db(tmp_path):
    """Simulates a pre-fix jobs.db: create the OLD schema by hand (no new
    columns), then confirm JobManager.init() migrates it in place without
    losing data."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE jobs (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            status TEXT NOT NULL, lean_source TEXT NOT NULL, proof TEXT,
            description TEXT, tier_config TEXT,
            parallel_agents INTEGER NOT NULL DEFAULT 4,
            max_turns INTEGER NOT NULL DEFAULT 100
        )"""
    )
    conn.execute(
        "INSERT INTO jobs (id, created_at, updated_at, status, lean_source, description, tier_config) "
        "VALUES ('legacy-1', 't', 't', 'complete', 'theorem foo : 1=1 := by sorry', 'old job', '{}')"
    )
    conn.commit()
    conn.close()

    jm = JobManager(db_path)
    await jm.init()  # must not raise, must migrate

    job = await jm.get_job("legacy-1")
    assert job is not None
    assert job.status == "complete"  # pre-existing data preserved
    assert job.owner_pid is None  # migrated column, no data for old rows
    assert job.cancel_requested == 0


@pytest.mark.asyncio
async def test_set_running_stamps_owner(tmp_path):
    jm = JobManager(tmp_path / "jobs.db")
    await jm.init()
    job_id = await jm.create_job("theorem foo : 1=1 := by sorry")
    await jm.set_running(job_id)
    job = await jm.get_job(job_id)
    assert job.status == "running"
    assert job.owner_pid == os.getpid()
    assert job.owner_started_at is not None


@pytest.mark.asyncio
async def test_startup_sweep_leaves_live_owner_running(tmp_path):
    """P1-4 core regression: a 'running' job owned by a PROCESS THAT IS
    STILL ALIVE must NOT be marked interrupted just because a fresh
    JobManager.init() (e.g. from a second process) runs against the same
    DB. Uses THIS test process's own pid as the stand-in live owner."""
    db_path = tmp_path / "jobs.db"
    jm = JobManager(db_path)
    await jm.init()
    job_id = await jm.create_job("theorem foo : 1=1 := by sorry")
    await jm.set_running(job_id)  # stamps owner_pid = this test process

    # Simulate a SECOND process calling init() against the same DB.
    jm2 = JobManager(db_path)
    await jm2.init()

    job = await jm2.get_job(job_id)
    assert job.status == "running"  # NOT interrupted -- owner is this (live) process


@pytest.mark.asyncio
async def test_startup_sweep_interrupts_dead_owner(tmp_path):
    """The other half of P1-4: a 'running' job whose owner PID is
    confirmed gone MUST be marked interrupted. Spawns and kills a real
    child process to get a guaranteed-dead, non-reused-yet pid within the
    test's short lifetime."""
    db_path = tmp_path / "jobs.db"
    jm = JobManager(db_path)
    await jm.init()
    job_id = await jm.create_job("theorem foo : 1=1 := by sorry")

    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
    dead_pid = proc.pid
    proc.wait()
    time.sleep(0.05)  # let the OS fully reap it

    # Manually stamp this job as owned by the now-dead pid (simulating a
    # crash: set_running would have done this while the process was alive).
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE jobs SET status='running', owner_pid=?, owner_started_at=? WHERE id=?",
        (dead_pid, 1.0, job_id),  # started_at=1.0 deliberately won't match anything alive
    )
    conn.commit()
    conn.close()

    jm2 = JobManager(db_path)
    await jm2.init()

    job = await jm2.get_job(job_id)
    assert job.status == "interrupted"


@pytest.mark.asyncio
async def test_cancel_flag_round_trip(tmp_path):
    jm = JobManager(tmp_path / "jobs.db")
    await jm.init()
    job_id = await jm.create_job("theorem foo : 1=1 := by sorry")
    assert await jm.is_cancel_requested(job_id) is False
    await jm.request_cancel(job_id)
    assert await jm.is_cancel_requested(job_id) is True


@pytest.mark.asyncio
async def test_cancel_flag_from_different_manager_instance(tmp_path):
    """The whole point of P1-6: one 'process' (JobManager instance) sets
    the flag, a DIFFERENT one reads it -- must see the same value via the
    shared DB file."""
    db_path = tmp_path / "jobs.db"
    jm1 = JobManager(db_path)
    await jm1.init()
    job_id = await jm1.create_job("theorem foo : 1=1 := by sorry")

    jm2 = JobManager(db_path)  # stand-in for the OTHER process
    await jm2.request_cancel(job_id)

    assert await jm1.is_cancel_requested(job_id) is True

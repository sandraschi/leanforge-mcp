"""CRUD endpoints for the problem library."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/problems", tags=["problems"])

PROBLEMS_SCHEMA = """
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



class ProblemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1)
    lean_source: str | None = None
    source: str = "user"
    difficulty: str = "medium"
    tags: str = ""
    notes: str = ""


class ProblemUpdate(BaseModel):
    title: str | None = None
    statement: str | None = None
    lean_source: str | None = None
    source: str | None = None
    difficulty: str | None = None
    tags: str | None = None
    notes: str | None = None


def _now():
    return datetime.now(timezone.utc).isoformat()


@router.get("")
async def list_problems(request: Request, source: str | None = None, limit: int = 50):
    db_path = request.app.state.config.database.path
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        if source:
            async with db.execute(
                "SELECT * FROM problems WHERE source=? ORDER BY updated_at DESC LIMIT ?",
                (source, limit),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM problems ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ) as cur:
                rows = await cur.fetchall()
    return {
        "count": len(rows),
        "problems": [dict(r) for r in rows],
    }


@router.get("/{problem_id}")
async def get_problem(request: Request, problem_id: str):
    db_path = request.app.state.config.database.path
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM problems WHERE id=?", (problem_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Problem not found.")
    return dict(row)


@router.post("", status_code=201)
async def create_problem(request: Request, body: ProblemCreate):
    pid = str(uuid.uuid4())
    now = _now()
    db_path = request.app.state.config.database.path
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO problems
               (id, title, statement, lean_source, source, difficulty, tags, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, body.title, body.statement, body.lean_source, body.source,
             body.difficulty, body.tags, body.notes, now, now),
        )
        await db.commit()
    return {"id": pid, "message": "Problem created."}


@router.put("/{problem_id}")
async def update_problem(request: Request, problem_id: str, body: ProblemUpdate):
    now = _now()
    fields = []
    values = []
    for key in ("title", "statement", "lean_source", "source", "difficulty", "tags", "notes"):
        val = getattr(body, key, None)
        if val is not None:
            fields.append(f"{key}=?")
            values.append(val)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    fields.append("updated_at=?")
    values.append(now)
    values.append(problem_id)
    db_path = request.app.state.config.database.path
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"UPDATE problems SET {', '.join(fields)} WHERE id=?", values
        )
        await db.commit()
    return {"message": "Problem updated."}


@router.delete("/{problem_id}")
async def delete_problem(request: Request, problem_id: str):
    db_path = request.app.state.config.database.path
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM problems WHERE id=?", (problem_id,))
        await db.commit()
    return {"message": "Problem deleted."}

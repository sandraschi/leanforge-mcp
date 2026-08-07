"""
leanforge-mcp: MCP server for AI-driven formal proof search in Lean 4.

Architecture: Agent A from AlphaProof Nexus (arXiv:2605.22763).
N independent subagents, compiler feedback as oracle, LLM tier escalation.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan as fastmcp_lifespan

from leanforge_mcp.core.config import load_config
from leanforge_mcp.core.job_manager import JobManager
from leanforge_mcp.core.lean_client import LeanClient
from leanforge_mcp.core.runner import Runner, set_runner_fallback
from leanforge_mcp.tools import control, mathlib, status, submit

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.toml"


def _load_config():
    if not _CONFIG_PATH.exists():
        print(
            f"ERROR: config.toml not found at {_CONFIG_PATH}\n"
            "Copy config.example.toml to config.toml and fill in your values.",
            file=sys.stderr,
        )
        sys.exit(1)
    return load_config(_CONFIG_PATH)


@fastmcp_lifespan
async def lifespan(server: FastMCP):
    """
    Startup: initialise all components inside the SERVING event loop so async
    SQLite connections and the task registry belong to the right loop.
    Yields the Runner as lifespan context -- tools retrieve it via get_runner(ctx).
    """
    config = _load_config()

    job_manager = JobManager(Path(config.database.path))
    await job_manager.init()

    lean = LeanClient(
        lake_path=Path(config.lean.lake_path),
        workspace_dir=Path(config.lean.workspace_dir),
        timeout=config.lean.compile_timeout,
        compile_semaphore=asyncio.Semaphore(config.lean.max_concurrent_compiles),
    )

    ok, msg = await lean.ensure_workspace()
    if ok:
        logger.info("Lean workspace OK")
    else:
        logger.warning("Lean workspace not ready:\n%s", msg)

    runner = Runner(config=config, job_manager=job_manager, lean=lean)
    set_runner_fallback(runner)
    logger.info("Runner ready, leanforge-mcp serving")

    yield {"runner": runner}

    # Shutdown: cancel any live proof jobs
    set_runner_fallback(None)
    for job_id in list(runner._tasks.keys()):
        await runner.cancel(job_id)
    logger.info("leanforge-mcp shut down")


mcp = FastMCP(
    name="leanforge-mcp",
    instructions=(
        "Formal proof search for Lean 4 theorems. "
        "Submit a theorem statement; get back a machine-verified Lean 4 proof. "
        "Runs parallel agentic subagents: LLM proposes, Lean compiler judges."
    ),
    lifespan=lifespan,
)

# mount() with no prefix keeps tool names unmodified
# (submit_theorem, get_proof_status, validate_lean, etc.)
mcp.mount(submit.router)
mcp.mount(status.router)
mcp.mount(control.router)
mcp.mount(mathlib.router)

# -- Skills ----------------------------------------------------------------

_SKILL_DIR = Path(__file__).parent / "skills"


@mcp.resource("skill://lean-expert/SKILL.md")
async def get_lean_expert_skill() -> str:
    """Lean 4 Expert skill -- current versions, tactics, error fixes."""
    skill_path = _SKILL_DIR / "lean_expert" / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    return "Skill not found."


@mcp.resource("skill://{name}")
async def get_skill(name: str) -> str:
    """Generic skill resolver."""
    skill_path = _SKILL_DIR / name / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    return f"Skill '{name}' not found."


@mcp.resource("resource://skills/list")
async def list_skills() -> str:
    """List all available skills."""
    if not _SKILL_DIR.is_dir():
        return "[]"
    skills = [p.parent.name for p in _SKILL_DIR.rglob("SKILL.md")]
    import json

    return json.dumps(skills)


# -- Prompts ---------------------------------------------------------------


@mcp.prompt()
async def lean_help(topic: str = "") -> str:
    """Get help with a Lean concept, tactic, or error."""
    if not topic:
        return (
            "I can help with Lean 4. Ask about tactics (simp, omega, ring, "
            "linarith), syntax (calc blocks, match expressions), common errors, "
            "or Mathlib lemmas. What would you like to know?"
        )
    return f"Here's what I know about '{topic}' in Lean 4.\n\nConsulting skill context...\n\nUse `get_mathlib_search` to find relevant lemmas."


@mcp.prompt()
async def theorem_coaching() -> str:
    """Get step-by-step guidance through a Lean proof."""
    return (
        "I'll help you write a Lean 4 proof. Describe the theorem you're trying "
        "to prove, what you've tried, and where you're stuck. I can suggest "
        "tactics, lemmas from Mathlib, and proof strategies."
    )


def main() -> None:
    config = _load_config()
    log_file = Path(config.logging.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    logger.info("leanforge-mcp starting")
    mcp.run(transport=config.server.transport)


if __name__ == "__main__":
    main()

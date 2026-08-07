"""MCP tools: submit_theorem, submit_lean_file"""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from leanforge_mcp.core.runner import get_runner

router = FastMCP("submit")

LEAN_STUB_TEMPLATE = """\
import Mathlib

-- {description}
theorem user_theorem : {statement} := by
  sorry
"""


class SubmitTheoremInput(BaseModel):
    statement: str = Field(
        description=(
            "The theorem to prove, as a Lean 4 proposition (the part after the colon). "
            "Example: '∀ n : N, 2 * ∑ i ∈ Finset.range (n+1), i = n * (n+1)'. "
            "Will be wrapped in a Lean stub with sorry."
        )
    )
    lean_stub: str | None = Field(
        default=None,
        description=(
            "Optional: a complete Lean 4 file with sorry placeholders. "
            "If provided, statement is used only for display. "
            "If omitted, the server wraps statement in a minimal Lean stub."
        ),
    )
    hints: str | None = Field(
        default=None,
        description="Optional: relevant Mathlib theorem names or proof strategy hints.",
    )
    tier: Annotated[int, Field(ge=1, le=3)] = Field(
        default=1,
        description=(
            "Starting LLM tier: 1=local Ollama free, 2=DeepSeek V4 Flash API cheap, "
            "3=Claude Fable 5 ($50/M output). Agents auto-escalate if they stall."
        ),
    )
    parallel_agents: Annotated[int, Field(ge=1, le=16)] = Field(default=4)
    max_turns: Annotated[int, Field(ge=1, le=1000)] = Field(default=100)


class SubmitLeanFileInput(BaseModel):
    lean_source: str = Field(description="Complete Lean 4 source file with sorry placeholders to fill.")
    description: str = Field(default="")
    tier: Annotated[int, Field(ge=1, le=3)] = Field(default=1)
    parallel_agents: Annotated[int, Field(ge=1, le=16)] = Field(default=4)
    max_turns: Annotated[int, Field(ge=1, le=1000)] = Field(default=100)


@router.tool(
    description=(
        "Submit a theorem for formal proof search. Returns a job_id immediately -- "
        "use get_proof_status to poll. The server runs parallel agents looping "
        "LLM-propose -> Lean-compile -> error-feedback until proven or budget exhausted."
    ),
)
async def submit_theorem(input: SubmitTheoremInput, ctx: Context) -> dict:
    runner = get_runner(ctx)
    if runner.lean.setup_in_progress:
        return {
            "status": "pending",
            "message": f"Leanforge setup running: {runner.lean.setup_status}. Try again shortly.",
        }
    if runner.lean.setup_error:
        return {
            "status": "error",
            "message": f"Leanforge setup failed: {runner.lean.setup_error}. Fix installation files.",
        }

    lean_source = input.lean_stub or LEAN_STUB_TEMPLATE.format(
        description=input.statement[:100],
        statement=input.statement,
    )
    if input.hints:
        lean_source = f"-- HINTS: {input.hints}\n" + lean_source

    job_id = await runner.start_job(
        lean_source=lean_source,
        description=input.statement[:200],
        tier=input.tier,
        parallel_agents=input.parallel_agents,
        max_turns=input.max_turns,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "tier": input.tier,
        "parallel_agents": input.parallel_agents,
        "max_turns": input.max_turns,
        "message": f"Job {job_id} started. Poll get_proof_status('{job_id}') every 10-30s.",
    }


@router.tool(
    description=(
        "Submit a complete Lean 4 file with sorry placeholders directly. "
        "Ideal for MiniF2F or AlphaProof Nexus problem stubs that are already formalized."
    ),
)
async def submit_lean_file(input: SubmitLeanFileInput, ctx: Context) -> dict:
    if "sorry" not in input.lean_source:
        return {
            "error": "No sorry found in Lean source. Nothing to prove.",
            "hint": "Add sorry where you want the agent to fill in proofs.",
        }

    runner = get_runner(ctx)
    if runner.lean.setup_in_progress:
        return {
            "status": "pending",
            "message": f"Leanforge setup running: {runner.lean.setup_status}. Try again shortly.",
        }
    if runner.lean.setup_error:
        return {
            "status": "error",
            "message": f"Leanforge setup failed: {runner.lean.setup_error}. Fix installation files.",
        }
    job_id = await runner.start_job(
        lean_source=input.lean_source,
        description=input.description,
        tier=input.tier,
        parallel_agents=input.parallel_agents,
        max_turns=input.max_turns,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "description": input.description,
        "sorry_count": input.lean_source.count("sorry"),
        "message": f"Job {job_id} started. Poll get_proof_status('{job_id}').",
    }

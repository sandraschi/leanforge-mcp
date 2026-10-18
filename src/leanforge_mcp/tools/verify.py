"""MCP tool: verify_proof -- re-check a proven file with verified external kernels."""

from __future__ import annotations

from fastmcp import Context, FastMCP

from leanforge_mcp.core.runner import get_runner

router = FastMCP("verify")


@router.tool(
    description=(
        "Re-verify Lean 4 source with independent verified kernels (con-leche, con-ron). "
        "Compiles first: unproven input is rejected without touching the kernels. "
        "Proven input is exported via leanexport and replayed through each kernel; "
        "all must accept. Needs a workspace on Lean >= 4.35.0, otherwise returns "
        "supported=false with the upgrade path. Slow (minutes for Mathlib proofs) -- "
        "use for results that matter, not per-turn checking."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": True},
    output_schema={"type": "object"},
)
async def verify_proof(
    lean_source: str,
    ctx: Context,
) -> dict:
    """Re-verify Lean 4 source with independent verified kernels.

    ## Return Format
    `{"success": True, "proven": bool, "verified": bool, "supported": bool,
    "toolchain": str, "kernels": [...], "message": str}`. `success` means the
    check ran; `verified` means every kernel accepted.
    `{"success": False, "status": ..., "message": str}` when setup is pending
    or failed, or the input is not proven.

    ## Examples
    `verify_proof("import Mathlib\\nexample : 1 = 1 := rfl\\n")`
    -> `{"success": True, "proven": True, "verified": ..., ...}` (needs a
    Lean >= 4.35.0 workspace for kernel replay, else `supported: False`).
    """
    runner = get_runner(ctx)
    if runner.lean.setup_in_progress:
        return {
            "success": False,
            "proven": False,
            "verified": False,
            "status": "pending",
            "message": f"Leanforge setup running: {runner.lean.setup_status}. Try again shortly.",
        }
    if runner.lean.setup_error:
        return {
            "success": False,
            "proven": False,
            "verified": False,
            "status": "error",
            "message": f"Leanforge setup failed: {runner.lean.setup_error}. Fix installation files.",
        }
    compiled = await runner.lean.compile(lean_source)
    if not compiled.proven:
        return {
            "success": False,
            "proven": False,
            "verified": False,
            "has_sorry": compiled.has_sorry,
            "errors": compiled.errors,
            "warnings": compiled.warnings,
            "message": "Not proven by the official kernel; fix compile errors first.",
        }
    cfg = runner.config.lean
    result = await runner.lean.verify_external(
        lean_source,
        kernels=tuple(cfg.external_checkers),
        verify_lib=cfg.verify_lib,
        timeout=cfg.verify_timeout,
    )
    return {
        "success": True,
        "proven": True,
        "verified": result.all_accepted,
        "supported": result.supported,
        "toolchain": result.toolchain_version,
        "kernels": [
            {
                "kernel": v.kernel,
                "accepted": v.accepted,
                "declarations": v.declarations,
                "detail": v.detail,
            }
            for v in result.results
        ],
        "message": result.message,
    }

"""
Lean 4 compiler client.

Compiles Lean source inside a persistent Lake project so that `import Mathlib`
resolves. A bare `lean file.lean` cannot see Mathlib — Lean code must live in a
Lake project with dependencies on the search path. We invoke `lake env lean <file>`
which runs the Lean compiler with the project's full search path configured.

The Lake project (with Mathlib dependency + cached oleans) must be set up ONCE:
    lake new leanforge_workspace math
    cd leanforge_workspace
    lake exe cache get        # downloads precompiled Mathlib oleans (~4GB)
    lake build
See LeanClient.ensure_workspace() and docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

WARNING_SORRY = "declaration uses 'sorry'"
# A proof file still containing an unfilled `sorry` tactic. We rely PRIMARILY on
# the compiler warning, not source regex (a comment containing "sorry" must not
# count). This pattern is only a secondary guard for the specific case where the
# warning is suppressed.
SORRY_TACTIC = re.compile(r"(^|\s):=\s*by\b[\s\S]*?\bsorry\b|^\s*sorry\s*$", re.MULTILINE)


@dataclass
class CompileResult:
    success: bool
    has_sorry: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_stderr: str = ""
    raw_stdout: str = ""

    @property
    def proven(self) -> bool:
        """True only if compiled cleanly AND the compiler reports no sorry."""
        return self.success and not self.has_sorry

    @property
    def error_message(self) -> str:
        if self.errors:
            return "\n".join(self.errors)
        if self.raw_stderr.strip():
            return self.raw_stderr
        return ""


class LeanClient:
    """
    Compiles Lean source via `lake env lean <tmpfile>` inside a Lake project
    workspace that has Mathlib as a dependency.
    """

    def __init__(
        self,
        lake_path: Path,
        workspace_dir: Path,
        timeout: int = 120,
        compile_semaphore: asyncio.Semaphore | None = None,
    ):
        # NOTE: we invoke `lake`, not `lean` directly. lake_path points to lake.exe.
        self.lake_path = lake_path
        self.workspace_dir = workspace_dir
        self.timeout = timeout
        # Gate concurrent Lean processes — each loads Mathlib and can use GBs of RAM.
        # On 64GB Goliath, default to 4 concurrent compiles regardless of agent count.
        self._sem = compile_semaphore or asyncio.Semaphore(4)

    async def compile(self, source: str) -> CompileResult:
        """
        Write source to a temp file inside the workspace, compile with
        `lake env lean <file>`, capture output. Mathlib resolves because we run
        inside the Lake project.
        """
        tmp_name = f"_lf_{uuid.uuid4().hex}.lean"
        tmp_path = self.workspace_dir / tmp_name

        async with self._sem:
            try:
                tmp_path.write_text(source, encoding="utf-8")

                proc = await asyncio.create_subprocess_exec(
                    str(self.lake_path),
                    "env",
                    "lean",
                    str(tmp_path),
                    cwd=str(self.workspace_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(), timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.communicate()
                    logger.warning("Lean compile timed out after %ds", self.timeout)
                    return CompileResult(
                        success=False,
                        has_sorry=False,
                        errors=[f"Lean compile timed out after {self.timeout}s"],
                    )

                # Lean reports diagnostics on stdout (file:line:col: error/warning),
                # build/toolchain noise on stderr.
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                combined = stdout + "\n" + stderr

                errors = self._extract(combined, "error")
                warnings = self._extract(combined, "warning")
                has_sorry = WARNING_SORRY in combined
                success = proc.returncode == 0 and not errors

                return CompileResult(
                    success=success,
                    has_sorry=has_sorry,
                    errors=errors,
                    warnings=warnings,
                    raw_stderr=stderr,
                    raw_stdout=stdout,
                )

            except FileNotFoundError:
                msg = f"lake executable not found at {self.lake_path}"
                logger.error(msg)
                return CompileResult(success=False, has_sorry=False, errors=[msg])
            except Exception as exc:
                logger.exception("Unexpected error during Lean compile")
                return CompileResult(success=False, has_sorry=False, errors=[str(exc)])
            finally:
                tmp_path.unlink(missing_ok=True)

    def _extract(self, text: str, kind: str) -> list[str]:
        """Extract lines containing 'error:' or 'warning:' with surrounding context."""
        out = []
        marker = f"{kind}:"
        for line in text.splitlines():
            if marker in line.lower():
                out.append(line.strip())
        return out

    async def ensure_workspace(self) -> tuple[bool, str]:
        """
        Verify the Lake workspace exists and Mathlib resolves.
        Returns (ok, message). Does NOT create the workspace — that's a one-time
        manual setup (lake new / lake exe cache get) documented in ARCHITECTURE.md,
        because pulling Mathlib is a ~4GB download we don't want to trigger silently.
        """
        lakefile_toml = self.workspace_dir / "lakefile.toml"
        lakefile_lean = self.workspace_dir / "lakefile.lean"
        if not lakefile_toml.exists() and not lakefile_lean.exists():
            return (
                False,
                f"No lakefile in {self.workspace_dir}. Run one-time setup:\n"
                f"  cd {self.workspace_dir.parent}\n"
                f"  lake new {self.workspace_dir.name} math\n"
                f"  cd {self.workspace_dir.name}\n"
                f"  lake exe cache get\n"
                f"  lake build",
            )

        # Smoke test: compile a trivial Mathlib import.
        result = await self.compile("import Mathlib\nexample : 1 = 1 := rfl\n")
        if result.success:
            return (True, "Workspace OK, Mathlib resolves.")
        return (
            False,
            f"Workspace exists but Mathlib smoke test failed: {result.error_message[:300]}\n"
            "Try: lake exe cache get && lake build",
        )

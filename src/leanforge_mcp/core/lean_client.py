"""
Lean 4 compiler client.

Compiles Lean source inside a persistent Lake project so that `import Mathlib`
resolves. A bare `lean file.lean` cannot see Mathlib -- Lean code must live in a
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

DIAGNOSTIC_BLOCK = re.compile(
    r"^(.+?:\d+:\d+:\s*(?:error|warning|info):\s*[\s\S]*?)(?=\n(?:.+?:\d+:\d+:\s*(?:error|warning|info):|\Z))",
    re.MULTILINE | re.IGNORECASE
)


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
        if self.raw_stdout.strip():
            return self.raw_stdout
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
        # Gate concurrent Lean processes -- each loads Mathlib and can use GBs of RAM.
        # On 64GB Goliath, default to 4 concurrent compiles regardless of agent count.
        self._sem = compile_semaphore or asyncio.Semaphore(4)

        # Setup state
        self.setup_in_progress = False
        self.setup_status = ""
        self.setup_error = None
        self._setup_task = None

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
                except TimeoutError:
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
        """Extract Lean diagnostic blocks starting with 'file:line:col: kind: ...'"""
        blocks = DIAGNOSTIC_BLOCK.findall(text)
        out = []
        marker = re.compile(rf":\s*{kind}:\s*", re.IGNORECASE)
        for block in blocks:
            if marker.search(block):
                out.append(block.strip())
        return out

    async def ensure_workspace(self) -> tuple[bool, str]:
        """
        Verify the Lake workspace exists and Mathlib resolves.
        If missing or broken, starts background installation.
        Returns (ok, message).
        """
        if self.setup_in_progress:
            return False, f"Setup in progress: {self.setup_status}"
        if self.setup_error:
            return False, f"Setup failed: {self.setup_error}"

        if not self.lake_path.exists():
            self.start_background_setup()
            return False, "lake executable not found. Starting automatic background installation..."

        lakefile_toml = self.workspace_dir / "lakefile.toml"
        lakefile_lean = self.workspace_dir / "lakefile.lean"
        if not lakefile_toml.exists() and not lakefile_lean.exists():
            self.start_background_setup()
            return False, f"Workspace not initialized in {self.workspace_dir}. Starting background setup..."

        # Smoke test: compile a trivial Mathlib import.
        result = await self.compile("import Mathlib\nexample : 1 = 1 := rfl\n")
        if result.success:
            return True, "Workspace OK, Mathlib resolves."

        self.start_background_setup()
        return (
            False,
            f"Mathlib smoke test failed. Triggering automatic background repair: {result.error_message[:200]}",
        )

    def start_background_setup(self) -> None:
        if self.setup_in_progress:
            return
        self.setup_in_progress = True
        self.setup_status = "Starting background setup..."
        self.setup_error = None
        self._setup_task = asyncio.create_task(self._run_setup_task())

    async def _run_setup_task(self) -> None:
        try:
            # 1. Install elan if lake.exe is missing
            if not self.lake_path.exists():
                self.setup_status = "Downloading and running elan installer..."
                logger.info("elan/lake not found. Initiating silent elan-init install.")

                import tempfile
                import urllib.request

                # Run download in a threadpool to avoid blocking event loop
                with tempfile.TemporaryDirectory() as tmpdir:
                    ps1_path = Path(tmpdir) / "elan-init.ps1"
                    url = "https://elan.lean-lang.org/elan-init.ps1"
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, urllib.request.urlretrieve, url, str(ps1_path)
                    )

                    if not ps1_path.exists():
                        raise RuntimeError("Failed to download elan-init.ps1")

                    # Run installer silently with NoPrompt
                    proc = await asyncio.create_subprocess_exec(
                        "powershell.exe",
                        "-ExecutionPolicy", "Bypass",
                        "-File", str(ps1_path),
                        "-NoPrompt", "1",
                        "-DefaultToolchain", "stable",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _stdout, stderr = await proc.communicate()
                    if proc.returncode != 0:
                        err_msg = stderr.decode(errors="replace")
                        raise RuntimeError(f"elan-init execution failed with code {proc.returncode}: {err_msg}")

                if not self.lake_path.exists():
                    raise RuntimeError(f"elan-init succeeded but lake was not found at expected path: {self.lake_path}")
                logger.info("elan/lake successfully installed.")

            # 2. Create Lake math workspace if missing
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            lakefile_toml = self.workspace_dir / "lakefile.toml"
            lakefile_lean = self.workspace_dir / "lakefile.lean"

            if not lakefile_toml.exists() and not lakefile_lean.exists():
                self.setup_status = f"Creating new Lean math project in {self.workspace_dir.name}..."
                logger.info("Initializing new Lean project in workspace.")

                # If the directory exists but is empty, remove it to let lake new recreate it
                if self.workspace_dir.exists() and not list(self.workspace_dir.iterdir()):
                    self.workspace_dir.rmdir()

                proc = await asyncio.create_subprocess_exec(
                    str(self.lake_path),
                    "new",
                    self.workspace_dir.name,
                    "math",
                    cwd=str(self.workspace_dir.parent),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    err_msg = stderr.decode(errors="replace")
                    raise RuntimeError(f"lake new failed with code {proc.returncode}: {err_msg}")

            # 3. Download Mathlib cache
            self.setup_status = "Downloading Mathlib precompiled cache (this can take several minutes)..."
            logger.info("Downloading Mathlib precompiled cache.")
            proc = await asyncio.create_subprocess_exec(
                str(self.lake_path),
                "exe",
                "cache",
                "get",
                cwd=str(self.workspace_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_msg = stderr.decode(errors="replace")
                raise RuntimeError(f"lake exe cache get failed with code {proc.returncode}: {err_msg}")

            # 4. Build workspace
            self.setup_status = "Building Lean/Mathlib workspace (compiling files)..."
            logger.info("Building Lean/Mathlib workspace.")
            proc = await asyncio.create_subprocess_exec(
                str(self.lake_path),
                "build",
                cwd=str(self.workspace_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_msg = stderr.decode(errors="replace")
                raise RuntimeError(f"lake build failed with code {proc.returncode}: {err_msg}")

            # 5. Verify
            self.setup_status = "Verifying installation..."
            logger.info("Verifying Lean workspace compilation.")
            result = await self.compile("import Mathlib\nexample : 1 = 1 := rfl\n")
            if not result.success:
                raise RuntimeError(f"Workspace verification failed: {result.error_message}")

            self.setup_status = "Ready"
            self.setup_in_progress = False
            logger.info("Lean/Mathlib workspace setup successfully completed and verified.")

        except Exception as exc:
            logger.exception("Error during background Lean/Mathlib setup")
            self.setup_error = str(exc)
            self.setup_status = f"Failed: {exc}"
            self.setup_in_progress = False

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
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Lean's sorry warning. The quoting style around `sorry` is NOT stable across
# Lean versions: Lean 4.31 emits backticks (declaration uses `sorry`), older
# releases used straight quotes ('sorry'). Matching one literal spelling made
# has_sorry silently always-False, which reported `sorry` proofs as PROVEN --
# an inverted oracle. Match any quoting, and never go back to a bare literal.
WARNING_SORRY_RE = re.compile(
    r"declaration\s+uses\s+[`'\"\u2018\u2019\u201c\u201d]?sorry[`'\"\u2018\u2019\u201c\u201d]?",
    re.IGNORECASE,
)

# A proof file still containing an unfilled `sorry` tactic. We rely PRIMARILY on
# the compiler warning, not source regex (a comment containing "sorry" must not
# count). This pattern is a secondary guard for the case where the warning is
# suppressed or renamed upstream; it is applied to a comment- and string-stripped
# view of the source (see _sorry_in_code) so prose can never trip it.
SORRY_TACTIC = re.compile(r"(^|\s):=\s*by\b[\s\S]*?\bsorry\b|^\s*sorry\s*$", re.MULTILINE)


def _sorry_in_code(source: str) -> bool:
    """True if an unfilled `sorry` appears in real code (not comments/strings).

    Uses the lexer's code mask so that a doc comment mentioning sorry, or a
    string literal containing it, cannot produce a false positive.
    """
    try:
        from leanforge_mcp.core.lean_lexer import _scan_code_mask

        is_code, _ = _scan_code_mask(source)
        masked = "".join(ch if is_code[i] else " " for i, ch in enumerate(source))
    except Exception:  # lexer must never make compilation fail
        logger.exception("code-mask failed; falling back to raw source for sorry guard")
        masked = source
    return bool(SORRY_TACTIC.search(masked))


DIAGNOSTIC_BLOCK = re.compile(
    r"^(.+?:\d+:\d+:\s*(?:error|warning|info):\s*[\s\S]*?)(?=\n(?:.+?:\d+:\d+:\s*(?:error|warning|info):|\Z))",
    re.MULTILINE | re.IGNORECASE,
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
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
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
                # Primary oracle: the compiler's own warning. Secondary guard:
                # an unfilled sorry still present in real code. Either one is
                # enough to refuse to call this proven.
                has_sorry = bool(WARNING_SORRY_RE.search(combined)) or _sorry_in_code(source)
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
                    await loop.run_in_executor(None, urllib.request.urlretrieve, url, str(ps1_path))

                    if not ps1_path.exists():
                        raise RuntimeError("Failed to download elan-init.ps1")

                    # Run installer silently with NoPrompt
                    proc = await asyncio.create_subprocess_exec(
                        "powershell.exe",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(ps1_path),
                        "-NoPrompt",
                        "1",
                        "-DefaultToolchain",
                        "stable",
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

    async def _run_lake(self, *args: str, timeout: int) -> tuple[int, str, str]:
        """Run `lake <args>` in the workspace. Returns (returncode, stdout, stderr)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                str(self.lake_path),
                *args,
                cwd=str(self.workspace_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return 127, "", f"lake executable not found at {self.lake_path}"
        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return 124, "", f"lake {' '.join(args)} timed out after {timeout}s"
        return (
            proc.returncode or 0,
            out_b.decode("utf-8", errors="replace"),
            err_b.decode("utf-8", errors="replace"),
        )

    async def lean_toolchain_version(self) -> tuple[int, int, int] | None:
        """Active workspace toolchain, e.g. (4, 35, 0). None if it cannot run."""
        code, out, _ = await self._run_lake("env", "lean", "--version", timeout=60)
        if code != 0:
            return None
        return parse_lean_version(out)

    async def toolchain_bin_dir(self) -> Path | None:
        """Toolchain bin/ dir holding leanexport + checker binaries. None if unknown."""
        code, out, _ = await self._run_lake("env", "lean", "--print-prefix", timeout=60)
        if code != 0 or not out.strip():
            return None
        return Path(out.strip()) / "bin"

    @staticmethod
    def checker_bin(bin_dir: Path, kernel: str) -> Path:
        """Checker executable path for this OS (`.exe` on Windows)."""
        exe = f"{kernel}.exe" if sys.platform == "win32" else kernel
        return bin_dir / exe

    async def verify_external(
        self,
        source: str,
        *,
        kernels: tuple[str, ...] | list[str] = ("con-leche", "con-ron"),
        verify_lib: str = "LeanforgeWorkspace",
        timeout: int = 600,
    ) -> VerifyResult:
        """Re-check proven source with independent verified kernels.

        `timeout` applies per stage (build, export, each checker): a Mathlib
        proof's export covers the whole dependency closure, so stages take
        minutes, not seconds. Checkers run sequentially to bound RAM.
        """
        version = await self.lean_toolchain_version()
        version_str = ".".join(map(str, version)) if version else "unknown"
        need = ".".join(map(str, EXTERNAL_CHECK_MIN_VERSION))
        if version is None or version < EXTERNAL_CHECK_MIN_VERSION:
            return VerifyResult(
                supported=False,
                toolchain_version=version_str,
                message=(
                    f"Workspace Lean is {version_str}; external kernel check needs >={need}. "
                    "Upgrade the workspace (lean-toolchain + Mathlib rev, lake update, "
                    "lake exe cache get, lake build). See docs/VERIFIED_KERNELS.md."
                ),
            )
        bin_dir = await self.toolchain_bin_dir()
        if bin_dir is None:
            return VerifyResult(
                supported=False,
                toolchain_version=version_str,
                message="Could not resolve the Lean toolchain prefix; is elan working?",
            )

        # Fail closed against vacuous acceptance: an empty/broken export is
        # "accepted 0 declarations" (exit 0). At least one declared name from
        # the source must appear in the export, or the whole run is rejected.
        from leanforge_mcp.core.lean_lexer import extract_signatures

        names = [s.name for s in extract_signatures(source) if s.name]

        mod = new_verify_module()
        lib_dir = self.workspace_dir / verify_lib
        mod_path = lib_dir / f"{mod}.lean"
        export_path = self.workspace_dir / f"_lfverify_{mod}.ndjson"
        target = f"{verify_lib}.{mod}"
        try:
            lib_dir.mkdir(parents=True, exist_ok=True)
            mod_path.write_text(source, encoding="utf-8")

            async with self._sem:
                code, out, err = await self._run_lake("build", target, timeout=timeout)
            if code != 0:
                return VerifyResult(
                    supported=True,
                    toolchain_version=version_str,
                    message=f"Verification build failed for {target}: {(err or out)[:500]}",
                )

            # Stream the export straight to disk: it can be hundreds of MB.
            try:
                with export_path.open("wb") as f:
                    proc = await asyncio.create_subprocess_exec(
                        str(self.lake_path),
                        "env",
                        "leanexport",
                        target,
                        cwd=str(self.workspace_dir),
                        stdout=f,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    try:
                        _, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    except TimeoutError:
                        proc.kill()
                        await proc.communicate()
                        return VerifyResult(
                            supported=True,
                            toolchain_version=version_str,
                            message=f"leanexport timed out after {timeout}s for {target}.",
                        )
                    export_err = err_b.decode("utf-8", errors="replace")
            except FileNotFoundError:
                return VerifyResult(
                    supported=True,
                    toolchain_version=version_str,
                    message=f"lake executable not found at {self.lake_path}",
                )
            if proc.returncode != 0:
                return VerifyResult(
                    supported=True,
                    toolchain_version=version_str,
                    message=f"leanexport failed for {target}: {export_err[:500]}",
                )
            if not export_path.exists() or export_path.stat().st_size < 2:
                return VerifyResult(
                    supported=True,
                    toolchain_version=version_str,
                    message="leanexport produced an empty file; refusing vacuous accept.",
                )
            missing = [n for n in names if not file_contains(export_path, n)]
            if names and len(missing) == len(names):
                return VerifyResult(
                    supported=True,
                    toolchain_version=version_str,
                    message=(f"Export contains none of the proof's declarations {names[:5]}; refusing vacuous accept."),
                )

            verdicts: list[KernelVerdict] = []
            for kernel in kernels:
                exe = self.checker_bin(bin_dir, kernel)
                if not exe.exists():
                    verdicts.append(
                        KernelVerdict(
                            kernel=kernel,
                            accepted=False,
                            detail=f"Not bundled with this toolchain (looked for {exe}).",
                        )
                    )
                    continue
                try:
                    proc = await asyncio.create_subprocess_exec(
                        str(exe),
                        str(export_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    try:
                        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    except TimeoutError:
                        proc.kill()
                        await proc.communicate()
                        verdicts.append(
                            KernelVerdict(kernel=kernel, accepted=False, detail=f"Timed out after {timeout}s.")
                        )
                        continue
                    text = out_b.decode("utf-8", errors="replace") + err_b.decode("utf-8", errors="replace")
                    count = parse_checker_accepted(text)
                    ok = proc.returncode == 0 and count is not None and count > 0
                    verdicts.append(
                        KernelVerdict(
                            kernel=kernel,
                            accepted=ok,
                            declarations=count,
                            detail=text.strip()[:500] if not ok else f"accepted {count} declarations",
                        )
                    )
                except Exception as exc:
                    verdicts.append(KernelVerdict(kernel=kernel, accepted=False, detail=str(exc)[:300]))
            return VerifyResult(
                supported=True,
                toolchain_version=version_str,
                results=verdicts,
                message="All selected kernels accepted the proof."
                if all(v.accepted for v in verdicts) and verdicts
                else "One or more kernels did NOT accept the proof; see per-kernel detail.",
            )
        finally:
            mod_path.unlink(missing_ok=True)
            export_path.unlink(missing_ok=True)
            # Drop this module's build artifacts so `lake build` stays clean.
            try:
                build_root = self.workspace_dir / ".lake" / "build"
                if build_root.is_dir():
                    for artifact in build_root.rglob(f"{mod}.*"):
                        try:
                            if artifact.is_file():
                                artifact.unlink()
                        except OSError:
                            pass
            except OSError:
                pass


# ---------------------------------------------------------------------------
# External kernel re-verification (Lean >= 4.35.0: con-leche / con-ron).
#
# The proof-search loop trusts the official Lean kernel: "compiles without
# sorry" == proven. AI agents found two kernel soundness bugs in August 2026,
# so proofs that actually matter (open problems) get re-checked against
# independent verified kernels before anyone claims a result.
#
# Pipeline per proof:
#   source -> temp module <workspace>/<verify_lib>/LfVerify<hex>.lean ->
#   `lake build` -> `lake env leanexport` (NDJSON on stdout, streamed to disk) ->
#   one checker binary per kernel, exit 0 + "accepted N declarations".
#
# `lake check` itself is NOT used: it needs a bwrap sandbox (Linux-only) and
# fails on Windows even with --from-export. We invoke the same checker
# binaries (shipped in the toolchain's bin/ dir) directly.
# See docs/VERIFIED_KERNELS.md.
# ---------------------------------------------------------------------------

# First Lean release whose toolchain bundles leanexport + verified kernels.
EXTERNAL_CHECK_MIN_VERSION = (4, 35, 0)

CHECKER_ACCEPTED_RE = re.compile(
    r"accepted\s+(\d+)\s+declarations?",
    re.IGNORECASE,
)

LEAN_VERSION_RE = re.compile(r"version\s+(\d+)\.(\d+)\.(\d+)")


def parse_lean_version(text: str) -> tuple[int, int, int] | None:
    """Parse 'Lean (version 4.35.0, ...)' -> (4, 35, 0). None if unparseable."""
    m = LEAN_VERSION_RE.search(text)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def parse_checker_accepted(text: str) -> int | None:
    """Parse 'accepted 57921 declarations' -> 57921. None when absent.

    Absence means the checker did NOT confirm the proof (rejection, crash,
    or unexpected output) -- callers must fail closed, never treat it as pass.
    """
    m = CHECKER_ACCEPTED_RE.search(text)
    return int(m.group(1)) if m else None


def new_verify_module() -> str:
    """Fresh temp module stem. Alphanumeric only: valid as a Lean module name."""
    return f"LfVerify{uuid.uuid4().hex[:12]}"


def file_contains(path: Path, needle: str, chunk_size: int = 1 << 20) -> bool:
    """Substring search without loading the whole file.

    Exports can be hundreds of MB (full dependency closure); str-in-text on
    the whole thing would spike RAM. Overlapping chunks keep it flat.
    """
    if not needle:
        return True
    overlap = len(needle) - 1
    tail = ""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                return False
            if needle in tail + chunk:
                return True
            tail = chunk[-overlap:] if overlap > 0 else ""


@dataclass
class KernelVerdict:
    kernel: str
    accepted: bool
    declarations: int | None = None
    detail: str = ""


@dataclass
class VerifyResult:
    supported: bool
    toolchain_version: str = ""
    results: list[KernelVerdict] = field(default_factory=list)
    message: str = ""

    @property
    def all_accepted(self) -> bool:
        """True only if supported AND every kernel confirmed the proof."""
        return self.supported and bool(self.results) and all(r.accepted for r in self.results)

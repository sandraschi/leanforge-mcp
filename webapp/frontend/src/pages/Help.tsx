import { useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type TabId =
  | "overview"
  | "install"
  | "configuration"
  | "tools"
  | "lean"
  | "development";

interface Tab {
  id: TabId;
  label: string;
}

const TABS: Tab[] = [
  { id: "overview",      label: "Overview" },
  { id: "install",       label: "Install" },
  { id: "configuration", label: "Configuration" },
  { id: "tools",         label: "Tools" },
  { id: "lean",          label: "Lean 4" },
  { id: "development",   label: "Development" },
];

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------
function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-semibold text-gray-100 mt-6 mb-2">{children}</h2>;
}
function H3({ children }: { children: React.ReactNode }) {
  return <h3 className="text-sm font-semibold text-indigo-300 mt-5 mb-1.5">{children}</h3>;
}
function P({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-gray-300 leading-relaxed mb-3">{children}</p>;
}
function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className="bg-zinc-900 border border-zinc-700 rounded p-3 text-xs text-green-300 font-mono overflow-x-auto mb-4 whitespace-pre">
      {children}
    </pre>
  );
}
function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="bg-zinc-800 text-indigo-300 px-1 py-0.5 rounded text-xs font-mono">
      {children}
    </code>
  );
}
function Table({ headers, rows }: { headers: string[]; rows: (string | React.ReactNode)[][] }) {
  return (
    <div className="overflow-x-auto mb-4">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="border-b border-zinc-700">
            {headers.map((h) => (
              <th key={h} className="text-left py-2 pr-4 text-gray-400 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-zinc-800">
              {row.map((cell, j) => (
                <td key={j} className="py-2 pr-4 text-gray-300 align-top">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
      className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2">
      {children}
    </a>
  );
}
function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-l-2 border-amber-500 bg-amber-950/30 pl-3 py-2 rounded-r text-xs text-amber-200 mb-4">
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab content
// ---------------------------------------------------------------------------
function OverviewTab() {
  return (
    <div>
      <P>
        leanforge-mcp is an MCP server for AI-driven formal proof search in Lean 4.
        Submit a theorem statement with a <InlineCode>sorry</InlineCode> placeholder;
        the server runs N parallel agents in a loop — the LLM proposes a proof edit,
        the Lean compiler judges it, errors feed back to the LLM — until a
        sorry-free compile is found or the budget runs out.
      </P>
      <P>
        Implements Agent A from{" "}
        <ExternalLink href="https://arxiv.org/abs/2605.22763">AlphaProof Nexus</ExternalLink>{" "}
        (DeepMind, May 2026): independent subagents, compiler feedback as the only oracle,
        LLM tier escalation.
      </P>

      <H2>How it works</H2>
      <Code>{`-- Input
theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  sorry

-- After proof search
theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  induction n with
  | zero      => simp
  | succ n ih => rw [Finset.sum_range_succ]; ring_nf; linarith`}</Code>

      <H2>Proof loop</H2>
      <Code>{`submit_theorem → Runner.start_job() → N parallel subagents
  each subagent:
    loop {
      LLM: propose search-replace edit to the .lean file
      lake env lean <file>: compile
      if proven (no sorry, no errors): done — cancel others
      else: feed compiler error back to LLM
    }
  all attempts persisted to SQLite`}</Code>

      <H2>LLM tier escalation</H2>
      <Table
        headers={["Turns", "Tier", "Model", "Cost"]}
        rows={[
          ["0–19",  "1 (local)", <InlineCode>deepseek-prover-v2:7b</InlineCode>, "Free (Ollama)"],
          ["20–59", "2 (API)",   <InlineCode>deepseek-v4-flash</InlineCode>,      "~$0.001/attempt"],
          ["60+",   "3 (API)",   <InlineCode>claude-fable-5</InlineCode>,          "$50/M output"],
        ]}
      />
      <Note>
        Tier-3 is expensive. Do not run overnight batches until token/cost accounting is implemented (P2-3).
      </Note>

      <H2>Status</H2>
      <P>
        Phase A complete — server starts, all tools callable from Claude Desktop.
        Phase B (correctness fixes) in progress.
        See <ExternalLink href="https://github.com/sandraschi/leanforge-mcp/blob/main/docs/ASSESSMENT_2026-06-24.md">ASSESSMENT_2026-06-24.md</ExternalLink> for the full gap analysis.
      </P>

      <H2>Links</H2>
      <Table
        headers={["Resource", "URL"]}
        rows={[
          ["GitHub", <ExternalLink href="https://github.com/sandraschi/leanforge-mcp">sandraschi/leanforge-mcp</ExternalLink>],
          ["AlphaProof Nexus paper", <ExternalLink href="https://arxiv.org/abs/2605.22763">arXiv:2605.22763</ExternalLink>],
          ["DeepSeek-Prover-V2", <ExternalLink href="https://arxiv.org/abs/2504.21801">arXiv:2504.21801</ExternalLink>],
          ["Mathlib4 docs", <ExternalLink href="https://leanprover-community.github.io/mathlib4_docs/">leanprover-community.github.io</ExternalLink>],
          ["LeanSearch", <ExternalLink href="https://leansearch.net">leansearch.net</ExternalLink>],
        ]}
      />
    </div>
  );
}

function InstallTab() {
  return (
    <div>
      <H2>Prerequisites</H2>
      <Table
        headers={["Tool", "Purpose", "Install"]}
        rows={[
          ["Claude Desktop", "Required host", <ExternalLink href="https://claude.ai/download">claude.ai/download</ExternalLink>],
          [<InlineCode>uv</InlineCode>, "Run server", <InlineCode>winget install astral-sh.uv</InlineCode>],
          [<InlineCode>git</InlineCode>, "Clone repo", <InlineCode>winget install Git.Git</InlineCode>],
          ["Lean 4 via elan", "Lean compiler", <InlineCode>winget install leanprover.elan</InlineCode>],
          ["Ollama", "Tier-1 local LLM", <ExternalLink href="https://ollama.com">ollama.com</ExternalLink>],
        ]}
      />

      <H2>1 — Clone and install</H2>
      <Code>{`git clone https://github.com/sandraschi/leanforge-mcp
cd leanforge-mcp
uv sync`}</Code>

      <H2>2 — Configure</H2>
      <Code>{`Copy-Item config.example.toml config.toml
# Edit config.toml: verify lake_path and workspace_dir`}</Code>

      <H2>3 — Lean + Mathlib workspace (one-time, ~4 GB)</H2>
      <Note>
        This step takes 20–40 minutes on first run. Nothing will compile until it completes.
      </Note>
      <Code>{`cd workspace
lake new leanforge_workspace math
cd leanforge_workspace
lake exe cache get     # downloads precompiled Mathlib oleans
lake build             # verifies everything resolves
cd ..\..\`}</Code>

      <H2>4 — Pull tier-1 model</H2>
      <Code>{`ollama pull deepseek-prover-v2:7b`}</Code>

      <H2>5 — Add to Claude Desktop</H2>
      <P>
        Config file: <InlineCode>%APPDATA%\Claude\claude_desktop_config.json</InlineCode>
      </P>
      <Code>{`{
  "mcpServers": {
    "leanforge": {
      "command": "uv",
      "args": [
        "--directory", "C:\\\\path\\\\to\\\\leanforge-mcp",
        "run", "python", "-m", "leanforge_mcp"
      ],
      "env": {
        "DEEPSEEK_API_KEY": "sk-...",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}`}</Code>

      <H2>6 — Verify</H2>
      <P>In Claude Desktop, ask:</P>
      <Code>{`"Validate this Lean 4 snippet: \`example : 1 = 1 := rfl\`"

Expected: {"proven": true, "has_sorry": false, "errors": []}`}</Code>
    </div>
  );
}

function ConfigurationTab() {
  return (
    <div>
      <P>
        leanforge-mcp reads <InlineCode>config.toml</InlineCode> from the repo root.
        Copy <InlineCode>config.example.toml</InlineCode> to get started.
        API keys go in the Claude Desktop <InlineCode>env</InlineCode> block — never in <InlineCode>config.toml</InlineCode>.
      </P>

      <H2>[lean]</H2>
      <Table
        headers={["Key", "Default", "Description"]}
        rows={[
          [<InlineCode>lake_path</InlineCode>, <InlineCode>…\.elan\bin\lake.exe</InlineCode>, "Absolute path to lake.exe. We run lake env lean, not lean directly."],
          [<InlineCode>workspace_dir</InlineCode>, <InlineCode>…\workspace\leanforge_workspace</InlineCode>, "Lake project with Mathlib + cached oleans. One-time setup required."],
          [<InlineCode>compile_timeout</InlineCode>, "120", "Seconds before a Lean compile is killed."],
          [<InlineCode>max_concurrent_compiles</InlineCode>, "4", "Semaphore cap on parallel lake processes. Each loads Mathlib (~GB RAM)."],
          [<InlineCode>retain_workspace</InlineCode>, "false", "Keep temp .lean files after job completes. Enable for debugging."],
        ]}
      />

      <H2>[agent]</H2>
      <Table
        headers={["Key", "Default", "Description"]}
        rows={[
          [<InlineCode>parallel_agents</InlineCode>, "4", "Default number of independent subagents per job."],
          [<InlineCode>max_turns</InlineCode>, "100", "Default turn budget per subagent."],
          [<InlineCode>escalate_to_tier2_after</InlineCode>, "20", "Turn at which agents switch from tier-1 to tier-2."],
          [<InlineCode>escalate_to_tier3_after</InlineCode>, "60", "Turn at which agents switch from tier-2 to tier-3."],
        ]}
      />

      <H2>[llm.tier1] — Local Ollama</H2>
      <Table
        headers={["Key", "Default", "Description"]}
        rows={[
          [<InlineCode>model</InlineCode>, "deepseek-prover-v2:7b", "Pull with ollama pull deepseek-prover-v2:7b"],
          [<InlineCode>base_url</InlineCode>, "http://localhost:11434/v1", "The /v1 suffix is required — Ollama's OpenAI-compatible endpoint."],
          [<InlineCode>max_tokens</InlineCode>, "2048", ""],
          [<InlineCode>temperature</InlineCode>, "0.7", ""],
        ]}
      />

      <H2>[llm.tier2] — DeepSeek API</H2>
      <Table
        headers={["Key", "Default", "Description"]}
        rows={[
          [<InlineCode>model</InlineCode>, "deepseek-chat", "Check platform.deepseek.com for current model name."],
          [<InlineCode>base_url</InlineCode>, "https://api.deepseek.com/v1", ""],
          [<InlineCode>api_key_env</InlineCode>, "DEEPSEEK_API_KEY", "Name of the env var holding your API key."],
          [<InlineCode>max_tokens</InlineCode>, "4096", ""],
        ]}
      />

      <H2>[llm.tier3] — Anthropic</H2>
      <Note>Tier-3 is expensive ($50/M output tokens). Cost accounting not yet implemented — use sparingly.</Note>
      <Table
        headers={["Key", "Default", "Description"]}
        rows={[
          [<InlineCode>model</InlineCode>, "claude-opus-4-8", "Update to current strongest model."],
          [<InlineCode>api_key_env</InlineCode>, "ANTHROPIC_API_KEY", ""],
          [<InlineCode>max_tokens</InlineCode>, "8192", ""],
          [<InlineCode>temperature</InlineCode>, "1.0", "Higher temperature for proof diversity at this stage."],
        ]}
      />

      <H2>[database]</H2>
      <Table
        headers={["Key", "Default", "Description"]}
        rows={[
          [<InlineCode>path</InlineCode>, <InlineCode>…\data\jobs.db</InlineCode>, "SQLite database. Parent directory created automatically."],
        ]}
      />

      <H2>[logging]</H2>
      <Table
        headers={["Key", "Default", "Description"]}
        rows={[
          [<InlineCode>level</InlineCode>, "INFO", "DEBUG / INFO / WARNING / ERROR"],
          [<InlineCode>log_file</InlineCode>, <InlineCode>…\logs\leanforge.log</InlineCode>, "Parent directory created automatically."],
        ]}
      />
    </div>
  );
}

function ToolsTab() {
  return (
    <div>
      <P>
        All tools return structured JSON. <InlineCode>submit_theorem</InlineCode> and{" "}
        <InlineCode>submit_lean_file</InlineCode> return immediately — proof search runs in the
        background. Poll with <InlineCode>get_proof_status</InlineCode> every 10–30 seconds.
      </P>

      <H2>submit_theorem</H2>
      <P>Submit a theorem statement for proof search.</P>
      <Table
        headers={["Parameter", "Type", "Default", "Description"]}
        rows={[
          [<InlineCode>statement</InlineCode>, "string", "required", "Lean 4 proposition. Must be valid Lean syntax — ∀ n : ℕ, … not English."],
          [<InlineCode>lean_stub</InlineCode>, "string", "null", "Optional full .lean file with sorry. If omitted the server wraps statement in a stub."],
          [<InlineCode>hints</InlineCode>, "string", "null", "Mathlib theorem names or strategy hints to prepend."],
          [<InlineCode>tier</InlineCode>, "int 1–3", "1", "Starting LLM tier."],
          [<InlineCode>parallel_agents</InlineCode>, "int 1–16", "4", "Number of independent subagents."],
          [<InlineCode>max_turns</InlineCode>, "int 1–1000", "100", "Turn budget per subagent."],
        ]}
      />
      <Code>{`// Returns
{
  "job_id": "uuid",
  "status": "queued",
  "tier": 1,
  "parallel_agents": 4,
  "message": "Job abc-123 started. Poll get_proof_status('abc-123') every 10-30s."
}`}</Code>

      <H2>get_proof_status</H2>
      <P>Poll a job. Status: <InlineCode>queued</InlineCode> → <InlineCode>running</InlineCode> → <InlineCode>complete</InlineCode> / <InlineCode>failed</InlineCode> / <InlineCode>cancelled</InlineCode></P>
      <Code>{`// Running
{ "status": "running", "latest_turn": 12,
  "latest_compiler_output": "error: tactic 'simp' failed..." }

// Complete
{ "status": "complete", "proof": "import Mathlib\n\ntheorem ... := by\n  ..." }`}</Code>

      <H2>validate_lean</H2>
      <P>Raw Lean 4 compile. No job created, no LLM involved. Use to test proofs manually.</P>
      <Code>{`validate_lean("import Mathlib\nexample : 1 = 1 := rfl\n")
// → {"proven": true, "has_sorry": false, "errors": [], "warnings": []}`}</Code>

      <H2>list_attempts</H2>
      <P>Inspect the trajectory for a job. Compiler output truncated to 400 chars per attempt.</P>
      <P>Special values for non-compile turns: <InlineCode>STUCK</InlineCode>, <InlineCode>PARSE_ERROR</InlineCode>, <InlineCode>EDIT_NOT_FOUND</InlineCode>, <InlineCode>LLM_ERROR: …</InlineCode></P>

      <H2>Other tools</H2>
      <Table
        headers={["Tool", "Description"]}
        rows={[
          [<InlineCode>submit_lean_file</InlineCode>, "Submit a full .lean file with sorry. For MiniF2F / AlphaProof Nexus stubs."],
          [<InlineCode>list_jobs</InlineCode>, "List all jobs with status and summary. Optional status_filter."],
          [<InlineCode>cancel_job</InlineCode>, "Cancel a running job (same process only — cross-process cancel pending)."],
          [<InlineCode>get_mathlib_search</InlineCode>, "Natural language search over Mathlib via LeanSearch API. Returns theorem names to use as hints."],
        ]}
      />
    </div>
  );
}

function LeanTab() {
  return (
    <div>
      <P>
        You don't need to be a mathematician to work on leanforge-mcp. You need enough
        Lean 4 to understand compiler errors and debug the pipeline.
      </P>

      <H2>What Lean is</H2>
      <P>
        Lean 4 is simultaneously a functional programming language and a proof assistant.
        In Lean, <strong>a proof is a program</strong> and <strong>a theorem is a type</strong> (the Curry–Howard correspondence).
        Proving <InlineCode>n + 0 = n</InlineCode> means constructing a term of that type.
        The Lean kernel checks it — if accepted, the proof is correct with no ambiguity possible.
      </P>

      <H2>The sorry placeholder</H2>
      <Code>{`theorem my_theorem (n : ℕ) : n + 0 = n := by
  sorry   -- compiles but emits: warning: declaration uses 'sorry'`}</Code>
      <P>
        A proof is valid only when every <InlineCode>sorry</InlineCode> is replaced with real tactics
        and the compiler emits no sorry warning. leanforge-mcp's entire job is filling sorry.
      </P>

      <H2>Key tactics</H2>
      <H3>Arithmetic</H3>
      <Table
        headers={["Tactic", "Use"]}
        rows={[
          [<InlineCode>ring</InlineCode>, "Ring identities: a*(b+c) = a*b + a*c. Fully automatic."],
          [<InlineCode>linarith</InlineCode>, "Linear arithmetic: x + 1 > x. Closes goal or raises contradiction."],
          [<InlineCode>omega</InlineCode>, "Integer/natural number arithmetic. Decision procedure."],
          [<InlineCode>norm_num</InlineCode>, "Concrete computations: 2 + 2 = 4, 7 ∣ 49."],
          [<InlineCode>ring_nf</InlineCode>, "Normalise ring expressions without closing. Use before linarith."],
          [<InlineCode>field_simp</InlineCode>, "Clear denominators. Pair with ring."],
        ]}
      />
      <H3>Simplification</H3>
      <Table
        headers={["Tactic", "Use"]}
        rows={[
          [<InlineCode>simp</InlineCode>, "Rewrite using Mathlib simp lemmas. Best first move on simple goals."],
          [<InlineCode>simp only [h₁, h₂]</InlineCode>, "Restricted simp. Predictable, preferred for non-trivial goals."],
          [<InlineCode>norm_cast</InlineCode>, "Normalise coercions between ℕ, ℤ, ℝ, etc."],
        ]}
      />
      <H3>Logic and structure</H3>
      <Table
        headers={["Tactic", "Use"]}
        rows={[
          [<InlineCode>exact h</InlineCode>, "Close goal with hypothesis or term h."],
          [<InlineCode>apply f</InlineCode>, "Reduce goal B to A using f : A → B."],
          [<InlineCode>induction n with</InlineCode>, "Induction on n. Names each case."],
          [<InlineCode>cases h with</InlineCode>, "Case-split on inductive type."],
          [<InlineCode>intro h</InlineCode>, "Introduce hypothesis from ∀ or →."],
          [<InlineCode>rw [lemma]</InlineCode>, "Rewrite goal using lemma."],
          [<InlineCode>decide</InlineCode>, "Decide decidable propositions by computation."],
        ]}
      />

      <H2>Reading compiler errors</H2>
      <Table
        headers={["Error", "Fix"]}
        rows={[
          ["tactic 'ring' failed, no goals", "ring called after goal closed. Delete it or reorder."],
          ["unknown identifier 'Nat.add_comm'", "Wrong lemma name. Use get_mathlib_search to find it."],
          ["type mismatch: expected n + 0 = n, given 0 + n = n", "Wrong direction. Add rw [add_comm] first, or use ring."],
          ["declaration uses 'sorry'", "Not an error — proof incomplete. proven = false."],
        ]}
      />

      <H2>Worked example</H2>
      <Code>{`import Mathlib

theorem sum_formula (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1) := by
  induction n with
  | zero      => simp                      -- base case handled by simplification
  | succ n ih =>
    rw [Finset.sum_range_succ]            -- unfold sum one step
    ring_nf                               -- normalise ring expressions
    linarith                              -- close with ih`}</Code>

      <H2>Benchmarks</H2>
      <Table
        headers={["Set", "Size", "Baseline (7B)", "URL"]}
        rows={[
          ["MiniF2F", "488 olympiad problems", "~40% (671B: 65%)", <ExternalLink href="https://github.com/leanprover-community/miniF2F">github</ExternalLink>],
          ["PutnamBench", "658 Putnam problems", "49/658 (671B)", <ExternalLink href="https://github.com/trishullab/PutnamBench">github</ExternalLink>],
          ["AlphaProof Nexus unsolved", "344 open Erdős stubs", "0 (open problems)", <ExternalLink href="https://github.com/google-deepmind/alphaproof-nexus-results">github</ExternalLink>],
        ]}
      />

      <H2>Key links</H2>
      <Table
        headers={["Resource", "URL"]}
        rows={[
          ["Lean 4 site", <ExternalLink href="https://lean-lang.org">lean-lang.org</ExternalLink>],
          ["Mathlib4 docs", <ExternalLink href="https://leanprover-community.github.io/mathlib4_docs/">leanprover-community.github.io</ExternalLink>],
          ["LeanSearch (natural language)", <ExternalLink href="https://leansearch.net">leansearch.net</ExternalLink>],
          ["Loogle (pattern search)", <ExternalLink href="https://loogle.lean-lang.org">loogle.lean-lang.org</ExternalLink>],
          ["Natural Number Game (browser)", <ExternalLink href="https://adam.math.hhu.de">adam.math.hhu.de</ExternalLink>],
          ["Lean 4 playground", <ExternalLink href="https://live.lean-lang.org">live.lean-lang.org</ExternalLink>],
          ["Mathematics in Lean (book)", <ExternalLink href="https://leanprover-community.github.io/mathematics_in_lean/">leanprover-community.github.io</ExternalLink>],
          ["AlphaProof Nexus paper", <ExternalLink href="https://arxiv.org/abs/2605.22763">arXiv:2605.22763</ExternalLink>],
          ["DeepSeek-Prover-V2 paper", <ExternalLink href="https://arxiv.org/abs/2504.21801">arXiv:2504.21801</ExternalLink>],
        ]}
      />
    </div>
  );
}

function DevelopmentTab() {
  return (
    <div>
      <H2>Setup</H2>
      <Code>{`# Install tools
winget install astral-sh.uv
winget install Casey.Just

# Clone and install with dev + web extras
git clone https://github.com/sandraschi/leanforge-mcp
cd leanforge-mcp
uv sync --extra web --extra dev`}</Code>

      <H2>Common tasks</H2>
      <Table
        headers={["Command", "Description"]}
        rows={[
          [<InlineCode>just lint</InlineCode>, "ruff check + ruff format --check"],
          [<InlineCode>just format</InlineCode>, "ruff format (auto-fix)"],
          [<InlineCode>just test</InlineCode>, "pytest tests/ -v  (pure Python, no Lean required)"],
          [<InlineCode>just smoke</InlineCode>, "scripts/smoke_test.py  (needs Lean workspace)"],
          [<InlineCode>just web-dev</InlineCode>, "Start webapp backend + frontend in dev mode"],
        ]}
      />

      <H2>Project layout</H2>
      <Code>{`src/leanforge_mcp/
  server.py           FastMCP entry point, lifespan, tool mounts
  core/
    agent.py          Proof loop, parallel subagent orchestration
    lean_client.py    lake env lean subprocess wrapper
    llm_client.py     Ollama / DeepSeek / Anthropic, tier escalation
    job_manager.py    SQLite CRUD — jobs and attempts
    runner.py         Runner class, get_runner(ctx), process fallback
    config.py         TOML loader and config dataclasses
  tools/
    submit.py         submit_theorem, submit_lean_file
    status.py         get_proof_status, list_attempts, list_jobs, validate_lean
    control.py        cancel_job
    mathlib.py        get_mathlib_search
webapp/
  backend/            FastAPI backend  (port 10855)
  frontend/           Vite/React dashboard  (port 10856)`}</Code>

      <H2>Critical rules</H2>
      <Table
        headers={["Rule", "Why"]}
        rows={[
          ["Never call lean directly", "Always lake env lean <file> via LeanClient — bare lean can't see Mathlib"],
          ["Never block the event loop", "All Lean and LLM calls are async"],
          ["Never hardcode paths", "Always read from Config"],
          ["Never modify theorem statements", "The tamper guard in agent.py will reject the edit"],
          ["Always use uv run", "Never bare python — avoids PATH resolution issues on Windows"],
        ]}
      />

      <H2>Phase B — current priorities</H2>
      <P>See <ExternalLink href="https://github.com/sandraschi/leanforge-mcp/blob/main/docs/ASSESSMENT_2026-06-24.md">ASSESSMENT_2026-06-24.md</ExternalLink> for full detail.</P>
      <Table
        headers={["Item", "File", "Issue"]}
        rows={[
          ["P1-1: helper-lemma tamper guard", "agent.py", "System prompt allows top-level lemmas but tamper guard rejects them"],
          ["P1-2: bracket-aware extract_statement", "agent.py", "Regex stops at first := including inside default-arg binders"],
          ["P1-4: owner_pid recovery", "job_manager.py", "Webapp restart marks live MCP-server jobs as interrupted"],
          ["P1-6: cross-process cancel", "job_manager.py", "cancel_job only works within the process that started the job"],
          ["P2-4: repeated-edit detection", "agent.py", "Model retries identical edits without feedback"],
        ]}
      />

      <Note>
        Phase C (REPL client, LLM timeout/retry, cost accounting) must be complete before any tier-2/3 overnight batch run.
      </Note>
    </div>
  );
}

const TAB_CONTENT: Record<TabId, React.ReactNode> = {
  overview:      <OverviewTab />,
  install:       <InstallTab />,
  configuration: <ConfigurationTab />,
  tools:         <ToolsTab />,
  lean:          <LeanTab />,
  development:   <DevelopmentTab />,
};

// ---------------------------------------------------------------------------
// Main Help page
// ---------------------------------------------------------------------------
export default function Help() {
  const [active, setActive] = useState<TabId>("overview");

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-semibold">Help</h1>
        <a
          href="https://github.com/sandraschi/leanforge-mcp"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-gray-500 hover:text-indigo-400"
        >
          github.com/sandraschi/leanforge-mcp ↗
        </a>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-zinc-700 mb-6 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
              active === tab.id
                ? "border-indigo-500 text-indigo-300"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="max-w-4xl">
        {TAB_CONTENT[active]}
      </div>
    </div>
  );
}

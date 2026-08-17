import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Job, SystemStatus } from "../api";
import { fetchJobs, fetchStatus } from "../api";
import StatusBadge from "../components/StatusBadge";

// ---------------------------------------------------------------------------
// Hero section
// ---------------------------------------------------------------------------

function BackendOfflineBanner() {
  return (
    <div className="border border-red-800 bg-red-950/30 rounded p-3 text-sm text-red-300 mb-4">
      Backend offline — start the webapp backend to see live status and jobs.
      <code className="ml-2 text-xs text-red-400">uv run python -m webapp.backend.main</code>
    </div>
  );
}

function StatusPill({ ok, label }: { ok: boolean | null; label: string }) {
  if (ok === null)
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-gray-500">
        <span className="w-2 h-2 rounded-full bg-gray-600 animate-pulse" />
        {label}: checking…
      </span>
    );
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs ${ok ? "text-green-400" : "text-amber-400"}`}>
      <span className={`w-2 h-2 rounded-full ${ok ? "bg-green-500" : "bg-amber-500"}`} />
      {label}: {ok ? "ready" : "not ready"}
    </span>
  );
}

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="border border-border rounded p-3 bg-surface-2 min-w-[90px]">
      <div className="text-2xl font-semibold text-gray-100">{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-indigo-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function Hero({ status, backendUp }: { status: SystemStatus | null; backendUp: boolean }) {
  return (
    <div className="border border-indigo-900/60 bg-indigo-950/20 rounded-lg p-6 mb-8">
      {/* Title */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-100 tracking-tight mb-1">
            leanforge-mcp
          </h1>
          <p className="text-indigo-300 text-sm font-medium">
            AI-driven formal proof search · Lean 4 · AlphaProof Nexus Agent A
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <StatusPill ok={backendUp} label="Backend" />
          <StatusPill
            ok={status?.lean_workspace.ok ?? null}
            label="Lean workspace"
          />
        </div>
      </div>

      {/* Concept explanation */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        <div className="bg-surface rounded p-3 border border-border">
          <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wide mb-1.5">What it does</div>
          <p className="text-xs text-gray-300 leading-relaxed">
            Submit a theorem with a <code className="text-green-400 bg-zinc-900 px-1 rounded">sorry</code> placeholder.
            The server runs N parallel LLM agents that propose edits,
            compile with the Lean 4 compiler, and feed errors back — until a
            sorry-free proof is found or the budget runs out.
          </p>
        </div>
        <div className="bg-surface rounded p-3 border border-border">
          <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wide mb-1.5">Why it matters</div>
          <p className="text-xs text-gray-300 leading-relaxed">
            A Lean proof is machine-verified against the axioms of dependent
            type theory. If it compiles without <code className="text-green-400 bg-zinc-900 px-1 rounded">sorry</code>,
            it is correct — no reviewer, no ambiguity, no subtle gap possible.
            The compiler is the oracle.
          </p>
        </div>
        <div className="bg-surface rounded p-3 border border-border">
          <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wide mb-1.5">Architecture</div>
          <p className="text-xs text-gray-300 leading-relaxed">
            Implements Agent A from{" "}
            <a
              href="https://arxiv.org/abs/2605.22763"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:underline"
            >
              AlphaProof Nexus
            </a>{" "}
            (DeepMind, May 2026): independent subagents, no shared state.
            LLM tiers escalate from local Ollama (free) → DeepSeek API → Anthropic.
          </p>
        </div>
      </div>

      {/* Proof example */}
      <div className="mb-5">
        <div className="text-xs text-gray-500 mb-1.5">Example — input and output:</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div>
            <div className="text-xs text-gray-600 mb-1">Input (with sorry)</div>
            <pre className="bg-zinc-900 border border-zinc-700 rounded p-2.5 text-xs text-gray-300 font-mono overflow-x-auto">{`theorem sum_formula (n : ℕ) :
  2 * ∑ i ∈ Finset.range (n+1), i
    = n * (n+1) := by
  sorry`}</pre>
          </div>
          <div>
            <div className="text-xs text-gray-600 mb-1">Output (machine-verified)</div>
            <pre className="bg-zinc-900 border border-zinc-700 rounded p-2.5 text-xs text-green-300 font-mono overflow-x-auto">{`theorem sum_formula (n : ℕ) :
  2 * ∑ i ∈ Finset.range (n+1), i
    = n * (n+1) := by
  induction n with
  | zero      => simp
  | succ n ih =>
    rw [Finset.sum_range_succ]
    ring_nf; linarith`}</pre>
          </div>
        </div>
      </div>

      {/* Stats row */}
      {status ? (
        <div className="flex flex-wrap gap-3 mb-4">
          <StatCard label="jobs total" value={status.jobs.total} />
          <StatCard
            label="running"
            value={status.jobs.running}
            sub={status.jobs.live_tasks > 0 ? `${status.jobs.live_tasks} live tasks` : undefined}
          />
          <StatCard label="complete" value={status.jobs.complete} />
          <StatCard label="failed" value={status.jobs.failed} />
          <StatCard label="parallel agents" value={status.config.parallel_agents} sub="default" />
          <StatCard label="max turns" value={status.config.max_turns} sub="per agent" />
          <StatCard label="tier-1 model" value={status.config.tier1_model.split(":")[0] ?? ""} sub={status.config.tier1_model.split(":")[1] ?? ""} />
        </div>
      ) : backendUp ? (
        <div className="text-xs text-gray-600 mb-4">Loading system status…</div>
      ) : (
        <BackendOfflineBanner />
      )}

      {/* Lean workspace warning */}
      {status && !status.lean_workspace.ok && (
        <div className="border border-amber-800 bg-amber-950/30 rounded p-3 text-xs text-amber-300 mb-4">
          <span className="font-semibold">Lean workspace not ready.</span>{" "}
          {status.lean_workspace.message}
          <div className="mt-1 text-amber-400/70">
            One-time setup required — see{" "}
            <Link to="/help" className="underline hover:text-amber-300">Help → Install</Link>.
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <Link
          to="/submit"
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded font-medium transition-colors"
        >
          Submit theorem
        </Link>
        <Link
          to="/problems"
          className="px-4 py-2 border border-border hover:border-indigo-700 text-gray-300 text-sm rounded transition-colors"
        >
          Problem library
        </Link>
        <Link
          to="/help"
          className="px-4 py-2 border border-border hover:border-indigo-700 text-gray-300 text-sm rounded transition-colors"
        >
          Documentation
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Job list
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [backendUp, setBackendUp] = useState(false);

  const loadStatus = () => {
    fetchStatus()
      .then((s) => {
        setStatus(s);
        setBackendUp(true);
      })
      .catch(() => {
        setStatus(null);
        setBackendUp(false);
      });
  };

  const loadJobs = () => {
    setLoading(true);
    fetchJobs(filter || undefined)
      .then((d) => setJobs(d.jobs))
      .catch(() => setJobs([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStatus();
    const si = setInterval(loadStatus, 15_000);
    return () => clearInterval(si);
  }, []);

  useEffect(() => {
    loadJobs();
    const ji = setInterval(loadJobs, 5_000);
    return () => clearInterval(ji);
  }, [filter]);

  const counts = {
    "": jobs.length,
    running: jobs.filter((j) => j.status === "running").length,
    complete: jobs.filter((j) => j.status === "complete").length,
    failed: jobs.filter((j) => j.status === "failed").length,
  };

  return (
    <div>
      <Hero status={status} backendUp={backendUp} />

      {/* Job list */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-200">Proof Jobs</h2>
        <div className="flex gap-2 text-sm">
          {(["", "running", "complete", "failed"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1 rounded border text-xs ${
                filter === s
                  ? "border-indigo-500 bg-indigo-950/40 text-indigo-300"
                  : "border-border text-gray-400 hover:text-gray-200"
              }`}
            >
              {s || "all"} ({counts[s as keyof typeof counts] ?? 0})
            </button>
          ))}
        </div>
      </div>

      {loading && jobs.length === 0 ? (
        <p className="text-gray-600 text-sm">Loading…</p>
      ) : jobs.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <p className="mb-2">No jobs yet.</p>
          <Link to="/submit" className="text-indigo-400 hover:underline text-sm">
            Submit a theorem to get started.
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <Link
              key={job.job_id}
              to={`/jobs/${job.job_id}`}
              className="block border border-border rounded p-4 hover:border-indigo-700 transition-colors bg-surface-2"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono text-gray-600">
                  {job.job_id.slice(0, 8)}
                </span>
                <StatusBadge status={job.status} />
              </div>
              <p className="text-sm text-gray-300 truncate">
                {job.description || "(no description)"}
              </p>
              <p className="text-xs text-gray-600 mt-1">
                {new Date(job.created_at).toLocaleString()}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

import { motion } from "framer-motion";
import { Inbox } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Job } from "../api";
import { fetchJobs } from "../api";
import StatusBadge from "../components/StatusBadge";

const ATTENTION = ["queued", "running", "interrupted"];

export default function InboxPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const load = () => {
    setLoading(true);
    fetchJobs(undefined, 100)
      .then((d) => setJobs(d.jobs.filter((j) => ATTENTION.includes(j.status))))
      .catch((e) =>
        setError(e instanceof Error ? e.message : "failed to load inbox"),
      )
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return jobs.filter(
      (j) =>
        (!statusFilter || j.status === statusFilter) &&
        (j.description || "").toLowerCase().includes(q),
    );
  }, [jobs, query, statusFilter]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      data-testid="inbox-page"
    >
      <div className="flex items-center gap-2 mb-1">
        <Inbox size={20} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Inbox</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-4">
        Jobs needing attention: queued, running, or interrupted proving runs.
      </p>

      <div className="flex gap-2 mb-4">
        <input
          data-testid="search-inbox"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search descriptions..."
          className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
        />
        <select
          data-testid="inbox-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-zinc-800 text-zinc-100 border border-zinc-600 rounded px-2 py-1 text-sm"
        >
          <option value="">All attention</option>
          {ATTENTION.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button
          type="button"
          data-testid="inbox-refresh"
          onClick={load}
          className="px-3 py-2 border border-zinc-700 rounded text-sm text-zinc-300 hover:border-indigo-500"
        >
          Refresh
        </button>
      </div>

      {loading && <p className="text-sm text-zinc-400">Loading inbox...</p>}
      {error && (
        <div className="border border-red-800 bg-red-950/30 rounded p-4 text-sm text-red-300">
          {error}
          <button type="button" onClick={load} className="ml-3 underline">
            Retry
          </button>
        </div>
      )}
      {!loading && !error && filtered.length === 0 && (
        <div className="text-center py-12 text-zinc-500">
          <p className="text-sm">
            Inbox zero. No queued, running, or interrupted jobs.
          </p>
          <Link
            to="/submit"
            className="text-indigo-400 hover:underline text-sm"
          >
            Submit a theorem to get started.
          </Link>
        </div>
      )}

      <div className="space-y-2" data-testid="inbox-count">
        {filtered.map((job) => (
          <Link
            key={job.job_id}
            to={`/jobs/${job.job_id}`}
            className="block border border-zinc-800 rounded p-4 hover:border-indigo-700 transition-colors bg-zinc-900"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono text-zinc-500">
                {job.job_id.slice(0, 8)}
              </span>
              <StatusBadge status={job.status} />
            </div>
            <p className="text-sm text-zinc-300 truncate">
              {job.description || "(no description)"}
            </p>
            <p className="text-xs text-zinc-500 mt-1">
              {new Date(job.created_at).toLocaleString()}
            </p>
          </Link>
        ))}
      </div>
      {!loading && filtered.length > 0 && (
        <p className="text-sm text-zinc-500 mt-3">
          {filtered.length} jobs need attention.
        </p>
      )}
    </motion.div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Job } from "../api";
import { fetchJobs } from "../api";
import StatusBadge from "../components/StatusBadge";

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");

  const load = () => {
    setLoading(true);
    fetchJobs(filter || undefined)
      .then((d) => setJobs(d.jobs))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  const counts = {
    all: jobs.length,
    running: jobs.filter((j) => j.status === "running").length,
    complete: jobs.filter((j) => j.status === "complete").length,
    failed: jobs.filter((j) => j.status === "failed").length,
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Proof Jobs</h1>
        <div className="flex gap-2 text-sm">
          {["", "running", "complete", "failed"].map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1 rounded border ${
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
        <p className="text-gray-500">Loading...</p>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg mb-2">No jobs yet</p>
          <p className="text-sm">
            Submit a theorem from the{" "}
            <Link to="/submit" className="text-indigo-400 hover:underline">
              New Theorem
            </Link>{" "}
            page.
          </p>
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
                <span className="text-sm font-mono text-gray-500">
                  {job.job_id.slice(0, 8)}
                </span>
                <StatusBadge status={job.status} />
              </div>
              <p className="text-sm text-gray-300 truncate">
                {job.description || "(no description)"}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {new Date(job.created_at).toLocaleString()}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

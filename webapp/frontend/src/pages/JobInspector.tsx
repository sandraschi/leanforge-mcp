import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Attempt, JobDetail } from "../api";
import { cancelJob, fetchJob, subscribeJobStream } from "../api";
import AttemptTimeline from "../components/AttemptTimeline";
import StatusBadge from "../components/StatusBadge";

export default function JobInspector() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [liveAttempts, setLiveAttempts] = useState<Attempt[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!jobId) return;
    fetchJob(jobId)
      .then((d) => {
        setJob(d);
        if (d.status === "queued" || d.status === "running") {
          subscribeJobStream(
            jobId,
            (att) => setLiveAttempts((prev) => [...prev, att]),
            () => {
              fetchJob(jobId).then(setJob);
            },
          );
        }
      })
      .catch(() => setError("Job not found"));
  }, [jobId]);

  if (error) {
    return (
      <div className="text-center py-16">
        <p className="text-red-400 mb-4">{error}</p>
        <Link to="/" className="text-indigo-400 hover:underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  if (!job) return <p className="text-sm text-zinc-400">Loading...</p>;

  const allAttempts = [...(job.attempts || []), ...liveAttempts];
  const isRunning = job.status === "queued" || job.status === "running";

  return (
    <div data-testid="job-page">
      <Link
        to="/"
        className="text-sm text-indigo-400 hover:underline mb-4 block"
      >
        &larr; Dashboard
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-xl font-semibold">Job {job.job_id.slice(0, 8)}</h1>
        <StatusBadge status={job.status} />
        {isRunning && (
          <button
            type="button"
            data-testid="job-cancel"
            onClick={async () => {
              await cancelJob(job.job_id);
              fetchJob(job.job_id).then(setJob);
            }}
            className="text-sm px-2 py-1 rounded border border-red-700 text-red-300 hover:bg-red-950/30"
          >
            Cancel
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="border border-border rounded p-3 text-sm bg-surface-2">
          <span className="text-zinc-400">Created</span>
          <p>{new Date(job.created_at).toLocaleString()}</p>
        </div>
        <div className="border border-border rounded p-3 text-sm bg-surface-2">
          <span className="text-zinc-400">Updated</span>
          <p>{new Date(job.updated_at).toLocaleString()}</p>
        </div>
      </div>

      {job.status === "complete" && job.proof && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-zinc-400 mb-2">Proof</h2>
          <pre
            data-testid="job-proof"
            className="border border-green-700 bg-green-950/20 rounded p-4 text-sm font-mono overflow-x-auto"
          >
            {job.proof}
          </pre>
        </div>
      )}

      <div data-testid="job-attempts">
        <h2 className="text-sm font-medium text-zinc-400 mb-2">
          Attempts ({allAttempts.length})
        </h2>
        <AttemptTimeline attempts={allAttempts} />
      </div>
    </div>
  );
}

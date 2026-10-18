import { motion } from "framer-motion";
import { ScrollText } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchLogs } from "../api";

const LEVELS = ["", "ERROR", "WARNING", "INFO", "DEBUG"];

export default function Logs() {
  const [entries, setEntries] = useState<string[]>([]);
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [level, setLevel] = useState("");
  const [limit, setLimit] = useState(200);

  const load = () => {
    setLoading(true);
    fetchLogs(limit, level || undefined)
      .then((d) => {
        setEntries(d.entries);
        setPath(d.path);
        if (!d.exists)
          setError("Log file does not exist yet -- start the backend first.");
        else setError("");
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "failed to load logs"),
      )
      .finally(() => setLoading(false));
  };

  useEffect(load, []);
  useEffect(() => {
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, [level, limit]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      data-testid="logs-page"
    >
      <div className="flex items-center gap-2 mb-1">
        <ScrollText size={20} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Logs</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-4" data-testid="logs-path">
        Live tail of {path || "the server log"} (auto-refreshes every 10s).
      </p>

      <div className="flex gap-2 mb-4">
        <select
          data-testid="logs-level"
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          className="bg-zinc-800 text-zinc-100 border border-zinc-600 rounded px-2 py-1 text-sm"
        >
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {l || "All levels"}
            </option>
          ))}
        </select>
        <select
          data-testid="logs-limit"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="bg-zinc-800 text-zinc-100 border border-zinc-600 rounded px-2 py-1 text-sm"
        >
          {[100, 200, 500].map((n) => (
            <option key={n} value={n}>
              Last {n}
            </option>
          ))}
        </select>
        <button
          type="button"
          data-testid="logs-refresh"
          onClick={load}
          className="px-3 py-1 border border-zinc-700 rounded text-sm text-zinc-300 hover:border-indigo-500"
        >
          Refresh
        </button>
      </div>

      {loading && entries.length === 0 && (
        <p className="text-sm text-zinc-400">Loading logs...</p>
      )}
      {error && (
        <div className="border border-red-800 bg-red-950/30 rounded p-4 text-sm text-red-300 mb-3">
          {error}
        </div>
      )}
      {entries.length === 0 && !loading && !error && (
        <p className="text-sm text-zinc-400">
          No log entries match this filter.
        </p>
      )}

      <pre
        data-testid="logs-entries"
        className="bg-zinc-900 border border-zinc-800 rounded p-3 text-xs text-zinc-300 font-mono overflow-auto max-h-[60vh] whitespace-pre-wrap"
      >
        {entries.join("\n")}
      </pre>
      <p className="text-sm text-zinc-500 mt-2" data-testid="logs-count">
        {entries.length} entries shown.
      </p>
    </motion.div>
  );
}

import { motion } from "framer-motion";
import { Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { McpToolInfo } from "../api";
import { fetchCapabilities } from "../api";

const PAGE_SIZE = 8;

export default function Tools() {
  const [tools, setTools] = useState<McpToolInfo[]>([]);
  const [server, setServer] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(0);

  useEffect(() => {
    fetchCapabilities()
      .then((d) => {
        setTools(d.tools);
        setServer(`${d.server} v${d.version}`);
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "failed to load tools"),
      )
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    const list = tools.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q),
    );
    list.sort((a, b) =>
      sortAsc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name),
    );
    return list;
  }, [tools, query, sortAsc]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice(
    page * PAGE_SIZE,
    page * PAGE_SIZE + PAGE_SIZE,
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      data-testid="tools-page"
    >
      <div className="flex items-center gap-2 mb-1">
        <Wrench size={20} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">MCP Tools</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-4" data-testid="tools-server">
        {server || "Live tool registry from GET /api/capabilities"}
      </p>

      <div className="flex gap-2 mb-4">
        <input
          data-testid="search-tools"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(0);
          }}
          placeholder="Search tools..."
          className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
        />
        <button
          type="button"
          data-testid="tools-sort"
          onClick={() => setSortAsc((s) => !s)}
          className="px-3 py-2 border border-zinc-700 rounded text-sm text-zinc-300 hover:border-indigo-500"
        >
          {sortAsc ? "A-Z" : "Z-A"}
        </button>
      </div>

      {loading && <p className="text-sm text-zinc-400">Loading tools...</p>}
      {error && (
        <div className="border border-red-800 bg-red-950/30 rounded p-4 text-sm text-red-300">
          {error}
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="ml-3 underline"
          >
            Retry
          </button>
        </div>
      )}
      {!loading && !error && filtered.length === 0 && (
        <p className="text-sm text-zinc-400">No tools match "{query}".</p>
      )}

      <div className="space-y-2">
        {pageItems.map((t) => (
          <div
            key={t.name}
            data-testid={`tool-card-${t.name}`}
            className="border border-zinc-800 rounded p-4 bg-zinc-900"
          >
            <code className="text-sm font-mono text-indigo-300">{t.name}</code>
            <p className="text-sm text-zinc-300 mt-1">{t.description}</p>
          </div>
        ))}
      </div>

      {pageCount > 1 && (
        <div
          className="flex items-center gap-2 mt-4 text-sm text-zinc-400"
          data-testid="tools-pagination"
        >
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1 border border-zinc-700 rounded disabled:opacity-30"
          >
            Prev
          </button>
          <span data-testid="tools-count">
            Page {page + 1} of {pageCount} ({filtered.length} tools)
          </span>
          <button
            type="button"
            disabled={page >= pageCount - 1}
            onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1 border border-zinc-700 rounded disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </motion.div>
  );
}

import { useEffect, useMemo, useState } from "react";
import type { Problem } from "../api";
import { API_BASE, createProblem, deleteProblem, fetchProblems } from "../api";

const PAGE_SIZE = 10;

export default function ProblemLibrary() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState("");
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState("updated");
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    title: "",
    statement: "",
    lean_source: "",
    source: "user",
    difficulty: "medium",
    tags: "",
    notes: "",
  });

  const load = () => {
    setLoading(true);
    fetchProblems(sourceFilter || undefined)
      .then((d) => setProblems(d.problems))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [sourceFilter]);

  useEffect(() => {
    setPage(0);
  }, [query, sourceFilter, sortKey, sortAsc]);

  const visible = useMemo(() => {
    const q = query.toLowerCase();
    const list = problems.filter(
      (p) =>
        (p.title || "").toLowerCase().includes(q) ||
        (p.statement || "").toLowerCase().includes(q) ||
        (p.tags || "").toLowerCase().includes(q),
    );
    const byDate = (p: Problem) =>
      new Date(sortKey === "created" ? p.created_at : p.updated_at).getTime();
    list.sort((a, b) => {
      let cmp: number;
      if (sortKey === "title")
        cmp = (a.title || "").localeCompare(b.title || "");
      else if (sortKey === "difficulty")
        cmp = (a.difficulty || "").localeCompare(b.difficulty || "");
      else cmp = byDate(a) - byDate(b);
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [problems, query, sortKey, sortAsc]);

  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const pageItems = visible.slice(
    page * PAGE_SIZE,
    page * PAGE_SIZE + PAGE_SIZE,
  );

  const handleCreate = async () => {
    if (!form.title.trim() || !form.statement.trim()) return;
    await createProblem(form);
    setShowCreate(false);
    setForm({
      title: "",
      statement: "",
      lean_source: "",
      source: "user",
      difficulty: "medium",
      tags: "",
      notes: "",
    });
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this problem?")) return;
    await deleteProblem(id);
    load();
  };

  const handleSubmitJob = async (p: Problem) => {
    const source =
      p.lean_source ||
      `import Mathlib\n\ntheorem ${p.title.replace(/\s+/g, "_")} : ${p.statement} := by\n  sorry\n`;
    const res = await fetch(`${API_BASE}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ statement: p.statement, lean_stub: source }),
    });
    const data = await res.json();
    window.open(`/jobs/${data.job_id}`, "_blank");
  };

  return (
    <div data-testid="problems-page">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Problem Library</h1>
        <div className="flex gap-2">
          {["", "miniF2F", "erdos", "putnam", "user"].map((s) => (
            <button
              type="button"
              key={s}
              onClick={() => setSourceFilter(s)}
              className={`px-3 py-1 rounded border text-sm ${
                sourceFilter === s
                  ? "border-indigo-500 bg-indigo-950/40 text-indigo-300"
                  : "border-border text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {s || "all"}
            </button>
          ))}
          <button
            type="button"
            data-testid="problems-new"
            onClick={() => setShowCreate(true)}
            className="px-3 py-1 rounded border border-indigo-600 text-indigo-300 text-sm hover:bg-indigo-950/30"
          >
            + New
          </button>
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        <input
          data-testid="search-problems"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search title, statement, tags..."
          className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
        />
        <select
          data-testid="problems-sort"
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value)}
          className="bg-zinc-800 text-zinc-100 border border-zinc-600 rounded px-2 py-1 text-sm"
        >
          <option value="updated">Updated</option>
          <option value="created">Created</option>
          <option value="title">Title</option>
          <option value="difficulty">Difficulty</option>
        </select>
        <button
          type="button"
          data-testid="problems-sort-dir"
          onClick={() => setSortAsc((s) => !s)}
          className="px-3 py-2 border border-zinc-700 rounded text-sm text-zinc-300 hover:border-indigo-500"
        >
          {sortAsc ? "Asc" : "Desc"}
        </button>
      </div>

      {showCreate && (
        <div className="border border-border rounded p-4 mb-6 bg-surface-2">
          <h2 className="text-sm font-medium mb-3">New Problem</h2>
          <div className="space-y-3">
            <input
              placeholder="Title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-sm"
            />
            <textarea
              placeholder="Theorem statement (after colon)"
              value={form.statement}
              onChange={(e) => setForm({ ...form, statement: e.target.value })}
              rows={2}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-sm"
            />
            <textarea
              placeholder="Optional Lean stub (with sorry)"
              value={form.lean_source}
              onChange={(e) =>
                setForm({ ...form, lean_source: e.target.value })
              }
              rows={3}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-sm font-mono"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCreate}
                className="px-4 py-1.5 bg-indigo-600 rounded text-sm hover:bg-indigo-500"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="px-4 py-1.5 border border-border rounded text-sm text-gray-400"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-zinc-400">Loading...</p>
      ) : visible.length === 0 ? (
        <p className="text-sm text-zinc-400 text-center py-16">
          No problems yet. Create one to get started.
        </p>
      ) : (
        <div className="space-y-2" data-testid="problems-count">
          {pageItems.map((p) => (
            <div
              key={p.id}
              className="border border-border rounded p-4 bg-surface-2"
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <span className="font-medium text-sm">{p.title}</span>
                  <span className="ml-2 text-sm text-zinc-400">{p.source}</span>
                  <span className="ml-2 text-sm text-zinc-400">
                    {p.difficulty}
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleSubmitJob(p)}
                    className="text-sm px-2 py-1 rounded border border-indigo-600 text-indigo-300 hover:bg-indigo-950/30"
                  >
                    Prove
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(p.id)}
                    className="text-sm px-2 py-1 rounded border border-red-700 text-red-300 hover:bg-red-950/30"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <pre className="text-xs text-zinc-400 font-mono whitespace-pre-wrap line-clamp-3">
                {p.statement}
              </pre>
              {p.tags && (
                <div className="flex gap-1 mt-2">
                  {p.tags.split(",").map((t) => (
                    <span
                      key={t}
                      className="text-xs px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300"
                    >
                      {t.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {!loading && pageCount > 1 && (
        <div
          className="flex items-center gap-2 mt-4 text-sm text-zinc-400"
          data-testid="problems-pagination"
        >
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1 border border-zinc-700 rounded disabled:opacity-30"
          >
            Prev
          </button>
          <span>
            Page {page + 1} of {pageCount} ({visible.length} problems)
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
      {!loading && pageCount <= 1 && visible.length > 0 && (
        <p className="text-sm text-zinc-500 mt-3">{visible.length} problems.</p>
      )}
    </div>
  );
}

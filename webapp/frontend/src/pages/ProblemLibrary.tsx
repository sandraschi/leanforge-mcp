import { useEffect, useState } from "react";
import type { Problem } from "../api";
import { API_BASE, fetchProblems, createProblem, deleteProblem } from "../api";

export default function ProblemLibrary() {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState("");
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

  const handleCreate = async () => {
    if (!form.title.trim() || !form.statement.trim()) return;
    await createProblem(form);
    setShowCreate(false);
    setForm({
      title: "", statement: "", lean_source: "", source: "user",
      difficulty: "medium", tags: "", notes: "",
    });
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this problem?")) return;
    await deleteProblem(id);
    load();
  };

  const handleSubmitJob = async (p: Problem) => {
    const source = p.lean_source || `import Mathlib\n\ntheorem ${p.title.replace(/\s+/g, "_")} : ${p.statement} := by\n  sorry\n`;
    const res = await fetch(API_BASE + "/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ statement: p.statement, lean_stub: source }),
    });
    const data = await res.json();
    window.open(`/jobs/${data.job_id}`, "_blank");
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Problem Library</h1>
        <div className="flex gap-2">
          {["", "miniF2F", "erdos", "putnam", "user"].map((s) => (
            <button
              key={s}
              onClick={() => setSourceFilter(s)}
              className={`px-3 py-1 rounded border text-xs ${
                sourceFilter === s
                  ? "border-indigo-500 bg-indigo-950/40 text-indigo-300"
                  : "border-border text-gray-400 hover:text-gray-200"
              }`}
            >
              {s || "all"}
            </button>
          ))}
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1 rounded border border-indigo-600 text-indigo-300 text-xs hover:bg-indigo-950/30"
          >
            + New
          </button>
        </div>
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
              onChange={(e) => setForm({ ...form, lean_source: e.target.value })}
              rows={3}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-sm font-mono"
            />
            <div className="flex gap-2">
              <button onClick={handleCreate} className="px-4 py-1.5 bg-indigo-600 rounded text-sm hover:bg-indigo-500">
                Save
              </button>
              <button onClick={() => setShowCreate(false)} className="px-4 py-1.5 border border-border rounded text-sm text-gray-400">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : problems.length === 0 ? (
        <p className="text-gray-500 text-center py-16">
          No problems yet. Create one to get started.
        </p>
      ) : (
        <div className="space-y-2">
          {problems.map((p) => (
            <div key={p.id} className="border border-border rounded p-4 bg-surface-2">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <span className="font-medium text-sm">{p.title}</span>
                  <span className="ml-2 text-xs text-gray-500">{p.source}</span>
                  <span className="ml-2 text-xs text-gray-500">{p.difficulty}</span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleSubmitJob(p)}
                    className="text-xs px-2 py-1 rounded border border-indigo-600 text-indigo-300 hover:bg-indigo-950/30"
                  >
                    Prove
                  </button>
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="text-xs px-2 py-1 rounded border border-red-700 text-red-300 hover:bg-red-950/30"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap line-clamp-3">
                {p.statement}
              </pre>
              {p.tags && (
                <div className="flex gap-1 mt-2">
                  {p.tags.split(",").map((t) => (
                    <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                      {t.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

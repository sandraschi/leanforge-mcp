import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { submitLeanFile, submitTheorem } from "../api";

export default function NewTheorem() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"simple" | "file">("simple");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const [simple, setSimple] = useState({
    statement: "",
    hints: "",
    tier: 1,
    parallel_agents: 4,
    max_turns: 100,
  });

  const [file, setFile] = useState({
    lean_source: "",
    description: "",
    tier: 1,
    parallel_agents: 4,
    max_turns: 100,
  });

  const handleSubmit = async () => {
    setSending(true);
    setError("");
    try {
      if (mode === "simple") {
        const result = await submitTheorem({
          statement: simple.statement,
          hints: simple.hints || undefined,
          tier: simple.tier,
          parallel_agents: simple.parallel_agents,
          max_turns: simple.max_turns,
        });
        navigate(`/jobs/${result.job_id}`);
      } else {
        const result = await submitLeanFile({
          lean_source: file.lean_source,
          description: file.description,
          tier: file.tier,
          parallel_agents: file.parallel_agents,
          max_turns: file.max_turns,
        });
        navigate(`/jobs/${result.job_id}`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <div data-testid="submit-page">
      <h1 className="text-2xl font-semibold mb-6">Submit Theorem</h1>

      <div className="flex gap-2 mb-4">
        <button
          type="button"
          onClick={() => setMode("simple")}
          className={`px-3 py-1 rounded text-sm border ${
            mode === "simple"
              ? "border-indigo-500 bg-indigo-950/40 text-indigo-300"
              : "border-border text-zinc-400"
          }`}
        >
          Simple
        </button>
        <button
          type="button"
          onClick={() => setMode("file")}
          className={`px-3 py-1 rounded text-sm border ${
            mode === "file"
              ? "border-indigo-500 bg-indigo-950/40 text-indigo-300"
              : "border-border text-zinc-400"
          }`}
        >
          Lean File
        </button>
      </div>

      {mode === "simple" ? (
        <div className="space-y-4">
          <div>
            <label
              htmlFor="nt-statement"
              className="text-sm text-zinc-400 block mb-1"
            >
              Theorem Statement
            </label>
            <textarea
              id="nt-statement"
              data-testid="submit-statement"
              value={simple.statement}
              onChange={(e) =>
                setSimple({ ...simple, statement: e.target.value })
              }
              placeholder="for all n : Nat, 2 * sum i in range (n+1), i = n * (n+1)"
              rows={3}
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <label
              htmlFor="nt-hints-simple"
              className="text-sm text-zinc-400 block mb-1"
            >
              Hints (optional)
            </label>
            <input
              id="nt-hints-simple"
              value={simple.hints}
              onChange={(e) => setSimple({ ...simple, hints: e.target.value })}
              placeholder="Mathlib lemma names or strategy hints"
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm"
            />
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label
              htmlFor="nt-source"
              className="text-sm text-zinc-400 block mb-1"
            >
              Lean 4 Source
            </label>
            <textarea
              id="nt-source"
              data-testid="submit-source"
              value={file.lean_source}
              onChange={(e) =>
                setFile({ ...file, lean_source: e.target.value })
              }
              placeholder="import Mathlib\ntheorem example : 1 + 1 = 2 := by\n  sorry"
              rows={8}
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <label
              htmlFor="nt-description"
              className="text-sm text-zinc-400 block mb-1"
            >
              Description
            </label>
            <input
              id="nt-description"
              value={file.description}
              onChange={(e) =>
                setFile({ ...file, description: e.target.value })
              }
              placeholder="Optional description"
              className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-sm"
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mt-4">
        <div>
          <label htmlFor="nt-tier" className="text-sm text-zinc-400 block mb-1">
            Starting Tier
          </label>
          <select
            id="nt-tier"
            value={mode === "simple" ? simple.tier : file.tier}
            onChange={(e) => {
              const v = Number(e.target.value);
              mode === "simple"
                ? setSimple({ ...simple, tier: v })
                : setFile({ ...file, tier: v });
            }}
            className="w-full bg-surface-2 border border-border rounded px-2 py-1.5 text-sm"
          >
            <option value={1}>1 — Local (free)</option>
            <option value={2}>2 — DeepSeek API</option>
            <option value={3}>3 — Claude Fable 5</option>
          </select>
        </div>
        <div>
          <label
            htmlFor="nt-agents"
            className="text-sm text-zinc-400 block mb-1"
          >
            Parallel Agents
          </label>
          <input
            id="nt-agents"
            type="number"
            min={1}
            max={16}
            value={
              mode === "simple" ? simple.parallel_agents : file.parallel_agents
            }
            onChange={(e) => {
              const v = Number(e.target.value);
              mode === "simple"
                ? setSimple({ ...simple, parallel_agents: v })
                : setFile({ ...file, parallel_agents: v });
            }}
            className="w-full bg-surface-2 border border-border rounded px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label
            htmlFor="nt-turns"
            className="text-sm text-zinc-400 block mb-1"
          >
            Max Turns
          </label>
          <input
            id="nt-turns"
            type="number"
            min={1}
            max={1000}
            value={mode === "simple" ? simple.max_turns : file.max_turns}
            onChange={(e) => {
              const v = Number(e.target.value);
              mode === "simple"
                ? setSimple({ ...simple, max_turns: v })
                : setFile({ ...file, max_turns: v });
            }}
            className="w-full bg-surface-2 border border-border rounded px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      {error && (
        <p data-testid="submit-error" className="text-red-400 text-sm mt-2">
          {error}
        </p>
      )}

      <button
        type="button"
        data-testid="submit-start"
        onClick={handleSubmit}
        disabled={sending}
        className="mt-6 px-6 py-2 bg-indigo-600 rounded text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
      >
        {sending ? "Submitting..." : "Submit for Proof Search"}
      </button>
    </div>
  );
}
